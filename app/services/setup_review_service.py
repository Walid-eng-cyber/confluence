from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib.util
import sys
import time
from types import ModuleType

from langchain_ollama import ChatOllama


_MODULE_CACHE: ModuleType | None = None


@dataclass
class ReviewItem:
    kind: str
    item: str
    status: str
    output: str


@dataclass
class ReviewResult:
    runtime_sec: float
    stage1_raw: str
    items: list[ReviewItem]
    stage3_verdict: str



def _load_poc_module() -> ModuleType:
    global _MODULE_CACHE

    if _MODULE_CACHE is not None:
        return _MODULE_CACHE

    script_path = Path(__file__).resolve().parents[2] / "scripts" / "setup_review_poc.py"
    spec = importlib.util.spec_from_file_location("setup_review_poc", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _MODULE_CACHE = module
    return module



def run_setup_review(setup_description: str) -> ReviewResult:
    poc = _load_poc_module()

    started = time.perf_counter()

    strategy_text = poc.STRATEGY_PATH.read_text(encoding="utf-8")
    sections = poc.extract_sections(strategy_text)

    effective_match_model = poc._resolve_match_model()

    llm_restate = ChatOllama(
        base_url=poc.OLLAMA_BASE_URL,
        model=poc.OLLAMA_RESTATE_MODEL,
        temperature=0.1,
        num_ctx=poc.OLLAMA_NUM_CTX_RESTATE,
    )
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

    stage1_raw = poc.restate_facts(llm_restate, setup_description)
    facts, unknowns = poc.parse_restate_output(stage1_raw)

    items: list[ReviewItem] = []
    fact_results: list[tuple[str, str, str]] = []
    unknown_results: list[tuple[str, str, str]] = []

    for fact in facts:
        status, output = poc.match_one_fact(
            llm_match,
            sections,
            fact,
            llm_on_length_retry=llm_match_retry,
            llm_for_ctx=llm_for_ctx,
            llm_on_length_retry_for_ctx=llm_retry_for_ctx,
        )
        fact_results.append((status, fact, output))
        items.append(ReviewItem(kind="FACT", item=fact, status=status, output=output))

    for unknown in unknowns:
        status, output = poc.match_one_unknown(
            llm_match,
            sections,
            unknown,
            llm_on_length_retry=llm_match_retry,
            llm_for_ctx=llm_for_ctx,
            llm_on_length_retry_for_ctx=llm_retry_for_ctx,
        )
        unknown_results.append((status, unknown, output))
        items.append(ReviewItem(kind="UNKNOWN", item=unknown, status=status, output=output))

    stage3_verdict = poc.build_stage3_verdict(fact_results, unknown_results)

    runtime_sec = round(time.perf_counter() - started, 2)
    return ReviewResult(
        runtime_sec=runtime_sec,
        stage1_raw=stage1_raw,
        items=items,
        stage3_verdict=stage3_verdict,
    )
