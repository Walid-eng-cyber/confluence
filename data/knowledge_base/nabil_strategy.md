# Nabil Trading System — Complete Strategy Reference

**Handoff document.** Everything needed to analyse a setup, score it, and decide.
Read this fully before answering any trading question.

---

## 0. How to use this document

You are assisting a trader who applies this system to XAU/USD, NAS100 and FX pairs.

**Your role is consultant, not supporter.** State your position first, reasoning second. If your read differs from his, say so and explain why rather than adopting his view. Say "I don't know" where that's honest. He has explicitly asked to be argued with rather than agreed with.

**Critical context on evidence quality:** every threshold and rule in this document is a hypothesis derived from a small sample — 5 live trades, one partial backtest month, one abandoned test. Nothing here is validated. Treat the numbers as a consistency framework, not as objective truth.

---

## 1. Core principle

> **Liquidity is not support and resistance.**
> A level is a *pool of resting orders*. Price is drawn there to fill institutional size, then reverses. You enter **after** the pool is taken, never at the level.

| | Support / Resistance | Liquidity |
|---|---|---|
| What it is | A barrier price bounces off | A pool of resting orders |
| Why price goes there | It's a wall | To fill institutional size |
| Expected behaviour | Reject on arrival | **Break through, THEN reverse** |
| Where you enter | At the level | **After it's been taken** |

**The test for any level:** does someone have stops here? Equal highs/lows, session extremes, PDH/PDL — yes. A random level where price paused once — no, not tradeable.

---

## 2. The framework

```
   DAILY   →  bias + market structure
      │        THE ONLY DIRECTIONAL DECISION
      ▼
   1 HOUR  →  structure + supply/demand zones
      │
      ▼
   15 MIN  →  structure + the zone you will trade
      │
      ▼
   1 MIN   →  execution only, no directional decision
```

**If a lower timeframe disagrees with the Daily, you wait or you skip. You never flip.**

---

## 3. Bias — how it's determined

**Bias changes on a break of structure, not on a big candle.**

- Higher highs + higher lows = bullish
- Lower highs + lower lows = bearish
- Lower highs + higher lows = **contracting range — neutral, not bearish**
- Mixed / unclear = **neutral → no trade**

A −$150 daily candle inside an uptrend is a pullback if the last higher low is intact. Do not let the size of a move do the thinking.

**When the daily is genuinely ambiguous, score criterion 1 as 5, not as a licence.** A neutral daily means the trade rests entirely on intraday structure, which is a thin foundation.

---

## 4. Which liquidity to target — the anti-false-setup rule

**This is the most important table in the document.**

| Daily | H1 | Regime | VALID TARGET | Entry side |
|---|---|---|---|---|
| Bull | Bull | Trend continuation | **PDH, then weekly high** | Long only |
| Bull | Bear | Pullback in uptrend | **PDH** — the draw is still up | Long only, after the low is swept |
| Bear | Bear | Trend continuation | **PDL, then weekly low** | Short only |
| Bear | Bull | Pullback in downtrend | **PDL** — the draw is still down | Short only, after the high is swept |
| Any | Range | Compression | Opposite side of the range | Fade the extremes |
| Neutral | Any | No bias | **NONE** | **NO TRADE** |

```
The DAILY bias names the target pool.
The H1 structure tells you continuation or pullback.
It NEVER changes which pool is the target.

Daily bull  →  target is ALWAYS the PDH side
Daily bear  →  target is ALWAYS the PDL side
```

**The most common false setup:** daily bull, H1 bear, price falling, and you short toward the PDL because it's nearer. **The PDL is the FUEL for the long, not the target.** This cost −1R on 28 August.

---

## 5. Pool hierarchy

| Rank | Pool | Strength | Role |
|---|---|---|---|
| 1 | Weekly high / low | Strongest | Multi-day target |
| 2 | **PDH / PDL** | Strong | **Primary daily target and DOL** |
| 3 | Overnight extreme | Medium | Intermediate stop on the way |
| 4 | **Asian session H/L** | Weaker | **London's first sweep — the TRIGGER** |
| 5 | Equal highs / lows | Varies | Local stop cluster |
| 6 | Prior M15 swing | Weakest | Scalp target only |

