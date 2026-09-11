"""Generate a period report from the trade log (Epic E).

Usage:
    python scripts/run_report.py [--period day|week|month] [--anchor YYYY-MM-DD] [--stats-only]
    python scripts/run_report.py --start YYYY-MM-DD --end YYYY-MM-DD
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.graphs.report_graph import build_report_graph, build_runtime
from app.services.trade_stats import format_report_findings, period_bounds
from app.services.trade_store import connect, fetch_by_date_range


def _arg(argv: list[str], name: str, default: str | None = None) -> str | None:
    if name in argv and argv.index(name) + 1 < len(argv):
        return argv[argv.index(name) + 1]
    return default


def main(argv: list[str]) -> int:
    start = _arg(argv, "--start")
    end = _arg(argv, "--end")

    if not (start and end):
        period = _arg(argv, "--period", "month")
        anchor_raw = _arg(argv, "--anchor")
        anchor = date.fromisoformat(anchor_raw) if anchor_raw else date.today()
        try:
            start, end = period_bounds(period, anchor)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2

    conn = connect()
    try:
        trades = fetch_by_date_range(conn, start, end)
    finally:
        conn.close()

    if not trades:
        print(f"No trades logged between {start} and {end}.")
        return 0

    print(format_report_findings(trades, start, end))

    if "--stats-only" in argv:
        return 0

    final = build_report_graph(build_runtime()).invoke({"start_date": start, "end_date": end})
    print("\n\n=== WRITTEN REPORT ===\n")
    print(final["narrative"])

    ungrounded = final.get("ungrounded_numbers") or []
    if ungrounded:
        print("\n[WARNING] numbers not present in the computed findings: " + ", ".join(ungrounded))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv))
