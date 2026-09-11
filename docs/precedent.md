# Precedent in Setup Review (D2)

The last MVP item: Setup Review now answers "have I done this before, and how did it go?"
from the trader's own logged trades.

## 1. What it produces

A `YOUR OWN RECORD` block appended to the two-sided case:

```
=== YOUR OWN RECORD ===
  Taken by the book:
  - Closest precedent that broke none of the checkable rules
    1 resolved, 0W, net -1.00R — too few to be a rate; read the trades
    XAUUSD, long
      · 2026-09-01 XAUUSD: loss -1.00R

  Rules you have broken before:
  - You have broken this before: taken despite scoring below 60, which the rubric
    marks NO TRADE (section 13)
    1 resolved, 0W, net -1.00R — too few to be a rate; read the trades
    on XAUUSD
      · 2026-08-28 XAUUSD: loss -1.00R
```

## 2. The design decision that matters

The obvious implementation is "find past trades similar to this setup". It does not work,
for a reason worth understanding.

**Setup Review never learns this setup's RR, score or session.** Stage 1 classifies those
four categories as *unknowns* by design — the trader has not stated them, and the parser is
forbidden from guessing. So the system cannot say "this setup breaks your RR rule". It does
not know the RR.

What it can say is: *the six times you took a trade below your 3:1 minimum, here is what
happened.*

**Precedent is keyed to rules, not to the setup's fields. That is what turns an unknown into
a warning** — the one thing the system could not otherwise do with an unknown except report
that it is missing.

The original backlog definition ("same zone grade + entry model") was unbuildable for a
different reason: both fields are populated for zero of twenty-five logged trades.

## 3. The two sides

They mirror the case above them.

**Rules you have broken before.** One group per checkable rule that has offenders in the
log. Narrowed to the setup's instrument when there are any on it, and saying so plainly when
there are not (`none on XAUUSD; showing every instrument`) rather than silently widening.

**Taken by the book.** Past trades that broke none of the checkable rules, narrowed to the
same instrument and direction where possible, best result first.

This is deliberately **not** called "precedent in favour". Following every rule does not make
a trade a winner — on the current log, the one clean XAUUSD long lost 1R. Labelling that as
support would be exactly the flattering distortion this system exists to avoid. The heading
describes what the trades *are*; the outcome line says how they went.

## 4. Small-sample honesty

A group with fewer than `TREND_THRESHOLD` (5) resolved trades appends
`too few to be a rate; read the trades` to its outcome line.

With a twenty-five trade log almost every group is under that, which is the honest state.
Per plan section 4.4: with a small log, "similar" means one to three trades, and the response
should surface those trades rather than imply a trend that is not there.

The block closes with a standing caveat:

> These are logged trades, not a prediction. A rule you have broken before is not a rule you
> are breaking now — this setup's RR, score and session are unknown.

## 5. How the setup is matched to history

Two deterministic detectors, both conservative:

1. `detect_instrument` matches only instruments the store already knows about, longest match
   first, with a fallback on the leading token so a setup saying "NQ" matches a logged
   `NQ (US100)`. It never invents a ticker.
2. `detect_direction` returns a direction only when exactly one of long/bullish/buy or
   short/bearish/sell appears. Ambiguity yields `None` rather than a guess.

Where detection fails, the block says which scope it fell back to.

## 6. What it deliberately does not do

**No model call.** The node runs pure SQL and Python. Precedent is a lookup, not a judgement.

**No new prompt content.** Injecting past trades into the Stage 2 match prompts would change
the exact prompt the eval harness measures and force a re-baseline. The block is composed
after matching, so `scripts/eval_match.py` is untouched.

**No cross-strategy borrowing.** History is fetched scoped to the selected strategy. A
strategy with no trades produces no block at all rather than borrowing another's record.

## 7. Implementation notes

- `app/services/trade_precedent.py` holds the detectors, grouping and formatting.
- The graph gains a node between `validate` and `recommend`:
  `parse → retrieve → validate → recall → recommend`.
- The node is named `recall` rather than `precedent` because LangGraph refuses a node that
  shares a name with a state key, and `precedent` is the state field it writes.
- `RuleFlag` now carries `offending_trades` alongside its display strings, so precedent
  lookup uses the rows directly instead of parsing formatted text back apart.

## 8. Limits

1. Matching is by instrument and direction. Zone grade and entry model would be stronger
   dimensions but are unlogged; backlog item C5 would populate them, and `find_similar`
   already accepts them as filters.
2. A rule that has never been broken produces no group, so the block is silent about rules
   you have always followed. That is intentional - the absence of a warning is not a claim.
3. Open trades appear in a group's listing but are excluded from its outcome line, since
   they have no result yet.