**Asia H/L is where the sequence starts. PDH/PDL is where it ends.** Targeting the Asian extreme in the intraday system is usually a false setup.

### Weighting a pool by actual liquidity

Not every untaken pool blocks a trade:

| Condition | Weight |
|---|---|
| Wide session range, untouched, confluent with an HTF level | **Blocking — wait** |
| Wide range, untouched, standalone | Medium — reduce size |
| Narrow range, or already partially tagged | Weak — note it, don't skip a sound setup |

---

## 6. Zone grading

| Grade | Definition | Trade it? |
|---|---|---|
| **A — Impulse-origin** | The base of the leg that *created* the move | **Yes** |
| **B — Retracement-formed** | A pause inside a move. Looks like a zone, acts like a speed bump. | Half size, full confirmation |
| **C — Mitigated** | Already traded into once | No |

**Evidence:** on 25 August, four B-grade zones failed in four hours. The one A-grade zone produced $73.

```
IMPULSE-ORIGIN                    RETRACEMENT-FORMED
price consolidates                price is already moving
     ↓                                   ↓
then EXPLODES away                pauses briefly
     ↓                                   ↓
the base = A-grade                then continues = B-grade
```

Ask: **did the move start here, or did it just pass through?**

**Zones stacking progressively downward in an uptrend = distribution, not accumulation. No trade.**

---

## 7. Entry — two models

### Model A — Confirmation entry
**Use when price DRIFTS into the zone (normal candle sizes).**

```
Sweep → CHoCH → Displacement with FVG → Enter at the FVG
Stop below the sweep extreme + buffer
```
Order is mandatory: **the sweep must come BEFORE the FVG.**

### Model B — Location entry
**Use when price ARRIVES ON AN IMPULSE (3x normal candle).**

```
Pool already cleared on the way in
Zone is A-grade and untouched
→ Limit at the zone edge, stop beyond the whole impulse
```

A $40 candle doesn't pause to print a CHoCH. **You're paid for location, not timing.**
**Model B requires A-grade location. Never on a B-grade zone.**

### The velocity test

| Approach | Model |
|---|---|
| Slow drift, small candles | **A** — confirmation is available and meaningful |
| Impulse, 3x normal candle | **B** — wait for confirmation and you miss it entirely |

---

## 8. Criterion 2 — the structure break

**A sweep-and-reclaim is NOT sufficient.** The most recent opposing swing must break before entry.

- For a long: the last **lower high** must be taken out
- For a short: the last **higher low**

| Date | Criterion 2 met? | Result |
|---|---|---|
| 25.08 | **Yes** — decline had exhausted | **+4.69R** |
| 26.08 | No — LH sequence intact | −1R |
| 27.08 | No — 4,606 never broke | −0.5R |

**Status: candidate rule, not yet validated.** Two failures, one success, same unmet condition in both failures. Log criterion 2 met Y/N on every setup — this is the primary open question.

### M15 CHoCH as a partial substitute

| Confirmation | Action |
|---|---|
| M15 CHoCH only, H1 still opposing | Quarter to half size. Log criterion 2 = N. |
| M15 CHoCH + H1 break | Full size. Criterion 2 = Y. |
| Neither | No trade |

**M15 CHoCH is acceptable when it comes with A-grade location. Not on its own.** Where it happens matters more than that it happens.

---

## 9. Stop placement

> **The stop goes beyond the nearest liquidity pool, not beyond the zone.**

```
✗ WRONG                        ✓ RIGHT
4,082 ┤ ×× stop                4,192 ┤ ×× stop
4,062 ┤ $$ PDH ← pool!         4,182 ┤ $$ PDH (cleared)
4,050 ┤ ▓▓ zone                4,150 ┤ ▓▓ zone
```

### The measured margin data

