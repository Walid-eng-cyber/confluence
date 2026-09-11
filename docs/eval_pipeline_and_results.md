# Setup Review Eval Pipeline and Results

## Purpose

This document describes the reproducible evaluation workflow added for Setup Review matching quality and runtime tracking.

It explains what each part is for, not only what it does.

It covers:

1. Ground truth data.
2. Eval harness behavior.
3. Scoring logic.
4. Collected run artifacts.
5. Baseline and follow-up comparisons.

## Files Added

1. tests/ground_truth.py
2. scripts/eval_match.py
3. scripts/score_eval.py

Why these three files exist:

1. tests/ground_truth.py is the fixed reference answer key. It prevents "moving target" evaluations.
2. scripts/eval_match.py is the data collector. It runs many attempts and stores raw outcomes.
3. scripts/score_eval.py is the interpreter. It turns raw outcomes into comparable quality metrics.

## 1) Ground Truth

File: tests/ground_truth.py

Contains 11 fixed entries (facts and unknowns), each with:

1. item_id
2. kind (FACT or UNKNOWN)
3. item_text
4. expected_section
5. expected_quote

Expected quotes are copied from data/knowledge_base/nabil_strategy.md.

What each field is for:

1. item_id:
   - Stable identity for joining and comparison across runs.
2. kind:
   - Tells the harness which matching function to call.
3. item_text:
   - The exact input the matcher must evaluate.
4. expected_section:
   - Section-level target for routing correctness checks.
5. expected_quote:
   - Row/line-level target for precision checks.

Why fixed ground truth matters:

1. It separates model variation from input variation.
2. It makes before/after prompt or runtime changes measurable.
3. It ensures improvements are reproducible.

## 2) Eval Harness

File: scripts/eval_match.py

Behavior:

1. Skips Call 1 (no restate pass in eval mode).
2. Uses the fixed 11 items from tests/ground_truth.py.
3. Runs Call 2 five attempts per item.
4. Records per attempt:
   - routed_sections
   - returned_section (expected section block extraction)
   - returned_quote
   - verified (true or false)
   - status and overall_status
5. Writes one JSON file to data/eval with timestamped name.

Expected total records per run:

1. 11 items × 5 attempts = 55 records.

What the harness is for:

1. Reliability measurement:
   - Repeated attempts show stability, not just one lucky sample.
2. Drift detection:
   - You can detect regressions in quote quality even when routing still looks good.
3. Auditability:
   - Full attempt records allow post-hoc investigation of failures.

Why Call 1 is skipped:

1. Goal here is to measure Call 2 quality only.
2. Including Call 1 would mix parser/restate noise into matching metrics.

What each recorded field is for:

1. routed_sections:
   - Checks deterministic router behavior.
2. returned_section:
   - Checks whether answer came from expected section.
3. returned_quote:
   - Raw quote to evaluate row precision.
4. verified:
   - Flags whether quote text is actually present in section source.
5. status and overall_status:
   - Distinguishes runtime failures from content-level misses.

Run command:

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe d:/confluence-scaffold/confluence/scripts/eval_match.py
```

## 3) Scoring Script

File: scripts/score_eval.py

Input:

1. Path to one run JSON from data/eval.

Per item it prints:

1. section hit X/5
2. row hit X/5
3. unverified count
4. heading quotes count

What scoring output is for:

1. section hit:
   - Guards routing correctness.
2. row hit:
   - Measures quote precision and semantic correctness at line/table-row level.
3. unverified:
   - Detects fabricated or non-source-grounded quotes.
4. heading quotes:
   - Detects low-value quote behavior (heading instead of rule content).

Definitions:

1. Section hit:
   - expected_section equals returned_section.
2. Row hit:
   - returned quote matches expected quote after setup_review_poc normalization.
3. Unverified:
   - quote verification false for the attempt.
4. Heading quotes:
   - returned quote starts with # or ends with colon.

Why totals matter:

1. totals records confirms full sample size integrity (must be 55).
2. totals row hits is the top-line accuracy proxy for this harness.
3. totals unverified and heading quotes are safety/quality red flags.

Run command:

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe d:/confluence-scaffold/confluence/scripts/score_eval.py <run_json_path> --save <output_txt_path>
```

## 4) Collected Artifacts

How to read artifacts:

1. run_*.json:
   - Raw per-attempt evidence. Use for debugging specific failures.
2. score_*.txt:
   - Human-readable summary for quick run-to-run comparison.

### Baseline (no new quality guard for this step)

1. Run JSON: data/eval/run_20260911_004055.json
2. Score table: data/eval/score_baseline_20260911_004055.txt
3. Runtime: 675.69s
4. Totals:
   - records 55
   - section hits 55
   - row hits 19
   - unverified 1
   - heading quotes 7

### Heading Guard Run

Change applied before this run:

1. Reject heading-like quotes as NOT_COVERED in setup_review_poc.

Artifacts:

1. Run JSON: data/eval/run_20260911_005322.json
2. Score table: data/eval/score_heading_guard_20260911_005322.txt
3. Runtime: 732.21s
4. Totals:
   - records 55
   - section hits 55
   - row hits 20
   - unverified 1
   - heading quotes 0

