#!/usr/bin/env python3
"""
Hard-task factory: M1 (author) + R1 (reviewer) + deterministic gate + Harbor/Sol eval + learning.

Flow per task (one revision each; easy tasks are rejected only after Sol testing):
  research(M1+web, cached per repo) -> scout(M1, slate) -> review_proposal(R1) -> revise_proposal(M1)
  -> build(M1) -> gate:build -> review_package(R1) -> fix_package(M1) -> instruction_check(M1) -> gate:final
  -> [eval: Harbor + GPT-6.1 Sol] -> [learn(M1): intel.md + painpoints.md + stats] -> [verdict: reject easy / report]

Run inside WSL (python3, docker, harbor). Claude Code is called through Windows interop.
  python3 factory.py run --count 10                 # full flow (eval only if config eval.enabled or --eval)
  python3 factory.py run --count 2 --until proposal # stop after the hardened proposals
  python3 factory.py run --resume                   # continue every unfinished task from its last stage
  python3 factory.py status
  python3 factory.py gate <task_id> [--oracle-runs 3]
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tomllib
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

FACTORY = Path(__file__).resolve().parent
CFG = json.loads((FACTORY / "config.json").read_text(encoding="utf-8"))
PIPE = Path(CFG["pipeline_dir"]["wsl"])
WORK = FACTORY / "work"
STATE_DIR = WORK / "state"
LOG_DIR = WORK / "logs"
WT_DIR = WORK / "wt"
REPO = WORK / "repos" / "_unset"


def select_repo(name: str) -> None:
    """Activate a repo profile from config.json `repos`."""
    global REPO
    if name not in CFG["repos"]:
        sys.exit(f"unknown repo profile {name!r}; known: {sorted(CFG['repos'])}")
    CFG["repo"] = CFG["repos"][name]
    REPO = WORK / "repos" / name


select_repo(CFG["default_repo"])
TASKS = PIPE / "tasks"
STATS = WORK / "painpoint_stats.json"
INTEL = PIPE / "intel.md"
PAINPOINTS = FACTORY / "painpoints.md"
LOCK = threading.Lock()

PROPOSAL_STAGES = ["review_proposal", "revise_proposal"]
PACKAGE_STAGES = ["build", "gate_build", "review_package", "fix_package", "instruction_check", "review_instruction",
                  "gate_final"]
EVAL_STAGES = ["eval", "learn", "verdict"]
# statuses that end a task's flow; --resume skips them
TERMINAL = {"blocked", "rejected_easy", "reported_expert", "reported_hard", "needs_review"}
RESEARCH_DIR = WORK / "research"
REJECTED = PIPE / "rejected_tasks"
REPORTS = PIPE / "harbour-test"
DRY_RUN = False


class StageError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- helpers
def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def log(msg: str) -> None:
    with LOCK:
        print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", file=sys.stderr, flush=True)


def win(p: Path | str) -> str:
    """WSL path -> path claude.exe (Windows) understands: /mnt/f/x -> F:/x."""
    s = str(p)
    m = re.match(r"^/mnt/([a-z])/(.*)$", s)
    return f"{m.group(1).upper()}:/{m.group(2)}" if m else s


def sh(cmd: list[str] | str, cwd: Path | None = None, check: bool = True, timeout: int | None = None,
       capture: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str), text=True, timeout=timeout, env=env,
                       stdout=subprocess.PIPE if capture else None, stderr=subprocess.STDOUT if capture else None,
                       stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise StageError(f"command failed ({r.returncode}): {cmd}\n{(r.stdout or '')[-3000:]}")
    return r


def schema(name: str) -> dict:
    return json.loads((FACTORY / "schemas" / f"{name}.json").read_text(encoding="utf-8"))


def proposal_schema(with_notes: bool) -> dict:
    """The single-proposal schema is derived from slate.json so there is one source of truth."""
    p = copy.deepcopy(schema("slate")["$defs"]["proposal"])
    if with_notes:
        p["properties"]["revision_notes"] = {"type": "array", "items": {"type": "string"}}
        p["required"] = p["required"] + ["revision_notes"]
    return p


def render(template: str, **kw) -> str:
    text = (FACTORY / "prompts" / f"{template}.md").read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", v if isinstance(v, str) else json.dumps(v, indent=2))
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        raise StageError(f"prompt {template} has unfilled placeholders: {sorted(set(left))}")
    return text


# ----------------------------------------------------------------------------- state
def load_state(tid: str) -> dict:
    f = STATE_DIR / f"{tid}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_state(st: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK:
        tmp = STATE_DIR / f"{st['task_id']}.json.tmp"
        tmp.write_text(json.dumps(st, indent=2), encoding="utf-8")
        tmp.replace(STATE_DIR / f"{st['task_id']}.json")


def mark(st: dict, stage: str, ok: bool, note: str = "") -> None:
    st.setdefault("history", []).append({"stage": stage, "at": now(), "ok": ok, "note": note[:500]})
    if ok:
        st.setdefault("done", {})[stage] = True
    save_state(st)


def all_states() -> list[dict]:
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(STATE_DIR.glob("*.json"))] if STATE_DIR.exists() else []


# ----------------------------------------------------------------------------- claude
READONLY_TOOLS = ["Read", "Glob", "Grep", "Bash(git log:*)", "Bash(git show:*)", "Bash(git grep:*)",
                  "Bash(git fetch:*)", "Bash(git diff:*)", "Bash(git blame:*)", "Bash(rg:*)", "Bash(ls:*)",
                  "Bash(find:*)", "Bash(wc:*)", "Bash(head:*)", "Bash(sed -n:*)"]


def kill_windows_claude(sid: str) -> str:
    """Killing the WSL interop process on timeout may leave the Windows claude.exe (and the shells/docker clients
    it started) running, still editing the task. Find it by its --session-id and kill the whole process tree."""
    ps = ("$p = Get-CimInstance Win32_Process -Filter \"Name='claude.exe'\" | "
          f"Where-Object {{ $_.CommandLine -like '*{sid}*' }}; "
          "if ($p) { $p | ForEach-Object { taskkill.exe /T /F /PID $_.ProcessId | Out-Null; $_.ProcessId } } "
          "else { 'none-found' }")
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps], text=True,
                           capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
        return (r.stdout or r.stderr or "").strip().replace("\r", "").replace("\n", ",")[:200] or "no output"
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"kill failed: {e!r}"


def claude(role: str, stage: str, task: str, prompt: str, out_schema: dict, cwd: Path, write: bool,
           web: bool = False) -> dict:
    m = CFG["models"][role]
    sid = str(uuid.uuid4())  # tags this claude.exe on the Windows side, so a timeout can kill exactly this run
    args = [CFG["claude_bin"], "-p", "--model", m["model"], "--effort", m["effort"],
            "--output-format", "json", "--no-session-persistence", "--strict-mcp-config", "--session-id", sid,
            "--json-schema", json.dumps(out_schema)]
    if web:
        # research stage only: read-only repo access plus web search/fetch, no edits
        args += ["--allowedTools", *READONLY_TOOLS, "WebSearch", "WebFetch",
                 "--disallowedTools", "Edit", "Write", "NotebookEdit"]
    elif write:
        # scoped, not unrestricted: edits are auto-accepted, shell is limited to the configured command list
        args += ["--permission-mode", "acceptEdits", "--allowedTools", *CFG["writer_allowed_tools"],
                 "--disallowedTools", "WebSearch", "WebFetch", "NotebookEdit"]
    else:
        args += ["--allowedTools", *READONLY_TOOLS,
                 "--disallowedTools", "Edit", "Write", "NotebookEdit", "WebSearch", "WebFetch"]
    logd = LOG_DIR / task
    logd.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%m%d-%H%M%S")
    (logd / f"{stage}.{stamp}.prompt.md").write_text(prompt, encoding="utf-8")
    if DRY_RUN:
        log(f"DRY {task}/{stage}: {role}={m['model']} cwd={win(cwd)} write={write} prompt={len(prompt)} chars")
        raise StageError("dry-run: stage not executed")
    log(f"{task}/{stage}: {role} ({m['model']}, effort {m['effort']}) started")
    try:
        # MSYS_NO_PATHCONV reaches claude.exe's Git Bash through WSLENV, so docker paths like /tests survive
        # CLAUDE_CODE_GIT_BASH_PATH: without it claude.exe launched from WSL finds no Git Bash and exposes only a
        # PowerShell tool, which the Bash(...) allow rules don't cover (every docker/bash/git-apply call was denied)
        env = {**os.environ, "MSYS_NO_PATHCONV": "1", "CLAUDE_CODE_GIT_BASH_PATH": CFG.get("git_bash_path", ""),
               "WSLENV": ":".join(x for x in (os.environ.get("WSLENV", ""), "MSYS_NO_PATHCONV/u",
                                              "CLAUDE_CODE_GIT_BASH_PATH") if x)}  # no /u: verified it then never arrives
        r = subprocess.run(args, input=prompt, cwd=cwd, text=True, capture_output=True, env=env,
                           timeout=CFG["timeouts_min"][stage] * 60, encoding="utf-8")
    except subprocess.TimeoutExpired:
        killed = kill_windows_claude(sid)
        raise StageError(f"{stage} timed out after {CFG['timeouts_min'][stage]} min; "
                         f"Windows claude.exe tree killed: {killed}")
    (logd / f"{stage}.{stamp}.out.json").write_text(r.stdout or "", encoding="utf-8")
    if r.stderr:
        (logd / f"{stage}.{stamp}.stderr.txt").write_text(r.stderr, encoding="utf-8")
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise StageError(f"{stage}: claude returned non-JSON (rc={r.returncode}): {(r.stdout or r.stderr)[-1500:]}")
    out = d.get("structured_output")
    if d.get("is_error") or not isinstance(out, dict):
        raise StageError(f"{stage}: {d.get('subtype')}: {str(d.get('result'))[-1500:]}")
    log(f"{task}/{stage}: done")
    return out


# ----------------------------------------------------------------------------- repo
def ensure_repo() -> None:
    rc = CFG["repo"]
    if not (REPO / ".git").exists():
        REPO.parent.mkdir(parents=True, exist_ok=True)
        log(f"cloning {rc['url']} (blob:none) ...")
        sh(["git", "clone", "-q", "--filter=blob:none", "--no-checkout", rc["url"], str(REPO)], timeout=1800)
        sh(["git", "-C", str(REPO), "config", "core.longpaths", "true"])
        sh(["git", "-C", str(REPO), "config", "core.autocrlf", "false"])
    head = sh(["git", "-C", str(REPO), "rev-parse", "HEAD"], check=False).stdout.strip()
    if head != rc["base_commit"] or sh(["git", "-C", str(REPO), "status", "--porcelain"], check=False).stdout.strip():
        sh(["git", "-C", str(REPO), "checkout", "-q", "-f", rc["base_commit"]], timeout=1800)
    r = sh(["git", "-C", str(REPO), "fetch", "-q", "origin", rc["upstream_branch"]], check=False, timeout=600)
    if r.returncode != 0:
        log("warn: could not fetch upstream branch (offline?); upstream leak check will use the cached ref")


def ensure_worktree(tid: str) -> Path:
    """Independent clone sharing objects with REPO via a RELATIVE alternates path, so both WSL git and
    Windows git (used by claude.exe) can open it."""
    wt = WT_DIR / tid
    if (wt / ".git").exists():
        return wt
    WT_DIR.mkdir(parents=True, exist_ok=True)
    sh(["git", "clone", "-q", "--shared", "--no-checkout", str(REPO), str(wt)], timeout=600)
    alt = wt / ".git" / "objects" / "info" / "alternates"
    alt.write_text(os.path.relpath(REPO / ".git" / "objects", wt / ".git" / "objects") + "\n", encoding="utf-8")
    for k, v in (("core.longpaths", "true"), ("core.autocrlf", "false")):
        sh(["git", "-C", str(wt), "config", k, v])
    sh(["git", "-C", str(wt), "checkout", "-q", CFG["repo"]["base_commit"]], timeout=1800)
    return wt


# ----------------------------------------------------------------------------- stats
def load_stats() -> dict:
    return json.loads(STATS.read_text(encoding="utf-8")) if STATS.exists() else {}


def update_stats(proposal: dict, summary: dict) -> None:
    with LOCK:
        stats = load_stats()
        for pp in proposal.get("pain_points", []):
            s = stats.setdefault(pp, {"tasks": [], "trials": 0, "passes": 0})
            if proposal["task_id"] not in s["tasks"]:
                s["tasks"].append(proposal["task_id"])
            s["trials"] += summary["trials"]
            s["passes"] += summary["passes"]
            s["pass_rate"] = round(s["passes"] / s["trials"], 3) if s["trials"] else None
        STATS.parent.mkdir(parents=True, exist_ok=True)
        STATS.write_text(json.dumps(stats, indent=2), encoding="utf-8")


def existing_tasks_text() -> str:
    lines = []
    for d in sorted(TASKS.glob("*/task.toml")):
        try:
            t = tomllib.loads(d.read_text(encoding="utf-8"))
            lines.append(f"- {d.parent.name}: {t.get('task', {}).get('description', '')}")
        except tomllib.TOMLDecodeError:
            lines.append(f"- {d.parent.name}")
    for st in all_states():
        p = st.get("proposal") or {}
        if st["task_id"] not in {Path(x).name for x in TASKS.glob('*')}:
            lines.append(f"- {st['task_id']} ({st.get('status', 'in progress')}): subsystem={p.get('subsystem')}; {p.get('title')}")
    return "\n".join(lines) or "- (none)"


# ----------------------------------------------------------------------------- stages
def research_file() -> Path:
    return RESEARCH_DIR / f"{CFG['repo']['name']}.md"


def common_paths() -> dict:
    rf = research_file()
    return {"REPO_DIR": win(REPO), "PAINPOINTS": win(PAINPOINTS), "INTEL": win(INTEL),
            "RESEARCH": f"`{win(rf)}`" if rf.exists() else "(no research brief for this repo yet; rely on the catalog)"}


def stage_research(force: bool = False) -> None:
    """Step 3 of the flow: fresh web research on SWE benchmarks and GPT-6.1 Sol / frontier-model pain points,
    applied to this repo. Cached per repo for research.max_age_days; failure never blocks the flow."""
    rf, max_age = research_file(), CFG.get("research", {}).get("max_age_days", 7)
    if rf.exists() and not force:
        age = (dt.datetime.now().timestamp() - rf.stat().st_mtime) / 86400
        if age < max_age:
            log(f"research: reusing {rf.name} ({age:.1f} days old, max {max_age})")
            return
    rc = CFG["repo"]
    prompt = render("research", REPO_URL=rc["url"], BASE_COMMIT=rc["base_commit"], REPO_NAME=rc["name"],
                    LANGUAGE=rc["language"], REPO_NOTES=rc["notes"], TODAY=dt.date.today().isoformat(),
                    PAINPOINT_STATS=json.dumps(load_stats() or {"note": "no Sol results yet"}, indent=2),
                    **{k: v for k, v in common_paths().items() if k != "RESEARCH"})
    out = claude("M1", "research", "_research", prompt, schema("research"), cwd=REPO, write=False, web=True)
    lines = [f"# Research brief: {rc['name']} ({dt.date.today().isoformat()})", "",
             f"Generated by the factory research stage (M1, web). Repo `{rc['url']}` @ `{rc['base_commit']}`.", "",
             "## Summary", "", out["summary"], "", "## Findings", ""]
    for f in out["findings"]:
        lines.append(f"- **[{f['evidence']}] {f['claim']}** Sources: {', '.join(f['sources']) or 'none'}. "
                     f"Applies to this repo: {f['repo_application']}")
    lines += ["", "## Candidate areas in this repo", ""]
    lines += [f"- {c['area']}: {c['why_hard_for_sol']} (pain points: {', '.join(c['pain_points'])})"
              for c in out["candidate_areas"]]
    lines += ["", "## Avoid in this repo", ""] + [f"- {x}" for x in out["avoid"]]
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    rf.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (RESEARCH_DIR / f"{rc['name']}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(f"research: {len(out['findings'])} findings, {len(out['candidate_areas'])} candidate areas -> {rf.name}")


def stage_scout(count: int) -> list[str]:
    rc = CFG["repo"]
    prompt = render("scout", COUNT=str(count), REPO_URL=rc["url"], BASE_COMMIT=rc["base_commit"],
                    REPO_NOTES=rc["notes"], UPSTREAM_BRANCH=rc["upstream_branch"], REPO_NAME=rc["name"],
                    PAINPOINT_STATS=json.dumps(load_stats() or {"note": "no Sol results yet"}, indent=2),
                    EXISTING_TASKS=existing_tasks_text(), **common_paths())
    out = claude("M1", "scout", "_slate", prompt, schema("slate"), cwd=REPO, write=False)
    ids = []
    taken = {st["task_id"] for st in all_states()} | {p.name for p in TASKS.glob("*")}
    for p in out["proposals"][:count]:
        tid = re.sub(r"[^a-z0-9-]+", "-", p["task_id"].lower()).strip("-")
        base, n = tid, 2
        while tid in taken:
            tid, n = f"{base}-{n}", n + 1
        p["task_id"] = tid
        taken.add(tid)
        st = {"task_id": tid, "repo": rc["name"], "base_commit": rc["base_commit"], "created": now(),
              "status": "proposed", "proposal_v1": p, "proposal": p, "history": []}
        mark(st, "scout", True, f"slate of {len(out['proposals'])}")
        ids.append(tid)
    log(f"scout: {len(ids)} proposals: {', '.join(ids)}")
    return ids


def stage_review_proposal(st: dict) -> None:
    prompt = render("review_proposal", PROPOSAL=st["proposal_v1"], **common_paths())
    out = claude("R1", "review_proposal", st["task_id"], prompt, schema("proposal_review"), cwd=REPO, write=False)
    st["proposal_review"] = out
    mark(st, "review_proposal", True, f"{out['predicted_outcome']}, {len(out['findings'])} findings")


def stage_revise_proposal(st: dict) -> None:
    prompt = render("revise_proposal", PROPOSAL=st["proposal_v1"], REVIEW=st["proposal_review"], **common_paths())
    out = claude("M1", "revise_proposal", st["task_id"], prompt, proposal_schema(True), cwd=REPO, write=False)
    out["task_id"] = st["task_id"]  # the id is fixed once allocated
    st["proposal"] = out
    st["status"] = "hardened"
    mark(st, "revise_proposal", True, f"{len(out.get('revision_notes', []))} revision notes")


def image_tag(tid: str) -> str:
    return f"factory-{tid}"


def build_prompt(st: dict) -> str:
    tid = st["task_id"]
    examples = ", ".join(f"`{win(p.parent)}`" for p in sorted(TASKS.glob("*/task.toml"))[:2])
    rules = "\n".join(f"- {r}" for r in CFG["repo"].get("build_rules", [])) or "- (none)"
    return render("build", PROPOSAL=st["proposal"], BASE_COMMIT=CFG["repo"]["base_commit"], WORKTREE=win(WT_DIR / tid),
                  TASK_DIR=win(TASKS / tid), TEMPLATE_DIR=win(PIPE / "task_template"), EXAMPLE_TASKS=examples,
                  INTEL=win(INTEL), VALIDATE_SCRIPT=win(PIPE / "validate_local.sh"), IMAGE_TAG=image_tag(tid),
                  DOCKER_BASE_IMAGE=CFG["repo"]["docker_base_image"], TASK_ID=tid, BUILD_RULES=rules,
                  ALLOWED_HOSTS=json.dumps(CFG["network_allowed_hosts"]))


def stage_build(st: dict) -> None:
    tid = st["task_id"]
    wt = ensure_worktree(tid)
    out = claude("M1", "build", tid, build_prompt(st), schema("build_report"), cwd=wt, write=True)
    st["build_report"] = out
    st["status"] = "built"
    mark(st, "build", True, f"nop={out['nop_reward']} oracle={out['oracle_reward']}")


def stage_review_package(st: dict) -> None:
    tid = st["task_id"]
    prompt = render("review_package", TASK_DIR=win(TASKS / tid), PROPOSAL=st["proposal"],
                    BUILD_REPORT=st.get("build_report", {}), GATE_REPORT=st.get("gate_build", {}), **common_paths())
    out = claude("R1", "review_package", tid, prompt, schema("package_review"), cwd=TASKS / tid, write=False)
    st["package_review"] = out
    n = {s: sum(i["severity"] == s for i in out["issues"]) for s in ("blocker", "major", "minor")}
    mark(st, "review_package", True, f"issues {n}")


def stage_fix_package(st: dict) -> None:
    tid = st["task_id"]
    gate_problems = [c for c in st.get("gate_build", {}).get("checks", []) if c["status"] not in ("pass", "skip")]
    rendered = LOG_DIR / tid / "build.rendered.md"  # the exact rules the build step got, placeholders filled
    rendered.parent.mkdir(parents=True, exist_ok=True)
    rendered.write_text(build_prompt(st), encoding="utf-8")
    prompt = render("fix_package", TASK_DIR=win(TASKS / tid), WORKTREE=win(ensure_worktree(tid)),
                    REVIEW=st["package_review"], GATE_REPORT=gate_problems,
                    BUILD_PROMPT=win(rendered), INTEL=win(INTEL),
                    VALIDATE_SCRIPT=win(PIPE / "validate_local.sh"), IMAGE_TAG=image_tag(tid))
    out = claude("M1", "fix_package", tid, prompt, schema("fix_report"), cwd=WT_DIR / tid, write=True)
    st["fix_report"] = out
    mark(st, "fix_package", True, f"addressed {len(out['issues_addressed'])}, not {len(out['issues_not_addressed'])}")


FORCE_INSTRUCTION_CHECK = False  # set by the `instruction-check` command


def stage_instruction_check(st: dict) -> None:
    """Step 9: M1 re-reads the packaged instruction.md for leaks/hints of the solution and returns a rewrite
    if needed. The factory (not the model) writes the file, keeping a backup."""
    tid, d = st["task_id"], TASKS / st["task_id"]
    if st.get("done", {}).get("gate_final") and not FORCE_INSTRUCTION_CHECK:
        # packaged before this stage existed: never rewrite an already-validated/evaluated task implicitly
        mark(st, "instruction_check", True, "skipped: packaged before this stage existed (use instruction-check)")
        return
    leaked, hits = instruction_lint(d)
    original = (d / "instruction.md").read_text(encoding="utf-8")
    prompt = render("instruction_check", TASK_DIR=win(d), PROPOSAL=st["proposal"],
                    LINT=json.dumps({"fix_names_in_instruction": leaked, "fix_path_words_in_instruction": hits}),
                    **{k: v for k, v in common_paths().items() if k != "RESEARCH"})
    out = claude("M1", "instruction_check", tid, prompt, schema("instruction_check"), cwd=d, write=False)
    st["instruction_check"] = out
    note = f"{len(out['leaks'])} leaks"
    if out["rewrite"]:
        new = out["new_instruction"].replace("\r\n", "\n").strip() + "\n"
        if not new.strip() or new == original:
            raise StageError("instruction_check asked for a rewrite but returned no new text")
        bak = WORK / "instruction_backups" / f"{tid}.{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        bak.parent.mkdir(parents=True, exist_ok=True)
        bak.write_text(original, encoding="utf-8")
        with open(d / "instruction.md", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new)
        leaked2, hits2 = instruction_lint(d)
        st.setdefault("done", {}).pop("gate_final", None)  # a new instruction must pass the final gate again
        note += f", rewritten ({len(original.split())}->{len(new.split())} words, backup {bak.name}); " \
                f"lint after: names={leaked2} words={hits2}"
        st["instruction_rewrite"] = {"backup": str(bak), "at": now()}
        st.setdefault("done", {}).pop("review_instruction", None)  # R1 must see this new text
    else:
        st.pop("instruction_rewrite", None)
    mark(st, "instruction_check", True, note)


def stage_review_instruction(st: dict) -> None:
    """R1 reviews an instruction.md that instruction_check rewrote (R1's package review saw the old text).
    Not approved -> the original is restored from the backup; no extra M1 round."""
    tid, d = st["task_id"], TASKS / st["task_id"]
    rw = st.get("instruction_rewrite")
    if not rw:
        mark(st, "review_instruction", True, "skipped: instruction not rewritten")
        return
    bak = Path(rw["backup"])
    prompt = render("review_instruction", TASK_DIR=win(d), ORIGINAL=win(bak), PROPOSAL=st["proposal"],
                    LEAKS=st.get("instruction_check", {}).get("leaks", []),
                    **{k: v for k, v in common_paths().items() if k != "RESEARCH"})
    out = claude("R1", "review_instruction", tid, prompt, schema("review_instruction"), cwd=d, write=False)
    st["instruction_review"] = out
    if out["approve"]:
        note = "rewrite approved"
    else:
        with open(d / "instruction.md", "w", encoding="utf-8", newline="\n") as fh:
            fh.write(bak.read_text(encoding="utf-8"))
        st.setdefault("done", {}).pop("gate_final", None)
        note = f"rewrite REJECTED, original restored: {'; '.join(out['problems'])[:300]}"
    st.pop("instruction_rewrite", None)
    mark(st, "review_instruction", True, note)


def write_report(st: dict, label: str) -> Path:
    ev, tid = st["eval"], st["task_id"]
    learn = st.get("learn", {})
    rows = "\n".join(f"| {i} | {t['reward']} | {t['minutes']} | {t['output_tokens']} | {t['exception'] or ''} |"
                     for i, t in enumerate(ev["attempts"], 1))
    p = st.get("proposal", {})
    text = f"""# {p.get('title', tid)}

**Task:** `{tid}` · repo `{st.get('repo')}` @ `{st.get('base_commit')}`
**Verdict:** {label} · **Sol outcome:** {ev['outcome']} ({ev['passes']}/{ev['trials'] - ev['errors']} scored passes, {ev['errors']} infra errors) · model `{ev['model']}`, effort {ev['effort']}
**Pain points targeted:** {', '.join(p.get('pain_points', []))}

## Attempts

| # | Reward | Minutes | Output tokens | Exception |
|---|---|---|---|---|
{rows}

## Learn stage (M1)

- Legitimate failures: {learn.get('legit_failures', 'n/a')}
- Task problems: {'; '.join(learn.get('task_problems', [])) or 'none'}
- Summary: {learn.get('summary', 'n/a')}

Run folder: `jobs/{ev['run']}/`. Generated by the factory verdict stage on {now()}.
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"REPORT_{tid}.md"
    if out.exists():  # never overwrite a hand-written report
        out = REPORTS / f"REPORT_{tid}.factory.md"
    out.write_text(text, encoding="utf-8")
    return out


def stage_verdict(st: dict) -> None:
    """After Harbor testing: reject easy tasks (moved to rejected_tasks/), report expert/hard ones."""
    tid, ev = st["task_id"], st["eval"]
    scored = ev["trials"] - ev["errors"]
    learn = st.get("learn", {})
    threshold = CFG["eval"].get("reject_if_passes_at_least", CFG["eval"]["attempts"])
    if scored < CFG["eval"]["attempts"]:
        # infra errors ate some attempts: never reject (or rate) a task on a partial sample
        label = (f"inconclusive: only {scored} of {CFG['eval']['attempts']} attempts scored "
                 f"({ev['passes']} passed, {ev['errors']} infra errors); re-run the eval")
        status = "needs_review"
    elif ev["passes"] >= threshold:
        label, status = "EASY - rejected", "rejected_easy"
    elif ev["passes"] == 0 and learn.get("task_problems"):
        label, status = "0 passes but the learn stage found task problems - check validity", "needs_review"
    elif ev["passes"] == 0:
        label, status = "EXPERT (Sol 0 passes)", "reported_expert"
    else:
        label, status = f"HARD (Sol {ev['passes']}/{scored})", "reported_hard"
    report = write_report(st, label)
    if status == "rejected_easy":
        REJECTED.mkdir(parents=True, exist_ok=True)
        dest = REJECTED / tid
        if dest.exists():
            dest = REJECTED / f"{tid}.{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.move(str(TASKS / tid), str(dest))  # moved, not deleted
        st["rejected_to"] = win(dest)
    st["verdict"] = {"label": label, "report": win(report), "at": now()}
    st["status"] = status
    mark(st, "verdict", True, f"{label}; report {report.name}")


# ----------------------------------------------------------------------------- gate (deterministic)
GENERIC_DIRS = {"src", "pkg", "lib", "controller", "server", "internal", "cmd", "common", "util", "utils",
                "model", "models", "core", "app", "api", "v2", "v2.0", "handler", "test", "testing"}


def _diff_files(patch: str) -> list[tuple[str, str]]:
    """[(path, 'new'|'deleted'|'modified')] for each file in a git diff."""
    out = []
    for block in re.split(r"(?m)^(?=diff --git )", patch):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", block)
        if m:
            head = block.split("@@", 1)[0]
            mode = "new" if "new file mode" in head else "deleted" if "deleted file mode" in head else "modified"
            out.append((m.group(2), mode))
    return out


def instruction_lint(d: Path) -> tuple[list[str], list[str]]:
    """Deterministic leak lint: (function/type names from the fix found in instruction.md -> gate fail,
    file/package words from the fix found in it -> gate warn, AP-1)."""
    instr = (d / "instruction.md").read_text(encoding="utf-8")
    sol = (d / "solution/solution.patch").read_text(encoding="utf-8", errors="replace")
    sol_files = _diff_files(sol)
    symbols = set(re.findall(r"^[+-]func (?:\([^)]*\) )?([A-Za-z_]\w{3,})\(", sol, re.M))
    symbols |= set(re.findall(r"^@@[^@]*@@ func (?:\([^)]*\) )?([A-Za-z_]\w{3,})\(", sol, re.M))
    symbols |= set(re.findall(r"^[+-]type ([A-Za-z_]\w{3,}) ", sol, re.M))
    leaked = sorted(s for s in symbols if re.search(rf"\b{re.escape(s)}\b", instr))
    words = {Path(p).stem.replace("_", " ") for p, _ in sol_files} | {seg for p, _ in sol_files for seg in Path(p).parent.parts}
    words = {w for w in words if w.lower() not in GENERIC_DIRS and len(w) >= 4}
    hits = sorted(w for w in words if re.search(rf"\b{re.escape(w)}\b", instr, re.I))
    return leaked, hits


def _apply_check(d: Path) -> subprocess.CompletedProcess:
    """Do solution.patch and test.patch apply at the base commit (plus environment/base.patch, if any)?"""
    patches = [str(d / "solution/solution.patch"), str(d / "tests/test.patch")]
    base_patch = d / "environment" / "base.patch"
    if not base_patch.exists():
        return sh(["git", "-C", str(REPO), "apply", "--check", *patches], check=False)
    # A throwaway index instead of a clone + full checkout: read the base tree into it, apply base.patch to the
    # index only, then check the two patches against that. No working tree is written, so this takes seconds even
    # on big repos. The index lives in WSL-native /tmp (drvfs /mnt/f lost git's cwd under heavy I/O, factory run 3).
    idx = Path("/tmp/factory-apply") / f"index-{d.name}-{os.urandom(3).hex()}"
    idx.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_INDEX_FILE": str(idx)}
    git = ["git", "-C", str(REPO)]
    try:
        sh([*git, "read-tree", CFG["repo"]["base_commit"]], env=env, timeout=600)
        r = sh([*git, "apply", "--cached", str(base_patch)], check=False, env=env)
        if r.returncode != 0:
            r.stdout = "environment/base.patch does not apply at base:\n" + r.stdout
            return r
        return sh([*git, "apply", "--cached", "--check", *patches], check=False, env=env)
    finally:
        idx.unlink(missing_ok=True)


def _docker(args: list[str], timeout: int = 3600) -> subprocess.CompletedProcess:
    return sh(["docker", *args], check=False, timeout=timeout)


# One limit for heavy test containers (compile, nop, oracle) across ALL tasks in this process: Docker Desktop has
# ~8 GB, and two final gates with parallel oracles could otherwise run 8 Go test containers at once and get
# OOM-killed, which looks like a failed oracle and blocks a valid task.
TEST_SEM = threading.BoundedSemaphore(max(1, CFG.get("gate", {}).get("max_test_containers", 3)))


def _test_run(tid: str, kind: str, args: list[str], timeout: int = 3600) -> subprocess.CompletedProcess:
    """`docker run --rm` for a heavy test container: throttled by TEST_SEM, optionally memory-capped, and
    named so a timed-out container is removed instead of running on after its client is killed."""
    name = f"factory-gate-{tid[:40]}-{kind}-{os.urandom(3).hex()}"
    mem = CFG.get("gate", {}).get("container_memory")
    with TEST_SEM:
        try:
            return sh(["docker", "run", "--rm", "--name", name, *(["--memory", mem] if mem else []), *args],
                      check=False, timeout=timeout)
        except subprocess.TimeoutExpired:
            sh(["docker", "rm", "-f", name], check=False, timeout=120)
            return subprocess.CompletedProcess(args, 124, f"[gate] {kind} container timed out after {timeout}s "
                                                          f"and was removed\n", None)


def _reward(r: subprocess.CompletedProcess) -> int | None:
    m = re.findall(r"__REWARD__=(\S*)", r.stdout or "")
    return int(m[-1]) if m and m[-1].isdigit() else None


def gate(tid: str, oracle_runs: int = 1, run_rewards: bool = True) -> dict:
    d = TASKS / tid
    rc = CFG["repo"]
    checks: list[dict] = []

    def add(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail[:2000]})

    req = ["instruction.md", "task.toml", "environment/Dockerfile", "solution/solve.sh", "solution/solution.patch",
           "tests/test.sh", "tests/test.patch"]
    missing = [r for r in req if not (d / r).is_file()]
    if missing:
        add("files_present", "fail", f"missing: {missing}")
        return {"ok": False, "at": now(), "checks": checks}
    add("files_present", "pass")

    # task.toml
    try:
        t = tomllib.loads((d / "task.toml").read_text(encoding="utf-8"))
        env, meta = t.get("environment", {}), t.get("metadata", {})
        probs = []
        if t.get("task", {}).get("name") != f"dataorigin/{tid}":
            probs.append(f"task.name should be dataorigin/{tid}")
        if env.get("network_mode") != "allowlist" or sorted(env.get("allowed_hosts", [])) != sorted(CFG["network_allowed_hosts"]):
            probs.append(f"[environment] must be network_mode='allowlist' with allowed_hosts={CFG['network_allowed_hosts']}")
        if meta.get("base_commit_hash") != rc["base_commit"]:
            probs.append("metadata.base_commit_hash mismatch")
        add("task_toml", "fail" if probs else "pass", "; ".join(probs))
    except tomllib.TOMLDecodeError as e:
        add("task_toml", "fail", f"invalid TOML: {e}")

    # line endings
    crlf = [f for f in ("solution/solution.patch", "tests/test.patch", "tests/test.sh", "solution/solve.sh",
                        "environment/Dockerfile", "environment/base.patch")
            if (d / f).exists() and b"\r" in (d / f).read_bytes()]
    add("lf_line_endings", "fail" if crlf else "pass", f"CRLF in {crlf}" if crlf else "")

    sol = (d / "solution/solution.patch").read_text(encoding="utf-8", errors="replace")
    tst = (d / "tests/test.patch").read_text(encoding="utf-8", errors="replace")
    sol_files, test_files = _diff_files(sol), _diff_files(tst)
    if rc["language"] == "go":
        is_test = lambda p: p.endswith("_test.go")
    elif rc["language"] in ("typescript", "javascript"):
        is_test = lambda p: bool(re.search(r"\.(spec|test)\.[cm]?[jt]sx?$", p)) or "/__tests__/" in p
    elif rc["language"] in ("python", "cpp", "rust", "java"):
        # tests/test_*.py, test/unit/**/FooTest.cpp + test/data, tests/suite/*.typ, crates/x/tests/*.rs, src/test/**
        is_test = lambda p: bool({"test", "tests"} & set(Path(p).parts[:-1])) or "/src/test/" in f"/{p}"
    elif rc["language"] == "lua":
        # Test::Nginx files t/**/*.t (apisix), busted *_spec.lua
        is_test = lambda p: (p.startswith("t/") and p.endswith(".t")) or p.endswith("_spec.lua")
    else:
        is_test = lambda p: "test" in Path(p).name.lower()
    # C++ hidden tests must be registered in the test dir's CMakeLists.txt, the only existing file test.patch may modify
    may_modify = lambda p: rc["language"] == "cpp" and is_test(p) and Path(p).name == "CMakeLists.txt"
    bad_sol = [p for p, _ in sol_files if is_test(p)]
    bad_tst = [p for p, mode in test_files if not is_test(p) or (mode == "modified" and not may_modify(p))]
    deleted = [p for p, mode in test_files if mode == "deleted" and is_test(p)]
    add("solution_patch_source_only", "fail" if bad_sol or not sol_files else "pass", f"test files in solution: {bad_sol}" if bad_sol else "")
    add("test_patch_new_test_files_only", "fail" if bad_tst or not any(m == "new" for _, m in test_files) else "pass",
        f"non-test or modified existing files: {bad_tst}" if bad_tst else "")
    if deleted:
        add("test_patch_deletes_existing_tests", "warn",
            f"test.patch deletes existing tests (allowed only when they pin base internals a valid fix may change; "
            f"R1 must confirm no behavioral coverage is lost): {deleted}")
    dirs = {str(Path(p).parent) for p, _ in sol_files}
    add("multi_site_fix", "pass" if len(sol_files) >= 2 else "warn",
        f"{len(sol_files)} file(s) in {len(dirs)} dir(s): {[p for p, _ in sol_files]}")

    # patches apply at base
    r = _apply_check(d)
    add("patches_apply_at_base", "pass" if r.returncode == 0 else "fail", r.stdout[-1500:])
    base_patch = d / "environment" / "base.patch"
    if base_patch.exists():
        bp_files = _diff_files(base_patch.read_text(encoding="utf-8", errors="replace"))
        add("base_patch_present", "warn", f"the image modifies the base commit (e.g. neutralized comments) in: "
            f"{[p for p, _ in bp_files]}. R1 must confirm it only removes hints and changes no behavior.")

    # instruction leak lint
    leaked, hits = instruction_lint(d)
    add("instruction_no_code_symbols", "fail" if leaked else "pass", f"names from the fix appear in instruction.md: {leaked}" if leaked else "")
    add("instruction_no_subsystem_terms", "warn" if hits else "pass",
        f"file/package words from the fix appear in instruction.md (AP-1, grep-able): {hits}" if hits else "")

    # upstream leak
    ref = f"origin/{rc['upstream_branch']}"
    r = sh(["git", "-C", str(REPO), "log", "--oneline", f"{rc['base_commit']}..{ref}", "--", *[p for p, _ in sol_files]], check=False)
    up = r.stdout.strip()
    add("upstream_not_fixed", "warn" if up else "pass", f"upstream commits after base touch the fix files (AP-6):\n{up}" if up else "")

    # docker checks
    img = image_tag(tid)
    # cache key = every file in the build context (Dockerfile, base.patch, anything else COPY'd), not just the Dockerfile
    h = hashlib.sha256()
    for f in sorted(p for p in (d / "environment").rglob("*") if p.is_file()):
        h.update(f.relative_to(d / "environment").as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    dsha = h.hexdigest()[:16]
    cur = _docker(["image", "inspect", "-f", '{{ index .Config.Labels "factory.dockerfile" }}', img]).stdout.strip()
    if cur != dsha:
        r = _docker(["build", "-q", "--label", f"factory.dockerfile={dsha}", "-t", img, str(d / "environment")], timeout=3600)
        if r.returncode != 0:
            add("docker_build", "fail", r.stdout[-2500:])
            return {"ok": False, "at": now(), "checks": checks}
    add("docker_build", "pass", img)

    r = _docker(["run", "--rm", "--network", "none", img, "bash", "-c",
                 "cd /app && echo commits=$(git rev-list --count HEAD) remotes=$(git remote | wc -l) "
                 "fetch_head=$(test -e .git/FETCH_HEAD && echo yes || echo no) solution=$(test -e /solution && echo yes || echo no) "
                 "dirty=$(git status --porcelain | wc -l) reflog=$(git reflog | wc -l) "
                 "base_patch_file=$(find / -xdev -name base.patch -not -path '/proc/*' 2>/dev/null | wc -l) "
                 f"head=$(git rev-parse HEAD)"])
    info = r.stdout.strip()
    need = ["commits=1", "remotes=0", "fetch_head=no", "solution=no", "dirty=0", "base_patch_file=0"]
    if base_patch.exists():
        # the neutralized base must be folded into the single commit: no reflog/ORIG_HEAD that reveals the original
        need.append("reflog=1")
    else:
        need.append(f"head={rc['base_commit']}")
    ok_hist = all(x in info for x in need)
    add("image_history_free", "pass" if ok_hist else "fail", f"{info}\nrequired: {need}")

    mounts = ["-v", f"{d / 'tests'}:/tests:ro", "-v", f"{d / 'solution'}:/solution:ro"]
    if rc["language"] == "go":
        mod = rc.get("module_dir", ".")
        pkgs = sorted({"./" + str(Path(p).parent.relative_to(mod)) + "/" for p, _ in test_files
                       if p.endswith("_test.go") and (mod == "." or p.startswith(mod + "/"))})
        r = _test_run(tid, "compile", ["--network", "none", *mounts, img, "bash", "-c",
                      f"cd /app && git apply /tests/test.patch && cd {mod} && go vet {' '.join(pkgs)}"])
        add("hidden_tests_compile_on_base", "pass" if r.returncode == 0 else "fail",
            "" if r.returncode == 0 else "hidden tests do not compile against the base commit (they probably reference "
                                         "symbols that only exist in the reference fix):\n" + r.stdout[-2000:])
    else:
        add("hidden_tests_compile_on_base", "warn",
            f"no automatic compile check for {rc['language']} yet: R1 must confirm the hidden tests only use "
            "APIs that exist at the base commit")

    if not run_rewards:
        # gate_build: M1's build step already ran nop/oracle and the final gate re-runs them x3,
        # so the build gate stays static (+ image history + hidden-test compile) and hands R1 the self-report
        add("nop_oracle_rewards", "skip", "not run in the build gate; see M1's build report (nop_reward/oracle_reward). "
            "The final gate runs nop + oracle x3 offline.")
        ok = all(c["status"] != "fail" for c in checks)
        return {"ok": ok, "at": now(), "oracle_runs": 0, "checks": checks}

    tail = "; echo __REWARD__=$(cat /logs/verifier/reward.txt 2>/dev/null)"
    r = _test_run(tid, "nop", ["--network", "none", *mounts, img, "bash", "-c", "bash /tests/test.sh" + tail])
    nop = _reward(r)
    add("nop_reward_0", "pass" if nop == 0 else "fail", f"reward={nop}\n" + (r.stdout or "")[-1500:])

    def oracle_once(i: int) -> subprocess.CompletedProcess:
        return _test_run(tid, f"oracle{i + 1}", ["--network", "none", *mounts, img, "bash", "-c",
                                                 "bash /solution/solve.sh && bash /tests/test.sh" + tail])

    # oracle runs side by side (throttled by TEST_SEM across tasks): faster, and contention also shakes out flaky tests
    with ThreadPoolExecutor(max_workers=max(1, oracle_runs)) as ex:
        runs = list(ex.map(oracle_once, range(oracle_runs)))
    rewards = [_reward(x) for x in runs]
    bad = next((x for x, rw in zip(runs, rewards) if rw != 1), None)
    add("oracle_reward_1_offline", "pass" if rewards and bad is None else "fail",
        f"rewards={rewards} (parallel)\n" + ("" if bad is None else (bad.stdout or "")[-2000:]))

    ok = all(c["status"] != "fail" for c in checks)
    return {"ok": ok, "at": now(), "oracle_runs": oracle_runs, "checks": checks}


def stage_gate(st: dict, label: str, oracle_runs: int) -> None:
    rep = gate(st["task_id"], oracle_runs, run_rewards=(label != "gate_build"))
    st[label] = rep
    fails = [c["name"] for c in rep["checks"] if c["status"] == "fail"]
    warns = [c["name"] for c in rep["checks"] if c["status"] == "warn"]
    if label == "gate_final":
        st["status"] = "packaged" if rep["ok"] else "blocked"
    # gate_build never blocks: its findings go to R1 and the single fix round
    mark(st, label, True if label == "gate_build" else rep["ok"], f"fail={fails} warn={warns}")
    log(f"{st['task_id']}/{label}: {'OK' if rep['ok'] else 'FAIL'} fail={fails} warn={warns}")


# ----------------------------------------------------------------------------- eval + learn
def harbor_bin() -> str:
    for c in (shutil.which("harbor"), str(Path.home() / ".local/bin/harbor")):
        if c and Path(c).exists():
            return c
    raise StageError("harbor CLI not found (uv tool install harbor)")


def stage_eval(st: dict) -> None:
    tid, ev = st["task_id"], CFG["eval"]
    # a fresh job folder per eval run: a retry must not count (or collide with) an earlier run's trials
    run = f"factory-{tid}-sol-{dt.datetime.now():%Y%m%d-%H%M%S}"
    rt = PIPE / "infrastructure" / "codex-runtime"
    overlay = f"factory-{tid}-codex:0.167.2"
    sh(["docker", "build", "-q", "--build-arg", f"BASE_IMAGE={image_tag(tid)}:latest", "-t", overlay, str(rt)], timeout=3600)
    compose = WORK / "compose" / f"{tid}.yaml"
    compose.parent.mkdir(parents=True, exist_ok=True)
    compose.write_text(
        "services:\n  main:\n"
        f"    image: {overlay}\n"
        "    build:\n"
        f"      context: {rt}\n"
        "      dockerfile: Dockerfile\n"
        "      args:\n"
        f"        BASE_IMAGE: {image_tag(tid)}:latest\n", encoding="utf-8")
    jobs = PIPE / "jobs"
    cmd = ["python3", str(PIPE / "run_eval.py"), str(TASKS / tid), "-a", ev["agent"], "-m", ev["model"],
           "--reasoning-effort", ev["reasoning_effort"], "--codex-auth-json", ev["codex_auth_json"],
           "--task-author", ev["task_author"], "-k", str(ev["attempts"]), "-n", "1", "--run-name", run,
           "-o", str(jobs), "--harbor-bin", harbor_bin(), "--", "--extra-docker-compose", str(compose)]
    log(f"{tid}/eval: {ev['model']} x{ev['attempts']} (effort {ev['reasoning_effort']}) ...")
    sh(cmd, cwd=PIPE, check=False, timeout=6 * 3600, capture=False)
    trials = []
    for rf in sorted((jobs / run).glob("*/result.json")):
        r = json.loads(rf.read_text(encoding="utf-8"))
        reward = ((r.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        try:
            mins = round((dt.datetime.fromisoformat(r["finished_at"].replace("Z", "+00:00")) -
                          dt.datetime.fromisoformat(r["started_at"].replace("Z", "+00:00"))).total_seconds() / 60, 1)
        except (KeyError, ValueError, AttributeError):
            mins = None
        exc = r.get("exception_info") or {}
        trials.append({"trial_dir": win(rf.parent), "reward": reward, "minutes": mins,
                       "output_tokens": (r.get("agent_result") or {}).get("n_output_tokens"),
                       "exception": exc.get("exception_type")})
    if not trials:
        raise StageError(f"no trial results under {jobs / run}")
    status = lambda t: "P" if (t["reward"] or 0) >= 1 else ("E" if t["reward"] is None and t["exception"] else "F")
    summary = {"run": run, "model": ev["model"], "effort": ev["reasoning_effort"],
               "outcome": "".join(status(t) for t in trials), "trials": len(trials),
               "passes": sum(status(t) == "P" for t in trials), "errors": sum(status(t) == "E" for t in trials),
               "attempts": trials}
    st["eval"] = summary
    st["status"] = "evaluated"
    scored = {**summary, "trials": summary["trials"] - summary["errors"]}  # infra errors don't count
    update_stats(st["proposal"], scored)
    mark(st, "eval", True, f"outcome {summary['outcome']}")


def stage_learn(st: dict) -> None:
    tid = st["task_id"]
    prompt = render("learn", TASK_ID=tid, TASK_DIR=win(TASKS / tid), PROPOSAL=st["proposal"],
                    REVIEW=st.get("proposal_review", {}), EVAL_SUMMARY=st["eval"],
                    TRIAL_DIRS=", ".join(f"`{t['trial_dir']}`" for t in st["eval"]["attempts"]),
                    INTEL=win(INTEL), PAINPOINTS=win(PAINPOINTS))
    out = claude("M1", "learn", tid, prompt, schema("learn"), cwd=PIPE, write=True)
    st["learn"] = out
    st["status"] = "learned"
    mark(st, "learn", True, out["summary"][:200])


# ----------------------------------------------------------------------------- flows
def run_stages(tid: str, stages: list[str], oracle_runs_final: int) -> bool:
    st = load_state(tid)
    for stage in stages:
        if st.get("done", {}).get(stage):
            continue
        try:
            if stage == "gate_build":
                stage_gate(st, "gate_build", 1)
            elif stage == "gate_final":
                stage_gate(st, "gate_final", oracle_runs_final)
                if not st["gate_final"]["ok"]:
                    return False
            else:
                globals()[f"stage_{stage}"](st)
        except StageError as e:
            mark(st, stage, False, str(e))
            st["status"] = f"error:{stage}"
            save_state(st)
            log(f"{tid}/{stage}: ERROR {str(e)[:300]}")
            return False
        except Exception as e:  # keep other tasks running
            mark(st, stage, False, "".join(traceback.format_exception(e))[-1500:])
            st["status"] = f"error:{stage}"
            save_state(st)
            log(f"{tid}/{stage}: CRASH {e!r}")
            return False
    return True


def parallel(ids: list[str], stages: list[str], workers: int, oracle_runs_final: int) -> list[str]:
    ok = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(run_stages, tid, stages, oracle_runs_final): tid for tid in ids}
        for f in as_completed(futs):
            if f.result():
                ok.append(futs[f])
    return ok


def cmd_run(a) -> None:
    global DRY_RUN
    DRY_RUN = a.dry_run
    ensure_repo()
    ids: list[str] = []
    if a.resume:
        ids += [s["task_id"] for s in all_states() if s.get("status") not in TERMINAL
                and s.get("repo", "harbor") == CFG["repo"]["name"]  # one repo profile per process
                and (not a.only or s["task_id"] in a.only)]
    if a.count and not a.skip_research:
        try:  # step 3: research before proposing (cached per repo; never blocks)
            stage_research(force=a.fresh_research)
        except StageError as e:
            log(f"research failed, scouting with the existing catalog: {e}")
    if a.count:
        remaining = a.count
        while remaining > 0:  # slates of at most 10 keep each scout call focused
            n = min(10, remaining)
            try:
                ids += stage_scout(n)
            except StageError as e:
                log(f"scout failed: {e}")
                break
            remaining -= n
    if not ids:
        log("nothing to do")
        return
    log(f"tasks: {ids}")
    conc = CFG["concurrency"]
    ids = parallel(ids, PROPOSAL_STAGES, conc["proposals"], a.oracle_runs)
    if a.until == "proposal":
        return
    ids = parallel(ids, PACKAGE_STAGES, conc["builds"], a.oracle_runs)
    if a.until == "package" or not (a.eval or CFG["eval"]["enabled"]):
        log(f"packaged: {ids}")
        return
    for tid in ids:  # one Codex login: evaluate sequentially
        run_stages(tid, EVAL_STAGES, a.oracle_runs)


def cmd_status(_a) -> None:
    rows = all_states()
    if not rows:
        print("no tasks yet")
        return
    print(f"{'task':48} {'repo':12} {'status':22} {'last stage':18} sol")
    for s in rows:
        last = (s.get("history") or [{}])[-1]
        print(f"{s['task_id'][:48]:48} {s.get('repo', 'harbor'):12} {s.get('status', ''):22} {last.get('stage', ''):18} "
              f"{(s.get('eval') or {}).get('outcome', '')}")


def cmd_research(a) -> None:
    global DRY_RUN
    DRY_RUN = a.dry_run
    ensure_repo()
    stage_research(force=True)
    print(win(research_file()))


def cmd_instruction_check(a) -> None:
    """Run step 9 on an already-packaged task, then re-run the final gate if the instruction was rewritten."""
    global FORCE_INSTRUCTION_CHECK
    FORCE_INSTRUCTION_CHECK = True
    ensure_repo()
    st = load_state(a.task_id)
    if not st:
        raise SystemExit(f"no factory state for {a.task_id}")
    st.setdefault("done", {}).pop("instruction_check", None)
    save_state(st)
    # no Docker by default: a rewrite clears done.gate_final, so the next package/package-all run re-gates it
    run_stages(a.task_id, ["instruction_check", "review_instruction"] + (["gate_final"] if a.gate else []), a.oracle_runs)
    st = load_state(a.task_id)
    print(json.dumps({"instruction_check": st.get("instruction_check"), "status": st.get("status"),
                      "last": (st.get("history") or [])[-3:]}, indent=2))


def cmd_gate(a) -> None:
    ensure_repo()
    print(json.dumps(gate(a.task_id, a.oracle_runs), indent=2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=CFG["default_repo"], help=f"repo profile from config.json ({', '.join(CFG['repos'])})")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--count", type=int, default=0, help="new tasks to scout")
    r.add_argument("--resume", action="store_true", help="continue unfinished tasks")
    r.add_argument("--only", nargs="*", help="with --resume: only these task ids")
    r.add_argument("--until", choices=["proposal", "package", "eval"], default="eval")
    r.add_argument("--eval", action="store_true", help="run the Sol eval even if config eval.enabled is false")
    r.add_argument("--oracle-runs", type=int, default=3, help="oracle repetitions in the final gate")
    r.add_argument("--dry-run", action="store_true", help="write prompts, don't call models")
    r.add_argument("--skip-research", action="store_true", help="scout without the research step")
    r.add_argument("--fresh-research", action="store_true", help="redo research even if the cached brief is recent")
    r.set_defaults(fn=cmd_run)
    rs = sub.add_parser("research", help="refresh the web research brief for --repo")
    rs.add_argument("--dry-run", action="store_true")
    rs.set_defaults(fn=cmd_research)
    ic = sub.add_parser("instruction-check", help="leak check / rewrite instruction.md of a packaged task")
    ic.add_argument("task_id")
    ic.add_argument("--oracle-runs", type=int, default=1)
    ic.add_argument("--gate", action="store_true", help="also re-run the final gate (Docker build, nop, oracle) after a rewrite")
    ic.set_defaults(fn=cmd_instruction_check)
    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)
    g = sub.add_parser("gate")
    g.add_argument("task_id")
    g.add_argument("--oracle-runs", type=int, default=1)
    g.set_defaults(fn=cmd_gate)
    a = ap.parse_args()
    select_repo(a.repo)
    a.fn(a)


if __name__ == "__main__":
    main()
