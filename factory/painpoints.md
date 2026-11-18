# GPT-6.1 Sol pain-point catalog

The task factory uses this file to aim tasks at what GPT-6.1 Sol actually fails at.
- The scout must cite pain-point IDs for every proposal.
- The reviewer (R1) hardens proposals against these entries.
- `learn` appends evidence from our own Sol runs. `painpoint_stats.json` (generated) holds per-ID pass rates; prefer IDs whose tasks Sol still solves.

**Evidence levels:** [PUBLIC] = published benchmark/paper result (not always Sol-specific); [OURS] = our own Sol trials.
No public source gives a Sol-specific failure taxonomy (checked 2026-11-12), so treat this file as a working hypothesis that our own runs confirm or refute.

## Where Sol is relatively weak (public scores)

- FrontierCode 2.0 (Cognition, 132 private tasks): informal/underspecified issues, graded on "would a maintainer merge it". Reference fixes touch 67% more files and 89% more lines than v1.1. Sol scores 25.6 (low) / 29.6 (medium) / 34.8 (high) / 39.0 (max) / 32.3 (extra-high); the leader is ~45.5. [PUBLIC]
- APEX-SWE (Mercor): integration across heterogeneous systems and **observability tasks: debugging production failures with incomplete information**. Sol 46.9, rank 23/72. [PUBLIC]
- By contrast Sol is strong on DeepSWE (75.2, rank 7/115), IOI-style algorithmic work (96.9) and code migration (65.1). Don't build tasks that are mainly algorithmic puzzles or mechanical migrations. [PUBLIC]

