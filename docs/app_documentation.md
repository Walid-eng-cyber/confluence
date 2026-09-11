# APP documentation

## 1. What this app is

This app is a Streamlit frontend over the Setup Review pipeline.

Its job is to:

1. Accept a trading setup description.
2. Evaluate that setup against the strategy document.
3. Return a structured, fail-safe result with explicit statuses.

It is intentionally safety-first:

1. Runtime/model failures are marked as ERROR.
2. ERROR is never treated as NOT_COVERED.
3. Final verdict is fail-closed when required checks fail.

## 2. Why it was implemented this way

The original risk in LLM-only evaluation was ambiguity and hidden failure modes.

This implementation reduces that risk by:

1. Deterministic routing in Python.
2. Per-item, section-scoped model calls.
3. Strict output normalization and verification.
4. Explicit status model and Stage 3 gate.

Result:

1. You can inspect every item and its governing section.
2. You can separate business logic misses from runtime faults.
3. You can benchmark quality and runtime with a reproducible eval harness.

## 3. High-level architecture

```mermaid
flowchart TD
    UI[Streamlit UI] --> SVC[Setup Review Service]
    SVC --> GRAPH[LangGraph: parse -> retrieve -> validate -> recommend]
    GRAPH --> POC[setup_review_poc.py]
    POC --> STRAT[nabil_strategy.md]
    POC --> OLLAMA[Ollama Models]
    GRAPH --> OUT[Stage 1 + Stage 2 + Stage 3 + two-sided case]
    OUT --> UI
```

What each block is for:

1. Streamlit UI: operator interaction and result display.
2. Service layer: invokes the graph and returns structured objects to UI.
3. LangGraph graph: the pipeline's control flow as explicit, inspectable nodes.
4. setup_review_poc.py: core matching logic and safety behavior.
5. Strategy markdown: source-of-truth rules.
6. Ollama: local model inference runtime.

## 4. Request lifecycle

When the user clicks Run setup review:

1. UI reads setup text.
2. Service invokes the compiled graph (built once per process, including model warmup).
3. parse node: Stage 1 model restates facts and unknowns.
4. retrieve node: re-reads the strategy sections and computes the deterministic routing plan.
5. validate node: Stage 2 evaluates each item against its routed sections, verifying quote
   grounding and normalizing response shape.
6. recommend node: Stage 3 verdict plus the two-sided case.
7. UI displays runtime, status counts, verdict, the case, and per-item evidence.

The retrieve node re-reads nabil_strategy.md on every run, so edits to the strategy take
effect without restarting the app. Model clients are cached, so they do not.

## 5. Core files and what they are for

1. streamlit_app.py
   - Frontend page for Setup Review MVP.
   - Shows metrics, Stage 1 raw output, Stage 2 item output, Stage 3 verdict.

2. app/services/setup_review_service.py
   - Runtime bridge between UI and graph.
   - Compiles the graph once, invokes it, returns typed result objects.

3. app/graphs/setup_review_graph.py
   - The pipeline as a LangGraph StateGraph (parse, retrieve, validate, recommend).
   - Owns model client construction and warmup; holds no strategy text.

4. app/core/pipeline_loader.py
   - Loads scripts/setup_review_poc.py as a module, once per process.

5. scripts/setup_review_poc.py
   - Core logic implementation.
   - Includes routing, parsing, matching, retries, normalization, verification, verdict gating,
     and two-sided case composition.

6. data/knowledge_base/nabil_strategy.md
   - Rule source of truth used for section parsing and quote verification.

## 6. Status model and why it exists

The app uses four statuses:

1. OK
   - Item evaluated successfully with parseable structured output.

2. NOT_COVERED
   - Routed section does not provide governing rule content for the item.

3. NOT_ROUTED
   - Deterministic router intentionally made no model call.

4. ERROR
   - Technical/runtime failure or malformed model output.

Purpose:

1. Prevent silent false negatives.
2. Make failure modes observable.
3. Keep final trade verdict safe under uncertainty.

## 7. Implementation details in setup_review_poc.py

Main components and purpose:

1. route()
   - Maps item text to strategy section numbers using KEYWORDS and ROUTING_MAP.

2. parse_numbered_h2_sections()
   - Builds a section map from numbered H2 headings.

3. parse_restate_output()
   - Extracts facts and unknowns from Stage 1 output robustly.

4. _invoke_with_retry()
   - Handles retries, timeout checks, length-cap diagnostics, and controlled retry escalation.

5. _normalize_structured_response()
   - Enforces strict output shape and heading guard behavior.

6. find_unverified_quotes()
   - Confirms returned quote belongs to routed section source text.

