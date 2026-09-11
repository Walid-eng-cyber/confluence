from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Confluence",
    page_icon="CT",
    layout="wide",
)

from app.ui import advisor_tab, review_tab, strategy_tab, theme, tracker_tab

theme.inject()

SECTIONS = {
    "Setup Review": review_tab.render,
    "Strategy": strategy_tab.render,
    "Trade Tracker": tracker_tab.render,
    "Advisor": advisor_tab.render,
}

st.title("Confluence")
st.caption("Setup review, strategy reference and trade record, grounded in your own rules.")

# Navigation is session state rather than st.tabs: a tab's selection is client-side and is
# lost on rerun, so using tabs would bounce you out of the section whenever a filter fired.
st.session_state.setdefault("section", next(iter(SECTIONS)))

columns = st.columns(len(SECTIONS))
for column, name in zip(columns, SECTIONS):
    active = st.session_state["section"] == name
    if column.button(
        name,
        use_container_width=True,
        type="primary" if active else "secondary",
        key=f"nav_{name}",
    ):
        st.session_state["section"] = name
        st.rerun()

st.divider()

SECTIONS[st.session_state["section"]]()
