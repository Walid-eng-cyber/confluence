from __future__ import annotations

import os
import re
from dataclasses import dataclass
from types import ModuleType
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from app.core.grounding import find_ungrounded_numbers
from app.core.pipeline_loader import load_pipeline_module
from app.models.trade import Trade
from app.services.trade_stats import RuleFlag, compute_strategy_stats, evaluate_rule_flags, format_findings
from app.services.strategy_registry import get_strategy
from app.services.trade_store import connect, fetch_by_date_range

OLLAMA_NUM_CTX_ADVISOR = int(os.getenv("OLLAMA_NUM_CTX_ADVISOR", "4096"))
OLLAMA_ADVISOR_NUM_PREDICT = int(os.getenv("OLLAMA_ADVISOR_NUM_PREDICT", "1024"))
OLLAMA_ADVISOR_KEEP_ALIVE = os.getenv("OLLAMA_ADVISOR_KEEP_ALIVE", "10m")

# Section 20 is the behavioural gap between written rules and actual behaviour, which is
# what rule-adherence flags are evidence of, so it is always in context.
ALWAYS_RETRIEVE_SECTIONS = ("20",)

NARRATE_PROMPT = """/no_think

You are reviewing a trader's own logged results against their written strategy. You are a \
consultant, not a supporter: state what the data shows, including where it contradicts the \
strategy document.

Rules:
- Use ONLY numbers that appear in COMPUTED FINDINGS. Do not calculate, estimate or recall \
any other number.
- Cite the strategy section number for every rule you refer to.
- Where a segment is marked INCONCLUSIVE, say it is not yet decidable instead of drawing a \
conclusion from it.
- Where a check is marked NOT CHECKABLE, say what would have to be logged to enable it.
- Do not give advice on any individual open position.

Answer with exactly these three headings:

WHAT THE NUMBERS SAY
<3-5 sentences>

RULE ADHERENCE
<one line per flag that fired, each citing its section>

NOT YET ANSWERABLE
<what this data cannot settle, and what to log next>

=== COMPUTED FINDINGS ===
{findings}

=== STRATEGY SECTIONS REFERENCED ===
{rule_context}
"""


class AdvisorState(TypedDict, total=False):
    strategy_id: str
    start_date: str
    end_date: str
    trades: list[Trade]
    stats: dict[str, object]
    flags: list[RuleFlag]
    findings: str
    rule_context: str
    narrative: str
    ungrounded_numbers: list[str]


@dataclass
class AdvisorRuntime:
    poc: ModuleType
    llm: ChatOllama


def _resolve_advisor_model(poc: ModuleType) -> str:
    configured = os.getenv("OLLAMA_ADVISOR_MODEL")
    installed = poc._list_installed_ollama_models()

    if configured and (not installed or configured in installed):
        return configured
    return poc._resolve_match_model()


def build_runtime() -> AdvisorRuntime:
    poc = load_pipeline_module()
    model = _resolve_advisor_model(poc)

    llm = ChatOllama(
        base_url=poc.OLLAMA_BASE_URL,
        model=model,
        temperature=0.1,
        num_ctx=OLLAMA_NUM_CTX_ADVISOR,
        num_predict=OLLAMA_ADVISOR_NUM_PREDICT,
        keep_alive=OLLAMA_ADVISOR_KEEP_ALIVE,
    )
    return AdvisorRuntime(poc=poc, llm=llm)


def build_strategy_advisor_graph(runtime: AdvisorRuntime):
    """Compile the Strategy Advisor graph: compute -> retrieve -> narrate."""
    poc = runtime.poc

    def compute_node(state: AdvisorState) -> AdvisorState:
        conn = connect()
        try:
            trades = fetch_by_date_range(
                conn,
                state.get("start_date", "1900-01-01"),
                state.get("end_date", "2999-12-31"),
            )
        finally:
            conn.close()

        config = get_strategy(state.get("strategy_id"))
        stats = compute_strategy_stats(trades, config)
        flags = evaluate_rule_flags(trades, config)
        return {
            "trades": trades,
            "stats": stats,
            "flags": flags,
            "findings": format_findings(stats, flags),
        }

    def retrieve_node(state: AdvisorState) -> AdvisorState:
        config = get_strategy(state.get("strategy_id"))
        sections = poc.extract_sections(config.document.read_text(encoding="utf-8"))

        wanted: list[str] = []
        for flag in state["flags"]:
            if (flag.offenders or not flag.checkable) and flag.section not in wanted:
                wanted.append(flag.section)
        for number in ALWAYS_RETRIEVE_SECTIONS:
            if number not in wanted:
                wanted.append(number)

        blocks = [sections[number] for number in sorted(wanted, key=int) if number in sections]
        return {"rule_context": "\n\n".join(blocks)}

    def narrate_node(state: AdvisorState) -> AdvisorState:
        prompt = NARRATE_PROMPT.format(
            findings=state["findings"],
            rule_context=state["rule_context"],
        )
        try:
            response = runtime.llm.invoke([HumanMessage(content=prompt)])
            narrative = poc._sanitize_model_text(response.content).strip()
        except Exception as exc:
            return {
                "narrative": f"NARRATION FAILED: {exc!r}\n\nThe computed findings above stand on their own.",
                "ungrounded_numbers": [],
            }

        return {
            "narrative": narrative,
            "ungrounded_numbers": find_ungrounded_numbers(narrative, state["findings"]),
        }

    graph = StateGraph(AdvisorState)
    graph.add_node("compute", compute_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("narrate", narrate_node)

    graph.add_edge(START, "compute")
    graph.add_edge("compute", "retrieve")
    graph.add_edge("retrieve", "narrate")
    graph.add_edge("narrate", END)

    return graph.compile()
