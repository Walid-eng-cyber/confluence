from __future__ import annotations

import streamlit as st

LONG = "#3fb950"
SHORT = "#f85149"
FLAT = "#8b949e"
ACCENT = "#f0b429"

_CSS = """
<style>
:root {
  --ct-long: #3fb950;
  --ct-short: #f85149;
  --ct-flat: #8b949e;
  --ct-accent: #f0b429;
  --ct-border: #30363d;
}

/* Numbers read as instrument data, not prose. */
[data-testid="stMetricValue"] {
  font-family: "SFMono-Regular", "JetBrains Mono", Consolas, monospace;
  font-size: 1.55rem;
  font-variant-numeric: tabular-nums;
}
[data-testid="stMetricLabel"] {
  text-transform: uppercase;
  letter-spacing: .06em;
  font-size: .7rem;
  color: var(--ct-flat);
}
[data-testid="stMetric"] {
  background: #161b22;
  border: 1px solid var(--ct-border);
  border-radius: 8px;
  padding: .75rem .9rem;
}

div[data-testid="stDataFrame"] { border: 1px solid var(--ct-border); border-radius: 8px; }

.stTabs [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--ct-border); }
.stTabs [data-baseweb="tab"] {
  padding: .5rem 1rem;
  font-weight: 600;
  letter-spacing: .02em;
}
.stTabs [aria-selected="true"] { color: var(--ct-accent); }

.ct-tape {
  display: flex; flex-wrap: wrap; gap: .5rem;
  margin: .25rem 0 1rem 0;
}
.ct-chip {
  font-family: "SFMono-Regular", Consolas, monospace;
  font-size: .78rem;
  padding: .28rem .6rem;
  border-radius: 999px;
  border: 1px solid var(--ct-border);
  background: #161b22;
  color: #c9d1d9;
  white-space: nowrap;
}
.ct-chip b { color: var(--ct-accent); font-weight: 600; }
.ct-long  { color: var(--ct-long); }
.ct-short { color: var(--ct-short); }
.ct-flat  { color: var(--ct-flat); }

.ct-rule {
  border-left: 3px solid var(--ct-accent);
  background: #161b22;
  padding: .6rem .9rem;
  margin: .35rem 0;
  border-radius: 0 6px 6px 0;
  font-size: .9rem;
}
</style>
"""


def inject() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def chips(items: list[tuple[str, str]]) -> None:
    """Render a compact label/value tape, the way a terminal shows session stats."""
    html = "".join(
        f'<span class="ct-chip">{label} <b>{value}</b></span>' for label, value in items
    )
    st.markdown(f'<div class="ct-tape">{html}</div>', unsafe_allow_html=True)


def r_colour(value: float | None) -> str:
    if value is None:
        return FLAT
    if value > 0:
        return LONG
    if value < 0:
        return SHORT
    return FLAT
