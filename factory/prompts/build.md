You are M1, the task author. Build and package the task below as a Harbor task folder, then validate it. An independent gate re-checks everything you report, and R1 reviews the package next, so report facts only.

## Final proposal
```json
{{PROPOSAL}}
```

## Workspace
- Your repository working copy, at the base commit `{{BASE_COMMIT}}`: `{{WORKTREE}}`. Make the source fix and the hidden tests here, then generate the patches from it.
- Task folder to create: `{{TASK_DIR}}`. Start from the skeleton in `{{TEMPLATE_DIR}}`.
- Two finished tasks from this repo to copy patterns from (Dockerfile, test.sh, task.toml): `{{EXAMPLE_TASKS}}`
- Lessons log, with the rules that cost us time before: `{{INTEL}}`. Read the "Building & validating" and network sections before you start.
- Local validator: `{{VALIDATE_SCRIPT}}` (usage: `bash <script> <task_dir> {{IMAGE_TAG}}`). It builds the image, then runs nop (must be 0) and oracle (must be 1).

## Environment facts (Windows host)
- Your Bash tool is Git Bash on Windows. Docker works. Language toolchains (Go, Node/pnpm) and Python are NOT installed on the host: run every build/test command inside a container (the task image, or `{{DOCKER_BASE_IMAGE}}` with the worktree mounted). `MSYS_NO_PATHCONV=1` is already set, so give docker Windows-style host paths (`cygpath -m <path>` or `F:/...`).
- Only these commands are permitted (anything else is denied automatically, so don't use it): docker, git, bash <script>, cygpath, ls, cat, head, tail, grep, rg, sed -n, find, wc, diff, mkdir, cp, cd, echo, test, sha256sum, plus the Read/Write/Edit tools. Put multi-step container work in one `docker run ... bash -c '...'` call.
- Write source and test files with the Write/Edit tools, not shell heredocs (heredocs mangled `\\` before).
- Never use `run_in_background` or Monitor. Run every command, including long `docker build`/test runs, in the foreground with a long `timeout` (up to 600000 ms; split longer work into steps). This is a headless session: a background notification can end it before you validate. If a command is moved to the background anyway (it outlived the timeout), keep working: poll for its result in the foreground (read its output file, `docker image inspect <tag>`) until it finishes. Never write your final report while a build or test is still running.

## Required task layout and rules
- `instruction.md`: issue-style, follows the proposal's `instruction_outline`. Write it the way a developer talks to their coding agent: short (about 100-180 words), behavior-focused, symptoms plus one or two concrete repros and the expected behavior. No spec tables, no interface-definition blocks, no enumerated edge cases or test cases. Describe symptoms in user/API terms. Never name files, functions, packages or internal subsystem terms. The agent must discover where and how to implement the change. Keep a one-line behavioral clause only where a hidden test needs it for a single interpretation. Don't tell the solver to make one API or path "agree with" or "match" another that already works (AP-11): that hands it a differential-test recipe. State the wrong result the user sees and what they expected instead.
- `solution/solution.patch`: source changes only. `tests/test.patch`: hidden tests only, as NEW `*_test` files (don't edit existing test files; avoid type/func names that collide with the package's existing test files). Generate both with `git add -N <new files>` then `git diff -- <paths>`. They must be LF and apply cleanly with `git apply` at the base commit.
- Hidden tests must not reference any symbol that only exists in your fix (a different correct fix must compile and pass). They may use existing exported APIs and package-level vars as seams.
- Existing test files: never modify them. If one pins base internals that a valid fix may change (and the proposal says so), the test patch may DELETE it. Fold any behavior it still covers into your new spec.
- `tests/test.sh`: write the reward to `/logs/verifier/reward.txt` on every path. Run the FAIL_TO_PASS tests, then the PASS_TO_PASS guards and the named existing test files (an explicit list, never a whole package that contains deleted or implementation-pinned specs), then a compile/type check of the code that depends on the change where the language has one. Reward is 1 only if all of them pass. Use the retention task's test.sh as the shape to follow.
- `environment/Dockerfile`: base `{{DOCKER_BASE_IMAGE}}`; `git init` + `git fetch --depth 1 origin <base>` + `git checkout FETCH_HEAD`, then `git remote remove origin` and `rm -f .git/FETCH_HEAD`. Install dependencies and warm caches at build time so that the agent and verifier phases work fully offline.
- Optional `environment/base.patch`: use it only when the proposal requires changing the base code the solver sees (e.g. neutralizing comments that give away the defect). It may only remove hints; it must not change behavior. In the Dockerfile: COPY it, `git apply` it, delete it, then fold the result into ONE fresh commit (`rm -rf .git && git init -q && git add -A && git commit -qm base`) so no reflog or history shows the original. Then generate solution.patch and test.patch against the patched base (in your worktree, apply base.patch and commit it first).

### Repository-specific rules
{{BUILD_RULES}}
- `task.toml`: name `dataorigin/{{TASK_ID}}`, metadata filled in (repo, base commit, category = `bugfix` or `feature_request` matching the proposal's title prefix, language, difficulty "hard", task_author_model "claude-opus-5-5"), `[environment] network_mode = "allowlist"` with `allowed_hosts = {{ALLOWED_HOSTS}}`.
- `solution/solve.sh`: applies `/solution/solution.patch` in `/app` (keep the template's).

## Validate before you finish
1. `bash {{VALIDATE_SCRIPT}} {{TASK_DIR}} {{IMAGE_TAG}}` → nop 0, oracle 1.
2. On the base image with only test.patch applied, run each FAIL_TO_PASS test by name and confirm it FAILS on an assertion (not a compile, import or type error), and confirm every PASS_TO_PASS guard PASSES.
3. Run the oracle once more with `--network none` to prove the tests are hermetic.
Fix whatever fails and repeat. If something can't be fixed, report it in `open_problems`. Do not hide it.

Return JSON matching the provided schema (paths relative to the task folder where applicable).
