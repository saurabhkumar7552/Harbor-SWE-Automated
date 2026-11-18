# Authoring tasks with Claude Opus 5.5

Roles in this pipeline:

| Role | Who | Where |
|---|---|---|
| Task author | Claude Opus 5.5 | Claude (this project), writes the task folder |
| Task validator | Harbor `oracle` agent | your machine, Docker |
| Solver under test | GPT-6.1 Sol via Codex CLI (ChatGPT login) | Harbor `codex` agent, inside each task container |

```
Opus 5.5 ──writes──► tasks/<id>/ ──oracle run──► must pass 100%
                                   └─nop run────► must FAIL (tests really test something)
                                   └─codex + gpt-6.1-sol ×3 ──► report.md
                                                                   │
                         Opus 5.5 reviews failed trajectories ◄────┘
                         (task bug? fix it. legit failure? keep it.)
```

## 1. Ask Opus to write a task

Copy `task_template/` to `tasks/<task-id>/` and give Opus a prompt like this:

> Repo: `<owner/repo>` at commit `<sha>`. Source PR/issue: `<link or pasted diff>`.
> Create a Harbor task in `tasks/<task-id>/` from `task_template/`:
> - `instruction.md`: written like a GitHub issue. Symptoms and expected behavior, no file names, no root cause, no hints about the tests.
> - `environment/Dockerfile`: clone at the base commit, warm the build cache.
> - `solution/solution.patch`: the source-only fix. `tests/test.patch`: the hidden tests only.
> - `tests/test.sh`: FAIL_TO_PASS and PASS_TO_PASS lists; reward 1 only if both pass.
> - Make it hard: the fix spans multiple files/layers, the cause is away from the symptom,
>   and the hidden tests include edge cases that a shortcut patch would miss.
> - Fill `[metadata]` in `task.toml` (repo, base commit, category, language).

## 2. Validate the task before running GPT-6.1 Sol

```bash
python run_eval.py tasks/ -a oracle -k 1 --run-name oracle-check   # every task must be P
python run_eval.py tasks/ -a nop    -k 1 --run-name nop-check      # every task must be F
```

A task that the oracle fails has a broken grader or environment. A task that `nop` (does nothing) passes has tests that check nothing.

## 3. Hard-task checklist

- [ ] One correct interpretation of `instruction.md`. A strong engineer could solve it without asking questions.
- [ ] The hidden tests check behavior, not one specific implementation. Any valid alternative fix passes.
- [ ] FAIL_TO_PASS tests fail on the base commit; PASS_TO_PASS tests pass on it.
- [ ] Oracle passes 3/3 runs (deterministic, no flaky timing or network dependence in tests).
- [ ] The fix needs changes in several places, or the root cause is away from where the symptom shows.
- [ ] At least one edge case that a symptom-only patch would fail.
- [ ] No answer leakage: no solution in git history after the base commit, no hints in comments, no `solution/` files inside the image.

## 4. After the GPT-6.1 Sol run

For every task in `unsolved` / `medium`, open the failed trial folder from the report and decide:

- **Legit failure** (wrong root cause, missed edge case, incomplete multi-file change): keep it. This is a good hard task.
- **Task bug** (ambiguous instruction, test demands one specific implementation, environment broke): fix the task and re-run.
- **Error (`E`)** (timeouts, Codex auth/rate limit, Docker): an infra problem, not difficulty. Re-run it.
