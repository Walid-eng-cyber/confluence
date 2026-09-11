"""One-off backfill of the Trade Ledger export into the SQLite trade store (C2).

Deliberately not a general-purpose journal parser (that is C4). It targets the column
layout of the Trade Ledger export and validates its own parse against the workbook's
Summary sheet before writing anything.

Usage:
    python scripts/import_trade_ledger.py <path-to-xlsx> [--dry-run] [--strategy <id>]

Trades are attributed to the default strategy unless --strategy names another one.
"""
from __future__ import annotations

import re
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.trade import Trade, outcome_from_r
from app.services.strategy_registry import default_strategy_id, strategy_ids
from app.services.trade_store import connect, count_trades, init_schema, replace_source

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SOURCE = "trade_ledger_export"

HEADER_TO_FIELD = {
    "Date": "trade_date",
    "Instrument": "instrument",
    "Direction": "direction",
    "Daily Bias": "daily_bias",
    "Regime": "regime",
    "Entry": "entry_price",
    "Stop": "stop_price",
    "Planned Target": "target_price",
    "Planned RR": "rr_planned",
    "Realized R": "rr_achieved",
    "Score /100": "score",
    "Size": "size",
    "Criterion 2 Met": "criterion_2_met",
    "Label": "labels",
    "Notes": "notes",
}


def _column_index(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for char in letters:
        n = n * 26 + (ord(char) - ord("A") + 1)
    return n - 1


def _serial_to_date(value: str) -> str:
    return (datetime(1899, 12, 30) + timedelta(days=float(value))).strftime("%Y-%m-%d")


def read_sheets(path: Path) -> dict[str, list[list[str]]]:
    """Read an .xlsx into {sheet name: rows of cell strings} using only the stdlib."""
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{NS}t"))
                      for si in root.findall(f"{NS}si")]

        date_styles: set[int] = set()
        if "xl/styles.xml" in archive.namelist():
            styles = ET.fromstring(archive.read("xl/styles.xml"))
            custom = {int(n.get("numFmtId")): n.get("formatCode") for n in styles.iter(f"{NS}numFmt")}
            cell_xfs = styles.find(f"{NS}cellXfs")
            if cell_xfs is not None:
                for idx, xf in enumerate(cell_xfs.findall(f"{NS}xf")):
                    fmt_id = int(xf.get("numFmtId", "0"))
                    code = custom.get(fmt_id, "")
                    if fmt_id in range(14, 23) or (code and re.search(r"[dmyY]", code)):
                        date_styles.add(idx)

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        names = [s.get("name") for s in workbook.iter(f"{NS}sheet")]

        sheets: dict[str, list[list[str]]] = {}
        for index, name in enumerate(names, start=1):
            entry = f"xl/worksheets/sheet{index}.xml"
            if entry not in archive.namelist():
                continue

            rows: list[list[str]] = []
            for row in ET.fromstring(archive.read(entry)).iter(f"{NS}row"):
                cells: dict[int, str] = {}
                for cell in row.findall(f"{NS}c"):
                    cell_type = cell.get("t", "n")
                    style = int(cell.get("s", "0"))
                    value_el = cell.find(f"{NS}v")
                    inline_el = cell.find(f"{NS}is")

                    if cell_type == "s" and value_el is not None:
                        value = shared[int(value_el.text)]
                    elif cell_type == "inlineStr" and inline_el is not None:
                        value = "".join(t.text or "" for t in inline_el.iter(f"{NS}t"))
                    elif value_el is None:
                        value = ""
                    else:
                        value = value_el.text or ""
                        if cell_type == "n" and style in date_styles and value:
                            value = _serial_to_date(value)

                    cells[_column_index(cell.get("r", "A1"))] = value.strip()

                width = (max(cells) + 1) if cells else 0
                rows.append([cells.get(i, "") for i in range(width)])

            sheets[name] = rows
    return sheets


def _text(value: str) -> str | None:
    return value or None


def _number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: str) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _leading_word(value: str, allowed: set[str]) -> str | None:
    """Take the first recognised word, so 'Bullish, messy (Weekly bearish)' -> bullish."""
    for word in re.findall(r"[A-Za-z]+", value.lower()):
        if word in allowed:
            return word
    return None


def _labels(value: str) -> str | None:
    return None if value in {"", "-"} else value