Five stops beaten by under a dollar on XAU: **37¢, 7¢, 29¢, 13¢, $1.**

Gold's M1 respects levels to roughly a dollar, not to the cent. Minimum **$8–10 buffer on XAU**, more during an impulse.

### Size the stop to the DAY, not to a fixed number

On 28 August a $9.38 stop was used on a day whose NY session ranged **$186**. The stop was 5% of the day's range. It was structurally correct and still hopeless.

**Use ATR. Convert everything to percentages or ATR multiples when changing instrument.**

| Rule | Gold | EURUSD | Silver |
|---|---|---|---|
| Stop buffer | $8–10 | 5–8 pips | ~0.25 × daily ATR |
| Typical stop | $18–25 | 10–15 pips | ~0.5% of price |

### The hard consequence

**If the correct stop breaks your RR, there is no trade.** Move the ENTRY. Never shrink the stop. On 07.07 and 08.07 the correct stop killed the RR and standing aside was right — even though the direction was right both times.

---

## 10. Risk and management

| Rule | Value |
|---|---|
| Minimum RR — intraday | **3 : 1** |
| Minimum RR — scalp | **2 : 1** |
| Stop buffer | $8–10 on XAU, ATR-scaled elsewhere |
| If RR < minimum | Move the entry, never the stop |

**Partials:**
```
TP1 at first liquidity  →  close 50%, stop to breakeven
TP2 at the DOL          →  close 30%
Runner                  →  trail below each new higher low
```

On 25 August a 4.69R winner gave back $20 mid-move for want of a partial.

---

## 11. Sessions

### Summer (CEST, UTC+2)
| Window | CEST | UTC-4 |
|---|---|---|
| Tokyo | 02:00 – 07:00 | 20:00 – 01:00 |
| **Mark Asia H/L** | **07:00** | 01:00 |
| **London killzone** | **09:00 – 11:00** | 03:00 – 05:00 |
| Dead zone — avoid | 11:30 – 14:00 | 05:30 – 08:00 |
| **NY killzone** | **14:30 – 17:00** | 08:30 – 11:00 |
| London close | 17:00 – 18:00 | 11:00 – 12:00 |

### Winter (CET, UTC+1)
London shifts an hour earlier: **killzone 08:00 – 10:00**, Asia marked at 06:00. **New York does not shift** — always 14:30.

Mark Asia H/L **including wicks**, at the Tokyo close, two hours before London.

---

## 12. Target hit or stopped = restart

```
Trade closes (either way)
        ↓
DO NOT look for the next entry
RE-RUN FROM DAILY
        ↓
1. Has the bias changed?
2. What is the NEW Draw on Liquidity?
3. Which zones are now SPENT?
4. Where does liquidity sit now?
5. ONLY NOW look for an entry
```

**This applies after losses too.** On 28 August a valid ~2R re-entry appeared 90 minutes after the stop-out and was missed because analysis stopped for the day.

---

## 13. Scoring rubric — score BEFORE the outcome is known

Ten criteria, 0–10 each.

| # | Criterion | 9–10 | 5–6 | 0–2 |
|---|---|---|---|---|
| 1 | **Bias aligned** | Matches daily | Daily neutral | Counter-daily |
| 2 | **Structure break** | Opposing swing broken | Reclaim only | Sequence still expanding |
| 3 | **Zone grade** | Impulse-origin | Flip zone | No zone, mid-air |
| 4 | **Zone untouched** | Body never entered | Wick only | Traded through |
| 5 | **Pool above stop cleared** | Swept, nothing left | Partial | Untaken pool above stop |
| 6 | **Target pool valid** | Untaken, structural draw | Minor pool | Already swept |
| 7 | **Discount / premium** | Bottom / top third | Mid-range edge | Dead centre |
| 8 | **Sweep quality** | Clean sweep + reclaim on volume | Shallow / thin liquidity | No sweep |
| 9 | **Killzone timing** | Inside killzone | Edge of window | Dead zone |
| 10 | **News risk** | Nothing within 2h | Minor release | Tier 1 within 2h |

