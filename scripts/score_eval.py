from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.ground_truth import GROUND_TRUTH_ITEMS


def _load_poc_module():
    script_path = PROJECT_ROOT / "scripts" / "setup_review_poc.py"
    spec = importlib.util.spec_from_file_location("setup_review_poc", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _is_heading_like(quote: str | None) -> bool:
    if not quote:
        return False
    q = quote.strip()
    if not q:
        return False
    if q.startswith("#"):
        return True
    if q.endswith(":"):
        return True
    return False


def _row_hit(
    poc,
    expected_quote: str | None,
    acceptable_quotes: tuple[str, ...] | None,
    returned_quote: str | None,
) -> bool:
    if expected_quote is None and not acceptable_quotes:
        return returned_quote in (None, "N/A", "NOT COVERED")
    if returned_quote is None:
        return False

    normalized_returned = poc._normalize(returned_quote)
    candidates = list(acceptable_quotes or ())
    if expected_quote:
        candidates.append(expected_quote)

    normalized_candidates = {poc._normalize(c) for c in candidates}
    return normalized_returned in normalized_candidates


def main() -> int:
    parser = argparse.ArgumentParser(description="Score eval JSON from eval_match.py")
    parser.add_argument("json_path", type=Path, help="Path to run_<timestamp>.json")
    parser.add_argument("--save", type=Path, default=None, help="Optional path to save printed table")
    args = parser.parse_args()

    payload = json.loads(args.json_path.read_text(encoding="utf-8"))
    records = payload["records"]

    poc = _load_poc_module()
    gt_by_id = {item.item_id: item for item in GROUND_TRUTH_ITEMS}

    by_item: dict[str, list[dict]] = {}
    for rec in records:
        by_item.setdefault(rec["item_id"], []).append(rec)

    lines: list[str] = []
    header = "item | section hit | row hit | unverified | heading quotes"
    lines.append(header)
    lines.append("-" * len(header))

    total_records = 0
    total_section_hit = 0
    total_row_hit = 0
    total_unverified = 0
    total_heading = 0

    for item_id, item_records in by_item.items():
        item_records = sorted(item_records, key=lambda r: r["attempt"])
        attempts = len(item_records)

        section_hit = 0
        row_hit = 0
        unverified = 0
        heading_quotes = 0

        for rec in item_records:
            total_records += 1
            expected_section = rec["expected_section"]
            returned_section = rec["returned_section"]
            expected_quote = rec["expected_quote"]
            returned_quote = rec["returned_quote"]
            verified = bool(rec["verified"])
            gt_item = gt_by_id.get(rec["item_id"])
            acceptable_quotes = gt_item.acceptable_quotes if gt_item is not None else None

            if expected_section == returned_section:
                section_hit += 1
                total_section_hit += 1

            if _row_hit(poc, expected_quote, acceptable_quotes, returned_quote):
                row_hit += 1
                total_row_hit += 1

            if not verified:
                unverified += 1
                total_unverified += 1

            if _is_heading_like(returned_quote):
                heading_quotes += 1
                total_heading += 1

        lines.append(
            f"{item_id} | section hit {section_hit}/{attempts} | row hit {row_hit}/{attempts} | unverified {unverified} | heading quotes {heading_quotes}"
        )

    lines.append("")
    lines.append(f"totals | records {total_records} | section hits {total_section_hit} | row hits {total_row_hit} | unverified {total_unverified} | heading quotes {total_heading}")

    output = "\n".join(lines)
    print(output)

    if args.save is not None:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(output + "\n", encoding="utf-8")
        print(f"SAVED: {args.save}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