def parse_trades(rows: list[list[str]], strategy_id: str) -> list[Trade]:
    header_index = next(i for i, row in enumerate(rows) if row and row[0] == "Date")
    header = rows[header_index]
    position = {name: idx for idx, name in enumerate(header) if name in HEADER_TO_FIELD}

    missing = set(HEADER_TO_FIELD) - set(position)
    if missing:
        raise ValueError(f"Export is missing expected column(s): {sorted(missing)}")

    def cell(row: list[str], header_name: str) -> str:
        idx = position[header_name]
        return row[idx] if idx < len(row) else ""

    trades: list[Trade] = []
    for row in rows[header_index + 1:]:
        if not row or not cell(row, "Date") or not cell(row, "Instrument"):
            continue

        rr_achieved = _number(cell(row, "Realized R"))
        rr_planned = _number(cell(row, "Planned RR"))

        trades.append(
            Trade(
                trade_date=cell(row, "Date"),
                instrument=cell(row, "Instrument"),
                outcome=outcome_from_r(rr_achieved),
                direction=_leading_word(cell(row, "Direction"), {"long", "short"}),
                daily_bias=_leading_word(cell(row, "Daily Bias"), {"bullish", "bearish", "neutral"}),
                daily_bias_raw=_text(cell(row, "Daily Bias")),
                regime=_leading_word(cell(row, "Regime"), {"continuation", "pullback", "range"}),
                regime_raw=_text(cell(row, "Regime")),
                entry_price=_number(cell(row, "Entry")),
                stop_price=_number(cell(row, "Stop")),
                target_price=_number(cell(row, "Planned Target")),
                # Spreadsheet-computed RR carries float noise (3.92428785607199); the ledger
                # notes themselves quote these to two places.
                rr_planned=round(rr_planned, 2) if rr_planned is not None else None,
                rr_achieved=rr_achieved,
                score=_integer(cell(row, "Score /100")),
                size=_leading_word(cell(row, "Size"), {"full", "half", "quarter"}),
                criterion_2_met=_text(cell(row, "Criterion 2 Met")),
                labels=_labels(cell(row, "Label")),
                notes=_text(cell(row, "Notes")),
                source=SOURCE,
                strategy_id=strategy_id,
            )
        )
    return trades


def parse_summary(rows: list[list[str]]) -> dict[str, float]:
    wanted = {
        "Total resolved trades": "resolved",
        "Wins": "wins",
        "Losses": "losses",
        "Breakeven": "breakeven",
        "Net R": "net_r",
        "Open trades (unresolved)": "open",
    }
    found: dict[str, float] = {}
    for row in rows:
        if len(row) >= 2 and row[0] in wanted:
            value = _number(row[1])
            if value is not None:
                found[wanted[row[0]]] = value
    return found


def verify_against_summary(trades: list[Trade], summary: dict[str, float]) -> list[str]:
    """Cross-check the parse against the workbook's own totals."""
    resolved = [t for t in trades if t.outcome != "open"]
    computed = {
        "resolved": len(resolved),
        "wins": sum(1 for t in resolved if t.outcome == "win"),
        "losses": sum(1 for t in resolved if t.outcome == "loss"),
        "breakeven": sum(1 for t in resolved if t.outcome == "breakeven"),
        "net_r": round(sum(t.rr_achieved or 0.0 for t in resolved), 2),
        "open": sum(1 for t in trades if t.outcome == "open"),
    }

    problems: list[str] = []
    for key, expected in summary.items():
        actual = computed[key]
        if abs(actual - expected) > 0.01:
            problems.append(f"{key}: parsed {actual}, summary sheet says {expected}")

    print("Parse vs Summary sheet:")
    for key in ("resolved", "wins", "losses", "breakeven", "net_r", "open"):
        expected = summary.get(key)
        flag = "OK" if key not in summary or abs(computed[key] - expected) <= 0.01 else "MISMATCH"
        print(f"  {key:<10} parsed={computed[key]:<8} summary={expected} [{flag}]")

    return problems


def main(argv: list[str]) -> int:
    flags = {"--dry-run", "--strategy"}
    args = [a for a in argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in argv

    strategy_id = default_strategy_id()
    if "--strategy" in argv:
        index = argv.index("--strategy") + 1
        if index >= len(argv):
            print("--strategy needs a strategy id", file=sys.stderr)
            return 2
        strategy_id = argv[index]
        args = [a for a in args if a != strategy_id]
        if strategy_id not in strategy_ids():
            print(f"Unknown strategy {strategy_id!r}; known: {strategy_ids()}", file=sys.stderr)
            return 2

    if not args:
        print(__doc__)
        return 2

    path = Path(args[0]).expanduser()
    if not path.exists():
        print(f"No such file: {path}", file=sys.stderr)
        return 2

    sheets = read_sheets(path)
    if "Trade Log" not in sheets:
        print(f"Expected a 'Trade Log' sheet, found: {list(sheets)}", file=sys.stderr)
        return 2

    trades = parse_trades(sheets["Trade Log"], strategy_id)
    print(f"Parsed {len(trades)} trades from {path.name}, attributed to '{strategy_id}'\n")

    summary = parse_summary(sheets.get("Summary", []))
    problems = verify_against_summary(trades, summary) if summary else []
    if not summary:
        print("  (no Summary sheet found - skipping cross-check)")

    if problems:
        print("\nRefusing to import, parse disagrees with the workbook:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    if dry_run:
        print("\n--dry-run: nothing written.")
        return 0

    conn = connect()
    try:
        init_schema(conn)
        written = replace_source(conn, SOURCE, trades)
        total = count_trades(conn)
    finally:
        conn.close()

    print(f"\nImported {written} trades (source='{SOURCE}'). Store now holds {total}.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main(sys.argv))
