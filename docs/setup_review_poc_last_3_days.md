# Setup Review PoC: Last 3 Days Work and How It Works

## Scope

This document captures:

1. What was changed during the last 3 days.
2. Why those changes were needed.
3. How the current Setup Review pipeline works end-to-end.
4. How to run it and interpret outputs.
5. Known limits and the safest next tuning steps.

This version is purpose-oriented: each component below explains both what it is and what it is for.

Code reference: confluence/scripts/setup_review_poc.py
Knowledge base reference: confluence/data/knowledge_base/nabil_strategy.md

## 1) Summary of the Last 3 Days

### Day 1: Stability and Deterministic Routing

Main goal: remove unsafe "single large call" behavior and reduce hallucinated rule mapping.

Changes made:

1. Reworked flow into two stages:
   - Stage 1: restate facts + unknowns.
   - Stage 2: evaluate each fact/unknown independently against routed sections.
2. Added deterministic routing:
   - ROUTING_MAP and KEYWORDS map facts to numbered strategy sections.
   - If route is empty, skip model call and return NOT_ROUTED path.
3. Added parser for numbered H2 sections:
   - parse_numbered_h2_sections() maps "## <n>. ..." to section text.
4. Added robust Stage 1 output parser:
   - parse_restate_output() handles marker and heading variants.

Impact:

1. Removed cross-section contamination from giant prompts.
2. Reduced accidental wrong-section matching.
3. Introduced deterministic no-call fallback for unrouted items.

### Day 2: Error Hardening and Quote Verification

Main goal: prevent crashes and make failures explicit.

Changes made:

1. Added retry wrapper _invoke_with_retry().
2. Added strict response normalization:
   - _normalize_structured_response() enforces structured output.
3. Added per-section quote verification:
   - find_unverified_quotes() validates quoted text appears in routed section text.
4. Reworked strategy section 15 markdown to improve quote continuity (table format).

Impact:

1. Script continues under backend instability instead of crashing.
2. Unsupported or malformed model output is surfaced consistently.
3. Quote verification became section-scoped, not whole-document scoped.

### Day 3: Correct Failure Semantics and Qwen3 Runtime Tuning

Main goal: separate true "not covered" from runtime failures and speed up local inference.

Changes made:

1. Introduced explicit status semantics:
   - OK, NOT_COVERED, ERROR, NOT_ROUTED.
2. Added fail-closed verdict logic:
   - any ERROR in required checks => Stage 3 verdict is ERROR (cannot review setup).
3. Split model roles:
   - OLLAMA_RESTATE_MODEL for Stage 1.
   - OLLAMA_MATCH_MODEL for Stage 2.
4. Added match model fallback if configured model is not installed.
5. Qwen3 runtime tuning for Stage 2:
   - /no_think at first line of match prompts.
   - timeout default raised to 60s.
   - keep_alive=10m to avoid repeated unload/load.
   - warmup call before loop.
   - num_predict capped and tuned (current default 768).
6. Added diagnostics:
   - repr(exception) on failures.
   - one-time raw parse debug.
   - explicit length-debug for done_reason=length and empty visible output.
7. Parser hardening for output drift:
   - strips <think>...</think>.
   - removes markdown bold markers.
   - normalizes curly quotes.
   - loose fallback capture after Field: label.

Impact:

1. Runtime failures are no longer mislabeled as NOT COVERED.
2. Stage 3 now blocks trade verdicts when critical checks fail to evaluate.
3. Timeouts dropped significantly after no_think + timeout/warmup tuning.

## 2) Current Architecture (How It Works)

## Inputs

1. Setup description text (currently in __main__).
2. Strategy markdown document: nabil_strategy.md.
3. Env configuration for Ollama models, context, retries, timeout, generation cap.

What inputs are for:

1. Setup description is the only user-provided scenario source.
2. Strategy markdown is the only rule authority.
3. Env config controls runtime speed, stability, and model behavior without code edits.

## Stage 1: Restate

1. restate_facts() sends RESTATE_PROMPT to OLLAMA_RESTATE_MODEL.
2. parse_restate_output() extracts:
   - facts list
   - unknowns list (limited to RR, pool status, session timing, news risk categories).

What Stage 1 is for:

1. Standardize free text into deterministic evaluation units.
2. Force explicit unknowns so Stage 3 can block unsafe verdicts.
3. Prevent Stage 2 from depending on fragile ad-hoc text parsing.

