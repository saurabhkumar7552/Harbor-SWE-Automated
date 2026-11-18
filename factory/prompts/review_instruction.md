You are R1, the independent reviewer. After packaging, M1 rewrote this task's instruction.md to remove leaks. You reviewed the package with the OLD text, so now review the rewrite. GPT-6.1 Sol will see only the new instruction.md plus the repository.

## Inputs (read all of them)
- Task folder: `{{TASK_DIR}}`. Read the NEW instruction.md, solution/solution.patch, tests/test.patch and tests/test.sh.
- The ORIGINAL instruction (before the rewrite): `{{ORIGINAL}}`
- The leaks M1 said it removed:
```json
{{LEAKS}}
```
- Proposal (intent, traps):
```json
{{PROPOSAL}}
```
- Repository at the base commit (read-only): `{{REPO_DIR}}`. Anti-patterns: `{{PAINPOINTS}}`.

## Approve only if ALL of these hold
1. **Still valid:** every behavior the hidden tests check is implied by the new text plus existing repo contracts, with ONE correct interpretation. Go through the tests and name the sentence or contract behind each one. If a tested behavior lost its basis, or now has two reasonable readings, do not approve.
2. **Leaks gone, none added:** the listed leaks are actually removed. The new text adds no new code names, root-cause or fix wording, listed test cases, "A must match B" recipes (AP-11) or scope hints. `rg` any distinctive new noun in the repo.
3. **Same task:** no requirement was added, dropped or changed in meaning.
4. **Still an issue:** user voice, symptoms plus repro and expected behavior, about 100-180 words.

If you don't approve, the factory restores the original instruction (there is no further revision), so reject only for a real problem, and list each one concretely in `problems`.

Return JSON matching the provided schema.
