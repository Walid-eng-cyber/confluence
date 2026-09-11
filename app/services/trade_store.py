from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

from app.models.trade import Trade
from app.services.strategy_registry import default_strategy_id

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY,
    trade_date      TEXT    NOT NULL,
    instrument      TEXT    NOT NULL,
    outcome         TEXT    NOT NULL,
    direction       TEXT,
    daily_bias      TEXT,
    daily_bias_raw  TEXT,
    regime          TEXT,
    regime_raw      TEXT,
    entry_price     REAL,
    stop_price      REAL,
    target_price    REAL,
    rr_planned      REAL,
    rr_achieved     REAL,
    score           INTEGER,
    size            TEXT,
    criterion_2_met TEXT,
    labels          TEXT,
    session         TEXT,
    htf_zone_grade  TEXT,
    entry_model     TEXT,
    sweep_before_fvg INTEGER,
    notes           TEXT,
    source          TEXT    NOT NULL,
    strategy_id     TEXT
);

CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_trades_instrument ON trades(instrument);
CREATE INDEX IF NOT EXISTS idx_trades_outcome ON trades(outcome);
"""

_COLUMNS = (
    "trade_date", "instrument", "outcome", "direction", "daily_bias", "daily_bias_raw",
    "regime", "regime_raw", "entry_price", "stop_price", "target_price", "rr_planned",
    "rr_achieved", "score", "size", "criterion_2_met", "labels", "session",
    "htf_zone_grade", "entry_model", "sweep_before_fvg", "notes", "source",
    "strategy_id",
)

# Columns find_similar may filter on. Fixed whitelist: values are parameterised, names are not.
_SIMILAR_FILTERS = (
    "instrument", "direction", "daily_bias", "regime", "size",
    "criterion_2_met", "htf_zone_grade", "entry_model", "session", "strategy_id",
)


def db_path() -> Path:
    configured = os.getenv("TRADE_DB_PATH", "./data/trades/confluence.db")
    path = Path(configured)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    target = Path(path) if path is not None else db_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a store was first created.

    strategy_id arrived with multi-strategy support. Rows written before it are attributed
    to the default strategy, which is correct: they could not have been logged under any
    other one.
    """
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(trades)")}

    if "strategy_id" not in existing:
        conn.execute("ALTER TABLE trades ADD COLUMN strategy_id TEXT")

    # Indexed here rather than in SCHEMA: on an older store the column does not exist until
    # the ALTER above has run.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_id)")

    conn.execute(
        "UPDATE trades SET strategy_id = ? WHERE strategy_id IS NULL",
        (default_strategy_id(),),
    )


def _to_trade(row: sqlite3.Row) -> Trade:
    return Trade(**{key: row[key] for key in row.keys()})


def replace_source(conn: sqlite3.Connection, source: str, trades: list[Trade]) -> int:
    """Replace every trade from one source, so re-importing never duplicates rows."""
    placeholders = ", ".join("?" for _ in _COLUMNS)
    columns = ", ".join(_COLUMNS)

    with conn:
        conn.execute("DELETE FROM trades WHERE source = ?", (source,))
        conn.executemany(
            f"INSERT INTO trades ({columns}) VALUES ({placeholders})",
            [tuple(getattr(trade, column) for column in _COLUMNS) for trade in trades],
        )
    return len(trades)


def count_trades(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]


def fetch_by_date_range(
    conn: sqlite3.Connection,
    start: str,
    end: str,
    include_open: bool = True,
) -> list[Trade]:
    """Fetch trades with trade_date between start and end, inclusive (ISO yyyy-mm-dd)."""
    sql = "SELECT * FROM trades WHERE trade_date >= ? AND trade_date <= ?"
    params: list[object] = [start, end]

    if not include_open:
        sql += " AND outcome != 'open'"

    sql += " ORDER BY trade_date, id"
    return [_to_trade(row) for row in conn.execute(sql, params)]


def find_similar(
    conn: sqlite3.Connection,
    include_open: bool = False,
    limit: int = 10,
    **filters: object,
) -> list[Trade]:
    """Fetch past trades matching the supplied dimensions.

    Plain SQL filtering, not vector search. Only non-None filters are applied, so a caller
    that knows the instrument and regime but not the zone grade still gets a useful answer
    instead of nothing.
    """
    unknown = set(filters) - set(_SIMILAR_FILTERS)
    if unknown:
        raise ValueError(f"Unsupported filter(s): {sorted(unknown)}")

    sql = "SELECT * FROM trades WHERE 1=1"
    params: list[object] = []

    for column in _SIMILAR_FILTERS:
        value = filters.get(column)
        if value is not None:
            sql += f" AND {column} = ?"
            params.append(value)

    if not include_open:
        sql += " AND outcome != 'open'"

    sql += " ORDER BY trade_date DESC, id DESC LIMIT ?"
    params.append(limit)

    return [_to_trade(row) for row in conn.execute(sql, params)]
