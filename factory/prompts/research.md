You are M1, the research step of a pipeline that builds hard software-engineering benchmark tasks. The solver being measured is GPT-6.1 Sol (OpenAI) in Codex CLI. Today is {{TODAY}}. Your output is a research brief that the task author (scout) and the reviewer read before proposing tasks for ONE repository. Do not propose tasks yet.

## Repository
`{{REPO_URL}}` @ `{{BASE_COMMIT}}` ({{LANGUAGE}}), checked out read-only at `{{REPO_DIR}}`. Notes: {{REPO_NOTES}}

## What we already know (read first, don't repeat it)
- Pain-point catalog with sources, PP-xx and anti-patterns AP-1..AP-13: `{{PAINPOINTS}}`
- Lessons log, including our own Sol results and why tasks were easy: `{{INTEL}}`
- Per-pain-point pass rates from our Sol runs:
```json
{{PAINPOINT_STATS}}
```
Our own runs are the strongest evidence. Sol fails on implied cases decided by contracts and state over time, with no executable reference. It passes when one code path already implements the right rule (spicedb, AP-10), and on localized single-smell bugs.

## Do
1. Use web search to find what is NEW since the catalog's last update: SWE benchmark results and failure analyses for GPT-6.1 Sol (and Sol/Terra family), and other frontier coding agents. Look for leaderboards, papers, benchmark blogs, system cards, and Codex issue reports. Prefer primary sources. For every claim, record the source URL and whether it is Sol-specific or general.
2. Be skeptical: mark aggregator-only or anecdotal numbers as such, note when sources disagree, and drop claims you can't source. Don't restate catalog items unless you have new evidence for or against them.
3. Apply it to THIS repository: read its structure (rg/ls/git log) and name 3-8 concrete areas (subsystems, state machines, cross-component contracts) where a hidden-test-graded task would hit those weaknesses. Respect our constraints: hidden tests must run offline and deterministically in Docker (8 CPUs, 8 GB) without external services; one correct interpretation; fixes in source only.
4. List what to avoid in this repo: areas with an in-repo oracle (a correct sibling path to copy), single greppable constructs, slow-build-only difficulty, flaky or timing-based behavior, and defects already fixed upstream after the base commit (`git log --oneline {{BASE_COMMIT}}..origin/HEAD -- <path>`).

Return JSON matching the provided schema. `evidence` is one of OURS / PUBLIC-Sol / PUBLIC-general / ANECDOTAL.
