# Hidden-test hardening protocol

How to add trickier hidden tests to an existing task without making it invalid. Each task is hardened separately and must end in the same state it started: nop = 0, oracle = 1 (3/3, offline). It also needs evidence that the new tests catch shortcut solutions.

## 0. Read first
- The whole task folder: instruction.md, task.toml, environment/Dockerfile, environment/base.patch (if any), solution/solution.patch, tests/test.patch, tests/test.sh.
- `harbor_pipeline/intel.md`: the sections about this task's repo (build facts, flaky areas, test layout).
- `harbor_pipeline/factory/painpoints.md`: PP-xx and AP-x.
- If it exists, `harbor_pipeline/factory/work/state/<task_id>.json`: the proposal's `traps`, R1's `sol_attack_path`, `premature_done` and findings. These are the shortcut fixes the task was designed against.
- If a Sol run exists for this task under `harbor_pipeline/jobs/*/<trial>/`, find what Sol changed (`artifacts/**/model.patch` if present; otherwise reconstruct the final diff from `agent/codex.txt` / `agent/trajectory.json`). These are the strongest shortcut candidates.

## 1. What makes a good tricky test
Every new test must follow from **the instruction plus contracts that already exist in the repo** (docs, sibling behavior, other implementations, existing tests). A different correct fix must pass it. Prefer:
- **Implied cases the instruction doesn't list (PP-11):** boundaries, empty/missing values, ordering, duplicates, repeated or idempotent operations, a second iteration, reload or restart.
- **Parity (PP-08):** the same behavior through every other entry point or implementation (other API, other protocol, other backend, other request type).
- **State over time (PP-07):** a sequence of operations where an early wrong design only shows up in a later step.
- **Error and partial-failure paths (PP-06):** what happens when one step fails midway; nothing leaks or half-applies.
- **Adjacent-behavior guards (PP-10):** behavior near the fix that must NOT change. These are PASS_TO_PASS tests that catch over-broad fixes.

Not allowed:
- Asserting on new helper names, signatures, internal structures, exact log or error message wording (unless the instruction or an existing contract fixes it), or timing.
- Tests that need something the instruction doesn't imply. If you're unsure whether a case is implied, it isn't: drop it.
- Sleeps as synchronization, fixed ports, shared temp dirs, wall-clock or random dependence, network, external services.

## 2. Prove the tests are tricky (required)
1. Write 2-4 **shortcut patches**: plausible incomplete fixes a strong agent would produce, written against the base. Examples: fixing only the first visible smell, the happy path only, one implementation of several, caching that goes stale, or Sol's own patch from a past run. Keep them in your scratch area (e.g. `harbor_pipeline/factory/work/hardening/<task_id>/shortcuts/`), NOT in the task folder.
2. Each shortcut must FAIL the new test.sh (reward 0), and you must name the test that catches it. If a shortcut passes, add or sharpen a test until it fails, or explain why that shortcut is actually a correct fix.
3. The reference solution must PASS every new test. If a clearly implied case fails with the reference, the reference is incomplete: extend solution.patch minimally and report it. If the case is not clearly implied, drop the test instead.

## 3. Package
- Put the new tests in the task's hidden test files (they are new files added by test.patch, so editing them is fine), or in additional NEW test files. Never modify the repo's existing test files. Keep any deletions test.patch already makes.
- Regenerate tests/test.patch with `git add -N` + `git diff` against the base (plus base.patch, if any) so it stays LF and applies cleanly.
- Update tests/test.sh: the new test names go in the explicit FAIL_TO_PASS or PASS_TO_PASS lists. Keep the reward logic, and keep guards against "zero tests selected".
- Don't change instruction.md unless a new test truly needs a contract the instruction doesn't imply. Prefer dropping the test. If you change it, keep AP-1..AP-3 (no file/function/subsystem names, no listed cases) and report the exact diff.

## 4. Validate (all of this, in Docker, offline)
- Base + new test.patch: every new FAIL_TO_PASS test fails **on an assertion** (not a compile, import or type error), every PASS_TO_PASS test passes, and test.sh reward = 0.
- Reference: `solve.sh` + `test.sh` reward = 1, **3 runs**, with `--network none`. Run the new tests 5 times in a row with the reference to check for flakiness.
- Every shortcut patch: reward = 0.
- If the task has a factory state, also run the deterministic gate: `bash harbor_pipeline/factory/run.sh <repo> gate <task_id>` (from `F:\GITHUB\DataOrigin_SWE`). Report any check that failed or warned.
- Use the existing image `factory-<task_id>` (build it from environment/ if it's missing). Use unique container names and remove your containers when done.

## 5. Report back
- New tests: name, F2P or P2P, what it checks, the PP-xx it targets, and why it follows from the instruction or a contract.
- Shortcut patches: a 1-line description each, the result (reward), and the test that catches it.
- Any change to solution.patch or instruction.md, with the reason.
- Validation results: nop, oracle ×3, flakiness ×5, gate.
- Anything you couldn't do, stated plainly.

Don't edit other tasks, the factory code, config or prompts, or intel.md (the operator records lessons). Don't run the Sol eval.
