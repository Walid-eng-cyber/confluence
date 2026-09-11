from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trade:
    """One logged trade.

    Fields mirror the Trade Ledger export. The four fields the export does not carry
    (session, htf_zone_grade, entry_model, sweep_before_fvg) stay nullable rather than
    guessed: they are described only in free-text notes, and inferring them would put
    invented data into the store the reports are meant to be grounded in.
    """

    trade_date: str
    instrument: str
    outcome: str
    direction: str | None = None
    daily_bias: str | None = None
    daily_bias_raw: str | None = None
    regime: str | None = None
    regime_raw: str | None = None
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    rr_planned: float | None = None
    rr_achieved: float | None = None
    score: int | None = None
    size: str | None = None
    criterion_2_met: str | None = None
    labels: str | None = None
    session: str | None = None
    htf_zone_grade: str | None = None
    entry_model: str | None = None
    sweep_before_fvg: int | None = None
    notes: str | None = None
    source: str = ""
    id: int | None = None


OUTCOME_WIN = "win"
OUTCOME_LOSS = "loss"
OUTCOME_BREAKEVEN = "breakeven"
OUTCOME_OPEN = "open"


def outcome_from_r(rr_achieved: float | None) -> str:
    """Derive outcome from realised R. An unresolved trade has no realised R yet."""
    if rr_achieved is None:
        return OUTCOME_OPEN
    if rr_achieved > 0:
        return OUTCOME_WIN
    if rr_achieved < 0:
        return OUTCOME_LOSS
    return OUTCOME_BREAKEVEN
