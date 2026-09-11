# System Overview

How Confluence works today, and what each piece is for. Companion to
app_documentation.md (the Streamlit app), trade_store_and_advisor.md (Epics C and F), and
eval_pipeline_and_results.md (quality measurement).

## 1. What the system is

A personal trading assistant that grounds every statement in either the written strategy
document or the logged trades. It runs locally through Ollama.

One principle runs through all of it:

1. Anything the model states must trace back to a quote from the strategy document or a
   number computed in Python.
2. The model is never asked to recall, estimate or recompute a number.
3. A check that could not be evaluated is reported as such, never as a pass.

There are two working pipelines (Setup Review, Strategy Advisor) and one data layer
(the trade store).

## 2. Setup Review

Purpose: answer whether a described setup is consistent with the written rules, without
issuing a trade instruction.

### Stage 1 - restate

An LLM call converts free text into discrete facts and unknowns. Unknowns are restricted to
four categories (RR, whether a pool has been taken, session timing, news risk) so the model
cannot invent open questions.

### Stage 2 - routed matching

The safety core. Instead of one large prompt over the whole document:

1. A deterministic Python router (KEYWORDS -> ROUTING_MAP) maps each item to numbered
   strategy sections. No model is involved in that decision.
2. One narrow call per item-section pair asks for the governing quote and its implication.
3. Every returned quote is verified against the actual section text.
4. Two guards reject low-value answers: a heading guard (a title quoted instead of a rule)
   and a table-row guard (an incomplete table row).

Four statuses, and the distinction between them is the point:

1. OK - evaluated, structured evidence returned.
2. NOT_COVERED - no usable rule content came back.
3. NOT_ROUTED - the router intentionally made no call.
4. ERROR - runtime or model failure.

ERROR is never collapsed into NOT_COVERED. A crash must not look like an absence of rules.

### Stage 3 - verdict

Fail-closed. Any ERROR means the setup cannot be reviewed. Any outstanding unknown means
INCOMPLETE. Only a clean run is COMPLETE.

### The graph (D3)

The pipeline is a LangGraph StateGraph: parse -> retrieve -> validate -> recommend. It was
previously a linear call chain, which left the control flow implicit and gave the routing
plan nowhere to live. Two consequences of the change:

1. Model clients are built and warmed once per process, not per run.
2. Strategy sections are re-read per run, so edits to nabil_strategy.md take effect without
   restarting the app.

### The two-sided case (D4)

Output is split into a supporting case and a risk/invalidation case, composed only from
Stage 2 evidence that has already been verified. No extra model call, so no new
hallucination surface.

Three rules govern the composition:

1. An unreadable Side label degrades to NEUTRAL, never SUPPORTS. A garbled response must not
   become an argument in favour of a trade.
2. Where an item routes to several sections, RISK outranks SUPPORTS, so a rule flagging a
   problem is never hidden behind a supporting match elsewhere.
3. Guard rejection diagnostics are never shown as trading rationale.

Side classification is gated behind ENABLE_SIDE_CLASSIFICATION, default off, because
enabling it changes the match prompt the eval harness measures. With the flag off the
rendered prompt is byte-identical to the committed baseline, so existing eval numbers stay
comparable.

## 3. Trade store

Purpose: hold one row per logged trade. Everything downstream reads from here.

The schema was built against the actual Trade Ledger export rather than the proposal in
README section 4.2, which the export contradicts. See trade_store_and_advisor.md section 3
for the full decision, including why session, htf_zone_grade, entry_model and
sweep_before_fvg are kept nullable and left NULL rather than inferred.

The importer cross-checks its own parse against the workbook's Summary sheet before writing
anything and aborts on a mismatch. Re-running replaces rows by source tag rather than
duplicating them.

## 4. Strategy Advisor

Purpose: report what the logged results say about the written rules.

1. compute - statistics and rule-adherence flags, calculated in Python.
2. retrieve - only the strategy sections behind flags that actually fired.
3. narrate - the model is handed those numbers and that rule text.

Five rule flags, each naming the section that defines the rule: RR below the intraday
minimum (10), sub-60 score taken (13), size above what the score permits (13), full size
with criterion 2 unmet (8), and dead-zone entries (11).

The dead-zone check reports NOT CHECKABLE because session is not logged. It is never
reported as clean. This is the same principle as ERROR not being NOT_COVERED: absence of
evidence is not evidence of compliance.

Segments under ten resolved trades are marked INCONCLUSIVE and the narrator is instructed to
say so, per README section 4.7b, so a rule change cannot be overfitted to a handful of
trades.

After narration, every number in the output is compared against the computed findings. The
comparison is numeric, so 22.9 matches a computed 22.90. It is advisory, not a gate.

## 5. Frontend

A Streamlit app with three sections:

1. Setup Review - the pipeline above, showing verdict, two-sided case, and per-item evidence.
2. Strategy - the strategy document rendered from source, so what is displayed cannot drift
   from what the pipeline actually reads.
3. Trade Tracker - the logged trades, with filters, summary metrics and an equity curve.

## 6. Eval harness

Separate from the app, and unchanged by the work above. Eleven fixed ground-truth items are
run repeatedly against Stage 2 and scored for section routing, quote precision, unverified
quotes and heading quotes. See eval_pipeline_and_results.md.

Any change to the match prompt must be re-baselined through this harness before it is
promoted to default.

## 7. What is not built

1. Reports (Epic E). It also cannot be built as specified: the entry-model, session and
   zone-grade breakdowns require fields that are populated for zero of the logged trades.
2. D2, similar past trades inside Setup Review. The store supports it; the definition of
   "similar" is still open, because the backlog's version depends on the unlogged fields.
3. Segment-level advisor critiques (F3) and cold-start mode (F4), both deliberately deferred.

## 8. Environment notes

1. OLLAMA_MODELS is set to D:\ollama\models, but the models this project uses (qwen3:8b,
   deepseek-r1:8b) are in the default store at C:\Users\<user>\.ollama\models. Ollama
   started without that override serves the wrong set.
2. The default two-model configuration (deepseek-r1:8b for Stage 1, qwen3:8b for Stage 2,
   pinned by keep_alive) needs roughly 10GB of VRAM. On an 8GB card this terminates
   llama-server. Point both at one model until the two-tier split is worth the swap cost.
