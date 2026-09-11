from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from app.graphs.setup_review_graph import build_runtime, build_setup_review_graph


_GRAPH_CACHE: Any | None = None


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
    two_sided_case: str


def _get_graph() -> Any:
    """Compile the graph once per process; model warmup is part of that cost."""
    global _GRAPH_CACHE

    if _GRAPH_CACHE is None:
        _GRAPH_CACHE = build_setup_review_graph(build_runtime())
    return _GRAPH_CACHE


def run_setup_review(setup_description: str, strategy_id: str | None = None) -> ReviewResult:
    graph = _get_graph()

    started = time.perf_counter()
    final = graph.invoke({
        "setup_description": setup_description,
        "strategy_id": strategy_id,
    })
    runtime_sec = round(time.perf_counter() - started, 2)

    items = [
        ReviewItem(kind="FACT", item=item, status=status, output=output)
        for status, item, output in final["fact_results"]
    ]
    items.extend(
        ReviewItem(kind="UNKNOWN", item=item, status=status, output=output)
        for status, item, output in final["unknown_results"]
    )

    return ReviewResult(
        runtime_sec=runtime_sec,
        stage1_raw=final["stage1_raw"],
        items=items,
        stage3_verdict=final["stage3_verdict"],
        two_sided_case=final["two_sided_case"],
    )
