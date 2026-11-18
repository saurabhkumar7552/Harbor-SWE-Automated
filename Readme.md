# Harbor eval pipeline

Give it a folder of Harbor tasks. It runs the agent up to 3 times per task and writes one combined report.

```
tasks/                 <- what you provide
  task-a/  task.toml  instruction.md  environment/  tests/  solution/
  task-b/  ...
        │
        ▼
run_eval.py ──► harbor run (Docker sandbox per trial) ──► jobs/<run>/<task>__<id>/result.json
        │                                                         verifier/stdout.txt
        ▼
jobs/<run>-report/report.md  report.json  report.csv
```

## Setup

```bash
uv tool install harbor            # or: pip install harbor
export ANTHROPIC_API_KEY=...      # whatever the agent/model needs
harbor run --help                 # confirm flags match your installed version
```

Docker must be running.

## Run

```bash
# Check the tasks themselves first: the oracle runs solution/solve.sh, so every task should pass
python run_eval.py tasks/ -a oracle -k 1 --run-name sanity

# 3 independent attempts per task (default mode) gives pass@1, pass@3 and a difficulty bucket
python run_eval.py tasks/ -a claude-code -m anthropic/claude-opus-4-1 --run-name opus-v1

# Retry only the tasks that failed, up to 3 tries (cheaper)
python run_eval.py tasks/ -a claude-code -m anthropic/claude-opus-4-1 --mode until-pass --run-name opus-retry

# Pass extra flags straight to harbor after --
python run_eval.py tasks/ -a codex -m openai/gpt-5 -- --env docker

# Rebuild the report from an existing run without re-running anything
python run_eval.py --report-only -o jobs --run-name opus-v1

# Print the harbor commands without running them
python run_eval.py tasks/ -a claude-code --dry-run
```

## Testing GPT-6.1 Sol through Codex (no API key)

Harbor's `codex` agent can use your ChatGPT/Codex login instead of `OPENAI_API_KEY`: it copies
your `auth.json` into each task container, runs `codex exec` there, then deletes it.

**One-time setup.** Run everything in WSL2 (Ubuntu) with Docker Desktop's WSL integration on:

```bash
npm i -g @openai/codex          # Codex CLI
codex login                     # sign in with your ChatGPT account (Plus/Pro/Business...)
#   no browser in WSL?  ->  codex login --device-auth
codex exec -m gpt-6.1-sol "say hi"   # confirm your account has GPT-6.1 Sol
uv tool install harbor
```

If you're already signed in to Codex on Windows, you can reuse that file:
`--codex-auth-json /mnt/c/Users/<you>/.codex/auth.json`.

**Run:**

```bash
# 1. Validate the Opus-authored tasks (no model needed)
python run_eval.py tasks/ -a oracle -k 1 --run-name oracle-check

# 2. GPT-6.1 Sol, 3 independent attempts per task
python run_eval.py tasks/ \
  -a codex -m openai/gpt-6.1-sol --reasoning-effort high \
  --codex-subscription --task-author claude-opus-5-5 \
  -k 3 -n 2 --run-name sol-v1

# Or retry only what failed, up to 3 tries
python run_eval.py tasks/ -a codex -m openai/gpt-6.1-sol --codex-subscription \
  --mode until-pass -k 3 -n 2 --run-name sol-retry
```

`--codex-subscription` sets Harbor's `CODEX_FORCE_AUTH_JSON=1` (or `CODEX_AUTH_JSON_PATH` with
`--codex-auth-json`) and removes any `OPENAI_API_KEY` from the environment, so the API is never billed.

Notes for subscription runs:
- Keep `-n` at 1–2. All trials share one ChatGPT account's rate limit and one login token.
  If you hit the limit, the trials show up as `E` in the report. Re-run them with `--mode until-pass`.
- Tasks need `network_mode = "public"` because Codex inside the container calls OpenAI.
- Reasoning effort for GPT-6.1 Sol: `low`, `medium`, `high`, `xhigh` or `max` (it rejects `none`/`minimal`).
- If you get "model is not supported when using Codex with a ChatGPT account", your plan
  doesn't have GPT-6.1 Sol yet.
- Treat `auth.json` like a password. Don't commit it or share it.

See `AUTHORING.md` for how Opus 5.5 writes the tasks, and `task_template/` for the task skeleton.

## Options

| Flag | Default | Meaning |
|---|---|---|
| `-k` | 3 | max attempts per task |
| `--mode` | independent | `independent` = K fresh attempts each; `until-pass` = re-run only failed tasks |
| `-n` | 4 | concurrent trials (containers) |
| `-r` | 1 | Harbor retries on **infra exceptions** (Docker errors etc.), which doesn't count as an attempt |
| `--threshold` | 1.0 | reward needed to count as a pass (lower it for partial-credit graders) |
| `-o` | jobs | Harbor jobs dir; the report goes in `jobs/<run>-report/` |
| `--reasoning-effort` | (agent default) | codex reasoning effort, passed as `--ak reasoning_effort=...` |
| `--codex-subscription` | off | use your ChatGPT login (`~/.codex/auth.json`), not an API key |
| `--codex-auth-json` | | explicit auth.json path (implies `--codex-subscription`) |
| `--task-author` | | recorded in the report, e.g. `claude-opus-5-5` |

## Reading the report

- **Outcomes**: one letter per attempt: `P` pass, `F` fail (verifier scored it), `E` error (crashed or timed out before scoring).
- **Bucket** (independent mode): `unsolved` 0/3, `medium` 1-2/3, `easy` 3/3. For hard-task benchmarks you want mostly `unsolved`/`medium`. **Read the failures**: an unsolved task is only good if the agent failed for a legitimate reason, not because of an unclear prompt or a broken test.
- **Error trials**: many `E` usually means an environment problem (build, timeout, network), not difficulty.
- **Failure details**: the last lines of `verifier/stdout.txt` for each failed attempt, plus the trial folder to open the full agent trajectory. `harbor view jobs` also gives a web UI.

## Notes

- Harbor's `-k/--n-attempts` runs independent trials. `-r/--max-retries` re-runs only on exceptions, never on a failing score, so "retry if the agent failed" is handled by `--mode until-pass` in this script.
- Put tasks as direct children of the tasks folder. Harbor reads the folder as a dataset.
- Result fields are read defensively (`verifier_result.rewards.reward`, `exception_info`, `agent_result.n_output_tokens`). If your Harbor version names them differently, adjust `load_trials()`.
