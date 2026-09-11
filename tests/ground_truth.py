from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundTruthItem:
    item_id: str
    kind: str  # FACT | UNKNOWN
    item_text: str
    expected_section: str | None
    expected_quote: str | None
    acceptable_quotes: tuple[str, ...] | None = None


GROUND_TRUTH_ITEMS: list[GroundTruthItem] = [
    GroundTruthItem(
        item_id="fact_xauusd",
        kind="FACT",
        item_text="XAUUSD",
        expected_section=None,
        expected_quote=None,
    ),
    GroundTruthItem(
        item_id="fact_daily_bias_bullish",
        kind="FACT",
        item_text="Daily bias bullish",
        expected_section="3",
        expected_quote="Higher highs + higher lows = bullish",
        acceptable_quotes=(
            "Higher highs + higher lows = bullish",
        ),
    ),
    GroundTruthItem(
        item_id="fact_hh_hl_intact",
        kind="FACT",
        item_text="Higher highs and higher lows intact",
        expected_section="3",
        expected_quote="Higher highs + higher lows = bullish",
        acceptable_quotes=(
            "Higher highs + higher lows = bullish",
        ),
    ),
    GroundTruthItem(
        item_id="fact_h1_pullback_a_grade_demand",
        kind="FACT",
        item_text="H1 pulled back into an A-grade demand zone",
        expected_section="6",
        expected_quote="| **A — Impulse-origin** | The base of the leg that *created* the move | **Yes** |",
        acceptable_quotes=(
            "| **A — Impulse-origin** | The base of the leg that *created* the move | **Yes** |",
            "A — Impulse-origin | The base of the leg that *created* the move | Yes",
            "The base of the leg that *created* the move",
        ),
    ),
    GroundTruthItem(
        item_id="fact_swept_zone_low",
        kind="FACT",
        item_text="Price just swept the zone's low",
        expected_section="15",
        expected_quote="| Price closes back inside | SWEEP | Original thesis remains alive |",
        acceptable_quotes=(
            "| Price closes back inside | SWEEP | Original thesis remains alive |",
            "Sweep | Body can print through the level, then close back inside | Not classified yet",
            "Price closes back inside | SWEEP | Original thesis remains alive",
            "Body can print through the level, then close back inside | Not classified yet",
        ),
    ),
    GroundTruthItem(
        item_id="fact_reacting_upward",
        kind="FACT",
        item_text="Price is starting to react upward",
        expected_section=None,
        expected_quote=None,
    ),
    GroundTruthItem(
        item_id="fact_no_choch",
        kind="FACT",
        item_text="No CHoCH confirmed yet",
        expected_section="8",
        expected_quote="| Neither | No trade |",
        acceptable_quotes=(
            "| Neither | No trade |",
            "Neither | No trade",
            "M15 CHoCH only, H1 still opposing | Quarter to half size. Log criterion 2 = N.",
        ),
    ),
    GroundTruthItem(
        item_id="unknown_rr",
        kind="UNKNOWN",
        item_text="Risk-reward ratio (RR)",
        expected_section="10",
        expected_quote="| If RR < minimum | Move the entry, never the stop |",
        acceptable_quotes=(
            "| If RR < minimum | Move the entry, never the stop |",
            "If RR < minimum | Move the entry, never the stop",
            "| Minimum RR — intraday | **3 : 1** |",
            "| Minimum RR — scalp | **2 : 1** |",
        ),
    ),
    GroundTruthItem(
        item_id="unknown_pool_taken",
        kind="UNKNOWN",
        item_text="Whether a specific liquidity pool has been taken",
        expected_section="5",
        expected_quote="| Wide session range, untouched, confluent with an HTF level | **Blocking — wait** |",
        acceptable_quotes=(
            "| Wide session range, untouched, confluent with an HTF level | **Blocking — wait** |",
            "Wide session range, untouched, confluent with an HTF level | **Blocking — wait**",
            "| Wide range, untouched, standalone | Medium — reduce size |",
            "| Narrow range, or already partially tagged | Weak — note it, don't skip a sound setup |",
        ),
    ),
    GroundTruthItem(
        item_id="unknown_session_timing",
        kind="UNKNOWN",
        item_text="Session timing",
        expected_section="11",
        expected_quote="Mark Asia H/L **including wicks**, at the Tokyo close, two hours before London.",
        acceptable_quotes=(
            "Mark Asia H/L **including wicks**, at the Tokyo close, two hours before London.",
            "| **Mark Asia H/L** | **07:00** | 01:00 |",
            "| **London killzone** | **09:00 – 11:00** | 03:00 – 05:00 |",
            "| **NY killzone** | **14:30 – 17:00** | 08:30 – 11:00 |",
            "Summer (CEST, UTC+2)",
            "Winter (CET, UTC+1)",
        ),
    ),
    GroundTruthItem(
        item_id="unknown_news_risk",
        kind="UNKNOWN",
        item_text="News risk",
        expected_section="14",
        expected_quote="| 9 | Tier 1 news within 2 hours | No stop survives a release — 02.07 ran $58 past |",
        acceptable_quotes=(
            "| 9 | Tier 1 news within 2 hours | No stop survives a release — 02.07 ran $58 past |",
            "Tier 1 news within 2 hours | No stop survives a release — 02.07 ran $58 past",
        ),
    ),
]
