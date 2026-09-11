# Reports (Epic E)

What the period report is, how it is built, and the two things it taught about narration.

## 1. What it does

Answers "how did I actually trade over this period" from the trade log alone. Daily, weekly
and monthly are not three features — they are one computation over different date bounds.

It does not consult the strategy document directly. The rules only enter through the
rule-breach flags, which already name the sections they came from. A period report is
grounded in what you did, not in what the rulebook says.

## 2. The pipeline

```
fetch    → trades for the date range, from SQLite
           ↓
compute  → every number, in Python
           ↓
narrate  → the model is handed the finished numbers and reads them back
```

This is the same compute-then-narrate discipline as the Advisor, and for the same reason:
the model is never in a position to calculate, because it is never asked to.

`narrate` short-circuits when the period is empty — no model call is made to say "nothing
happened."

## 3. What is computed

| Piece | Detail |
|---|---|
| Overall | resolved count, W/L/BE, win rate, net R, avg R, open count |
| RR discipline | realised R minus planned RR, averaged, plus how many hit or beat plan |
| By instrument | one block per instrument, **sorted worst net R first** so problems lead |
| By score bucket | section 13's below-60 / 60-74 / 75+ |
| By criterion 2 | met vs unmet |
| No-trade labels | counts of the section 17 labels recorded |
| Rule breaches | the checkable flags that fired in this period |
| Not checkable | flags that could not be evaluated, never reported as clean |

Open trades are excluded from every performance figure and counted separately. A segment
under ten resolved trades is marked `INCONCLUSIVE`.

## 4. Period bounds

`period_bounds(period, anchor)` returns inclusive ISO bounds for the day, week or month
containing `anchor`. Weeks run Monday to Sunday. Month-end is derived by rolling into the
next month and stepping back a day, so February and December need no special casing.

This function is the whole of backlog item E3: the three report types differ only in what it
returns.

## 5. Two lessons from watching it narrate

The first run produced correct headline numbers and **two wrong sentences**. Both are worth
understanding, because they generalise.

### It inverted a direction

It wrote *"Planned RR was below realized RR by an average of -2.24"*. The truth is the
reverse — realised fell short of plan. The number was right; the direction was wrong.

The cause was ambiguous input. The findings said:

```
planned vs realised RR: avg -2.24 across 13 trades
```

"planned vs realised" does not say which was subtracted from which. It now reads:

```
realised R minus planned RR: -2.24 on average across 13 trades, meaning realised fell
short of plan; 4 of them hit or beat plan
```

### It ranked a list wrongly

It called JPN225 (+5.31R) the highest net R when EURUSD (+7.29R) was higher. The instrument
list is sorted worst-first, and the model misread it.

The fix is not a better prompt. It is to stop asking the model to derive anything:

```
best net R: EURUSD +7.29R · worst net R: EURGBP -1.00R
```

**The principle:** if the model has to compute, compare or rank to produce a sentence, it can
get it wrong — and the grounding check will not catch it, because every number involved is
real. Anything the narrative needs to state should be stated in the findings first.

### Why the grounding check missed both

`find_ungrounded_numbers` tests set membership: does this number appear in the findings? In
both errors it did. The check detects fabricated magnitudes, not misused real ones. That
limit is documented where the function lives, and surfaced in the UI under every narrative.

## 6. Using it

In the app, the **Reports** section: pick day, week, month or all-logged, pick an anchor date,
and the numbers render immediately. The written report sits behind a button because it costs
a model call. "Raw computed findings" shows exactly what the model was given.

From the command line:

```powershell
python scripts/run_report.py --period month --anchor 2026-09-15
python scripts/run_report.py --period week --stats-only
python scripts/run_report.py --start 2026-09-01 --end 2026-09-30
```

`--stats-only` skips the model entirely.

Configuration: `OLLAMA_REPORT_MODEL` (falls back to the Setup Review match model),
`OLLAMA_NUM_CTX_REPORT`, `OLLAMA_REPORT_NUM_PREDICT`, `OLLAMA_REPORT_KEEP_ALIVE`.

## 7. What it cannot do

The original plan (product_plan.md section 4.2) specified breakdowns by entry model, session
and zone grade. Those three fields are populated for **zero of twenty-five** logged trades,
because the ledger export never carried them. The report delivers instrument, score bucket
and criterion-2 breakdowns instead.

Backlog item C5 — extracting those fields from the free-text notes — would unlock them.
