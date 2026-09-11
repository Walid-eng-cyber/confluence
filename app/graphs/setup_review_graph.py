from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType
from typing import Callable, TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from app.core.pipeline_loader import load_pipeline_module


class SetupReviewState(TypedDict, total=False):
    setup_description: str
    stage1_raw: str
    facts: list[str]
    unknowns: list[str]
    sections: dict[str, str]
    routes: dict[str, list[str]]
    fact_results: list[tuple[str, str, str]]
    unknown_results: list[tuple[str, str, str]]
    stage3_verdict: str
    two_sided_case: str


@dataclass
class SetupReviewRuntime:
    """Model clients shared by every node.

    Deliberately holds no strategy text: sections are re-read per run so edits to
    nabil_strategy.md take effect without restarting the app.
    """

    poc: ModuleType
    llm_restate: ChatOllama
    llm_match: ChatOllama
    llm_match_retry: ChatOllama
    llm_for_ctx: Callable[[int], ChatOllama]
    llm_retry_for_ctx: Callable[[int], ChatOllama]


def build_runtime() -> SetupReviewRuntime:
    poc = load_pipeline_module()

    match_model = poc._resolve_match_model()

    llm_restate = ChatOllama(
        base_url=poc.OLLAMA_BASE_URL,
        model=poc.OLLAMA_RESTATE_MODEL,
        temperature=0.1,
        num_ctx=poc.OLLAMA_NUM_CTX_RESTATE,
    )
    llm_match = ChatOllama(
        base_url=poc.OLLAMA_BASE_URL,
        model=match_model,
        temperature=0.1,
        num_ctx=poc.OLLAMA_NUM_CTX_MATCH,
        num_predict=poc.OLLAMA_MATCH_NUM_PREDICT,
        keep_alive=poc.OLLAMA_MATCH_KEEP_ALIVE,
    )
    llm_match_retry = ChatOllama(
        base_url=poc.OLLAMA_BASE_URL,
        model=match_model,
        temperature=0.1,
        num_ctx=poc.OLLAMA_NUM_CTX_MATCH,
        num_predict=poc.OLLAMA_MATCH_NUM_PREDICT_RETRY,
        keep_alive=poc.OLLAMA_MATCH_KEEP_ALIVE,
    )

    poc.warm_match_model(llm_match)

    cache_base: dict[tuple[int, int], ChatOllama] = {}
    cache_retry: dict[tuple[int, int], ChatOllama] = {}

    def llm_for_ctx(num_ctx: int) -> ChatOllama:
        return poc._build_match_llm(
            model=match_model,
            num_ctx=num_ctx,
            num_predict=poc.OLLAMA_MATCH_NUM_PREDICT,
            cache=cache_base,
        )

    def llm_retry_for_ctx(num_ctx: int) -> ChatOllama:
        return poc._build_match_llm(
            model=match_model,
            num_ctx=num_ctx,
            num_predict=poc.OLLAMA_MATCH_NUM_PREDICT_RETRY,
            cache=cache_retry,
        )

    return SetupReviewRuntime(
        poc=poc,
        llm_restate=llm_restate,
        llm_match=llm_match,
        llm_match_retry=llm_match_retry,
        llm_for_ctx=llm_for_ctx,
        llm_retry_for_ctx=llm_retry_for_ctx,
    )


def build_setup_review_graph(runtime: SetupReviewRuntime):
    """Compile the Setup Review graph: parse -> retrieve -> validate -> recommend."""
    poc = runtime.poc

    def parse_node(state: SetupReviewState) -> SetupReviewState:
        stage1_raw = poc.restate_facts(runtime.llm_restate, state["setup_description"])
        facts, unknowns = poc.parse_restate_output(stage1_raw)
        return {"stage1_raw": stage1_raw, "facts": facts, "unknowns": unknowns}

    def retrieve_node(state: SetupReviewState) -> SetupReviewState:
        sections = poc.extract_sections(poc.STRATEGY_PATH.read_text(encoding="utf-8"))
        items = list(state["facts"]) + list(state["unknowns"])
        return {
            "sections": sections,
            "routes": {item: poc.route(item) for item in items},
        }

    def validate_node(state: SetupReviewState) -> SetupReviewState:
        routes = state["routes"]
        sections = state["sections"]
        fact_results: list[tuple[str, str, str]] = []
        unknown_results: list[tuple[str, str, str]] = []

        for fact in state["facts"]:
            status, output = poc.match_one_fact(
                runtime.llm_match,
                sections,
                fact,
                llm_on_length_retry=runtime.llm_match_retry,
                llm_for_ctx=runtime.llm_for_ctx,
                llm_on_length_retry_for_ctx=runtime.llm_retry_for_ctx,
                section_numbers=routes.get(fact),
            )
            fact_results.append((status, fact, output))

        for unknown in state["unknowns"]:
            status, output = poc.match_one_unknown(
                runtime.llm_match,
                sections,
                unknown,
                llm_on_length_retry=runtime.llm_match_retry,
                llm_for_ctx=runtime.llm_for_ctx,
                llm_on_length_retry_for_ctx=runtime.llm_retry_for_ctx,
                section_numbers=routes.get(unknown),
            )
            unknown_results.append((status, unknown, output))

        return {"fact_results": fact_results, "unknown_results": unknown_results}

    def recommend_node(state: SetupReviewState) -> SetupReviewState:
        fact_results = state["fact_results"]
        unknown_results = state["unknown_results"]
        return {
            "stage3_verdict": poc.build_stage3_verdict(fact_results, unknown_results),
            "two_sided_case": poc.build_two_sided_case(fact_results, unknown_results),
        }

    graph = StateGraph(SetupReviewState)
    graph.add_node("parse", parse_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("validate", validate_node)
    graph.add_node("recommend", recommend_node)

    graph.add_edge(START, "parse")
    graph.add_edge("parse", "retrieve")
    graph.add_edge("retrieve", "validate")
    graph.add_edge("validate", "recommend")
    graph.add_edge("recommend", END)

    return graph.compile()
