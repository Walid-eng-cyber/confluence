from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.models.trade import OUTCOME_BREAKEVEN, OUTCOME_LOSS, OUTCOME_OPEN, OUTCOME_WIN, Trade

# docs/product_plan.md section 4.7b: a segment with fewer trades than this is inconclusive
# rather than acted on, so the advisor cannot overfit a rule change to a handful of trades.
MIN_SEGMENT_TRADES = 10

# Strategy section 10: minimum RR is 3:1 intraday, 2:1 scalp.
MIN_RR_INTRADAY = 3.0

# Strategy section 13: score thresholds and the size each one permits.
SIZE_RANK = {"quarter": 1, "half": 2, "full": 3}


@dataclass(frozen=True)
class StatBlock:
    label: str
    trades: int
    wins: int
    losses: int
    breakeven: int
    net_r: float
    win_rate: float | None
    avg_r: float | None
    inconclusive: bool

    def line(self) -> str:
        if not self.trades:
            return f"{self.label}: no trades"
        rate = "n/a" if self.win_rate is None else f"{self.win_rate:.0%}"
        avg = "n/a" if self.avg_r is None else f"{self.avg_r:+.2f}R"
        tail = "  [INCONCLUSIVE: under %d trades]" % MIN_SEGMENT_TRADES if self.inconclusive else ""
        return (
            f"{self.label}: {self.trades} trades, {self.wins}W/{self.losses}L/"
            f"{self.breakeven}BE, win rate {rate}, net {self.net_r:+.2f}R, avg {avg}{tail}"
        )


@dataclass(frozen=True)
class RuleFlag:
    code: str
    section: str
    summary: str
    offenders: list[str] = field(default_factory=list)
    checkable: bool = True
    unavailable_reason: str | None = None

    def line(self) -> str:
        if not self.checkable:
            return f"[{self.code}] NOT CHECKABLE (section {self.section}): {self.unavailable_reason}"
        if not self.offenders:
            return f"[{self.code}] clean (section {self.section}): {self.summary}"
        return (
            f"[{self.code}] {len(self.offenders)} trade(s) (section {self.section}): "
            f"{self.summary}\n    " + "\n    ".join(self.offenders)
        )


def _ident(trade: Trade) -> str:
    return f"{trade.trade_date} {trade.instrument}"


def _resolved(trades: list[Trade]) -> list[Trade]:
    return [t for t in trades if t.outcome != OUTCOME_OPEN]


def build_stat_block(label: str, trades: list[Trade]) -> StatBlock:
    """Aggregate resolved trades. Open trades carry no result and are excluded."""
    resolved = _resolved(trades)
    wins = sum(1 for t in resolved if t.outcome == OUTCOME_WIN)
    losses = sum(1 for t in resolved if t.outcome == OUTCOME_LOSS)
    breakeven = sum(1 for t in resolved if t.outcome == OUTCOME_BREAKEVEN)
    net_r = round(sum(t.rr_achieved or 0.0 for t in resolved), 2)

    return StatBlock(
        label=label,
        trades=len(resolved),
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        net_r=net_r,
        win_rate=(wins / len(resolved)) if resolved else None,
        avg_r=round(net_r / len(resolved), 2) if resolved else None,
        inconclusive=len(resolved) < MIN_SEGMENT_TRADES,
    )


def score_bucket(score: int | None) -> str | None:
    """Strategy section 13 buckets."""
    if score is None:
        return None
    if score < 60:
        return "below 60"
    if score <= 74:
        return "60-74"
    return "75+"


def compute_strategy_stats(trades: list[Trade]) -> dict[str, object]:
    """Whole-strategy numbers, computed in code so the model never estimates them."""
    resolved = _resolved(trades)
    open_trades = [t for t in trades if t.outcome == OUTCOME_OPEN]

    planned_vs_achieved = [
        t for t in resolved if t.rr_planned is not None and t.rr_achieved is not None
    ]
    rr_gap = None
    if planned_vs_achieved:
        rr_gap = round(
            sum(t.rr_achieved - t.rr_planned for t in planned_vs_achieved)
            / len(planned_vs_achieved),
            2,
        )

    by_score: list[StatBlock] = []
    for bucket in ("below 60", "60-74", "75+"):
        members = [t for t in trades if score_bucket(t.score) == bucket]
        if members:
            by_score.append(build_stat_block(f"score {bucket}", members))

    by_criterion: list[StatBlock] = []
    for value, label in (("Y", "criterion 2 met"), ("N", "criterion 2 unmet")):
        members = [t for t in trades if t.criterion_2_met == value]
        if members:
            by_criterion.append(build_stat_block(label, members))

    label_counts: dict[str, int] = {}
    for trade in trades:
        if not trade.labels:
            continue
        for label in (part.strip() for part in trade.labels.split(";")):
            if label:
                label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "overall": build_stat_block("overall", trades),
        "logged_total": len(trades),
        "open_trades": [_ident(t) for t in open_trades],
        "avg_rr_planned_vs_achieved": rr_gap,
        "rr_compared_count": len(planned_vs_achieved),
        "by_score_bucket": by_score,
        "by_criterion_2": by_criterion,
        "label_counts": label_counts,
        "unscored_trades": sum(1 for t in trades if t.score is None),
    }


