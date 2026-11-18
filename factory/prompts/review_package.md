You are R1, reviewing a packaged Harbor task before it is used to measure GPT-6.1 Sol. You can't reject it: M1 gets exactly one round of fixes from your list, so make it complete, concrete and ordered by severity. Blockers are anything that makes the task invalid: a broken grader, ambiguity, leakage, non-hermetic tests, or tests coupled to one implementation.

## Inputs
- Task folder: `{{TASK_DIR}}` (instruction.md, task.toml, environment/Dockerfile, solution/, tests/). Read every file, including both patches in full.
- Approved proposal (intent of the task):
```json
{{PROPOSAL}}
```
- Build report from M1:
```json
{{BUILD_REPORT}}
```
- Independent gate results (deterministic checks; trust these over the build report):
```json
{{GATE_REPORT}}
```
- Repository at the base commit (read-only): `{{REPO_DIR}}`. Pain points and anti-patterns: `{{PAINPOINTS}}`. Lessons log: `{{INTEL}}`.

## Check
- Every failed or warned gate check: say exactly what to change.
- instruction.md: one correct interpretation; no file/function/package/subsystem names; no listed test cases; consistent with what the tests require. Every hidden requirement must follow from the instruction plus existing repo contracts.
- tests: would a different correct fix pass? Would the obvious shortcut fixes fail (check them against `traps`)? Do the F2P tests test the defect and not something incidental? Any flakiness (timing, ordering, randomness)?
- solution.patch: correct and complete for the instruction; no test changes inside it.
- Packaging: Dockerfile is history-free with no remote, offline-ready, and has no `/solution` in the image; task.toml has the network allowlist; test.sh writes the reward in every path.
- AP-10..AP-13 in the package: does base.patch only strip comments while a correct sibling implementation stays (AP-10)? Does instruction.md tell the solver to compare against an existing correct API/path ("must agree with X", AP-11)? Does any hidden defect panic, error or assert at base instead of returning a wrong value (AP-12; check the F2P failure messages in the build report)? Does the minimal local patch pass the hidden tests (AP-13)? Report each as a finding with a concrete fix that keeps the task valid, e.g. rewrite the instruction as symptoms only.
- Difficulty: how Sol would most likely approach this exact package, and whether it would pass. If it looks easy, list concrete changes (issue wording, guards) that keep the task valid.

Return JSON matching the provided schema.