7. match_one_fact() and match_one_unknown()
   - Execute per-item routed matching and aggregate status.

8. build_stage3_verdict()
   - Converts item-level outputs into final fail-safe decision state.

## 8. Runtime controls and purpose

Important controls:

1. /no_think in match prompts
   - Reduces hidden reasoning-token burn and latency.

2. keep_alive + warmup
   - Reduces cold-start and reload overhead.

3. num_predict and num_predict_retry
   - Controls output length and allows one controlled rescue on length-capped empty output.

4. timeout and retries
   - Prevents hanging calls and captures deterministic failure semantics.

5. section-focused excerpts + per-section num_ctx
   - Reduces prompt load and improves runtime efficiency.

6. ENABLE_SIDE_CLASSIFICATION (default 0)
   - Adds a Side field (SUPPORTS / RISK / NEUTRAL) to the Stage 2 fact prompt so the
     two-sided case can argue each rule-matched fact.
   - Off by default because enabling it changes the exact match prompt the eval harness
     measures. Re-baseline scripts/eval_match.py before promoting it, per the decision rule
     in eval_pipeline_and_results.md.
   - With the flag off the rendered prompt is byte-identical to the pre-D4 baseline.

## 9. Frontend behavior

UI behavior in streamlit_app.py:

1. Text area for setup description.
2. Run button triggers full pipeline execution.
3. Summary metrics:
   - runtime
   - OK count
   - NOT_COVERED count
   - ERROR count
   - NOT_ROUTED count
4. Stage 3 verdict shown first.
5. Two-sided case.
6. Stage 1 raw output expandable.
7. Stage 2 per-item details expandable.

Purpose:

1. Give quick top-line health (counts + verdict).
2. Preserve full traceability for diagnostics.

### The two-sided case

build_two_sided_case() composes the supporting and risk sides from Stage 2 output only. It
makes no model call and adds no claim that is not already backed by a quote checked against
the routed section, so it introduces no new hallucination surface.

Placement rules:

1. Supporting side: facts whose governing rule was matched and labelled SUPPORTS.
2. Risk side: facts labelled RISK, facts with no governing rule matched, facts the router
   skipped, missing inputs, and anything that failed to evaluate.
3. Unclassified: facts matched to a rule but labelled NEUTRAL.

Safety behaviour:

1. An unreadable or ambiguous Side label degrades to NEUTRAL, never to SUPPORTS, so a
   garbled response cannot become an argument in favour of a trade.
2. Where one item routes to several sections, RISK outranks SUPPORTS, so a rule flagging a
   problem is never hidden behind a supporting match elsewhere.
3. Guard rejection diagnostics (heading-like quote, incomplete table row) are never shown as
   trading rationale. An item on a guard path is reported as having no governing rule matched.
4. With ENABLE_SIDE_CLASSIFICATION off, every rule-matched fact is unclassified and the case
   says so, rather than implying an empty supporting side is a finding.

## 10. Evaluation and quality measurement

The app pipeline is accompanied by reproducible evaluation scripts.

1. tests/ground_truth.py
   - Fixed 11-item answer key.

2. scripts/eval_match.py
   - Runs 5 attempts per item and writes JSON evidence.

3. scripts/score_eval.py
   - Computes section hit, row hit, unverified, heading quotes.

Purpose:

1. Compare baseline and changes objectively.
2. Detect regressions before adopting prompt/runtime changes.

## 11. How to run

Run the app:

```powershell
cd d:/confluence-scaffold/confluence
d:/confluence-scaffold/.venv-1/Scripts/python.exe -m streamlit run streamlit_app.py
```

Open:

1. http://localhost:8501

## 12. Known limits

1. Row-level quote precision can still vary by section complexity.
2. Some runs may require length-cap retry escalation for specific items.
3. Current MVP is single-page, single-flow (Setup Review only).
4. The default two-model config does not fit an 8GB GPU. OLLAMA_RESTATE_MODEL
   (deepseek-r1:8b) and OLLAMA_MATCH_MODEL (qwen3:8b) are about 5GB each, and
   keep_alive pins the match model after warmup, so a run needs roughly 10GB. On an
   RTX 4060 with a desktop already using about 2GB this terminates llama-server and can
   take the whole Ollama service down. Point both variables at one model until the two-tier
   split is worth the swap cost.
5. Guards map a bad quote to NOT_COVERED, so that status means "no usable rule content was
   returned", not strictly "the section has no such rule".

## 13. Next implementation candidates

1. Persist run history in data/ for side-by-side comparisons in UI.
2. Add inline quality flags for unverified or heading-like quote outcomes.
3. Add operator presets for speed-first vs quality-first runtime settings.
