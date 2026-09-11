from __future__ import annotations

import streamlit as st

from app.services.setup_review_service import ReviewItem, run_setup_review

DEFAULT_SETUP = (
    "XAUUSD. Daily bias bullish, higher highs and higher lows intact. "
    "H1 pulled back into an A-grade demand zone. Price just swept the zone's low "
    "and is starting to react upward, no CHoCH confirmed yet."
)

VERDICT_RENDER = {
    "COMPLETE": st.success,
    "INCOMPLETE": st.warning,
    "ERROR": st.error,
}


def _status_counts(items: list[ReviewItem]) -> dict[str, int]:
    counts = {"OK": 0, "NOT_COVERED": 0, "ERROR": 0, "NOT_ROUTED": 0}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def render(strategy_id: str | None = None) -> None:
    st.subheader("Setup Review")
    st.caption("Deterministic routing, section-grounded quotes, fail-closed verdict.")

    setup = st.text_area(
        "Setup description",
        value=DEFAULT_SETUP,
        height=130,
        help=(
            "Plain language. The pipeline extracts facts and unknowns, routes each to the "
            "strategy sections that govern it, and verifies every quote against the source."
        ),
    )

    if not st.button("Run setup review", type="primary", use_container_width=True):
        st.info("Describe a setup and run the review.")
        return

    with st.spinner("Routing items and checking each against the strategy..."):
        try:
            result = run_setup_review(setup.strip(), strategy_id)
        except Exception as exc:
            st.error(f"Run failed: {exc!r}")
            return

    counts = _status_counts(result.items)
    cols = st.columns(5)
    cols[0].metric("Runtime", f"{result.runtime_sec:.0f}s")
    cols[1].metric("OK", counts["OK"])
    cols[2].metric("Not covered", counts["NOT_COVERED"])
    cols[3].metric("Errors", counts["ERROR"])
    cols[4].metric("Unrouted", counts["NOT_ROUTED"])

    status = next(
        (line.split(":", 1)[1].strip()
         for line in result.stage3_verdict.splitlines() if line.startswith("Status:")),
        "",
    )
    VERDICT_RENDER.get(status, st.info)(result.stage3_verdict)

    st.markdown("#### Two-sided case")
    st.caption("Built only from quotes already verified against the routed sections.")
    st.code(result.two_sided_case, language="text")

    with st.expander("Stage 2 evidence, per item", expanded=False):
        for item in result.items:
            st.markdown(f"**{item.kind}: {item.item}** — `{item.status}`")
            st.code(item.output, language="text")

    with st.expander("Stage 1 raw output", expanded=False):
        st.code(result.stage1_raw, language="text")
