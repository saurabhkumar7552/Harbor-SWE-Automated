#!/usr/bin/env python3
"""
Harbor eval pipeline: point it at a folder of tasks, run an agent up to K times
per task, and get ONE combined report (Markdown + JSON + CSV).

Modes
  independent  (default) every task gets K independent attempts in one Harbor job
               (-k K). Gives pass@1, pass@K and a difficulty bucket per task.
  until-pass   attempt 1 runs on all tasks; attempts 2..K run only on tasks that
               have not passed yet. Cheaper, but only tells you "solved within K".

Usage
  python run_eval.py TASKS_DIR -a claude-code -m anthropic/claude-opus-4-1
  python run_eval.py TASKS_DIR -a codex -m openai/gpt-5 --mode until-pass -k 3
  python run_eval.py --report-only --jobs-dir jobs --run-name myrun   # rebuild report
  Anything after "--" is passed straight to `harbor run`.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TASK_MARKER = "task.toml"  # every Harbor task directory has one


# --------------------------------------------------------------------------- tasks
def find_tasks(root: Path) -> list[Path]:
    """Return task dirs under root (root itself if it is a single task)."""
    if (root / TASK_MARKER).is_file():
        return [root]
    tasks = sorted(p.parent for p in root.rglob(TASK_MARKER))
    if not tasks:
        sys.exit(f"No tasks found under {root} (looked for {TASK_MARKER}).")
    return tasks


def make_subset_dataset(tasks: list[Path], dest: Path) -> Path:
    """Copy a subset of tasks into a fresh dataset dir (works on Windows, no symlinks)."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for t in tasks:
        shutil.copytree(t, dest / t.name)
    return dest


# --------------------------------------------------------------------------- harbor
def run_harbor(path: Path, job_name: str, args, n_attempts: int) -> int:
    cmd = [
        args.harbor_bin, "run",
        "-p", str(path),
        "-a", args.agent,
        "-k", str(n_attempts),
        "-n", str(args.concurrency),
        "-r", str(args.max_retries),          # retries on infra EXCEPTIONS only
        "-o", str(args.jobs_dir),
        "--job-name", job_name,
    ]
    if args.model:
        cmd += ["-m", args.model]
    if args.reasoning_effort:
        cmd += ["--ak", f"reasoning_effort={args.reasoning_effort}"]
    cmd += args.harbor_args
    print("\n>>> " + " ".join(cmd), flush=True)
    if args.dry_run:
        return 0
    return subprocess.call(cmd, env=harbor_env(args))


def harbor_env(args) -> dict:
    """Environment for `harbor run`. With --codex-subscription, Harbor's codex agent
    uploads your ChatGPT-login auth.json into each container instead of using an API key."""
    env = dict(os.environ)
    if args.codex_subscription:
        if args.codex_auth_json:
            env["CODEX_AUTH_JSON_PATH"] = str(Path(args.codex_auth_json).expanduser().resolve())
        else:
            env["CODEX_FORCE_AUTH_JSON"] = "1"  # -> ~/.codex/auth.json
        env.pop("OPENAI_API_KEY", None)
        env.pop("CODEX_API_KEY", None)
    return env


def preflight(args) -> None:
    if not args.codex_subscription:
        return
    if args.agent != "codex":
        sys.exit("--codex-subscription only works with -a codex")
    auth = Path(args.codex_auth_json or "~/.codex/auth.json").expanduser()
    if not auth.is_file():
        sys.exit(f"{auth} not found. Run `codex login` (ChatGPT account) on this machine first, "
                 "or pass --codex-auth-json PATH.")
    try:
        mode = json.loads(auth.read_text(encoding="utf-8")).get("auth_mode")
        if mode and "chatgpt" not in str(mode).lower():
            print(f"warn: {auth} has auth_mode={mode!r}, not a ChatGPT login", file=sys.stderr)
    except (OSError, json.JSONDecodeError):
        print(f"warn: could not parse {auth}", file=sys.stderr)
    if args.concurrency > 2:
        print(f"warn: -n {args.concurrency} with one ChatGPT login shares one rate limit and one token; "
              "consider -n 1 or 2", file=sys.stderr)


# --------------------------------------------------------------------------- results
def _get(d, *keys, default=None):
    for k in keys:
        if not isinstance(d, dict) or k not in d or d[k] is None:
            return default
        d = d[k]
    return d