### Update 2026-11-14 (third-party figures; harnesses differ, numbers don't all reconcile)
- Still no SWE-bench Verified / Pro score for GPT-6.1 Sol from OpenAI or any leaderboard. [PUBLIC, Sol] [layer3labs guide](https://www.layer3labs.io/guides/gpt-6-1-sol-benchmarks)
- DeepSWE v1.1: 75.2% at high effort (OpenAI launch chart), 71.9% (BenchLM), 72.3% at max tied with Opus 5.5 at the top (Mercor APEX board). → Sol is STRONG on DeepSWE-style repo tasks. [PUBLIC, Sol, sources disagree] [OpenAI](https://openai.com/blog/introducing-gpt-6-1-sol), [BenchLM](https://benchlm.ai/compare/gpt-6-1-sol-vs-gpt-6-sol), [Mercor](https://www.mercor.com/apex/oss-benchmarks/oss-deep-swe-leaderboard/sample-task/)
- Terminal-Bench 4.0: 56.1% (Artificial Analysis) vs ~62% in another chart, behind Kimi K3.1 Pro and Opus 5.5. Terminal-Bench Science 0.1 at max effort: 57.0% vs GPT-6 Astra 68.1% and Opus 5.5 63.3%. FrontierCode: second behind Opus 5.5 (no number found). SciCode named a weak spot. [PUBLIC, Sol, aggregator figures that conflict] [Vellum](https://vellum.ai/blog/gpt-6-1-sol-benchmarks-explained), [llm-stats](https://llm-stats.com/blog/research/gpt-6-1-sol-launch)
- Artificial Analysis, eval by eval at max effort: Sol is better than GPT-6 Astra on 2 evals and worse on 6 (index 51.8 vs 52.7). BenchLM public coding lane: Astra 74.2 vs Sol 67 (intervals overlap). [PUBLIC, Sol, secondary] [orcarouter summary](https://www.orcarouter.ai/blog/gpt-6-1-sol-independent-benchmark), [BenchLM](https://benchlm.ai/compare/gpt-6-1-sol-vs-gpt-6-astra)
- SWE-Marathon: one aggregator lists 68/160 passing trials (~42%) for Sol; rank unclear. [PUBLIC, Sol, aggregator only, unverified] [benchmarklist](https://benchmarklist.com/models/openai-gpt-6.1-sol/)
- System card (secondary): coding-deception misrepresentation 1.50% (GPT-6 Sol 1.30%, Astra 0.51%); "unwanted persistence after a warning blocks an action" in 23.5% of rollouts vs Astra 17.4%. 10-30% more output tokens than GPT-6 Sol. [PUBLIC, Sol, secondary] [DataCamp](https://www.datacamp.com/blog/gpt-6-1-sol), [llm-stats](https://llm-stats.com/blog/research/gpt-6-1-sol-launch)
- OpenAI calls the abandon-at-first-obstacle behaviour "model laziness" and targeted it in this release; a developer blog reports a reproducible, EARLY AGENTS.md rule-violation pattern ("acknowledge, apologise, re-violate"). [PUBLIC, Sol, secondary/anecdotal] [letsdatascience](https://letsdatascience.com/blog/openai-killed-its-flagship-shipped-the-cheap-one-instead), [Codex blog](https://codex.danielvaughan.com/2026/10/26/gpt61-sol-agents-md-compliance-regression-acknowledge-apologise-re-violate/)
- Reading: Sol's relative weakness is scientific/terminal/long-horizon and multi-eval breadth, not single-repo bug fixing (DeepSWE, our two PPP runs). No Sol trajectory study on concurrency or server code exists.

### Update 2026-11-15 (newer scores; still third-party, still no OpenAI SWE-bench Verified/Pro number)
- Terminal-Bench 4.1 (66 tasks): Sol 60.9% ±3 at max effort in Codex, rank 4, behind Opus 5.5 65.8%, Fable 5.2 65.8%, Sonnet 5.5 63.9%; GPT-6 Astra 60.3%. Intervals overlap with ranks 3-5. Supersedes the 4.0 figures above, which mirrors still report as 58.2 / 56.1 / 55.05 (don't reconcile; harness or rerun differences). [PUBLIC, Sol] [Snorkel board](https://snorkel.ai/leaderboard/terminal-bench/), [BenchLM](https://benchlm.ai/benchmarks/terminal-bench)
- Terminal-Bench-Science (70 tasks, one shared Mini-SWE-agent harness): Sol 52.86%, rank 3, behind GPT-6 Astra 62.86% and Fable 5.2 55.71%. Lower than the 57.0% max-effort figure above; Vals says its numbers are not comparable to the official 0.1 board. → The 10-point gap to Astra holds on both. [PUBLIC, Sol] [Vals](https://www.vals.ai/benchmarks/terminal-bench-science)
- FrontierCode, by version (don't mix them): 2.0 = 39.0% at max, rank 4, leader Opus 5.5 45.5% (matches the figures above; rank is from secondary reports); 1.1 on Artificial Analysis = 49% at max vs Opus 5.5 52%; 1.1 Extended (Cognition) = 60.4% medium / 58.1% low vs Opus 5.5 65.3%. → Sol trails the leader by 3-6.5 points on every mergeability board. [PUBLIC, Sol, secondary] [SmartScope](https://smartscope.blog/en/blog/frontiercode-2-0-mergeability-benchmark-leaderboard-scores-ai-2026/), [Magica](https://magica.com/news/frontiercode-1-1-leaderboard-maintainer-mergeability), [AlphaSignal](https://alphasignal.ai/news/cognition-brings-gpt-6-1-sol-to-devin-slashing-coding-costs-by-57), [Artificial Analysis](https://artificialanalysis.ai/articles/frontiercode)
- DeepSWE v1.1: Sol loses more than 3 points going from high to max effort (75.2 high vs 71.4 max in Vellum's table). → More reasoning does not help Sol on repo tasks; our eval at high effort is its best setting. [PUBLIC, Sol, secondary] [Vellum](https://www.vellum.ai/md/blog/gpt-6-1-sol-benchmarks-explained)
- DOES NOT RECONCILE: one publisher's own "RFE LLM Benchmark" table lists "SWE-Bench Pro" 96.1% for Sol and 95.8% for Sonnet 5.5, with no citation; other sources say OpenAI publishes no SWE-bench Pro score for Sol, and a third-party page has the predecessor GPT-5.6 Sol at 64.6% on the commercial set. Do not use the 96.1% figure. [PUBLIC, Sol, unverified] [FullStack](https://www.fullstack.com/blog/claude-sonnet-5-5-vs-gpt-6-1-sol-best-mid-price-model), [morphllm](https://morphllm.com/swe-bench-pro)
- APEX-SWE: could not re-confirm the "46.9, rank 23/72" figure above on 2026-11-15 (search found no Sol row; leader figures also conflict between Mercor 65.5% and BenchLM 58.8%). Treat it as unverified until read off the live board. SWE-EVO and SWE-Marathon: no GPT-6.1 Sol entry found. [PUBLIC] [Mercor board](https://www.mercor.com/apex/apex-swe-leaderboard/)
- SWE-Marathon, Sol family only: GPT-5.5 under Codex has the highest premature-stop share (15%) and a 24% reward-hacking share among the configurations; the v1.1 board has GPT-5.6 Sol at ~39% (leader Kimi K3 42.0%, nobody above 50%). Not GPT-6.1 Sol. [PUBLIC, Sol-family, secondary summaries] [arXiv 2606.07682](https://arxiv.org/abs/2606.07682), [Codex blog](https://codex.danielvaughan.com/2026/07/30/swe-marathon-ultra-long-horizon-benchmark-codex-cli-token-budget-self-verification-scaffold-efficiency/)

## Our own Sol results (strongest evidence; extend with every run)

- `harbor-replication-brace-expansion`: PPP at high effort, ~8 min, ~10k output tokens. The instruction spelled out every rule; one pure function. [OURS]
- `harbor-retention-immutable-bypass`: PPP at medium effort, ~5 min, ~7k output tokens. Symptom-only instruction, but it named the subsystems. Sol's first two commands were `rg` for those names; all three bugs were visible smells in one 40-line function. [OURS]
- Conclusion so far: Sol is fast and reliable at **localized** defects when the issue names the subsystem, even when they're spread across 2 files. Single-function or single-smell bugs are EASY regardless of how the issue is written.

## Pain points (target these)

### PP-01 Underspecified issue, design judgment required
Issue in user terms, with no spec of the internal contract. The correct fix needs a decision a maintainer would make (where the invariant belongs, which layer owns it). The hidden tests check the behavior implied by the repo's own existing contracts (docs, other callers, existing tests), not by the issue text.
Source: FrontierCode 2.0. Guard: there must still be ONE correct interpretation, derivable from the repo. The reviewer must check this.

### PP-02 Debugging from indirect evidence (observability)
The issue gives only observed behavior: a log excerpt, a metric, a wrong API response, an intermittent symptom. The faulty code is not named and is several calls away. Agents must form and test hypotheses instead of grepping a keyword.
Source: APEX-SWE observability tasks.

### PP-03 Cross-component contract mismatch (integration)
Two components that are each locally reasonable disagree about a contract (units, encoding, nullability, ordering, pagination cursor, retry/idempotency semantics, time zone, path normalization). Fixing either side alone breaks the other side's callers; the fix must pick the owner and adapt the others.
Source: APEX-SWE integration; FrontierCode multi-file references.

### PP-04 Edit quality after correct localization ("coherence collapse")
60-69% of capable-model failures reach and edit the right functions but produce an incorrect patch, often by overwriting a correct intermediate edit. Tasks where the obvious one-line fix is subtly wrong and the correct fix needs a careful multi-site edit punish this.
Source: "Coherence Collapse" (arXiv 2603.24631).

### PP-05 Multi-bug chains / masked second defect
Fixing the first defect exposes a second dependent one (the first bug was masking it). Agents stop after the first green signal. Performance drops up to 70% as chain length grows.
Source: ChainSWE (arXiv 2607.02606). Guard: both defects must be reachable from the single issue's symptoms.

### PP-06 Weak self-verification / premature termination
Agents declare success after the happy path passes. Tasks whose correctness depends on cases the agent must think to test (concurrency, retries, partial failure, pagination boundaries, large inputs, ordering) catch this.
Source: SWE-Marathon (arXiv 2606.07682): poor self-verification, premature termination, self-reported infeasibility.

### PP-07 Stateful / temporal behavior
Bugs that only show across calls or over time: caches and their invalidation, retries, idempotency, ordering of async events, resumable jobs, pagination across pages, TTLs. Single-call reasoning and single-call tests don't reveal them.
Source: derived from PP-06 + ChainSWE; consistent with our OURS evidence that local smells are easy.

### PP-08 Wide blast radius, consistent change
The fix is a contract change that must be propagated to every caller/implementation (interfaces with several implementations, adapters, serializers), and the hidden tests exercise more than one of them. Partial propagation fails.
Source: FrontierCode 2.0 (more files and lines per reference fix).
Added 2026-11-13: SWE-Bench Pro (reference fixes average 107.4 lines across 4.1 files) finds that frontier agents (GPT-5, Opus 4.1) fail mostly through *semantic* errors (35.9-51.7%) in large multi-file edits, not through localization. [PUBLIC, general] [arXiv 2509.16941](https://arxiv.org/abs/2509.16941)

### PP-09 Interface guessing instead of reading (added 2026-11-13)
In feature work, agents call helpers, attributes and signatures they assume exist instead of reading the real ones. FeatureBench's failure analysis (secondary summaries) names NameError as the most common failure (cross-file dependency resolution), then TypeError/AttributeError from hallucinated interfaces. Visible unit tests raise success a lot, so the hidden tests must not be inferable from the instruction. [PUBLIC, general] [FeatureBench arXiv 2602.10975](https://arxiv.org/abs/2602.10975)
Use: features whose correct implementation has to go through an existing internal contract (a registry, a visitor/dispatch table, a base class's hooks) that the agent must read to use correctly.

### PP-10 Regressions in adjacent behavior / over-implementation (added 2026-11-13)
Patches that fix the issue often break other things. The TDAD paper reports about 6.5 broken tests per generated patch on average, on SWE-bench Verified. SWE-CI (secondary reports) says most models break previously passing tests on about 75% of long-maintenance tasks. FeatBench reports "regressive implementation" and "aggressive implementation" (extending functionality beyond the request) as main feature-task failures. [PUBLIC, general] [TDAD arXiv 2603.17973](https://arxiv.org/abs/2603.17973), [FeatBench arXiv 2509.22237](https://arxiv.org/abs/2509.22237)
Use: PASS_TO_PASS guards on neighboring behavior that the obvious broad change would alter (other dialects, other formats, default options).

### PP-11 Plausible patch, wrong semantics on implied cases (added 2026-11-13)
Strengthening the tests rejected 19.78% of patches that had passed SWE-bench Verified's original tests (top-30 leaderboard agents). Agents satisfy the stated case and miss semantically implied ones. [PUBLIC, general] [SWE-ABS arXiv 2603.00520](https://arxiv.org/abs/2603.00520)
Use: hidden tests on cases implied by the repo's contracts (round-trip, other input forms, nulls/empties, other implementations) but not stated in the issue. Overlaps with PP-06; this is the stronger, measured version.

### PP-12 Early uncaught error in long trajectories (added 2026-11-13)
Long-horizon failure is driven mainly by one early mistake that goes uncaught and compounds, not by how often errors happen. [PUBLIC, general] [arXiv 2609.17930](https://arxiv.org/abs/2609.17930). Agent code also degrades as agents extend their own earlier code (erosion rises in 80% of trajectories; no agent solves a problem end-to-end). [PUBLIC, general] [SlopCodeBench arXiv 2603.24755](https://arxiv.org/abs/2603.24755)
Use: tasks where an early, plausible design decision (the wrong layer or representation) makes every later step look fine until a hidden test on an implied case fails. Supports PP-05.

### Sol-specific public signals (added 2026-11-13; weak, mostly secondary)
- OpenAI does not publish SWE-bench Verified or Pro scores for GPT-6.1 Sol (SonarSource writeup). On Terminal-Bench 4.0 (Artificial Analysis, secondary reports) Sol scores 56.1%, behind Opus 5.5 (59.6%) and Kimi K3.1 Pro (67.2%). [PUBLIC, Sol] [SonarSource](https://www.sonarsource.com/blog/openai-gpt-6-1-sol-evaluation/), [The New Stack](https://thenewstack.io/openai-gpt-6-1-sol/)
- System card: higher coding-deception (misrepresentation) rate than GPT-6 Astra (1.50% vs 0.51%), and modest regressions vs GPT-5.6 Sol in synthetic agentic environments. → Don't trust Sol's self-report; tests must catch "claimed but not done". [PUBLIC, Sol] [GPT-6.1 Sol system card](https://cdn.openai.com/pdf/38e3efcf-545e-44cd-99ec-2b7eb395f4cc/oai_GPT_6_1_Sol.pdf), [DataCamp summary](https://www.datacamp.com/blog/gpt-6-1-sol)
- OpenAI's own maintenance blog: on a code-cleanup task Sol found 92% as many issues as GPT-6 Astra and missed some that Astra caught. [PUBLIC, Sol] [OpenAI dev blog](https://developers.openai.com/blog/maintaining-software-with-the-gpt-6-family)
- Anecdotal, unverified: Sol ends turns early with a status report; a reported regression in following AGENTS.md instructions. [PUBLIC, Sol, anecdote] [blog](https://vincentschmalbach.com/something-wrong-at-openai), [Codex scorecard blog](https://codex.danielvaughan.com/2026/11/01/28-days-of-shipping-end-of-sprint-scorecard-openai-codex/)
- SonarSource: Sol writes about 39% more code than GPT-6 Sol on the same tasks, with 32% more code-smell findings in absolute terms. → Verbose, broad patches; consistent with PP-10. [PUBLIC, Sol]

## Anti-patterns (proven or likely EASY for Sol; reviewer must flag)

- **AP-1** The instruction names the subsystem, package, or internal concept (e.g. "retention", "immutability rule") that greps straight to the code. [OURS]
- **AP-2** The bug is a visible smell next to the obvious entry point: `return false` on error, a doubled parse, a lookup inside a loop. [OURS]
- **AP-3** The instruction lists the exact cases the tests check. [OURS]
- **AP-4** A single pure function, or one file. [OURS]
- **AP-5** Mainly algorithmic, or a mechanical migration (Sol is strong there). [PUBLIC]
- **AP-6** An upstream fix exists after the base commit (leak through network or training). Prefer bugs that are unfixed upstream. [OURS]

## Feature tasks: where agents fail (added 2026-11-13)

Feature benchmarks are far harder than bug-fix ones: FeatBench's best resolved rate is 29.94%; FeatureBench's best (Opus 4.5) is about 11%. [PUBLIC, general] Kinds of feature work to target:
- **F-1 Integration with several existing contracts.** The feature has to plug into a registry, options parsing, serialization *and* the consumer side. Incomplete implementation is a top FeatBench failure, and cross-file NameErrors top FeatureBench (PP-09).
- **F-2 Consistent behavior across all implementations.** The same capability must work in every sibling (all dialects/drivers/readers, sync and async paths, REST and GraphQL). Agents implement the one named in the issue (PP-08). Hidden tests exercise more than one sibling.
- **F-3 Symmetry/round-trip.** A new input form must also come out right on the output side (parse ↔ generate, read ↔ write, import ↔ export). The issue mentions one direction; the repo's round-trip tests imply the other (PP-11).
- **F-4 No over-reach.** Guards on neighboring behavior catch "aggressive implementation" (PP-10).
- Validity rules for feature tasks: the behavior must be clearly implied by existing contracts (docs, config options, other implementations, an open upstream issue) and have ONE correct interpretation. Hidden tests use only entry points that exist at base (public API, CLI, pipeline JSON), never new names the reference fix invents. A feature whose name or option the tests must call must be specified in the instruction exactly, so pick features reachable through existing entry points.

## Long-horizon tasks (added 2026-11-14)

New evidence only (PP-06/PP-12 already cover premature termination and early compounding errors). Checked 2026-11-14: no public long-horizon result exists for GPT-6.1 Sol.
- **PP-13 Release-scale, multi-step change.** SWE-EVO (48 tasks from release notes, ~21 files per task): GPT-5.2 drops from 72.80% on SWE-bench Verified to 22.92%; best model ~25%; strong models fail mostly on instruction following (missing parts of the requested change). [PUBLIC, general] [SWE-EVO arXiv 2512.18470](https://arxiv.org/abs/2512.18470)
- **PP-14 Early stall in long workflows.** LongCLI-Bench: every agent system is under 20% pass (incl. Claude Code + Opus 4.6); most tasks stall below 30% step completion, so critical failures happen EARLY. Its dual test sets separate "requirement met" from "no regression". [PUBLIC, general] [LongCLI-Bench arXiv 2602.14337](https://arxiv.org/abs/2602.14337)
- **PP-15 Decisions made early are not carried through.** When the design is revealed progressively instead of up front, Claude Code and Codex both end with lower implementation fidelity. [PUBLIC, general, includes Codex] [arXiv 2603.17104](https://arxiv.org/abs/2603.17104)
- SWE-Marathon numbers (adds to PP-06): frontier agents solve under 30% (NeurIPS listing: under 20%) of multi-hour tasks; reward-hacking behaviour in 13.8% of rollouts; premature termination 7.6% of 526 failures (secondary blog, labels from one LLM analyzer). [PUBLIC, general] [arXiv 2606.07682](https://arxiv.org/abs/2606.07682)
- "Tests pass" ≠ done: maintainers would merge AI PRs ~24 points less often than the SWE-bench grader passes them (METR, Mar 2026); earlier METR review found 0 of the reviewed test-passing PRs mergeable as-is (small sample). → Hidden tests must cover the whole contract, not the happy path. [PUBLIC, general] [METR note](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/), [METR Aug 2025](https://metr.org/blog/2025-08-12-research-update-towards-reconciling-slowdown-with-time-horizons)
- Sol family: METR could not give a robust time horizon for GPT-5.6 Sol (predecessor, not 6.1) because it cheated on tasks; the estimate ranged from ~11 h to >270 h depending on how cheating runs were scored (secondary reports). → Keep verifier tamper protections (pinned base, fail closed). [PUBLIC, Sol-family, secondary] [eWeek](https://eweek.com/news/openai-sol-agent-benchmark/)

- **PP-16 Interleaving-dependent and distributed-state bugs (added 2026-11-14).** Agents without concurrency-testing tools produce patches that look correct but fail under specific interleavings (Spaghetti Bench, incl. Apache Kafka bugs); deterministic replay tools raised fix rates a lot. DDBench (60 historical bugs from 13 distributed systems) shows a 61-point spread between models on its hardest set. [PUBLIC, general, both early-stage] [Spaghetti Bench](https://pastalab.org/spaghetti-bench/blog.html), [DDBench](https://benchmarklist.com/benchmarks/ddbench/), [ConcurBugBench](https://daplab.cs.columbia.edu/projects/concurbugbench/)
  Use (servers/brokers): state that must survive restart/recovery or propagate between components (config → storage → API, interest across links), where the happy-path test passes and the bug shows only after a restart, a reconnect or an ordering the agent must construct. Hidden tests must make the interleaving DETERMINISTIC (explicit sequencing, no sleeps), otherwise the task is flaky.

**What to target (long-horizon):** one behavior whose reference change runs through several components that must agree (config parsing → validation → runtime → status/API output); a chain of dependent decisions where a wrong early choice (layer, representation, ownership of state) only shows up at a later step; root cause or design found by building/running the system; several behavioral hidden tests across the whole path, including cases implied by existing contracts, so the happy-path or first-component-only version fails. Name the "done too early" partial solution and the test that catches it.

**Anti-patterns (long but easy for Sol):**
- **AP-7** "Long" only because of volume: boilerplate, generated code, mechanical renames, the same edit in N places (Sol is strong at migrations, AP-5).
- **AP-8** Many independent small edits: each piece is local and separately testable, so no early decision constrains a later one.
- **AP-9** Long only because the build/test cycle is slow; the reasoning itself is short.
- **AP-10** In-repo oracle: one code path already implements the correct rule (e.g. Check), and the fix is making the other paths copy it. Sol writes a differential test against it and finds every site. [OURS: spicedb self-parity PPP at medium, 2026-11-16]
- **AP-11** The instruction says "A must agree with B" when B exists and is correct. That is a test recipe, not a symptom. [OURS: spicedb]
- **AP-12** A "masked" second defect that panics, errors, or hits an assertion (MustBugf, nil deref). The agent's first broad test crashes on it. Masked defects must return a plausible wrong result. [OURS: spicedb]
- **AP-13** Traps that need the agent to pick a wrong design costing more effort than the right one. A trap counts only if the minimal, most local patch falls into it. [OURS: spicedb; R1 predicted it]

## Sol in long Codex sessions; database and authorization systems (added 2026-11-15)

Checked 2026-11-15: still no OpenAI or academic trajectory study of GPT-6.1 Sol. The Sol-specific items below are user reports with no OpenAI response; none is a measured rate.
- **PP-17 Wrong diagnosis recorded as confirmed, then never revisited (Sol in Codex).** User reports on openai/codex: at High effort Sol records "incomplete or incorrectly scoped diagnoses as confirmed root causes" and shows "prolonged execution without recognizing that the investigation is heading in the wrong direction" (#54001, tasks that took 20-30 min on GPT-5.6 Sol taking 90+ min); "repeatedly stalled or prematurely stopped" on long tasks (#52279); passes its own tests and review, then an external review finds nine defects, four P1 (#52643, Ultra + Fast); at Extra High "assumptions became requirements" and "completion claims changed their scope" (forum). [PUBLIC, Sol, anecdotal, unconfirmed by OpenAI] [#54001](https://github.com/openai/codex/issues/54001), [#52279](https://github.com/openai/codex/issues/52279), [#52643](https://github.com/openai/codex/issues/52643), [forum](https://community.openai.com/t/repeated-scope-drift-in-long-codex-tasks-agent-generated-assumptions-become-requirements/1409425)
  Use: the Sol-specific form of PP-12. Tasks where the first plausible root cause explains the reported symptom but is only one of several places that must change, so a fix built on it passes the agent's own checks. Matches our OURS evidence in reverse: Sol is fast when the first diagnosis is the whole story.
- **PP-18 Diagnosis without completed repair in database systems.** DBA-Bench (instrumented PostgreSQL, 848 runs): diagnosis pass 32.7%, outcome pass (required state restored) 19.6%, safe pass 12.4%; 62.1% of runs that diagnosed correctly still failed the outcome check. It is an operations benchmark, not code patching. [PUBLIC, general] [DBA-Bench arXiv 2607.22165](https://arxiv.org/abs/2607.22165)
  Use: database tasks whose hidden tests check the resulting state across several statements (data, indexes, derived views, later reads), not that one statement returns the right value.
- **PP-19 Access-control repair is partial without help.** BAC-Bench (broken access control in web apps): unscaffolded models repair about 38% of flaws on average, simple scaffolds raise it to about 66%, best agent about 79%. [PUBLIC, general] [BAC-Bench arXiv 2610.34290](https://arxiv.org/abs/2610.34290)
  Use: permission rules that must hold on every path to the same data (each read, write and derived path), with hidden tests on paths the issue does not name. Overlaps PP-08; this is the measured authorization version.
- Gap: no public benchmark measures agents repairing query-planner, transaction or permission-graph code in a database engine. DDBench (60 bugs, 13 distributed systems, already under PP-16) is the closest code-repair set. [PUBLIC, general] [arXiv 2608.14863](https://arxiv.org/abs/2608.14863)

## Sources

- Added 2026-11-15: [Snorkel Terminal-Bench 4.1](https://snorkel.ai/leaderboard/terminal-bench/), [Vals Terminal-Bench-Science](https://www.vals.ai/benchmarks/terminal-bench-science), [SmartScope FrontierCode 2.0](https://smartscope.blog/en/blog/frontiercode-2-0-mergeability-benchmark-leaderboard-scores-ai-2026/), [Vellum](https://www.vellum.ai/md/blog/gpt-6-1-sol-benchmarks-explained), [openai/codex #54001](https://github.com/openai/codex/issues/54001), [#52279](https://github.com/openai/codex/issues/52279), [#52643](https://github.com/openai/codex/issues/52643), [DBA-Bench](https://arxiv.org/abs/2607.22165), [BAC-Bench](https://arxiv.org/abs/2610.34290), [DDBench paper](https://arxiv.org/abs/2608.14863)
- [GPT-6.1 Sol benchmark analysis (DataLearner)](https://www.datalearner.com/en/ai-models/pretrained-models/gpt-6-1-sol/analysis)
- [FrontierCode 2.0 (Cognition)](https://cognition.com/blog/frontier-code-2.0)
- [APEX-SWE (Mercor)](https://www.mercor.com/blog/introducing-apex-swe/), [paper](https://arxiv.org/abs/2601.08806v1)
- [Coherence Collapse: Diagnosing Why Code Agents Fail After Reaching the Right Code](https://arxiv.org/abs/2603.24631)
- [ChainSWE: Benchmarking Coding Agents on Multi-Bug Software Maintenance](https://arxiv.org/abs/2607.02606)
- [SWE-Marathon](https://arxiv.org/abs/2606.07682)
- [DeepSWE](https://arxiv.org/pdf/2607.07946) (reports agents reading gold commits from .git history → keep images history-free)
- Added 2026-11-13 (re-checked: still no public Sol-specific SWE failure taxonomy): [SWE-Bench Pro](https://arxiv.org/abs/2509.16941), [FeatureBench](https://arxiv.org/abs/2602.10975), [FeatBench](https://arxiv.org/abs/2509.22237), [TDAD](https://arxiv.org/abs/2603.17973), [SWE-ABS](https://arxiv.org/abs/2603.00520), [Locating Hidden Failures](https://arxiv.org/abs/2609.17930), [SlopCodeBench](https://arxiv.org/abs/2603.24755), [GPT-6.1 Sol system card](https://cdn.openai.com/pdf/38e3efcf-545e-44cd-99ec-2b7eb395f4cc/oai_GPT_6_1_Sol.pdf), [SonarSource Sol eval](https://www.sonarsource.com/blog/openai-gpt-6-1-sol-evaluation/), [OpenAI GPT-6 maintenance blog](https://developers.openai.com/blog/maintaining-software-with-the-gpt-6-family)
- Added 2026-11-14 (Sol scores, concurrency): [OpenAI GPT-6.1 Sol launch](https://openai.com/blog/introducing-gpt-6-1-sol), [Vellum](https://vellum.ai/blog/gpt-6-1-sol-benchmarks-explained), [llm-stats](https://llm-stats.com/blog/research/gpt-6-1-sol-launch), [BenchLM](https://benchlm.ai/compare/gpt-6-1-sol-vs-gpt-6-astra), [Mercor DeepSWE board](https://www.mercor.com/apex/oss-benchmarks/oss-deep-swe-leaderboard/sample-task/), [benchmarklist](https://benchmarklist.com/models/openai-gpt-6.1-sol/), [orcarouter](https://www.orcarouter.ai/blog/gpt-6-1-sol-independent-benchmark), [DataCamp](https://www.datacamp.com/blog/gpt-6-1-sol), [Spaghetti Bench](https://pastalab.org/spaghetti-bench/blog.html), [DDBench](https://benchmarklist.com/benchmarks/ddbench/), [ConcurBugBench](https://daplab.cs.columbia.edu/projects/concurbugbench/)
- Added 2026-11-14 (long-horizon): [SWE-EVO](https://arxiv.org/abs/2512.18470), [LongCLI-Bench](https://arxiv.org/abs/2602.14337), [When the Specification Emerges](https://arxiv.org/abs/2603.17104), [SWE-Marathon](https://arxiv.org/abs/2606.07682), [METR: SWE-bench-passing PRs not mergeable](https://metr.org/notes/2026-03-10-many-swe-bench-passing-prs-would-not-be-merged-into-main/), [METR algorithmic vs holistic](https://metr.org/blog/2025-08-12-research-update-towards-reconciling-slowdown-with-time-horizons), [METR time horizons](https://metr.org/time-horizons/), [eWeek on METR/GPT-5.6 Sol](https://eweek.com/news/openai-sol-agent-benchmark/)

## Evidence log (appended by the learn stage)
