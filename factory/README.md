# Hard-task factory

Automates the flow in the diagram: repo → clone → research (web: SWE benchmarks, Sol/frontier pain points) → M1 proposes → R1 hardens (1 revision) → M1 builds/packages → R1 reviews the package (1 revision) → M1 instruction leak check/rewrite → Harbor testing → intel.md → reject easy tasks / report expert-hard ones. Before testing there are no rejections: every task gets exactly one proposal revision and one packaging revision. After Sol testing, easy tasks are rejected. A deterministic gate checks the parts that models can't be trusted to self-report.

| Role | Model (config.json → `models`) | Tools |
|---|---|---|
| M1 author / builder / fixer / learner | `claude-opus-5-5` | read-only to propose; scoped write set to build |
| R1 reviewer (proposal + package) | `claude-fable-5` (newer and cheaper: `claude-fable-5-2`) | read-only |
| Solver under test | GPT-6.1 Sol via Harbor `codex` | allowlisted network |

## Stages (per task, resumable)

```
research (M1 + web)       once per repo, cached work/research/<repo>.md for research.max_age_days (7)
scout (M1, one slate of ≤10 distinct proposals aimed at painpoints.md + the research brief)
 ├─ review_proposal (R1)      sol_attack_path, findings, hardening_round (no reject)
 ├─ revise_proposal (M1)      the single revision
 ├─ build (M1)                worktree fix + hidden tests + task folder + self-validation
 ├─ gate_build (code)         static checks + image + hidden-test compile, no nop/oracle → handed to R1 (never blocks)
 ├─ review_package (R1)       blockers / majors / minors
 ├─ fix_package (M1)          the single packaging revision
 ├─ instruction_check (M1)   leak/hint review of instruction.md; the factory writes the rewrite (backup in work/instruction_backups/)
 ├─ review_instruction (R1)  only after a rewrite: R1 checks the new text (tests still implied, leaks gone, same task);
 │                           not approved → the original instruction is restored
 ├─ gate_final (code)         must pass (nop, oracle ×3 in parallel, offline); else status=blocked (needs a human)
 ├─ eval (Harbor + Sol ×3)    sequential, one Codex login
 ├─ learn (M1)                appends intel.md + painpoints.md evidence; updates painpoint_stats.json
 └─ verdict (code)            fewer than eval.attempts (3) scored attempts (infra errors) → needs_review, never rejected;
                              Sol passes ≥ eval.reject_if_passes_at_least (3) → rejected_easy, folder moved to
                              rejected_tasks/; 0 passes → reported_expert (needs_review if learn found task problems);
                              otherwise reported_hard. Report: harbour-test/REPORT_<task>.md (.factory.md if one exists)
```

## What the gate checks (`python3 factory.py gate <task_id>`)

- **Files and config:** all task files are present; task.toml has the right name and base commit, and `network_mode = "allowlist"` with exactly the OpenAI/ChatGPT hosts; LF line endings.
- **Patches:** solution.patch is source-only, test.patch adds NEW test files only, and both apply at the base commit. A single-file fix gets a warning (AP-4).
- **Instruction leak lint:** function/type names from the fix in instruction.md fail the gate. File/package words in it give a warning (AP-1).
- **Upstream leak:** a warning if upstream commits after the base touch the fix files (AP-6).
- **Image:** exactly one commit, no git remote, no FETCH_HEAD, no `/solution`, HEAD equals the base commit.
- **Hidden tests compile on base:** if they don't, they're coupled to the reference fix.
- **Rewards:** final gate only: nop = 0, then oracle = 1 ×3, the three runs in parallel (also a flakiness check under CPU load). Every run uses `--network none`. The build gate is static + image history + hidden-test compile; it skips nop/oracle because M1 already ran them and the final gate repeats them.
- **Container limit:** heavy gate containers (compile, nop, oracle) share one limit across all tasks (`gate.max_test_containers`, default 3; optional `gate.container_memory`). Containers are named, and a timed-out one is removed.
- **Patch check with base.patch:** done in a throwaway git index (read-tree + apply --cached), seconds instead of a clone + checkout.
- **Image cache:** the task image is rebuilt only when a file in `environment/` changes (Dockerfile, base.patch, any COPY source).

## Run (inside WSL Ubuntu)

```bash
cd /mnt/f/GITHUB/DataOrigin_SWE/harbor_pipeline/factory
python3 factory.py run --count 1 --until proposal   # first check: one hardened proposal
python3 factory.py run --resume --until package     # build + package it
python3 factory.py run --count 10 --until package   # the 10-task batch, without Sol
python3 factory.py run --resume --eval              # Sol eval + learn for everything packaged
python3 factory.py status                           # table: repo, status, last stage, Sol outcome
```

From Claude Code (Git Bash), the same actions go through one launcher that a single permission rule covers:
`bash harbor_pipeline/factory/run.sh <repo> status|propose <n>|package <task>|package-all|eval <task>|gate <task>|research|instruction-check <task>`.

Tasks packaged before the instruction_check stage existed are not rewritten implicitly; run `instruction-check <task>` on them. It does not touch Docker: a rewrite clears the final gate, so the next `package <task>` re-runs it (or pass `--gate` to factory.py).

State lives in `work/state/<task>.json` (every model output and gate report). Prompts and raw model outputs are in `work/logs/<task>/`. A failed stage marks the task `error:<stage>`; `--resume` retries from that stage. Tasks marked `blocked` failed the final gate after the one fix round and need a human.

## Scaling notes

- `concurrency.proposals` / `concurrency.builds` in config.json. Builds are Docker-heavy (each one builds an image and runs Go tests), so 2-3 at a time is right for one machine. Eval is sequential because it shares one ChatGPT login.
- Model stages have no spending caps; only `timeouts_min` limits how long a stage may run. On a timeout the factory also kills the Windows claude.exe process tree, found by its `--session-id`.
- Each eval run writes to a new job folder (`jobs/factory-<task>-sol-<timestamp>`), so a retried eval never counts an earlier run's trials.
- Another repo: add a profile under `repos` in config.json (url, base commit, language, module_dir, docker base image, notes, build_rules) and pass `--repo <name>`. Test-file detection knows Go and TypeScript/JavaScript, plus python/cpp/rust/java by test directory (`test/`, `tests/`, `src/test/`) and lua (`t/**/*.t`, `*_spec.lua`); for cpp, test.patch may also modify the test dir's CMakeLists.txt; the automatic "hidden tests compile on base" check is Go-only (other languages get a warning for R1).

## Safety

- Reviewers, the scout and instruction_check are read-only (Read/Glob/Grep and read-only git/rg). instruction_check returns text; the factory writes instruction.md.
- The research stage is the only one with web access (WebSearch/WebFetch), and it is read-only on disk.
- Writing stages use `acceptEdits` plus the explicit `writer_allowed_tools` list (Docker, git, bash scripts, read-only shell tools). Web tools are denied everywhere except the research stage. Nothing runs with permission checks disabled.
- Task images are history-free and Sol's network is allowlisted, so the solver can't fetch upstream fixes.
