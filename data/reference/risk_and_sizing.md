# Risk and Position Sizing — Reference

**An original summary of widely taught risk-management fundamentals**, written for this
system's reference corpus.

This is methodology reference, not a strategy, and not advice. It exists so the advisor can
draft from established practice rather than from nothing. Nothing here is validated against
your own results.

---

## 1. Why sizing dominates outcome

Two traders with the same entries and exits can end with opposite results, because position
size decides how much each outcome matters.

A strategy's edge is expressed per trade as expectancy:

```
expectancy = (win rate x average win) - (loss rate x average loss)
```

Positive expectancy is necessary but not sufficient. Size determines whether a normal losing
streak is survivable, and survival is what allows expectancy to express itself over enough
trades to matter.

**The order of importance is: survive, then compound, then optimise.**

---

## 2. Fixed fractional risk

The most widely taught approach: risk a constant fraction of current equity per trade.

| Risk per trade | Effect |
|---|---|
| 0.25 - 0.5% | Very slow drawdowns, slow growth. Suits an unvalidated strategy. |
| 1% | Common default for a tested approach |
| 2% | Aggressive; a ten-loss streak costs roughly 18% of the account |
| Above 2% | Requires evidence most traders do not have |

Position size follows from the stop, never the reverse:

```
size = (equity x risk fraction) / (entry - stop, in price terms)
```

**The stop is a structural decision; the size is arithmetic that follows it.** Choosing a
size first and then placing the stop where the size allows is the most common way a sound
method produces unsound risk.

---

## 3. Drawdown arithmetic

Losses compound against you asymmetrically.

| Drawdown | Gain needed to recover |
|---|---|
| 10% | 11% |
| 20% | 25% |
| 33% | 50% |
| 50% | 100% |

This asymmetry is the argument for conservative sizing. It is also why a maximum drawdown
limit is a rule, not a preference: past a certain depth, recovery requires performance the
strategy has never demonstrated.

### Streaks are normal, not evidence of failure

At a 50% win rate, a run of six losses in a hundred trades is expected, not exceptional. A
sizing scheme that cannot absorb a routine streak is mis-sized, and abandoning a method
during one discards the sample that would have told you whether it works.

---

## 4. Risk-reward and its interaction with win rate

They are not independent. The breakeven win rate for a given reward-to-risk ratio:

| Reward : risk | Breakeven win rate |
|---|---|
| 1 : 1 | 50% |
| 2 : 1 | 33% |
| 3 : 1 | 25% |
| 5 : 1 | 17% |

**A minimum reward-to-risk rule is a statement about the win rate you believe you have.**
Requiring 3:1 means accepting that most trades will lose, and that the method must be judged
over enough trades for the winners to appear.

The corresponding failure is moving the stop closer to manufacture the ratio. That changes
the ratio on paper and worsens it in reality, because a stop placed for arithmetic rather
than structure is reached more often.

---

## 5. Correlation and concentration

Risking 1% on five positions that move together is risking 5% on one idea.

| Situation | Treatment |
|---|---|
| Same instrument, multiple entries | One position for risk purposes |
| Correlated instruments (indices, or USD pairs in the same direction) | Aggregate, then size the group |
| Genuinely unrelated markets | Size independently |

**Count risk by idea, not by ticket.**

---

## 6. Adding to positions

| Approach | Effect |
|---|---|
| Adding to winners (pyramiding) | Raises average entry; increases risk on an already-profitable position |
| Adding to losers (averaging down) | Increases exposure as the thesis weakens |

Adding to a loser converts a defined loss into an undefined one. If a position is added to,
the stop and total risk must be recomputed for the combined position — the original stop no
longer describes the risk being carried.

---

## 7. Stops that reflect the market, not the account

A stop should sit where the reason for the trade is disproven. Two consequences:

1. **Scale the stop to volatility, not to a fixed number.** An average-true-range multiple
   travels between instruments and regimes; a fixed currency amount does not.
2. **If the correct stop makes the trade too large, the trade is too large.** Reduce size or
   skip. Do not move the stop.

Volatility-scaled sizing keeps risk constant as conditions change: as the average range
widens, the stop widens and the position shrinks automatically.

---

## 8. When to change the rules

Changing a sizing rule after a losing streak is the most common way a method is abandoned
just before it would have worked.

| Trigger | Justified change |
|---|---|
| Drawdown limit reached | Reduce size or stop trading. Do not raise risk to recover. |
| Sample large enough to measure (commonly 30+ trades per variant) | Adjust from measured expectancy |
| A losing streak within expected bounds | No change |
| A single large loss | Investigate whether the stop was honoured, not whether the rule was wrong |

**Record the rule and the reason before the outcome is known.** A rule changed after the
result is indistinguishable from a rule fitted to it.

---

## 9. What this reference cannot tell you

1. **Your actual win rate and average win.** Both are required to size from expectancy, and
   both need a sample of your own trades.
2. **Your tolerance for drawdown**, which is behavioural. A mathematically survivable
   drawdown you abandon is not survivable in practice.
3. **Whether your edge is real.** Sizing amplifies whatever expectancy exists, including a
   negative one.

---

*Summary of widely taught fundamentals, written for this system's reference corpus. Not
financial advice.*