### Thresholds

| Score | Action | Live evidence |
|---|---|---|
| **75 +** | Full size | 2 setups: 1 win (+4.69R), 1 open |
| **60 – 74** | Half size | 2 setups, both lost |
| **Below 60** | **NO TRADE** | **4 setups, 4 losses** |

**RR is a hard gate outside the score.** A 75+ setup with RR below minimum is still no trade.

---

## 14. The ten false-setup conditions

| # | If this is true... | It's false because... |
|---|---|---|
| 1 | Target pool is on the wrong side of the daily bias | Trading the pullback as the trend |
| 2 | The pool beyond your zone has NOT been taken | That pool is a magnet pulling price through your stop |
| 3 | Your target has already been swept | Targeting empty space — no orders to draw price |
| 4 | Price mid-range, both session pools consumed | No draw in either direction |
| 5 | Zone formed during a retracement | It's a pause, not demand |
| 6 | The opposing swing has not broken | Sweep-and-reclaim alone failed twice |
| 7 | Setup is in the 11:30–14:00 dead zone | Sweeps don't reverse without volume |
| 8 | Correct stop breaks the minimum RR | Move the entry, never shrink the stop |
| 9 | Tier 1 news within 2 hours | No stop survives a release — 02.07 ran $58 past |
| 10 | Entering after the move, not before | The window between confirmation and chase is ~15 min |

---

## 15. Break vs sweep — the honest limitation

> **You cannot reliably tell a break from a sweep at the moment it happens.**
> A full body close beyond a level is **NOT** a classifier. Sweeps close bodies through levels routinely and then reverse.

| Pattern | What the breaking candle does | Immediate read |
|---|---|---|
| Sweep | Body can print through the level, then close back inside | Not classified yet |
| Break | Body can print through the level, then close beyond | Not classified yet |

**Both can look identical on the breaking candle.**

**The only reliable classifier is the retest:**

| Retest outcome | Classification | Action/meaning |
|---|---|---|
| Holds as the opposite (S→R) | BREAK | Continuation thesis holds |
| Price closes back inside | SWEEP | Original thesis remains alive |

### The break-and-go gap

The system has **no entry model for a market that never retraces.**

| Date | What happened | Missed |
|---|---|---|
| 06.07 | Sweep in Asia, price never returned | — |
| 08.07 | Broke down from London open, no retrace | $75 |
| 28.08 | PDL broken on displacement, no retrace | $157 / 3.5R |

**Three instances, all significant.** Candidate fix: continuation entry on the retest of the broken level. **Status: PAPER ONLY.** Log every instance and record what the retest entry would have done, but keep it out of the main statistics until 30 logged instances.

---

## 16. Full decision tree

```
DAILY bias?
  ├─ unclear ──────────────────────────► NO TRADE  (no bias)
  ▼
NAME THE TARGET POOL  (bull=PDH, bear=PDL)
  ├─ already swept ────────────────────► NO TRADE  (target swept)
  ▼
H1 structure: continuation or pullback?
  ├─ range ────────────────────────────► wait for the break
  ▼
MARK the M15 zone, in the daily direction
  ├─ grade C ──────────────────────────► NO TRADE  (zone grade)
  ├─ no zone at price ─────────────────► NO TRADE  (open space)
  ▼
IDENTIFY the pool BEYOND the zone  (the fuel)
  ├─ untaken ──────────────────────────► WAIT. Not a trade yet.
  ▼
Pool taken. Did price RECLAIM?
  ├─ no ───────────────────────────────► NO TRADE  (level failed)
  ▼
CRITERION 2: opposing swing broken?
  ├─ no ───────────────────────────────► half size max, log N
  ▼
ARRIVAL: drift or impulse?
  ├─ drift ────────────────────────────► Model A: sweep/CHoCH/FVG
  ├─ impulse ──────────────────────────► Model B: limit at edge
  ├─ through with no reaction ─────────► NO TRADE  (zone broken)
  ▼
STOP beyond swept extreme + buffer
  ├─ sits above another pool ──────────► move beyond that pool
  ▼
RR ≥ 3.0 (intraday) / 2.0 (scalp)?
  ├─ no ───────────────────────────────► move ENTRY. still no?
  │                                       NO TRADE  (RR fail)
  ▼
TIMING: killzone? news within 2h?
  ├─ dead zone ────────────────────────► skip or half size
  ├─ news ─────────────────────────────► NO TRADE  (news block)
  ▼
SCORE /100
  ├─ below 60 ─────────────────────────► NO TRADE
  ├─ 60–74 ────────────────────────────► HALF SIZE
  └─ 75+ ──────────────────────────────► FULL SIZE
  ▼
ENTER → partial at first liquidity → BE → trail
  ▼
CLOSED (either way) → RESTART FROM DAILY
```

