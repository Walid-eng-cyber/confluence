from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.graphs.report_graph import build_report_graph, build_runtime
from app.services.trade_stats import (
    StatBlock, build_instrument_blocks, compute_strategy_stats, evaluate_rule_flags,
    format_report_findings, period_bounds, rr_discipline,
)
from app.services.trade_store import connect, fetch_by_date_range, init_schema
from app.services.strategy_registry import get_strategy
from app.ui import theme
from app.ui.common import empty_state


@st.cache_resource(show_spinner=False)
def _graph():
    return build_report_graph(build_runtime())


def _load(start: str, end: str, strategy_id: str):
    conn = connect()
    try:
        init_schema(conn)
        return fetch_by_date_range(conn, start, end, strategy_id=strategy_id)
    finally:
        conn.close()


def _instrument_frame(blocks: list[StatBlock]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Instrument": b.label,
                "Trades": b.trades,
                "W/L/BE": f"{b.wins}/{b.losses}/{b.breakeven}",
                "Win rate": None if b.win_rate is None else b.win_rate,
                "Net R": b.net_r,
                "Avg R": b.avg_r,
            }
            for b in blocks
        ]
    )


def render(strategy_id: str | None = None) -> None:
    config = get_strategy(strategy_id)
    st.subheader("Reports")
    st.caption(
        "Daily, weekly and monthly are the same computation over different dates. Every "
        "number is calculated in Python; the model only reads them back."
    )

    everything = _load("1900-01-01", "2999-12-31", config.id)
    if not everything:
        empty_state(config, "report")
        return

    logged = sorted(t.trade_date for t in everything)
    first, last = date.fromisoformat(logged[0]), date.fromisoformat(logged[-1])

    left, right = st.columns([1, 2])
    period = left.selectbox("Period", ["day", "week", "month", "all logged"], index=2,
                            key="report_period")

    if period == "all logged":
        start, end = logged[0], logged[-1]
        right.caption(f"Every logged trade: {start} to {end}")
    else:
        anchor = right.date_input(
            "Anchor date", value=last, min_value=first, max_value=last, key="report_anchor",
            help="Any date inside the period you want reported.",
        )
        start, end = period_bounds(period, anchor)
        right.caption(f"{period.capitalize()} covering {start} to {end}")

    trades = _load(start, end, config.id)
    if not trades:
        st.warning(f"No trades logged between {start} and {end}.")
        return

    stats = compute_strategy_stats(trades, config)
    overall: StatBlock = stats["overall"]
    discipline = rr_discipline(trades)

    cols = st.columns(5)
    cols[0].metric("Resolved", overall.trades)
    cols[1].metric("Win rate", "n/a" if overall.win_rate is None else f"{overall.win_rate:.0%}")
    cols[2].metric("Net R", f"{overall.net_r:+.2f}")
    cols[3].metric("Avg R", "n/a" if overall.avg_r is None else f"{overall.avg_r:+.2f}")
    cols[4].metric("Open", len(stats["open_trades"]))

    if discipline["count"]:
        st.caption(
            f"Planned vs realised RR: {discipline['avg_gap']:+.2f} on average across "
            f"{discipline['count']} trades where both were logged — "
            f"{discipline['hit_or_beat']} hit or beat the plan."
        )

    instrument_blocks = build_instrument_blocks(trades)
    if instrument_blocks:
        st.markdown("**By instrument** — worst net R first")
        frame = _instrument_frame(instrument_blocks)
        st.dataframe(
            frame.style
            .map(lambda v: f"color: {theme.r_colour(v)}; font-weight: 600", subset=["Net R"])
            .format({"Win rate": "{:.0%}", "Net R": "{:+.2f}", "Avg R": "{:+.2f}"}, na_rep="-"),
            use_container_width=True,
            hide_index=True,
        )

    breaches = [f for f in evaluate_rule_flags(trades, config) if f.offenders]
    st.markdown("**Rule breaches in period**")
    if not breaches:
        st.markdown(":green[✓ none of the checkable rules were breached]")
    for flag in breaches:
        st.markdown(f":red[● **{flag.code}**] — {len(flag.offenders)}, section {flag.section}")
        with st.expander(f"Show the {len(flag.offenders)} trade(s)", expanded=False):
            for offender in flag.offenders:
                st.markdown(f"- {offender}")

    with st.expander("Raw computed findings — what the model is given", expanded=False):
        st.code(format_report_findings(trades, start, end, config), language="text")

    st.divider()
    st.markdown("#### Written report")

    signature = f"{config.id}:{start}:{end}"
    cached = st.session_state.get("report_narrative")

    if st.button("Write the report", type="primary", use_container_width=True):
        with st.spinner("Reading the numbers back..."):
            try:
                final = _graph().invoke({
                    "start_date": start,
                    "end_date": end,
                    "strategy_id": config.id,
                })
            except Exception as exc:
                st.error(f"Report run failed: {exc!r}")
                return
        st.session_state["report_narrative"] = {
            "signature": signature,
            "text": final["narrative"],
            "ungrounded": final.get("ungrounded_numbers") or [],
        }
        cached = st.session_state["report_narrative"]

    if not cached:
        st.caption("The numbers above need no model. Write the report to read them back.")
        return

    if cached["signature"] != signature:
        st.caption("The period changed. Write the report again for the current selection.")
        return

    if cached["ungrounded"]:
        st.warning(
            "Numbers in the report that appear nowhere in the computed findings: "
            + ", ".join(cached["ungrounded"])
        )

    st.markdown(cached["text"])
    st.caption(
        "The computed blocks above are the source of truth. The grounding check only catches "
        "numbers absent from them, not a real figure attached to the wrong claim."
    )
