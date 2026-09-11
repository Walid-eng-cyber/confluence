from __future__ import annotations

import re

import streamlit as st

from app.core.pipeline_loader import load_pipeline_module
from app.services.trade_stats import MIN_RR_INTRADAY
from app.ui import theme

# The sections a trader wants in front of them, rather than all 21 at once.
PINNED = ("1", "4", "6", "7", "10", "13", "16")


@st.cache_data(show_spinner=False)
def _load_strategy() -> tuple[str, dict[str, str], dict[str, str]]:
    """Return (raw text, {number: body}, {number: title}).

    Read from the same file the pipeline reads, so what is displayed cannot drift from
    what is actually evaluated against.
    """
    poc = load_pipeline_module()
    raw = poc.STRATEGY_PATH.read_text(encoding="utf-8")
    sections = poc.extract_sections(raw)

    titles = {
        number: (re.match(r"##\s+\d+\.\s*(.+)", body.splitlines()[0]) or [None, ""])[1].strip()
        for number, body in sections.items()
    }
    return raw, sections, titles


def _headline(sections: dict[str, str]) -> str | None:
    """The author's own one-sentence summary (section 21), stripped of quote markers."""
    body = sections.get("21")
    if not body:
        return None
    lines = [
        line.lstrip("> ").strip()
        for line in body.splitlines()[1:]
        if line.strip().startswith(">")
    ]
    return " ".join(lines).replace("**", "") or None


def render() -> None:
    raw, sections, titles = _load_strategy()

    st.subheader("Strategy")
    st.caption(
        "Rendered from data/knowledge_base/nabil_strategy.md, the same file Setup Review "
        "quotes from. Editing that file updates both."
    )

    headline = _headline(sections)
    if headline:
        st.markdown(f'<div class="ct-rule">{headline}</div>', unsafe_allow_html=True)

    theme.chips([
        ("Min RR intraday", f"{MIN_RR_INTRADAY:g}:1"),
        ("Min RR scalp", "2:1"),
        ("Score &lt;60", "no trade"),
        ("Score 60-74", "half size"),
        ("Score 75+", "full size"),
        ("Sections", str(len(sections))),
    ])
    st.caption("Thresholds above are the ones the advisor's rule checks enforce.")

    query = st.text_input(
        "Filter sections",
        placeholder="e.g. liquidity, stop, killzone, criterion 2",
        key="strategy_filter",
    ).strip().lower()

    if query:
        matches = [n for n, body in sections.items() if query in body.lower()]
        st.caption(f"{len(matches)} section(s) match.")
        show, expanded = matches, True
    else:
        show, expanded = list(PINNED), False
        st.caption("Showing key sections. Search above, or open the full document below.")

    for number in sorted(show, key=int):
        body = sections.get(number)
        if not body:
            continue
        with st.expander(f"{number}. {titles.get(number, '')}", expanded=expanded):
            st.markdown(body.split("\n", 1)[1] if "\n" in body else body)

    if not query:
        with st.expander("Full document", expanded=False):
            st.markdown(raw)
