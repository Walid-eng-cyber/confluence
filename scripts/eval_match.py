from __future__ import annotations

import importlib.util
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_ollama import ChatOllama

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


def _extract_section_block(output_text: str, section_number: str) -> str | None:
    pattern = re.compile(
        rf"Section\s+{re.escape(section_number)}:\n(.*?)(?:\n\nSection\s+\d+:|\n\nVerification:|$)",
        re.DOTALL,
    )
    match = pattern.search(output_text)
    if not match:
        return None
    return match.group(1).strip()


def _extract_line_value(text: str, label: str) -> str | None:
    match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.*)$", text)
    if not match:
        return None
    value = match.group(1).strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1].strip()
    return value


def _parse_result_for_expected_section(output_text: str, expected_section: str | None) -> dict[str, Any]:
    overall_status = _extract_line_value(output_text, "Status") or "UNKNOWN"

    if expected_section is None:
        return {
            "returned_section": None,
            "returned_quote": _extract_line_value(output_text, "Quote"),
            "status": overall_status,
            "verified": True,
        }

    block = _extract_section_block(output_text, expected_section)
    if block is None:
        return {
            "returned_section": None,
            "returned_quote": None,
            "status": overall_status,
            "verified": False,
        }

    section_status = _extract_line_value(block, "Status") or overall_status
    section_quote = _extract_line_value(block, "Quote")
    unverified_marker = f'Verification: UNVERIFIED quote in section {expected_section}:'
    verified = unverified_marker not in output_text

    return {
        "returned_section": expected_section,
        "returned_quote": section_quote,
        "status": section_status,
        "verified": verified,
    }


def main() -> int:
    poc = _load_poc_module()

    strategy_text = poc.STRATEGY_PATH.read_text(encoding="utf-8")
    sections = poc.extract_sections(strategy_text)
    effective_match_model = poc._resolve_match_model()

    llm_match = ChatOllama(
        base_url=poc.OLLAMA_BASE_URL,
        model=effective_match_model,
        temperature=0.1,
        num_ctx=poc.OLLAMA_NUM_CTX_MATCH,
        num_predict=poc.OLLAMA_MATCH_NUM_PREDICT,
        keep_alive=poc.OLLAMA_MATCH_KEEP_ALIVE,
    )
    llm_match_retry = ChatOllama(
        base_url=poc.OLLAMA_BASE_URL,
        model=effective_match_model,
        temperature=0.1,
        num_ctx=poc.OLLAMA_NUM_CTX_MATCH,
        num_predict=poc.OLLAMA_MATCH_NUM_PREDICT_RETRY,
        keep_alive=poc.OLLAMA_MATCH_KEEP_ALIVE,
    )

    poc.warm_match_model(llm_match)

    llm_cache_base: dict[tuple[int, int], ChatOllama] = {}
    llm_cache_retry: dict[tuple[int, int], ChatOllama] = {}

    def llm_for_ctx(num_ctx: int):
        return poc._build_match_llm(
            model=effective_match_model,
            num_ctx=num_ctx,
            num_predict=poc.OLLAMA_MATCH_NUM_PREDICT,
            cache=llm_cache_base,
        )

    def llm_retry_for_ctx(num_ctx: int):
        return poc._build_match_llm(
            model=effective_match_model,
            num_ctx=num_ctx,
            num_predict=poc.OLLAMA_MATCH_NUM_PREDICT_RETRY,
            cache=llm_cache_retry,
        )

    default_attempts = 5
    high_signal_attempts = 10
    attempt_plan: dict[str, int] = {
        "unknown_rr": high_signal_attempts,
        "fact_swept_zone_low": high_signal_attempts,
        "fact_h1_pullback_a_grade_demand": high_signal_attempts,
    }
    records: list[dict[str, Any]] = []

    started = time.perf_counter()

    for item in GROUND_TRUTH_ITEMS:
        attempts_for_item = attempt_plan.get(item.item_id, default_attempts)
        for attempt in range(1, attempts_for_item + 1):
            routed_sections = poc.route(item.item_text)

            if item.kind == "FACT":
                status, output = poc.match_one_fact(
                    llm_match,
                    sections,
                    item.item_text,
                    llm_on_length_retry=llm_match_retry,
                    llm_for_ctx=llm_for_ctx,
                    llm_on_length_retry_for_ctx=llm_retry_for_ctx,
                )
            else:
                status, output = poc.match_one_unknown(
                    llm_match,
                    sections,
                    item.item_text,
                    llm_on_length_retry=llm_match_retry,
                    llm_for_ctx=llm_for_ctx,
                    llm_on_length_retry_for_ctx=llm_retry_for_ctx,
                )

            parsed = _parse_result_for_expected_section(output, item.expected_section)

            records.append(
                {
                    "item_id": item.item_id,
                    "kind": item.kind,
                    "item_text": item.item_text,
                    "attempt": attempt,
                    "expected_section": item.expected_section,
                    "expected_quote": item.expected_quote,
                    "routed_sections": routed_sections,
                    "overall_status": status,
                    "returned_section": parsed["returned_section"],
                    "returned_quote": parsed["returned_quote"],
                    "status": parsed["status"],
                    "verified": parsed["verified"],
                }
            )

    elapsed = round(time.perf_counter() - started, 2)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = PROJECT_ROOT / "data" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"run_{timestamp}.json"

    payload = {
        "created_at": datetime.now().isoformat(),
        "attempts_per_item": default_attempts,
        "attempt_plan": attempt_plan,
        "item_count": len(GROUND_TRUTH_ITEMS),
        "record_count": len(records),
        "runtime_sec": elapsed,
        "config": {
            "match_model": effective_match_model,
            "num_ctx_match": poc.OLLAMA_NUM_CTX_MATCH,
            "num_predict": poc.OLLAMA_MATCH_NUM_PREDICT,
            "num_predict_retry": poc.OLLAMA_MATCH_NUM_PREDICT_RETRY,
            "timeout_sec": poc.OLLAMA_MATCH_TIMEOUT_SEC,
            "retries": poc.OLLAMA_RETRIES,
        },
        "records": records,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"WROTE: {out_path}")
    print(f"RECORDS: {len(records)}")
    print(f"RUNTIME_SEC: {elapsed}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