Observed effect:

1. Quality improved for heading pollution (7 to 0).
2. Row hits improved slightly (19 to 20).
3. Runtime increased in this run.

What this run was for:

1. First controlled quality intervention.
2. Directly tests whether rejecting heading-like quotes improves useful output.

### Dynamic Per-Section Context Run

Change applied before this run:

1. Per-section num_ctx sizing with cached LLM clients.

Artifacts:

1. Run JSON: data/eval/run_20260911_010525.json
2. Score table: data/eval/score_dynamic_ctx_20260911_010525.txt
3. Runtime: 673.27s
4. Totals:
   - records 55
   - section hits 55
   - row hits 20
   - unverified 2
   - heading quotes 0

Observed effect:

1. Runtime recovered compared with heading-guard run.
2. Row-hit total stayed the same.
3. Unverified count worsened slightly (1 to 2).

What this run was for:

1. Performance optimization test under the same scoring method.
2. Verification that speed optimization does not silently destroy quality.

### Targeted Fix Run

Artifacts:

1. Run JSON: data/eval/run_20260911_105820.json
2. Score table: data/eval/score_targeted_fix_20260911_105820.txt
3. Runtime: 1068.84s
4. Totals:
   - records 70
   - section hits 70
   - row hits 30
   - unverified 0
   - heading quotes 0

Note the sample size changed: three high-signal items (unknown_rr, fact_swept_zone_low,
fact_h1_pullback_a_grade_demand) now run ten attempts instead of five, so 70 records rather
than 55. Totals are not directly comparable with the three runs above; per-item rates are.

Observed effect:

1. Unverified quotes reached 0, from 1-2 in the earlier runs.
2. Row hits 30/70 (43%) against 20/55 (36%) in the dynamic-context run.
3. Runtime rose with the larger sample.

Where the remaining misses are concentrated:

1. The four unknown items score 0 row hits between them. They route correctly every time and
   return verified quotes, but not the expected row.
2. fact_swept_zone_low is 3/10, and fact_no_choch 0/5.

## 5) Interpretation

1. Section routing is stable (55/55 section hits in all runs).
2. Primary residual issue is row-level quote precision, not section routing.
3. Heading guard is a clear quality win and should be kept.
4. Dynamic context sizing improves speed but can introduce small verification variance.

What this means operationally:

1. Do not spend time on router redesign right now.
2. Spend effort on quote extraction quality and quote validation robustness.
3. Keep any speed change gated by this eval pipeline before promoting to default.

## 6) Metric Glossary (What each metric is for)

1. section hit:
   - Purpose: route correctness.
   - Bad trend means router/prompt section selection issue.
2. row hit:
   - Purpose: exact evidence quality.
   - Bad trend means quote selection or parsing issue.
3. unverified:
   - Purpose: anti-hallucination control.
   - Any increase is a safety warning.
4. heading quotes:
   - Purpose: enforce rule-content evidence, not decorative text.
   - Any non-zero value indicates weak quoting behavior.
5. runtime_sec:
   - Purpose: practicality for real usage.
   - Should improve only if quality metrics remain stable.

## 7) Status Glossary (What each status is for)

1. OK:
   - Call produced parseable structured output and passed basic shape checks.
2. NOT_COVERED:
   - Section genuinely does not contain the needed rule content.
3. NOT_ROUTED:
   - Router intentionally made no model call.
4. ERROR:
   - Runtime or model-output failure. Never treat as NOT_COVERED.

Why this status model exists:

1. Prevents dangerous false negatives where runtime failure looks like policy absence.
2. Enables fail-closed verdict behavior in Setup Review.

## 8) Repeatable Workflow

1. Run eval harness:

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe d:/confluence-scaffold/confluence/scripts/eval_match.py
```

2. Score latest run:

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe d:/confluence-scaffold/confluence/scripts/score_eval.py d:/confluence-scaffold/confluence/data/eval/run_<timestamp>.json --save d:/confluence-scaffold/confluence/data/eval/score_<label>_<timestamp>.txt
```

3. Compare totals and per-item row-hit drift against baseline before keeping any prompt/runtime change.

Decision rule after every experiment:

1. Keep change only if:
   - section hits do not regress,
   - row hits improve or hold,
   - unverified and heading quotes do not worsen,
   - runtime is acceptable for your use.

## 9) Outstanding: the side-classification flag

`ENABLE_SIDE_CLASSIFICATION` adds a `Side` field to the Stage 2 fact prompt so the two-sided
case can argue each rule-matched fact. **It has been off since it was written, and none of
the runs above measure it.**

It is off precisely because it changes the prompt this harness measures. With the flag off
the rendered prompt is byte-identical to the pre-feature baseline, which is asserted by a
test comparing against commit a66034d.

Promoting it means: run the harness with `ENABLE_SIDE_CLASSIFICATION=1`, score it, and apply
the decision rule above against run_20260911_105820. Until that happens, the two-sided case
ships with every rule-matched fact listed as unclassified, and says so in its own output.

This is the last item standing between the MVP being built and being delivered as specified.
