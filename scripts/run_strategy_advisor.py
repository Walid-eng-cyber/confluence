"""Run the Strategy Advisor over the logged trades (Epic F).

Usage:
    python scripts/run_strategy_advisor.py [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--stats-only]
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.graphs.strategy_advisor_graph import build_runtime, build_strategy_advisor_graph
from app.services.trade_stats import compute_strategy_stats, evaluate_rule_flags, format_findings
from app.services.trade_store import connect, fetch_by_date_range


def _arg(argv: list[str], name: str, default: str) -> str:
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def main(argv: list[str]) -> int:
    start = _arg(argv, "--start", "1900-01-01")
    end = _arg(argv, "--end", "2999-12-31")

    if "--stats-only" in argv:
        conn = connect()
        try:
            trades = fetch_by_date_range(conn, start, end)
        finally:
            conn.close()
        print(format_findings(compute_strategy_stats(trades), evaluate_rule_flags(trades)))
        return 0

    graph = build_strategy_advisor_graph(build_runtime())
    final = graph.invoke({"start_date": start, "end_date": end})

    print(final["findings"])
    print("\n\n=== ADVISOR NARRATIVE ===\n")
    print(final["narrative"])

    ungrounded = final.get("ungrounded_numbers") or []
    if ungrounded:
        print("\n[WARNING] numbers in the narrative that are not in the computed findings: "
              + ", ".join(ungrounded))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv))