## Stage 2: Routed matching

For each fact and unknown:

1. route() selects section IDs from KEYWORDS/ROUTING_MAP.
2. If no route:
   - return NOT_ROUTED and skip model call.
3. For each routed section:
   - build prompt with /no_think first line.
   - call _invoke_with_retry().
   - normalize output into strict structure.
   - verify quote text belongs to that exact routed section.
4. Merge per-section status into per-item overall status:
   - ERROR takes precedence over OK/NOT_COVERED.

What Stage 2 is for:

1. Keep each model call narrow and section-scoped.
2. Replace fuzzy whole-doc reasoning with deterministic route + evidence lookup.
3. Separate runtime failure from policy absence via explicit statuses.
4. Preserve auditability: every implication must be tied to a returned quote.

## Stage 3: Verdict

build_stage3_verdict() enforces fail-closed behavior:

1. If any required item status is ERROR:
   - Verdict: cannot review this setup.
   - Status: ERROR.
2. Else if unknowns exist:
   - Verdict: incomplete.
   - Status: INCOMPLETE.
3. Else:
   - Verdict: complete.
   - Status: COMPLETE.

What Stage 3 is for:

1. Convert item-level evidence into one operational decision state.
2. Enforce fail-closed behavior under uncertainty or runtime faults.
3. Block accidental "trade pass" when required checks did not evaluate.

## 3) Status Semantics

1. OK:
   - Model response parsed successfully.
   - Quote/field structure present.
2. NOT_COVERED:
   - Model explicitly indicated section does not address item.
3. NOT_ROUTED:
   - Deterministic router found no applicable section.
   - No model call was made.
4. ERROR:
   - Runtime/model failure (timeout, backend/server error, token-cap exhaustion with empty output, malformed response).

What each status is for:

1. OK:
   - Means the item was evaluated and produced structured, usable evidence.
2. NOT_COVERED:
   - Means routed section lacks governing content for this item.
3. NOT_ROUTED:
   - Means deterministic router intentionally skipped model call.
4. ERROR:
   - Means evaluation failed technically and cannot be treated as business logic.

Important safety rule:

1. ERROR is never treated as NOT_COVERED.
2. Any blocking ERROR causes Stage 3 fail-closed verdict.

## 4) Runtime and Performance Notes

Observed behavior after tuning:

1. /no_think and warmup removed most timeout-driven failures.
2. Remaining failures were concentrated in specific routed items and often associated with done_reason=length and empty visible content.
3. Typical runtime improved from very long runs under retries/timeouts to materially shorter runs, while preserving explicit error semantics.

Why empty output with done_reason=length matters:

1. It indicates generation budget can be consumed without visible answer text in response.content.
2. This is distinct from a normal truncated answer where partial text is visible.

What runtime controls are for:

1. /no_think:
   - Suppress long reasoning traces that consume tokens/time before visible output.
2. warmup + keep_alive:
   - Reduce first-call and mid-run model reload latency.
3. timeout:
   - Bound hangs and convert them into explicit ERROR outcomes.
4. num_predict cap + capped-retry:
   - Control runaway generations while allowing one controlled recovery pass.
5. section-focused excerpts:
   - Reduce prompt size and token pressure for faster, more stable calls.

## 5) Key Configuration Variables

Current important env knobs used by setup_review_poc.py:

1. OLLAMA_BASE_URL
2. OLLAMA_RESTATE_MODEL
3. OLLAMA_MATCH_MODEL
4. OLLAMA_NUM_CTX_RESTATE
5. OLLAMA_NUM_CTX_MATCH
6. OLLAMA_NUM_CTX_MATCH_CAP
7. OLLAMA_RETRIES
8. OLLAMA_RETRY_DELAY_SEC
9. OLLAMA_RETRY_MAX_DELAY_SEC
10. OLLAMA_MATCH_TIMEOUT_SEC
11. OLLAMA_MATCH_NUM_PREDICT
12. OLLAMA_MATCH_KEEP_ALIVE
13. RAW_PARSE_DEBUG_ONCE

What each variable is for:

1. OLLAMA_BASE_URL:
   - Endpoint for local Ollama server.
2. OLLAMA_RESTATE_MODEL:
   - Model used only for Stage 1 fact/unknown extraction.
3. OLLAMA_MATCH_MODEL:
   - Model used for Stage 2 section matching and quoting.
