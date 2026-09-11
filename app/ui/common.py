from __future__ import annotations

import streamlit as st

from app.models.strategy import StrategyConfig
from app.services.trade_store import connect, count_trades, init_schema


def empty_state(config: StrategyConfig, noun: str) -> None:
    """Explain an empty view honestly.

    An empty store and a strategy with no history yet are different situations, and saying
    so is more useful than one generic message. Trades under other strategies are withheld
    on purpose: blending methodologies would produce a figure that describes neither.
    """
    conn = connect()
    try:
        init_schema(conn)
        total = count_trades(conn)
    finally:
        conn.close()

    if total == 0:
        st.info(
            "No trades in the store yet. Import the ledger export:\n\n"
            "`python scripts/import_trade_ledger.py <path-to-xlsx>`"
        )
        return

    st.info(
        f"**No trades logged under {config.name} yet.** "
        f"The store holds {total} trade(s) under other strategies; they are not shown here, "
        f"because mixing methodologies would produce a {noun} that describes neither.\n\n"
        "To log trades against this strategy:\n\n"
        f"`python scripts/import_trade_ledger.py <path-to-xlsx> --strategy {config.id}`"
    )
