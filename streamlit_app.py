from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="Confluence",
    page_icon="CT",
    layout="wide",
)

from app.services.strategy_registry import default_strategy_id, list_strategies
from app.ui import advisor_tab, reports_tab, review_tab, strategy_tab, theme, tracker_tab

theme.inject()

SECTIONS = {
    "Setup Review": review_tab.render,
    "Strategy": strategy_tab.render,
    "Trade Tracker": tracker_tab.render,
    "Reports": reports_tab.render,
    "Advisor": advisor_tab.render,
}

st.title("Confluence")
st.caption("Setup review, strategy reference and trade record, grounded in your own rules.")

strategies = list_strategies()
st.session_state.setdefault("strategy_id", default_strategy_id())

# Navigation is session state rather than st.tabs: a tab's selection is client-side and is
# lost on rerun, so using tabs would bounce you out of the section whenever a filter fired.
st.session_state.setdefault("section", next(iter(SECTIONS)))

nav, picker = st.columns([4, 1])

with nav:
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

with picker:
    ids = [config.id for config in strategies]
    chosen = st.selectbox(
        "Strategy",
        ids,
        index=ids.index(st.session_state["strategy_id"]),
        format_func=lambda value: next(c.name for c in strategies if c.id == value),
        label_visibility="collapsed",
        key="strategy_picker",
    )
    if chosen != st.session_state["strategy_id"]:
        st.session_state["strategy_id"] = chosen
        st.rerun()

st.divider()

SECTIONS[st.session_state["section"]](st.session_state["strategy_id"])