def _duration(r: dict) -> float | None:
    try:
        a = dt.datetime.fromisoformat(str(r["started_at"]).replace("Z", "+00:00"))
        b = dt.datetime.fromisoformat(str(r["finished_at"]).replace("Z", "+00:00"))
        return round((b - a).total_seconds(), 1)
    except Exception:
        return None


def _tail(path: Path, n: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return ""


def load_trials(job_dir: Path, attempt_offset: int, threshold: float, tail_lines: int) -> list[dict]:
    """Read every <job_dir>/<trial>/result.json written by Harbor."""
    trials = []
    for rf in sorted(job_dir.glob("*/result.json")):
        try:
            r = json.loads(rf.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"warn: could not read {rf}: {e}", file=sys.stderr)
            continue
        rewards = _get(r, "verifier_result", "rewards", default={}) or {}
        reward = rewards.get("reward")
        exc = r.get("exception_info") or None
        if reward is not None and float(reward) >= threshold:
            status = "pass"
        elif reward is None and exc:
            status = "error"            # crashed before the verifier produced a score
        else:
            status = "fail"
        trials.append({
            "task": r.get("task_name") or rf.parent.name.split("__")[0],
            "trial": r.get("trial_name") or rf.parent.name,
            "job": job_dir.name,
            "attempt_offset": attempt_offset,
            "status": status,
            "reward": reward,
            "rewards": rewards,
            "exception_type": _get(exc or {}, "exception_type"),
            "exception_message": (_get(exc or {}, "exception_message") or "")[:500],
            "duration_sec": _duration(r),
            "input_tokens": _get(r, "agent_result", "n_input_tokens"),
            "output_tokens": _get(r, "agent_result", "n_output_tokens"),
            "started_at": r.get("started_at"),
            "verifier_tail": _tail(rf.parent / "verifier" / "stdout.txt", tail_lines) if status != "pass" else "",
            "trial_dir": str(rf.parent),
        })
    return trials


def number_attempts(trials: list[dict]) -> None:
    """Give each trial an attempt number per task (by job order, then start time)."""
    by_task: dict[str, list[dict]] = {}
    for t in trials:
        by_task.setdefault(t["task"], []).append(t)
    for ts in by_task.values():
        ts.sort(key=lambda t: (t["attempt_offset"], t["started_at"] or "", t["trial"]))
        for i, t in enumerate(ts, 1):
            t["attempt"] = i


# --------------------------------------------------------------------------- report
def bucket(passes: int, attempts: int, mode: str) -> str:
    if passes == 0:
        return "unsolved"
    if mode == "until-pass":
        return "solved"
    if passes == attempts:
        return "easy"
    return "medium"


def build_report(trials: list[dict], all_tasks: list[str], meta: dict, out_dir: Path) -> dict:
    number_attempts(trials)
    mode = meta["mode"]
    per_task = []
    for name in all_tasks:
        ts = sorted((t for t in trials if t["task"] == name), key=lambda t: t["attempt"])
        passes = sum(t["status"] == "pass" for t in ts)
        errors = sum(t["status"] == "error" for t in ts)
        first_pass = next((t["attempt"] for t in ts if t["status"] == "pass"), None)
        scored = [float(t["reward"]) for t in ts if t["reward"] is not None]
        per_task.append({
            "task": name,
            "attempts": len(ts),
            "passes": passes,
            "errors": errors,
            "pass_at_1": round(passes / len(ts), 3) if ts else None,
            "solved": passes > 0,
            "first_pass_attempt": first_pass,
            "mean_reward": round(sum(scored) / len(scored), 3) if scored else None,
            "bucket": bucket(passes, len(ts), mode) if ts else "not-run",
            "outcomes": "".join({"pass": "P", "fail": "F", "error": "E"}[t["status"]] for t in ts),
            "trials": ts,
        })

    ran = [t for t in per_task if t["attempts"]]
    solved = sum(t["solved"] for t in ran)
    summary = {
        "tasks_total": len(all_tasks),
        "tasks_run": len(ran),
        "trials_total": len(trials),
        "solved_within_k": solved,
        "solve_rate_within_k": round(solved / len(ran), 3) if ran else None,
        "mean_pass_at_1": round(sum(t["pass_at_1"] for t in ran) / len(ran), 3) if ran and mode == "independent" else None,
        "first_try_rate": round(sum(t["first_pass_attempt"] == 1 for t in ran) / len(ran), 3) if ran else None,
        "error_trials": sum(t["status"] == "error" for t in trials),
        "buckets": {b: sum(t["bucket"] == b for t in per_task) for b in sorted({t["bucket"] for t in per_task})},
    }
    report = {"meta": meta, "summary": summary, "tasks": per_task}

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    write_csv(per_task, out_dir / "report.csv")
    (out_dir / "report.md").write_text(render_md(report), encoding="utf-8")
    return report


def write_csv(per_task: list[dict], path: Path) -> None:
    cols = ["task", "bucket", "outcomes", "attempts", "passes", "errors", "pass_at_1",
            "first_pass_attempt", "mean_reward"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(per_task)


def render_md(rep: dict) -> str:
    m, s = rep["meta"], rep["summary"]
    pct = lambda x: "n/a" if x is None else f"{x * 100:.1f}%"
    L = [
        f"# Harbor eval report: {m['run_name']}",
        "",
        f"- **Agent / model:** {m['agent']} / {m.get('model') or 'default'}"
        + (f" (reasoning: {m['reasoning_effort']})" if m.get("reasoning_effort") else ""),
        f"- **Auth:** {m.get('auth', 'n/a')}",
        f"- **Tasks authored by:** {m.get('task_author') or 'n/a'}",
        f"- **Mode:** {m['mode']}, up to {m['k']} attempts per task (pass threshold reward >= {m['threshold']})",
        f"- **Tasks dir:** `{m['tasks_dir']}`",
        f"- **Generated:** {m['generated_at']}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Tasks run | {s['tasks_run']} / {s['tasks_total']} |",
        f"| Trials | {s['trials_total']} |",
        f"| Solved within {m['k']} | {s['solved_within_k']} ({pct(s['solve_rate_within_k'])}) |",
        f"| Solved on first try | {pct(s['first_try_rate'])} |",
        f"| Mean pass@1 | {pct(s['mean_pass_at_1'])} |",
        f"| Error trials (infra/crash) | {s['error_trials']} |",
        "",
        "**Buckets:** " + ", ".join(f"{k}: {v}" for k, v in s["buckets"].items()),
        "",
        "## Per task",
        "",
        "Outcomes: P = pass, F = fail, E = error (no verifier score).",
        "",
        "| Task | Bucket | Outcomes | Passes | pass@1 | First pass | Mean reward |",
        "|---|---|---|---|---|---|---|",
    ]
    order = {"unsolved": 0, "medium": 1, "solved": 2, "easy": 3, "not-run": 4}
    for t in sorted(rep["tasks"], key=lambda t: (order.get(t["bucket"], 9), t["task"])):
        L.append(f"| {t['task']} | {t['bucket']} | `{t['outcomes'] or '-'}` | {t['passes']}/{t['attempts']} "
                 f"| {pct(t['pass_at_1'])} | {t['first_pass_attempt'] or '-'} | {t['mean_reward'] if t['mean_reward'] is not None else '-'} |")

    failed = [t for t in rep["tasks"] if any(x["status"] != "pass" for x in t["trials"])]
    if failed:
        L += ["", "## Failure details", ""]
        for t in failed:
            L.append(f"### {t['task']}")
            for x in t["trials"]:
                if x["status"] == "pass":
                    continue
                L.append(f"- **Attempt {x['attempt']}: {x['status']}** (reward {x['reward']}, "
                         f"{x['duration_sec']}s), `{x['trial_dir']}`")
                if x["exception_type"]:
                    L.append(f"  - Exception: `{x['exception_type']}`: {x['exception_message']}")
                if x["verifier_tail"]:
                    L += ["", "  ```", *("  " + ln for ln in x["verifier_tail"].splitlines()), "  ```"]
            L.append("")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tasks_dir", nargs="?", type=Path, help="folder of Harbor tasks (or one task)")
    ap.add_argument("-a", "--agent", default="oracle", help="Harbor agent name (default: oracle)")
    ap.add_argument("-m", "--model", help="model name, e.g. anthropic/claude-opus-4-1")
    ap.add_argument("-k", "--attempts", type=int, default=3, help="max attempts per task (default 3)")
    ap.add_argument("--mode", choices=["independent", "until-pass"], default="independent")
    ap.add_argument("-n", "--concurrency", type=int, default=4)
    ap.add_argument("-r", "--max-retries", type=int, default=1, help="Harbor retries on infra exceptions")
    ap.add_argument("-o", "--jobs-dir", type=Path, default=Path("jobs"))
    ap.add_argument("--run-name", default=None, help="prefix for job names (default: timestamp)")
    ap.add_argument("--threshold", type=float, default=1.0, help="reward needed to count as pass")
    ap.add_argument("--tail-lines", type=int, default=25, help="verifier stdout lines kept per failure")
    ap.add_argument("--reasoning-effort", choices=["low", "medium", "high", "xhigh", "max"],
                    help="codex agent reasoning effort (passed as --ak reasoning_effort=...)")
    ap.add_argument("--codex-subscription", action="store_true",
                    help="use your ChatGPT/Codex login (~/.codex/auth.json) instead of an API key")
    ap.add_argument("--codex-auth-json", help="explicit path to a Codex auth.json (implies subscription auth)")
    ap.add_argument("--task-author", default=None, help="who/what wrote the tasks, e.g. claude-opus-5-5 (for the report)")
    ap.add_argument("--harbor-bin", default="harbor")
    ap.add_argument("--report-only", action="store_true", help="skip running, rebuild report from jobs dir")
    ap.add_argument("--dry-run", action="store_true", help="print harbor commands only")
    argv = sys.argv[1:]
    extra: list[str] = []
    if "--" in argv:  # everything after "--" goes straight to `harbor run`
        i = argv.index("--")
        argv, extra = argv[:i], argv[i + 1:]
    args = ap.parse_args(argv)
    args.harbor_args = extra
    if args.codex_auth_json:
        args.codex_subscription = True
    if not args.report_only:
        preflight(args)

    run_name = args.run_name or dt.datetime.now().strftime("eval-%Y%m%d-%H%M%S")
    args.jobs_dir = args.jobs_dir.resolve()
    job_dirs: list[tuple[Path, int]] = []  # (job dir, attempt offset)

    if args.report_only:
        found = sorted(p for p in args.jobs_dir.glob(f"{run_name}*") if p.is_dir() and not p.name.endswith("-report"))
        if not found:
            sys.exit(f"No job dirs matching {run_name}* in {args.jobs_dir}")
        job_dirs = [(p, i) for i, p in enumerate(found)]
        all_tasks = None
    else:
        if not args.tasks_dir:
            ap.error("tasks_dir is required unless --report-only")
        tasks = find_tasks(args.tasks_dir.resolve())
        all_tasks = [t.name for t in tasks]
        print(f"Found {len(tasks)} task(s): {', '.join(all_tasks)}")

        if args.mode == "independent":
            job = f"{run_name}"
            path = tasks[0] if len(tasks) == 1 else args.tasks_dir.resolve()
            run_harbor(path, job, args, args.attempts)
            job_dirs.append((args.jobs_dir / job, 0))
        else:
            remaining = tasks
            staging = args.jobs_dir / f"{run_name}-staging"
            for i in range(1, args.attempts + 1):
                if not remaining:
                    break
                job = f"{run_name}-try{i}"
                path = remaining[0] if len(remaining) == 1 else make_subset_dataset(remaining, staging / f"try{i}")
                run_harbor(path, job, args, 1)
                job_dirs.append((args.jobs_dir / job, i - 1))
                if args.dry_run:
                    continue
                passed = {t["task"] for t in load_trials(args.jobs_dir / job, i - 1, args.threshold, 0)
                          if t["status"] == "pass"}
                remaining = [t for t in remaining if t.name not in passed]
                print(f"After attempt {i}: {len(tasks) - len(remaining)}/{len(tasks)} solved, "
                      f"{len(remaining)} going to next attempt")
            shutil.rmtree(staging, ignore_errors=True)

    if args.dry_run:
        return

    trials = []
    for jd, off in job_dirs:
        if not jd.exists():
            print(f"warn: job dir {jd} missing (harbor failed?)", file=sys.stderr)
            continue
        trials += load_trials(jd, off, args.threshold, args.tail_lines)
    if all_tasks is None:
        all_tasks = sorted({t["task"] for t in trials})

    meta = {
        "run_name": run_name, "agent": args.agent, "model": args.model, "mode": args.mode,
        "reasoning_effort": args.reasoning_effort, "task_author": args.task_author,
        "auth": "codex-subscription" if args.codex_subscription else "api-key/env",
        "k": args.attempts, "threshold": args.threshold,
        "tasks_dir": str(args.tasks_dir) if args.tasks_dir else None,
        "jobs": [str(j) for j, _ in job_dirs],
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    out = args.jobs_dir / f"{run_name}-report"
    rep = build_report(trials, all_tasks, meta, out)
    s = rep["summary"]
    print(f"\nSolved {s['solved_within_k']}/{s['tasks_run']} within {args.attempts} attempts. "
          f"Report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
