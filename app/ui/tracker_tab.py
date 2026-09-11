from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from app.models.trade import Trade
from app.services.trade_stats import build_stat_block, evaluate_rule_flags
from app.services.trade_store import connect, fetch_by_date_range, init_schema
from app.services.strategy_registry import get_strategy
from app.ui import theme
from app.ui.common import empty_state

COLUMNS = [
    ("trade_date", "Date"),
    ("instrument", "Instrument"),
    ("direction", "Dir"),
    ("regime", "Regime"),
    ("outcome", "Outcome"),
    ("rr_planned", "Planned RR"),
    ("rr_achieved", "Realised R"),
    ("score", "Score"),
    ("size", "Size"),
    ("criterion_2_met", "Crit 2"),
    ("labels", "Labels"),
]


@st.cache_data(ttl=30, show_spinner=False)
def _load(strategy_id: str) -> list[dict]:
    conn = connect()
    try:
        init_schema(conn)
        trades = fetch_by_date_range(
            conn, "1900-01-01", "2999-12-31", strategy_id=strategy_id
        )
    finally:
        conn.close()
    return [asdict(t) for t in trades]


def _colour_r(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return f"color: {theme.FLAT}"
    return f"color: {theme.r_colour(float(value))}; font-weight: 600"


_OUTCOME_STYLE = {
    "win": f"color: {theme.LONG}; font-weight: 600",
    "loss": f"color: {theme.SHORT}; font-weight: 600",
    "breakeven": f"color: {theme.FLAT}",
    "open": f"color: {theme.ACCENT}",
}


def _colour_outcome(value: object) -> str:
    return _OUTCOME_STYLE.get(str(value), "")


def render(strategy_id: str | None = None) -> None:
    config = get_strategy(strategy_id)
    rows = _load(config.id)

    st.subheader("Trade Tracker")
    st.caption(f"Trades logged under {config.name}.")

    if not rows:
        empty_state(config, "record")
        return

    frame = pd.DataFrame(rows)

    left, mid, right = st.columns([2, 1, 1])
    instruments = sorted(frame["instrument"].dropna().unique())
    chosen = left.multiselect("Instrument", instruments, default=[], key="tracker_instrument")
    outcomes = mid.multiselect(
        "Outcome", ["win", "loss", "breakeven", "open"], default=[], key="tracker_outcome"
    )
    crit = right.selectbox("Criterion 2", ["any", "Y", "N", "not logged"], key="tracker_crit")

    view = frame
    if chosen:
        view = view[view["instrument"].isin(chosen)]
    if outcomes:
        view = view[view["outcome"].isin(outcomes)]
    if crit == "Y":
        view = view[view["criterion_2_met"] == "Y"]
    elif crit == "N":
        view = view[view["criterion_2_met"] == "N"]
    elif crit == "not logged":
        view = view[view["criterion_2_met"].isna()]

    if view.empty:
        st.warning("No trades match these filters.")
        return

    selected = [Trade(**row) for row in view.to_dict("records")]
    block = build_stat_block("filtered", selected)
    open_count = int((view["outcome"] == "open").sum())

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Resolved", block.trades)
    m2.metric("Win rate", "n/a" if block.win_rate is None else f"{block.win_rate:.0%}")
    m3.metric("Net R", f"{block.net_r:+.2f}")
    m4.metric("Avg R", "n/a" if block.avg_r is None else f"{block.avg_r:+.2f}")
    m5.metric("Open", open_count)

    if block.inconclusive and block.trades:
        st.caption(
            f"{block.trades} resolved trades: under the 10-trade threshold, so treat this "
            "sample as inconclusive rather than as evidence."
        )

    resolved = view[view["outcome"] != "open"].sort_values(["trade_date", "id"])
    if not resolved.empty:
        curve = pd.DataFrame(
            {"Cumulative R": resolved["rr_achieved"].fillna(0).cumsum().to_list()},
            index=range(1, len(resolved) + 1),
        )
        curve.index.name = "Trade #"
        st.line_chart(curve, color=theme.ACCENT, height=220)

    display = view[[key for key, _ in COLUMNS]].rename(columns=dict(COLUMNS))
    # Unlogged text fields read as "None" otherwise, which looks like data rather than a gap.
    text_columns = ["Dir", "Regime", "Size", "Crit 2", "Labels"]
    display[text_columns] = display[text_columns].fillna("-")

    styled = (
        display.style
        .map(_colour_r, subset=["Realised R"])
        .map(_colour_outcome, subset=["Outcome"])
        .format({"Planned RR": "{:.2f}", "Realised R": "{:+.2f}", "Score": "{:.0f}"},
                na_rep="-")
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    with st.expander("Rule-adherence flags on this selection", expanded=False):
        for flag in evaluate_rule_flags(selected, config):
            if not flag.checkable:
                st.markdown(f"**{flag.code}** — not checkable (section {flag.section})")
                st.caption(flag.unavailable_reason or "")
            elif flag.offenders:
                st.markdown(
                    f"**{flag.code}** — {len(flag.offenders)} trade(s), section {flag.section}"
                )
                st.caption("\n\n".join(flag.offenders))
            else:
                st.markdown(f"**{flag.code}** — clean (section {flag.section})")

    with st.expander("Notes", expanded=False):
        for row in view.sort_values("trade_date", ascending=False).to_dict("records"):
            if row.get("notes"):
                st.markdown(
                    f"**{row['trade_date']} · {row['instrument']}** "
                    f"<span class='ct-flat'>({row['outcome']})</span>",
                    unsafe_allow_html=True,
                )
                st.caption(row["notes"])
