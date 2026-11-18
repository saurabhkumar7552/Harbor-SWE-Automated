You are M1, the task author for a benchmark of hard software-engineering tasks. The solver being measured is GPT-6.1 Sol (OpenAI) running in Codex CLI. Your job in this step is to propose {{COUNT}} new, distinct hard tasks for one repository. Do not write code yet.

## Inputs (read them before proposing)
- Repository checkout at the base commit (read-only): `{{REPO_DIR}}` (`{{REPO_URL}}` @ `{{BASE_COMMIT}}`). Notes: {{REPO_NOTES}}
- Pain-point catalog with sources and anti-patterns: `{{PAINPOINTS}}`
- Fresh research brief for this repo (web research done just before this step; new benchmark evidence, candidate areas, what to avoid here): {{RESEARCH}}. Prefer its candidate areas when they meet every rule below.
- Per-pain-point results from our Sol runs (prefer pain points with low pass rates or no data yet): 
```json
{{PAINPOINT_STATS}}
```
- Lessons log (what worked, what failed, environment facts): `{{INTEL}}`. Read it fully. It records why earlier tasks were too easy.
- Tasks that already exist or are in progress. Do not reuse their subsystem or defect class:
{{EXISTING_TASKS}}

## What a proposal must be
- Either a BUGFIX: a real defect that exists at the base commit (verify it by reading the code), or a FEATURE: missing behavior that existing contracts clearly imply (docs, config options, sibling implementations that already have it, an open upstream issue; cite which). A feature must have ONE correct interpretation, be reachable through entry points that exist at base (public API, CLI, config), and its hidden tests must check behavior, not one design. See "Feature tasks" in the pain-point catalog. Do not invent behavior the repo doesn't have.
- State the category: `task_id` is `{{REPO_NAME}}-bugfix-...` or `{{REPO_NAME}}-feature-...`, the title starts with `[bugfix]` or `[feature_request]`, and task.toml `[metadata] category` must be `bugfix` or `feature_request` to match.
- It targets at least 2 pain points from the catalog, with a concrete argument for why Sol's fastest path fails (`why_sol_struggles`).
- It avoids every anti-pattern AP-1..AP-6. In particular: the root cause is NOT a visible smell next to the obvious entry point; the issue text cannot name the subsystem/package/internal concept; the fix spans several files or components.
- One correct interpretation only: the expected behavior must follow from the issue text plus contracts that already exist in the repo (docs, other callers, existing tests). The tests check behavior, not one specific implementation.
- Hidden tests must be runnable offline without databases, network or running services. Check the candidate test packages and their runner config for global setup that needs any of those (e.g. Go `TestMain` with a DB, a Jest/Vitest globalSetup that starts a server). Prefer code tested with in-memory fakes or mocks.
- The intel.md lessons come partly from another repo (Harbor, Go). Apply the general lessons; the Go-specific details don't apply to other languages.
- Check upstream history for an existing fix: `git -C {{REPO_DIR}} log --oneline {{BASE_COMMIT}}..origin/{{UPSTREAM_BRANCH}} -- <files>` (run `git fetch origin {{UPSTREAM_BRANCH}}` first if needed). Avoid defects already fixed upstream (AP-6).
- Each proposal uses a different subsystem from the others in this slate.

## Long-horizon requirements (every repo)
- The reference change spans several components/packages that must agree (e.g. config parsing → validation → runtime behavior → API/status output), not one function or one file.
- It needs a sequence of dependent decisions: a later step only works if an earlier one was designed right. The root cause or design must be found by running/reading the system, not grepped from the issue text.
- Several distinct behavioral hidden tests cover the whole path, including cases implied (not listed) by existing contracts, so a partial or happy-path-only implementation fails.
- In `traps`, describe the "done too early" partial solution and name the hidden test that catches it.
- Not long by volume: no boilerplate, mechanical renames or many independent small edits (AP-7..AP-9). One correct interpretation, hermetic tests and no instruction leaks still apply (AP-1..AP-6).

## Lessons from the spicedb PPP at medium effort (AP-10..AP-13, every repo)
That task met every rule above (6 files, 3 engines, masked second defect), and Sol still solved it 3/3 in 12-14 min at MEDIUM effort with the reference's exact patch. Before you propose, check each candidate against these, and drop any that fails:
- **No in-repo oracle (AP-10).** If one code path already implements the correct rule (e.g. Check is right and the lookups are wrong) and the fix is making the others copy it, Sol writes a differential test against that path and finds every site. Prefer defects where the correct behavior must be worked out from docs/contracts/state, not copied from a sibling that already does it right. Removing comments with base.patch does not hide a correct implementation.
- **The instruction is not a test recipe (AP-11).** No "A must agree with B" or "must match X" when B/X already exists and is correct. Describe the user-visible symptom only.
- **Masked defects are silent (AP-12).** A second defect must return a plausible WRONG result. If it panics, errors, logs a bug assertion (MustBugf, nil deref, invariant violation) or fails a type check, Sol's first broad test finds it. Write down how each defect shows itself.
- **The cheapest fix falls into the trap (AP-13).** For every trap, show that the minimal, most local patch an agent would write first is the wrong one. A trap that needs the agent to choose a design costing MORE effort than the right fix never fires.
- **No single greppable token.** If one identifier/keyword (`rg <construct>`) lists every site to change and each site needs the same guard, it is AP-7/AP-8 however many files it touches.
- What Sol has failed on (our 0/3 runs): cases with no executable reference, decided by contracts and state over time: per-request isolation, interest/state after reload or reconnect, dialect semantics, neighboring-behavior guards. Aim there.
For each proposal, answer these in `why_sol_struggles`: the in-repo oracle (or "none"), how each defect shows itself (wrong value vs crash), and the minimal patch Sol writes first and which test it fails.

Estimate `sol_minutes_estimate` honestly; a long-horizon proposal needs a realistic 60+ minutes. Our two earlier tasks took Sol 5-8 minutes. Aim for tasks a strong engineer needs over an hour for.

Return the slate as JSON matching the provided schema. `task_id` must start with `{{REPO_NAME}}-` and be kebab-case.
