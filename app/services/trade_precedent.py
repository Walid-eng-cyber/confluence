from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.strategy import StrategyConfig
from app.models.trade import OUTCOME_OPEN, OUTCOME_WIN, Trade
from app.services.trade_stats import evaluate_rule_flags

# Below this, a group is precedent to read, not a rate to reason from. README section 4.4:
# with a small log, "similar" means one to three trades, and the response should surface
# those trades rather than imply a trend that is not there.
TREND_THRESHOLD = 5


@dataclass(frozen=True)
class PrecedentGroup:
    heading: str
    section: str | None
    trades: list[Trade] = field(default_factory=list)
    note: str = ""

    def outcome_line(self) -> str:
        resolved = [t for t in self.trades if t.outcome != OUTCOME_OPEN]
        if not resolved:
            return "no resolved trades"

        wins = sum(1 for t in resolved if t.outcome == OUTCOME_WIN)
        net = round(sum(t.rr_achieved or 0.0 for t in resolved), 2)
        summary = f"{len(resolved)} resolved, {wins}W, net {net:+.2f}R"
        if len(resolved) < TREND_THRESHOLD:
            summary += " — too few to be a rate; read the trades"
        return summary

    def lines(self) -> list[str]:
        out = [f"  - {self.heading}" + (f" (section {self.section})" if self.section else "")]
        out.append(f"    {self.outcome_line()}")
        if self.note:
            out.append(f"    {self.note}")
        for trade in self.trades[:5]:
            detail = f"{trade.trade_date} {trade.instrument}: {trade.outcome}"
            if trade.rr_achieved is not None:
                detail += f" {trade.rr_achieved:+.2f}R"
            out.append(f"      · {detail}")
        if len(self.trades) > 5:
            out.append(f"      · ... and {len(self.trades) - 5} more")
        return out


def detect_instrument(text: str, known: list[str]) -> str | None:
    """Match an instrument the store already knows about. No guessing at new tickers."""
    lowered = text.lower()
    matches = [name for name in known if name.lower() in lowered]
    if matches:
        return max(matches, key=len)

    # "NQ (US100)" should still match a setup that just says NQ.
    for name in known:
        head = re.split(r"[\s(]", name)[0].lower()
        if len(head) >= 2 and re.search(rf"\b{re.escape(head)}\b", lowered):
            return name
    return None


def detect_direction(text: str) -> str | None:
    lowered = text.lower()
    long_hit = re.search(r"\b(long|bullish|buy)\b", lowered) is not None
    short_hit = re.search(r"\b(short|bearish|sell)\b", lowered) is not None
    if long_hit == short_hit:
        return None
    return "long" if long_hit else "short"


def build_precedents(
    history: list[Trade],
    config: StrategyConfig,
    setup_text: str,
) -> tuple[list[PrecedentGroup], list[PrecedentGroup]]:
    """Return (cautionary, supporting) precedent from the trader's own logged trades.

    Cautionary groups answer "you have done this before, and here is how it went" for each
    rule this strategy can check. They are keyed to rules rather than to the setup's own
    fields because Setup Review never learns this setup's RR, score or session - those are
    always unknowns. Precedent is what turns an unknown into a warning.

    Supporting groups are past trades on the same instrument that broke none of the
    checkable rules: the closest thing in the log to this setup done properly.
    """
    if not history:
        return [], []

    instruments = sorted({t.instrument for t in history})
    instrument = detect_instrument(setup_text, instruments)
    direction = detect_direction(setup_text)

    flags = evaluate_rule_flags(history, config)
    breached_ids = {id(t) for flag in flags for t in flag.offending_trades}

    cautionary: list[PrecedentGroup] = []
    for flag in flags:
        if not flag.offending_trades:
            continue

        scoped = [t for t in flag.offending_trades if t.instrument == instrument] if instrument else []
        if scoped:
            trades, note = scoped, f"on {instrument}"
        else:
            trades = flag.offending_trades
            note = (
                f"none on {instrument}; showing every instrument"
                if instrument else "across all instruments"
            )

        # Flag summaries carry parenthetical caveats that belong in the flag, not a heading.
        short = flag.summary.split(" (")[0]
        cautionary.append(PrecedentGroup(
            heading=f"You have broken this before: {short}",
            section=flag.section,
            trades=sorted(trades, key=lambda t: t.trade_date, reverse=True),
            note=note,
        ))

    clean = [
        t for t in history
        if id(t) not in breached_ids and t.outcome != OUTCOME_OPEN
    ]
    if instrument:
        same_instrument = [t for t in clean if t.instrument == instrument]
        if direction:
            narrower = [t for t in same_instrument if t.direction == direction]
            if narrower:
                same_instrument = narrower
        if same_instrument:
            clean = same_instrument
            scope = f"{instrument}" + (f", {direction}" if direction else "")
        else:
            scope = f"no clean {instrument} trades; showing every instrument"
    else:
        scope = "instrument not recognised in the setup; showing every instrument"

    supporting: list[PrecedentGroup] = []
    if clean:
        supporting.append(PrecedentGroup(
            heading="Closest precedent that broke none of the checkable rules",
            section=None,
            trades=sorted(clean, key=lambda t: t.rr_achieved or 0.0, reverse=True),
            note=scope,
        ))

    return cautionary, supporting


def format_precedents(
    cautionary: list[PrecedentGroup],
    supporting: list[PrecedentGroup],
) -> str:
    if not cautionary and not supporting:
        return ""

    lines = ["=== YOUR OWN RECORD ==="]

    if supporting:
        # Not "in favour": following every rule does not make a trade a winner, and the
        # outcome line may well say it lost. That is the useful part.
        lines.append("  Taken by the book:")
        for group in supporting:
            lines.extend(group.lines())

    if cautionary:
        if supporting:
            lines.append("")
        lines.append("  Rules you have broken before:")
        for group in cautionary:
            lines.extend(group.lines())

    lines.append("")
    lines.append(
        "  These are logged trades, not a prediction. A rule you have broken before is not "
        "a rule you are breaking now - this setup's RR, score and session are unknown."
    )
    return "\n".join(lines)