def evaluate_rule_flags(trades: list[Trade]) -> list[RuleFlag]:
    """Rule-adherence checks, each tied to the strategy section that defines the rule."""
    flags: list[RuleFlag] = []

    below_rr = [
        _ident(t) + f" (planned RR {t.rr_planned})"
        for t in trades
        if t.rr_planned is not None and t.rr_planned < MIN_RR_INTRADAY
    ]
    flags.append(RuleFlag(
        code="RR_BELOW_MINIMUM",
        section="10",
        summary=(
            f"taken with planned RR under the {MIN_RR_INTRADAY}:1 intraday minimum "
            "(the 2:1 scalp floor cannot be applied: the ledger does not record whether a "
            "trade was intraday or scalp)"
        ),
        offenders=below_rr,
    ))

    sub_sixty = [
        _ident(t) + f" (score {t.score}, {t.size or 'size not logged'})"
        for t in trades
        if t.score is not None and t.score < 60
    ]
    flags.append(RuleFlag(
        code="SUB_60_SCORE_TAKEN",
        section="13",
        summary="taken despite scoring below 60, which the rubric marks NO TRADE",
        offenders=sub_sixty,
    ))

    oversized: list[str] = []
    for trade in trades:
        if trade.score is None or trade.size is None:
            continue
        rank = SIZE_RANK.get(trade.size)
        if rank is None:
            continue
        bucket = score_bucket(trade.score)
        allowed = 0 if bucket == "below 60" else (SIZE_RANK["half"] if bucket == "60-74" else SIZE_RANK["full"])
        if rank > allowed:
            permitted = "no trade" if allowed == 0 else "half"
            oversized.append(
                f"{_ident(trade)} (score {trade.score} -> {permitted}, taken {trade.size})"
            )
    flags.append(RuleFlag(
        code="SIZE_EXCEEDS_SCORE",
        section="13",
        summary="sized above what the score threshold permits",
        offenders=oversized,
    ))

    full_size_unmet = [
        _ident(t)
        for t in trades
        if t.criterion_2_met == "N" and t.size == "full"
    ]
    flags.append(RuleFlag(
        code="FULL_SIZE_CRITERION_2_UNMET",
        section="8",
        summary="taken at full size with criterion 2 unmet, where the rule caps size at half",
        offenders=full_size_unmet,
    ))

    flags.append(RuleFlag(
        code="DEAD_ZONE_ENTRY",
        section="11",
        summary="entries inside the 11:30-14:00 dead zone",
        checkable=False,
        unavailable_reason=(
            "session is not recorded in the trade ledger, so dead-zone and killzone "
            "adherence cannot be checked. Log session per trade to enable this."
        ),
    ))

    return flags


PERIODS = ("day", "week", "month")


