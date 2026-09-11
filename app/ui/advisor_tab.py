from __future__ import annotations

from datetime import date

import streamlit as st

from app.graphs.strategy_advisor_graph import build_runtime, build_strategy_advisor_graph
from app.services.trade_stats import (
    RuleFlag, StatBlock, compute_strategy_stats, evaluate_rule_flags,
)
from app.services.trade_store import connect, fetch_by_date_range, init_schema
from app.ui import theme

FULL_RANGE = ("1900-01-01", "2999-12-31")


@st.cache_resource(show_spinner=False)
def _graph():
    """Compiled once per process; model clients are built here, not per run."""
    return build_strategy_advisor_graph(build_runtime())


def _load(start: str, end: str):
    conn = connect()
    try:
        init_schema(conn)
        return fetch_by_date_range(conn, start, end)
    finally:
        conn.close()


def _render_block(block: StatBlock) -> None:
    label = block.label
    if block.inconclusive and block.trades:
        label += "  ·  inconclusive"
    st.markdown(
        f"<div class='ct-chip'>{label} <b>{block.trades}</b> trades · "
        f"<b>{'n/a' if block.win_rate is None else format(block.win_rate, '.0%')}</b> win · "
        f"<b style='color:{theme.r_colour(block.net_r)}'>{block.net_r:+.2f}R</b></div>",
        unsafe_allow_html=True,
    )


def _render_flag(flag: RuleFlag) -> None:
    if not flag.checkable:
        st.markdown(
            f"<span class='ct-flat'>◦ **{flag.code}** — not checkable (section {flag.section})</span>",
            unsafe_allow_html=True,
        )
        st.caption(flag.unavailable_reason or "")
        return

    if not flag.offenders:
        st.markdown(f":green[✓ **{flag.code}**] — clean (section {flag.section})")
        return

    st.markdown(
        f":red[● **{flag.code}**] — {len(flag.offenders)} trade(s), section {flag.section}"
    )
    st.caption(flag.summary)
    with st.expander(f"Show the {len(flag.offenders)} trade(s)", expanded=False):
        for offender in flag.offenders:
            st.markdown(f"- {offender}")


def render() -> None:
    st.subheader("Strategy Advisor")
    st.caption(
        "Statistics and rule checks are computed in Python. The model only narrates them, "
        "and never sees a number it could recompute."
    )

    trades_all = _load(*FULL_RANGE)
    if not trades_all:
        st.info(
            "No trades in the store yet. Import the ledger export:\n\n"
            "`python scripts/import_trade_ledger.py <path-to-xlsx>`"
        )
        return

    dates = sorted(t.trade_date for t in trades_all)
    first, last = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])

    picked = st.date_input(
        "Period",
        value=(first, last),
        min_value=first,
        max_value=last,
        help="Defaults to every logged trade.",
        key="advisor_period",
    )
    if not isinstance(picked, tuple) or len(picked) != 2:
        st.caption("Pick an end date to continue.")
        return

    start, end = picked[0].isoformat(), picked[1].isoformat()
    trades = _load(start, end)
    if not trades:
        st.warning("No trades in that period.")
        return

    stats = compute_strategy_stats(trades)
    flags = evaluate_rule_flags(trades)
    overall: StatBlock = stats["overall"]

    cols = st.columns(5)
    cols[0].metric("Resolved", overall.trades)
    cols[1].metric("Win rate", "n/a" if overall.win_rate is None else f"{overall.win_rate:.0%}")
    cols[2].metric("Net R", f"{overall.net_r:+.2f}")
    cols[3].metric("Avg R", "n/a" if overall.avg_r is None else f"{overall.avg_r:+.2f}")
    cols[4].metric("Open", len(stats["open_trades"]))

    gap = stats["avg_rr_planned_vs_achieved"]
    if gap is not None:
        st.caption(
            f"Realised R minus planned RR averages {gap:+.2f} across "
            f"{stats['rr_compared_count']} trades where both were logged."
        )

    left, right = st.columns(2)
    with left:
        st.markdown("**By score bucket**")
        for block in stats["by_score_bucket"]:
            _render_block(block)
    with right:
        st.markdown("**By criterion 2**")
        for block in stats["by_criterion_2"]:
            _render_block(block)

    if any(b.inconclusive for b in stats["by_score_bucket"] + stats["by_criterion_2"]):
        st.caption(
            "Segments marked inconclusive hold fewer than 10 resolved trades. The strategy "
            "document says not to change a rule before 30."
        )

    st.markdown("#### Rule adherence")
    for flag in flags:
        _render_flag(flag)

    st.divider()
    st.markdown("#### Narrative")

    signature = f"{start}:{end}"
    cached = st.session_state.get("advisor_narrative")

    if st.button("Generate narrative", type="primary", use_container_width=True):
        with st.spinner("Retrieving the sections behind each flag, then narrating..."):
            try:
                final = _graph().invoke({"start_date": start, "end_date": end})
            except Exception as exc:
                st.error(f"Advisor run failed: {exc!r}")
                return
        st.session_state["advisor_narrative"] = {
            "signature": signature,
            "text": final["narrative"],
            "ungrounded": final.get("ungrounded_numbers") or [],
        }
        cached = st.session_state["advisor_narrative"]

    if not cached:
        st.caption("The numbers above need no model. Generate a narrative to read them back.")
        return

    if cached["signature"] != signature:
        st.caption("The period changed. Generate again to narrate the current selection.")
        return

    if cached["ungrounded"]:
        st.warning(
            "Numbers in the narrative that appear nowhere in the computed findings: "
            + ", ".join(cached["ungrounded"])
            + ". A rounded restatement will also appear here."
        )

    st.markdown(cached["text"])

    st.caption(
        "The computed blocks above are the source of truth. The grounding check only catches "
        "numbers that appear nowhere in them, so it cannot catch a figure that is real but "
        "attached to the wrong claim — the model has been observed miscounting a win/loss "
        "split this way. Read the narrative as a summary to verify, not as a result."
    )