**Fourteen NO TRADE exits. That is the design.** Six of eight July sessions produced no trade and that was the system working.

---

## 17. Fixed no-trade labels

Use these exact labels so counts are comparable:

`no bias` · `zone unreached` · `pool untaken` · `RR fail` · `sweep outside session` · `break-and-go` · `TF conflict` · `news block` · `criterion 2 unmet` · `target already swept`

---

## 18. Live record — the honest state of the evidence

| Date | Instrument | Score | Size | Result | Failure type |
|---|---|---|---|---|---|
| 25.08 | XAUUSD | ~85 | full | **+4.69R** | — |
| 26.08 | XAUUSD | 84 | full | −1R | Thesis / criterion 2 |
| 27.08 | XAUUSD | 63 | half | −0.5R | Criterion 2 |
| 28.08 | XAUUSD | 56 | full | −1R | Stop vs volatility |
| 31.08 | NAS100 | 61 | half | ? | — |

**Net ≈ +2.19R across 4 resolved trades. Win rate 25%.**

Positive only because the one winner ran 4.69R while losses were capped. **On four trades this proves nothing.**

### Backtests

| Market | Period | Trades | Result | Finding |
|---|---|---|---|---|
| XAGUSD | Dec 2025 | 23 | +21% @ 3% risk | Positive expectancy (+0.30R), untagged |
| BTCUSD | May 2024 | 6 | −9% | **Abandoned day 10** |
| EURUSD | Jun 2025 | — | pending | Next |

**BTC established an instrument boundary:** the system requires session-clustered stop liquidity. Works on FX, metals, indices. **Fails on 24/7 crypto** — sweeps fire and price runs through, because there's no session close creating stop clusters.

---

## 19. Known open questions

1. **Does criterion 2 predict failure?** Split trades by criterion-2-met Y/N, compare expectancy.
2. **Is the 60 threshold real?** Bucket setups by score, compare expectancy per bucket. If they overlap, discard the threshold.
3. **Intraday or scalp — better expectancy?** Same sessions, both models, include spread cost.
4. **How often is break-and-go?** If >30% of trending sessions, a continuation model is needed.
5. **What stop distance survives?** Percentile of MAE on **winning** trades = the minimum stop that keeps winners alive.

**Do not change any rule before 30 trades per system.**

---

## 20. Behavioural notes — the largest problem in the system

**The gap between the written rules and the actual behaviour is bigger than any rule problem.**

- Trades were taken on five consecutive sessions; the framework says most days are no-trade
- 28 August was taken at full size on a 56 score, when the threshold said half or nothing
- Sub-60 setups are **4 for 4 losing**
- The recurring error is entering *after* the move rather than before — the window between confirmation and chase is roughly 15 minutes

**When assisting: if a setup scores below threshold, lead with "your rule says don't" rather than analysing management for a trade that shouldn't be taken.**

---

## 21. One sentence

> **Location is what makes a trade work. Confirmation is what makes it enterable.
> The pool below the zone is the fuel, not the target.**

---

*Personal trading framework. Not financial advice. Every threshold is a hypothesis from a small sample. Test them; do not trust them.*
