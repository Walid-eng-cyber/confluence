# ICT Concepts — Reference Strategy

**An original summary of publicly taught Inner Circle Trader concepts**, written in the same
structure as the other strategies in this system so it can be evaluated by the same pipeline.

This is a *reference* strategy, not a personal one. It is included to check that the system
works against a strategy it was not built around, and as a starting point if you want to
draft rules for a new instrument.

**Nothing here is validated on your own data.** Treat every threshold as a convention taught
by others, not as a tested edge. Not financial advice.

---

## 0. How to use this document

You are assisting a trader applying these concepts to FX, indices or metals.

**Your role is consultant, not supporter.** State your read first and the reasoning second.
Say "I don't know" where that is honest. These concepts are widely taught but sparsely
evidenced; where a rule below is a convention rather than a measured result, say so.

---

## 1. Core premise

> **Price moves to where orders rest, not to where a line was drawn.**
> The claim is that institutional order flow leaves readable traces: pools of stops get
> taken, imbalances get revisited, and structure breaks at particular times of day.

| | Retail reading | Order-flow reading |
|---|---|---|
| A prior high | Resistance to fade | A pool of stops to be taken |
| A sharp gap | Strength to chase | An imbalance likely to be revisited |
| A break of a level | Entry trigger | Unclassified until it is retested |

**The test for any level:** would a crowd of traders have stops there? Session highs and lows,
prior-day extremes, equal highs and lows — yes. A level price merely touched once — no.

---

## 2. Timeframe framework

```
   DAILY    →  directional context and the draw on liquidity
      ▼
   1 HOUR   →  structure, and where the imbalances sit
      ▼
   15 MIN   →  the zone you will actually trade
      ▼
   1-5 MIN  →  execution only
```

**A lower timeframe never overrides the higher one. It only refines the entry.**

---

## 3. Market structure and bias

Structure is defined by the sequence of swing points:

- Higher highs and higher lows = bullish
- Lower highs and lower lows = bearish
- Overlapping or unclear = **no directional trade**

**Break of structure (BOS)** — price takes out the prior swing in the *same* direction as the
trend. It confirms continuation; it does not start anything.

**Market structure shift (MSS)** — price takes out the most recent opposing swing after
sweeping liquidity, on a displacement leg. This is the reversal signal, and it is only
meaningful when it follows a sweep.

**A shift without a preceding sweep is a break, not a reversal.** That distinction is the
most common source of false entries.

---

## 4. Liquidity — where it sits

| Rank | Pool | Why it matters |
|---|---|---|
| 1 | Weekly high / low | Multi-day draw |
| 2 | Previous day high / low | The primary daily objective |
| 3 | Session high / low | London and New York extremes |
| 4 | Asian range high / low | First target of the London session |
| 5 | Equal highs / equal lows | Obvious clustered stops |
| 6 | Prior short-term swing | Minor, scalp only |

**Buy-side liquidity** sits above highs; **sell-side liquidity** sits below lows. Price is
drawn toward whichever side is untapped.

**The sequence to expect:** an early session sweep of the near pool, then a move toward the
far pool. Entering in the direction of the sweep, before the reversal, is the classic error.

---

## 5. Order blocks

An **order block** is the last opposing candle before a displacement move — the last down
candle before a strong rally, or the last up candle before a strong decline.

| Quality | Definition | Trade it? |
|---|---|---|
| **High** | Caused displacement, took liquidity first, untouched since | Yes |
| **Medium** | Caused displacement but no clear sweep before it | Reduced size, wait for confirmation |
| **Low** | Already traded into, or no displacement followed | No |

**A zone only matters if the move actually started there.** A candle price merely passed
through is not an order block. Ask: did the move originate here, or did it just travel
through?

---

## 6. Fair value gaps and imbalance

A **fair value gap (FVG)** is a three-candle pattern where the first candle's wick and the
third candle's wick do not overlap, leaving a range through which price moved without
two-sided trade.

| Condition | Reading |
|---|---|
| FVG formed on the displacement leg away from a sweep | Highest-quality entry area |
| FVG already fully filled | Spent — no longer an entry |
| FVG formed mid-range with no sweep behind it | Weak; likely to be traded straight through |

**The gap is an entry location, not a signal.** It answers *where*, never *whether*.

---

## 7. Premium and discount

Take the swing you are trading and split it in half.

- Below the midpoint = **discount** — the area to buy
- Above the midpoint = **premium** — the area to sell
- At the midpoint = no edge from location

The commonly taught refinement is the **optimal trade entry**, the 62-79% retracement band
of the leg. Entering a long in premium, or a short in discount, gives away the location
advantage the entire approach depends on.

---

## 8. Entry models

### Model A — Sweep, shift, then gap

**Use when price moves into the zone at normal speed.**

```
Sweep a pool → market structure shift → displacement leaving an FVG → enter in the FVG
Stop beyond the sweep extreme
```

The order is mandatory: **the sweep must come before the shift, and the shift before the entry.**

