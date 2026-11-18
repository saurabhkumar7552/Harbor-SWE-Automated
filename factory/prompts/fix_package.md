You are M1. R1 reviewed your packaged task. This is your one and only fix round. Fix every blocker and major issue, and every minor one that is cheap. If an issue is factually wrong, explain it in `issues_not_addressed`.

- Task folder: `{{TASK_DIR}}`
- Your repository working copy (base commit, with your fix and tests): `{{WORKTREE}}`. Regenerate both patches from it after any change.
- R1 review:
```json
{{REVIEW}}
```
- Gate results that failed or warned:
```json
{{GATE_REPORT}}
```
- Rules and environment facts are the same as in the build step: `{{BUILD_PROMPT}}` (read it). Lessons log: `{{INTEL}}`.

Never use `run_in_background` or Monitor: run every command in the foreground with a long `timeout` (headless session; a background notification can end it before you validate). If a command is moved to the background anyway, poll for its result in the foreground until it finishes. Never write your final report while a build or test is still running.

When you are done, re-validate: `bash {{VALIDATE_SCRIPT}} {{TASK_DIR}} {{IMAGE_TAG}}` (nop 0, oracle 1). Then confirm every FAIL_TO_PASS test fails on base (not with a compile error) and every PASS_TO_PASS guard passes. If the Dockerfile changed, rebuild the image first (`docker rmi -f {{IMAGE_TAG}}` is fine for this per-task tag). Return JSON matching the provided schema.
