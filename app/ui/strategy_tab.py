from __future__ import annotations

import re

import streamlit as st

from app.core.pipeline_loader import load_pipeline_module
from app.services.strategy_registry import get_strategy
from app.ui import theme


@st.cache_data(show_spinner=False)
def _load_strategy(strategy_id: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """Return (raw text, {number: body}, {number: title}).

    Read from the same file the pipeline reads, so what is displayed cannot drift from
    what is actually evaluated against.
    """
    poc = load_pipeline_module()
    raw = get_strategy(strategy_id).document.read_text(encoding="utf-8")
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


def render(strategy_id: str | None = None) -> None:
    config = get_strategy(strategy_id)
    raw, sections, titles = _load_strategy(config.id)

    st.subheader(config.name)
    if config.description:
        st.caption(config.description)
    st.caption(
        f"Rendered from {config.document.name}, the same file Setup Review quotes from. "
        "Editing that file updates both."
    )

    headline = _headline(sections)
    if headline:
        st.markdown(f'<div class="ct-rule">{headline}</div>', unsafe_allow_html=True)

    chips: list[tuple[str, str]] = []
    if config.min_rr_intraday is not None:
        chips.append(("Min RR", f"{config.min_rr_intraday:g}:1"))
    if config.score_no_trade_below is not None:
        chips.append((f"Score &lt;{config.score_no_trade_below}", "no trade"))
    if config.score_full_size_at is not None:
        chips.append((f"Score {config.score_full_size_at}+", "full size"))
    chips.append(("Sections", str(len(sections))))
    chips.append(("Routed topics", str(len(config.routing_map))))
    theme.chips(chips)
    st.caption("Thresholds above are the ones this strategy's rule checks enforce.")

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
        # The sections this strategy actually routes to — what the pipeline can quote.
        routed = {number for numbers in config.routing_map.values() for number in numbers}
        show, expanded = sorted(routed, key=int), False
        st.caption(
            f"Showing the {len(routed)} sections Setup Review routes to. Search above, or "
            "open the full document below."
        )

    for number in sorted(show, key=int):
        body = sections.get(number)
        if not body:
            continue
        with st.expander(f"{number}. {titles.get(number, '')}", expanded=expanded):
            st.markdown(body.split("\n", 1)[1] if "\n" in body else body)

    if not query:
        with st.expander("Full document", expanded=False):
            st.markdown(raw)
