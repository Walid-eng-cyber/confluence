from __future__ import annotations

import streamlit as st

from app.services.setup_review_service import ReviewItem, run_setup_review


st.set_page_config(
    page_title="Confluence Setup Review MVP",
    page_icon="CT",
    layout="wide",
)

st.title("Confluence: Setup Review MVP")
st.caption("Deterministic routing + section-grounded checks + fail-closed verdict")

DEFAULT_SETUP = (
    "XAUUSD. Daily bias bullish, higher highs and higher lows intact. "
    "H1 pulled back into an A-grade demand zone. Price just swept the zone's low "
    "and is starting to react upward, no CHoCH confirmed yet."
)

setup_description = st.text_area(
    "Setup description",
    value=DEFAULT_SETUP,
    height=140,
    help="Describe the setup in plain language. The pipeline extracts facts and unknowns, then routes each item to strategy sections.",
)

run_clicked = st.button("Run setup review", type="primary", use_container_width=True)


def _status_count(items: list[ReviewItem]) -> dict[str, int]:
    counts = {"OK": 0, "NOT_COVERED": 0, "ERROR": 0, "NOT_ROUTED": 0}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


if run_clicked:
    with st.spinner("Running review..."):
        try:
            result = run_setup_review(setup_description.strip())
        except Exception as exc:
            st.error(f"Run failed: {repr(exc)}")
            st.stop()

    counts = _status_count(result.items)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Runtime (s)", result.runtime_sec)
    col2.metric("OK", counts.get("OK", 0))
    col3.metric("NOT_COVERED", counts.get("NOT_COVERED", 0))
    col4.metric("ERROR", counts.get("ERROR", 0))
    col5.metric("NOT_ROUTED", counts.get("NOT_ROUTED", 0))

    st.subheader("Stage 3 Verdict")
    st.code(result.stage3_verdict, language="text")

    with st.expander("Stage 1 Raw Output", expanded=False):
        st.code(result.stage1_raw, language="text")

    st.subheader("Stage 2 Item Results")
    for item in result.items:
        with st.expander(f"{item.kind}: {item.item} [{item.status}]", expanded=False):
            st.code(item.output, language="text")
else:
    st.info("Enter a setup description and click Run setup review.")
