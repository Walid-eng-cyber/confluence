from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from app.models.strategy import StrategyConfig, load_strategy_config

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STRATEGY_DIR = PROJECT_ROOT / "data" / "strategies"


@lru_cache(maxsize=1)
def _configs() -> dict[str, StrategyConfig]:
    if not STRATEGY_DIR.exists():
        return {}

    found: dict[str, StrategyConfig] = {}
    for path in sorted(STRATEGY_DIR.glob("*.json")):
        config = load_strategy_config(path)
        if config.id in found:
            raise ValueError(f"Duplicate strategy id {config.id!r} in {path.name}")
        found[config.id] = config
    return found


def reload() -> None:
    """Drop the cache, so a strategy added on disk is picked up without a restart."""
    _configs.cache_clear()


def list_strategies() -> list[StrategyConfig]:
    return sorted(_configs().values(), key=lambda c: c.name)


def strategy_ids() -> list[str]:
    return [config.id for config in list_strategies()]


def default_strategy_id() -> str:
    """Resolution order: DEFAULT_STRATEGY_ID, then the config marked default, then first.

    Alphabetical order must never decide this: adding a reference strategy whose name sorts
    earlier would silently switch the app away from the trader's own rules.
    """
    available = _configs()
    if not available:
        raise RuntimeError(f"No strategy configs found in {STRATEGY_DIR}")

    configured = os.getenv("DEFAULT_STRATEGY_ID")
    if configured and configured in available:
        return configured

    flagged = [config.id for config in list_strategies() if config.is_default]
    if flagged:
        return flagged[0]

    return list_strategies()[0].id


def get_strategy(strategy_id: str | None = None) -> StrategyConfig:
    available = _configs()
    if not available:
        raise RuntimeError(f"No strategy configs found in {STRATEGY_DIR}")

    wanted = strategy_id or default_strategy_id()
    if wanted not in available:
        raise KeyError(f"Unknown strategy {wanted!r}; registered: {sorted(available)}")
    return available[wanted]
