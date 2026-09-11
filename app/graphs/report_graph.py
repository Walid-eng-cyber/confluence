from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from app.core.grounding import find_ungrounded_numbers
from app.core.pipeline_loader import load_pipeline_module
from app.models.trade import Trade
from app.services.trade_stats import format_report_findings
from app.services.strategy_registry import get_strategy
from app.services.trade_store import connect, fetch_by_date_range

OLLAMA_NUM_CTX_REPORT = int(os.getenv("OLLAMA_NUM_CTX_REPORT", "4096"))
OLLAMA_REPORT_NUM_PREDICT = int(os.getenv("OLLAMA_REPORT_NUM_PREDICT", "768"))
OLLAMA_REPORT_KEEP_ALIVE = os.getenv("OLLAMA_REPORT_KEEP_ALIVE", "10m")

NARRATE_PROMPT = """/no_think

You are writing a trading period report for the trader whose results these are. The numbers \
below were computed from their trade log. Your job is to read them back clearly, not to \
re-derive them.

Rules:
- Use ONLY numbers that appear in COMPUTED FINDINGS. Do not calculate, estimate or recall \
any other number.
- Do not infer a cause for a result. Say what happened, not why, unless the findings say why.
- Where a segment is marked INCONCLUSIVE, say it is not yet decidable.
- Where a check is marked NOT CHECKABLE, say what would have to be logged to enable it.
- Do not give advice on any individual open position.

Answer with exactly these three headings:

THE PERIOD
<2-4 sentences: activity, result, and how planned RR compared with realised>

WHAT STANDS OUT
<2-4 bullet points, each tied to a number from the findings>

RULE ADHERENCE
<one line per breach, or state that none of the checkable rules were breached>

=== COMPUTED FINDINGS ===
{findings}
"""


class ReportState(TypedDict, total=False):
    strategy_id: str
    start_date: str
    end_date: str
    trades: list[Trade]
    findings: str
    narrative: str
    ungrounded_numbers: list[str]


@dataclass
class ReportRuntime:
    llm: ChatOllama


def _resolve_report_model() -> str:
    poc = load_pipeline_module()
    configured = os.getenv("OLLAMA_REPORT_MODEL")
    installed = poc._list_installed_ollama_models()

    if configured and (not installed or configured in installed):
        return configured
    return poc._resolve_match_model()


def build_runtime() -> ReportRuntime:
    poc = load_pipeline_module()
    return ReportRuntime(
        llm=ChatOllama(
            base_url=poc.OLLAMA_BASE_URL,
            model=_resolve_report_model(),
            temperature=0.1,
            num_ctx=OLLAMA_NUM_CTX_REPORT,
            num_predict=OLLAMA_REPORT_NUM_PREDICT,
            keep_alive=OLLAMA_REPORT_KEEP_ALIVE,
        )
    )


def build_report_graph(runtime: ReportRuntime):
    """Compile the Report graph: fetch -> compute -> narrate.

    No retrieve step: a period report is grounded in the trade log, not the rulebook. The
    strategy only enters through the rule-breach flags, which already name their sections.
    """

    def fetch_node(state: ReportState) -> ReportState:
        conn = connect()
        try:
            trades = fetch_by_date_range(
                conn,
                state["start_date"],
                state["end_date"],
                strategy_id=get_strategy(state.get("strategy_id")).id,
            )
        finally:
            conn.close()
        return {"trades": trades}

    def compute_node(state: ReportState) -> ReportState:
        return {
            "findings": format_report_findings(
                state["trades"],
                state["start_date"],
                state["end_date"],
                get_strategy(state.get("strategy_id")),
            )
        }

    def narrate_node(state: ReportState) -> ReportState:
        if not state["trades"]:
            return {
                "narrative": "No trades were logged in this period.",
                "ungrounded_numbers": [],
            }

        prompt = NARRATE_PROMPT.format(findings=state["findings"])
        try:
            response = runtime.llm.invoke([HumanMessage(content=prompt)])
            poc = load_pipeline_module()
            narrative = poc._sanitize_model_text(response.content).strip()
        except Exception as exc:
            return {
                "narrative": f"NARRATION FAILED: {exc!r}\n\nThe computed findings stand on their own.",
                "ungrounded_numbers": [],
            }

        return {
            "narrative": narrative,
            "ungrounded_numbers": find_ungrounded_numbers(narrative, state["findings"]),
        }

    graph = StateGraph(ReportState)
    graph.add_node("fetch", fetch_node)
    graph.add_node("compute", compute_node)
    graph.add_node("narrate", narrate_node)

    graph.add_edge(START, "fetch")
    graph.add_edge("fetch", "compute")
    graph.add_edge("compute", "narrate")
    graph.add_edge("narrate", END)

    return graph.compile()
