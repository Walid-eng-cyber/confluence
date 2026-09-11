# Trade Store and Strategy Advisor

Covers Epic C (trade store and backfill) and Epic F (Strategy Advisor, critique mode).

## 1. What these are

1. A SQLite store holding one row per logged trade.
2. Deterministic statistics and rule-adherence checks computed over those rows.
3. A LangGraph advisor that narrates those computed numbers against the strategy document.

The ordering matters: numbers are computed in Python, then handed to the model. The model is
never asked to recall, estimate or recompute them.

## 2. Files

1. app/models/trade.py
   - The Trade record and outcome derivation.
2. app/services/trade_store.py
   - Schema, connection, writes, and the C3 query helpers.
3. app/services/trade_stats.py
   - F1: whole-strategy statistics and rule-adherence flags. Shared, so Epic E can reuse it.
4. app/graphs/strategy_advisor_graph.py
   - F2: the compute -> retrieve -> narrate graph.
5. scripts/import_trade_ledger.py
   - C2: one-off backfill from the Trade Ledger export.
6. scripts/run_strategy_advisor.py
   - Runner for the advisor.

## 3. Schema decisions

The Trade Ledger export disagrees with the schema proposed in product_plan.md section 4.2, so the
table was built against the real data. This resolves open question section 8.2.

Present in the export and added to the schema:

1. direction, regime, entry_price, stop_price, target_price
2. score (the section 13 rubric result)
3. size (full / half / quarter)
4. criterion_2_met (Y / N)
5. labels (the section 17 fixed no-trade labels)

Proposed in section 4.2 but absent from the export, kept nullable and left NULL:

1. session
2. htf_zone_grade
3. entry_model
4. sweep_before_fvg

These are described only in free-text notes. They are not inferred, because guessing them
would put invented data into the store that reports are supposed to be grounded in. Two
consequences follow:

1. C3's "similar" cannot mean "same zone grade + entry model" as the backlog specifies.
   find_similar applies only the filters it is given, over the dimensions actually logged.
2. The dead-zone adherence check reports NOT CHECKABLE rather than clean.

Both normalised and raw values are stored for daily_bias and regime. The raw strings carry
weekly context ("Bullish (Weekly bullish, Daily pullback)") that normalisation would discard.

## 4. Import and its self-check

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/import_trade_ledger.py <path-to-xlsx> [--dry-run]
```

Before writing anything the importer cross-checks its own parse against the workbook's
Summary sheet: resolved count, wins, losses, breakeven, net R and open count. A mismatch
aborts the import. This is what stops a silent mis-parse from reaching the store.

The import is idempotent. Re-running replaces every row carrying the same source tag.

## 5. A discrepancy in the workbook's Summary sheet

The Summary sheet's overall figures are correct and reconcile exactly. Its per-segment win
rates do not: they divide segment wins by resolved plus open trades, so an unresolved trade
is counted as a non-win.

| Segment | Summary sheet | Computed here |
|---|---|---|
| Criterion 2 met | 63.6% over 11 | 70% over 10 resolved |
| Criterion 2 unmet | 18.2% over 11 | 25% over 8 resolved |
| Score 60-74 | 40% | 50% |
| Score 75+ | 42.9% | 50% |

trade_stats.py excludes open trades from every performance figure. Net R reconciles with the
sheet in both cases, because an open trade contributes no R.

## 6. Rule-adherence flags

Each flag names the strategy section that defines the rule it checks.

1. RR_BELOW_MINIMUM (section 10): planned RR under the 3:1 intraday floor. The 2:1 scalp
   floor cannot be applied, because the ledger does not record intraday versus scalp.
2. SCORE_BELOW_THRESHOLD_TAKEN (section 13): taken despite scoring below 60.
3. SIZE_EXCEEDS_SCORE (section 13): sized above what the score bucket permits.
4. FULL_SIZE_CRITERION_2_UNMET (section 8): full size with criterion 2 unmet.
5. DEAD_ZONE_ENTRY (section 11): NOT CHECKABLE, session is not logged.

A flag that cannot be evaluated is reported as NOT CHECKABLE, never as clean. This mirrors
the ERROR-is-not-NOT_COVERED rule in Setup Review: absence of evidence is not evidence of
compliance.

## 7. Small-sample honesty

Per product_plan.md section 4.7b, any segment with fewer than MIN_SEGMENT_TRADES (10) resolved trades
is marked INCONCLUSIVE and the narrator is instructed to say so rather than draw a
conclusion. At present every score bucket and the criterion-2-unmet segment fall under that
threshold.

## 8. Running the advisor

```powershell
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/run_strategy_advisor.py
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/run_strategy_advisor.py --stats-only
d:/confluence-scaffold/.venv-1/Scripts/python.exe scripts/run_strategy_advisor.py --start 2026-09-01 --end 2026-09-30
```

--stats-only skips the model entirely and prints the computed findings, which is the fast
path when you only want the numbers.

Configuration: OLLAMA_ADVISOR_MODEL (falls back to the Setup Review match model if unset or
not installed), OLLAMA_NUM_CTX_ADVISOR, OLLAMA_ADVISOR_NUM_PREDICT, OLLAMA_ADVISOR_KEEP_ALIVE.

## 9. Numeric grounding check

After narration, find_ungrounded_numbers compares every number in the narrative against the
computed findings, numerically so 22.9 matches 22.90. Section numbers and small ordinals are
ignored. Anything left over is printed as a warning.

It is advisory, not a gate, and it will flag a rounded restatement (47.6% for a computed
48%) as well as an invented one. Treat a warning as something to eyeball.

## 10. Known limits

1. Similarity and dead-zone checks are limited by the four fields the export does not carry.
2. The five handoff trades carry a result but little else: direction and regime are populated
   for 20 of 25 rows, score and criterion_2_met for 22 of 25.
3. Segment-level mismatch mining (F3) is deliberately out of scope until trade volume
   supports it.
4. The advisor has no UI yet. Wiring it into Streamlit is Epic G.