### Model B — Location only

**Use when price arrives on a large impulse that will not pause.**

```
Pool already taken on the way in
Zone is high quality and untouched
→ limit order at the zone edge, stop beyond the whole impulse leg
```

Fast markets do not print a tidy structure shift. You are paid for location, not timing.
**Model B requires a high-quality zone. Never on a medium or low one.**

### Choosing between them

| Arrival | Model |
|---|---|
| Measured, normal candles | **A** — confirmation is available and worth waiting for |
| Impulsive, outsized candle | **B** — waiting for confirmation means missing it entirely |

---

## 9. Stop placement

> **The stop goes beyond the liquidity that was taken, not just beyond the zone.**

If a pool sits between your stop and the zone, the stop is inside a magnet and will be
reached. Move the stop beyond that pool, or do not take the trade.

| Instrument | Typical buffer |
|---|---|
| FX majors | 5-10 pips beyond the extreme |
| Gold | Roughly 0.25 x daily ATR |
| Indices | Beyond the swept swing plus spread |

**Never shrink the stop to make the risk-reward work. Move the entry instead, or skip it.**

---

## 10. Risk and targets

| Rule | Value |
|---|---|
| Minimum risk-reward — intraday | **2 : 1** |
| Minimum risk-reward — swing | **3 : 1** |
| Risk per trade | Fixed and pre-decided, commonly 0.5-1% |
| If the correct stop breaks the minimum | Move the entry, never the stop |

**Targets are liquidity, not round numbers.** The objective is the opposing pool: the prior
day's extreme, the session extreme, or the next untapped equal highs or lows.

Common management: take partial profit at the first pool, move the stop to breakeven, and
let the remainder run toward the primary draw.

---

## 11. Killzones and timing

Times in New York time (ET).

| Window | ET | What it is for |
|---|---|---|
| London killzone | 02:00 - 05:00 | First expansion; often sweeps the Asian range |
| New York killzone | 07:00 - 10:00 | Highest displacement of the day |
| London close | 10:00 - 12:00 | Reversal window; reduced size |
| Afternoon lull | 12:00 - 14:00 | **Avoid** — sweeps here often fail to reverse |

**The concept depends on session structure.** It is weakest in instruments that trade
continuously, because there is no session close to cluster stops.

---

## 12. No-trade conditions

| # | If this is true... | It is invalid because... |
|---|---|---|
| 1 | No liquidity was taken before the entry | There is no reason for the reversal |
| 2 | Structure shifted without a preceding sweep | That is a break, not a reversal |
| 3 | Entry sits in premium for a long, or discount for a short | The location edge is gone |
| 4 | The zone has already been traded into | The orders there are spent |
| 5 | An untaken pool sits between the stop and the entry | It is a magnet pulling price through the stop |
| 6 | The target pool has already been swept | There is nothing left to draw price |
| 7 | Setup falls in the afternoon lull | Insufficient participation to reverse |
| 8 | The correct stop breaks the minimum risk-reward | Move the entry, never the stop |
| 9 | High-impact news is due within the hour | No stop placement survives a release |
| 10 | The move has already run to the target | Entering late inverts the risk-reward |

---

## 13. Setup checklist

Score before the outcome is known. One point each.

| # | Check |
|---|---|
| 1 | Higher-timeframe direction is clear |
| 2 | A named liquidity pool was actually taken |
| 3 | Structure shifted after that sweep, not before |
| 4 | Entry sits in an untouched order block or FVG |
| 5 | Entry is on the correct side of the midpoint |
| 6 | Target is an identified untapped pool |
| 7 | Stop sits beyond the swept extreme |
| 8 | Risk-reward clears the minimum |
| 9 | Inside a killzone |
| 10 | No high-impact news within the hour |

| Score | Action |
|---|---|
| **8 - 10** | Full size |
| **6 - 7** | Half size |
| **Below 6** | **No trade** |

**Risk-reward is a hard gate outside the score.** A 10/10 setup below the minimum is still no
trade.

---

## 14. News and high-impact events

Scheduled high-impact releases break the assumptions this approach rests on: spreads widen,
stops are reached at prices that never traded meaningfully, and liquidity pools are taken
without the usual reversal.

**Convention: no new positions within one hour either side of a high-impact release.**

---

## 15. Known limitations

**These concepts are widely taught and sparsely evidenced.** Three limits worth stating:

1. **A sweep and a break look identical while they happen.** The classification is only
   reliable after the retest. Any rule claiming to tell them apart in real time is claiming
   more than the price action supports.
2. **Order blocks and FVGs are identified with hindsight.** The same chart marked by two
   traders often produces different zones, which makes the approach hard to test objectively.
3. **There is no model for a market that never retraces.** When price displaces away and
   never returns to the zone, the framework has no entry. That is not a rare case.

**Do not treat any threshold in this document as validated. Log outcomes against it before
trusting it.**

---

*Summary of publicly taught concepts, written for this system. Not financial advice, and not
affiliated with or endorsed by any trading educator.*