def period_bounds(period: str, anchor: date) -> tuple[str, str]:
    """Inclusive ISO bounds for the day, week or month containing `anchor`.

    Daily, weekly and monthly reports are the same code path with different bounds, which is
    the whole of backlog item E3.
    """
    if period == "day":
        start = end = anchor
    elif period == "week":
        start = anchor - timedelta(days=anchor.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = anchor.replace(day=1)
        next_month = (start + timedelta(days=32)).replace(day=1)
        end = next_month - timedelta(days=1)
    else:
        raise ValueError(f"Unknown period {period!r}; expected one of {PERIODS}")

    return start.isoformat(), end.isoformat()


def build_instrument_blocks(trades: list[Trade]) -> list[StatBlock]:
    """Per-instrument performance, worst net R first so problems lead."""
    instruments = sorted({t.instrument for t in trades})
    blocks = [
        build_stat_block(instrument, [t for t in trades if t.instrument == instrument])
        for instrument in instruments
    ]
    return sorted([b for b in blocks if b.trades], key=lambda b: b.net_r)


def rr_discipline(trades: list[Trade]) -> dict[str, object]:
    """How planned RR compared with what was realised, where both were logged."""
    paired = [t for t in trades if t.rr_planned is not None and t.rr_achieved is not None]
    if not paired:
        return {"count": 0, "avg_gap": None, "hit_or_beat": 0}

    gaps = [t.rr_achieved - t.rr_planned for t in paired]
    return {
        "count": len(paired),
        "avg_gap": round(sum(gaps) / len(gaps), 2),
        "hit_or_beat": sum(1 for gap in gaps if gap >= 0),
    }


def format_report_findings(
    trades: list[Trade],
    start: str,
    end: str,
) -> str:
    """The factual block for a period report, computed entirely in code."""
    stats = compute_strategy_stats(trades)
    flags = evaluate_rule_flags(trades)
    overall: StatBlock = stats["overall"]  # type: ignore[assignment]
    discipline = rr_discipline(trades)

    lines = [f"=== PERIOD {start} to {end} ===", overall.line()]
    lines.append(
        f"logged in period: {stats['logged_total']} ({len(stats['open_trades'])} still open)"
    )

    if discipline["count"]:
        direction = "short of" if discipline["avg_gap"] < 0 else "above"
        lines.append(
            f"realised R minus planned RR: {discipline['avg_gap']:+.2f} on average across "
            f"{discipline['count']} trades, meaning realised fell {direction} plan; "
            f"{discipline['hit_or_beat']} of them hit or beat plan"
        )

    instrument_blocks = build_instrument_blocks(trades)
    if instrument_blocks:
        lines.append("")
        lines.append("=== BY INSTRUMENT (worst net R first) ===")
        lines.extend(block.line() for block in instrument_blocks)
        # Stated outright so the narrator never has to rank a list itself.
        lines.append(
            f"best net R: {instrument_blocks[-1].label} {instrument_blocks[-1].net_r:+.2f}R · "
            f"worst net R: {instrument_blocks[0].label} {instrument_blocks[0].net_r:+.2f}R"
        )

    for title, key in (("BY SCORE BUCKET", "by_score_bucket"), ("BY CRITERION 2", "by_criterion_2")):
        blocks: list[StatBlock] = stats[key]  # type: ignore[assignment]
        if blocks:
            lines.append("")
            lines.append(f"=== {title} ===")
            lines.extend(block.line() for block in blocks)

    label_counts: dict[str, int] = stats["label_counts"]  # type: ignore[assignment]
    if label_counts:
        lines.append("")
        lines.append("=== RECORDED NO-TRADE LABELS ===")
        lines.extend(f"{label}: {count}" for label, count in sorted(label_counts.items()))

    fired = [flag for flag in flags if flag.offenders]
    lines.append("")
    lines.append("=== RULE BREACHES IN PERIOD ===")
    if fired:
        lines.extend(flag.line() for flag in fired)
    else:
        lines.append("none of the checkable rules were breached")

    unavailable = [flag for flag in flags if not flag.checkable]
    if unavailable:
        lines.append("")
        lines.append("=== NOT CHECKABLE ===")
        lines.extend(flag.line() for flag in unavailable)

    return "\n".join(lines)


def format_findings(stats: dict[str, object], flags: list[RuleFlag]) -> str:
    """Render computed numbers as the factual block handed to the narrator."""
    overall: StatBlock = stats["overall"]  # type: ignore[assignment]

    lines = ["=== WHOLE-STRATEGY STATS ===", overall.line()]

    lines.append(f"logged trades: {stats['logged_total']} ({len(stats['open_trades'])} still open)")
    if stats["open_trades"]:
        lines.append("open: " + ", ".join(stats["open_trades"]))  # type: ignore[arg-type]

    gap = stats["avg_rr_planned_vs_achieved"]
    if gap is not None:
        lines.append(
            f"avg realised R minus planned RR: {gap:+.2f} across {stats['rr_compared_count']} trades"
        )
    if stats["unscored_trades"]:
        lines.append(f"trades with no score logged: {stats['unscored_trades']}")

    for title, key in (("BY SCORE BUCKET", "by_score_bucket"), ("BY CRITERION 2", "by_criterion_2")):
        blocks: list[StatBlock] = stats[key]  # type: ignore[assignment]
        if blocks:
            lines.append("")
            lines.append(f"=== {title} ===")
            lines.extend(block.line() for block in blocks)

    label_counts: dict[str, int] = stats["label_counts"]  # type: ignore[assignment]
    if label_counts:
        lines.append("")
        lines.append("=== RECORDED NO-TRADE LABELS ===")
        lines.extend(f"{label}: {count}" for label, count in sorted(label_counts.items()))

    lines.append("")
    lines.append("=== RULE-ADHERENCE FLAGS ===")
    lines.extend(flag.line() for flag in flags)

    return "\n".join(lines)
