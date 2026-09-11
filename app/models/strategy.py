from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StrategyConfig:
    """Everything the pipeline needs to evaluate setups against one strategy.

    The pipeline used to hardcode one strategy's section numbers, keywords and thresholds.
    They live here instead, so adding a strategy is a document plus a config rather than a
    code change.
    """

    id: str
    name: str
    document: Path
    description: str = ""

    # The strategy the app opens on. Never left to sort order.
    is_default: bool = False

    # Topic -> the words that identify it, and the sections that govern it. Routing stays
    # deterministic; only the table is per-strategy.
    keywords: dict[str, list[str]] = field(default_factory=dict)
    routing_map: dict[str, list[str]] = field(default_factory=dict)

    # Section text to drop before prompting, keyed by section number. Used where a section
    # mixes rule definitions with worked examples that attract the model lexically.
    trim_markers: dict[str, str] = field(default_factory=dict)

    # Rule-adherence thresholds. None disables the corresponding check for this strategy.
    min_rr_intraday: float | None = None
    score_no_trade_below: int | None = None
    score_full_size_at: int | None = None

    # Flag code -> the section number that defines that rule in THIS document.
    flag_sections: dict[str, str] = field(default_factory=dict)

    def topics(self) -> list[str]:
        return sorted(set(self.keywords) & set(self.routing_map))


def load_strategy_config(path: Path) -> StrategyConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    required = {"id", "name", "document"}
    missing = required - set(raw)
    if missing:
        raise ValueError(f"{path.name} is missing required field(s): {sorted(missing)}")

    document = Path(raw["document"])
    if not document.is_absolute():
        # Relative to the project root, so configs read the same wherever they are loaded from.
        document = (Path(__file__).resolve().parents[2] / document).resolve()

    keywords = raw.get("keywords", {})
    routing_map = raw.get("routing_map", {})

    unrouted = sorted(set(keywords) - set(routing_map))
    if unrouted:
        raise ValueError(
            f"{path.name}: topic(s) {unrouted} have keywords but no routing_map entry, so "
            "they would never route anywhere"
        )

    return StrategyConfig(
        id=raw["id"],
        name=raw["name"],
        document=document,
        description=raw.get("description", ""),
        is_default=bool(raw.get("default", False)),
        keywords=keywords,
        routing_map=routing_map,
        trim_markers=raw.get("trim_markers", {}),
        min_rr_intraday=raw.get("min_rr_intraday"),
        score_no_trade_below=raw.get("score_no_trade_below"),
        score_full_size_at=raw.get("score_full_size_at"),
        flag_sections=raw.get("flag_sections", {}),
    )