4. OLLAMA_NUM_CTX_RESTATE:
   - Context window for Stage 1 prompts.
5. OLLAMA_NUM_CTX_MATCH:
   - Base Stage 2 context window.
6. OLLAMA_NUM_CTX_MATCH_CAP:
   - Maximum allowed Stage 2 context to avoid runaway memory/latency.
7. OLLAMA_RETRIES:
   - Number of retry attempts for failed calls.
8. OLLAMA_RETRY_DELAY_SEC:
   - Initial retry backoff delay.
9. OLLAMA_RETRY_MAX_DELAY_SEC:
   - Ceiling for exponential backoff.
10. OLLAMA_MATCH_TIMEOUT_SEC:
   - Maximum allowed elapsed time per Stage 2 call.
11. OLLAMA_MATCH_NUM_PREDICT:
   - Base output token cap for Stage 2.
12. OLLAMA_MATCH_KEEP_ALIVE:
   - Model residency duration in Ollama to reduce reload overhead.
13. RAW_PARSE_DEBUG_ONCE:
   - One-time raw output debug toggle for diagnosing parse failures.

Related advanced knobs now in code:

1. OLLAMA_MATCH_NUM_PREDICT_RETRY:
   - Higher cap used only for length-capped empty-output retry.
2. OLLAMA_SECTION_CTX_FLOOR:
   - Minimum context size for per-section dynamic context sizing.

## 6) How to Run

From repository root:

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe d:/confluence-scaffold/confluence/scripts/setup_review_poc.py
```

Optional compile check:

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe -m py_compile d:/confluence-scaffold/confluence/scripts/setup_review_poc.py
```

## 7) How to Read Output

1. Stage 1:
   - confirms extracted facts and unknowns.
2. Stage 2:
   - each item shows route, status, section-level quote/effect.
   - verification warnings indicate quote text not found in routed section verbatim.
3. Stage 3:
   - final operational decision state for automation safety.

What each output stage is for:

1. Stage 1 output:
   - Validates parser input quality before expensive matching.
2. Stage 2 output:
   - Provides traceable evidence per item (route, quote, implication/blocks, status).
3. Stage 3 output:
   - Provides single safe action state for downstream decision logic.

Operational interpretation:

1. Stage 3 ERROR => do not make a trade call from this run.
2. Stage 3 INCOMPLETE => missing required information, no verdict.
3. Stage 3 COMPLETE => all routed checks executed without runtime failure.

## 8) Known Remaining Issues

1. Some sections can still intermittently hit length-capped empty outputs.
2. Quote selection quality can vary within long/complex sections.
3. Section 11 quote verification can fail depending on model quote granularity and markdown structure.

Why these issues matter:

1. Length-capped empty output creates false negatives unless retried/guarded.
2. Row-level quote drift reduces trust even when section routing is correct.
3. Verification variance can hide quality regressions unless measured repeatedly.

## 9) Recommended Next Steps

1. Keep global num_predict moderate; only apply larger cap on targeted sections that repeatedly hit done_reason=length.
2. Add per-section prompt-shortening for long sections (targeted local excerpt inside section).
3. Keep RAW_PARSE_DEBUG_ONCE enabled for tuning sessions, disable in routine runs.
4. Keep fail-closed verdict logic unchanged (safety critical).

What these next steps are for:

1. Preserve safety guarantees while improving runtime practicality.
2. Improve row-level evidence precision without destabilizing section routing.
3. Keep changes measurable through the eval pipeline before promotion.

## 10) Component Purpose Map

Quick reference for the most important functions in setup_review_poc.py:

1. route():
   - Purpose: deterministic topic-to-section routing.
2. parse_numbered_h2_sections():
   - Purpose: stable extraction of numbered strategy sections.
3. parse_restate_output():
   - Purpose: resilient Stage 1 parser for facts/unknowns.
4. _invoke_with_retry():
   - Purpose: guarded model invocation with timeout/retry/fallback semantics.
5. _normalize_structured_response():
   - Purpose: enforce strict structured output for downstream parsing.
6. find_unverified_quotes():
   - Purpose: quote-grounding check against routed source section.
7. match_one_fact() / match_one_unknown():
   - Purpose: per-item section-scoped evaluation and status aggregation.
8. build_stage3_verdict():
   - Purpose: fail-closed final decision synthesis.
