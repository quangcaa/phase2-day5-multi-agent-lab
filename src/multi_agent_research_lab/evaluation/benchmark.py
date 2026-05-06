"""Benchmark for single-agent vs multi-agent with quality scoring."""

import json
import logging
from time import perf_counter
from typing import Callable

from multi_agent_research_lab.core.schemas import BenchmarkMetrics
from multi_agent_research_lab.core.state import ResearchState

logger = logging.getLogger(__name__)

Runner = Callable[[str], ResearchState]


def _estimate_cost_from_state(state: ResearchState) -> float:
    """Sum up cost_usd from all agent results in the state."""

    total = 0.0
    for result in state.agent_results:
        cost = result.metadata.get("cost_usd")
        if cost is not None:
            total += cost

    # Also check trace events for baseline
    for event in state.trace:
        cost = event.get("payload", {}).get("cost_usd")
        if cost is not None:
            total += cost

    return total


def _compute_quality_score(query: str, state: ResearchState) -> float | None:
    """Use LLM-as-judge to score the final answer quality (0-10).

    Evaluates: relevance, completeness, accuracy, citations, clarity.
    """

    if not state.final_answer:
        return 0.0

    try:
        from multi_agent_research_lab.services.llm_client import LLMClient

        llm = LLMClient()
        system_prompt = (
            "You are a strict quality evaluator. Score the following answer on a scale "
            "of 0 to 10 based on these criteria:\n"
            "- Relevance to the query (0-2)\n"
            "- Completeness and depth (0-2)\n"
            "- Factual accuracy (0-2)\n"
            "- Citation/source usage (0-2)\n"
            "- Clarity and structure (0-2)\n\n"
            "Respond with ONLY a JSON object: "
            '{"score": <number>, "breakdown": {"relevance": <0-2>, "completeness": <0-2>, '
            '"accuracy": <0-2>, "citations": <0-2>, "clarity": <0-2>}, '
            '"justification": "<brief explanation>"}'
        )

        has_sources = len(state.sources) > 0
        user_prompt = (
            f"Query: {query}\n\n"
            f"Answer to evaluate:\n{state.final_answer[:3000]}\n\n"
            f"Number of sources cited: {len(state.sources)}\n"
            f"Has structured research notes: {state.research_notes is not None}\n"
            f"Has analysis: {state.analysis_notes is not None}"
        )

        response = llm.complete(system_prompt, user_prompt)

        # Parse score
        try:
            data = json.loads(response.content.strip())
            score = float(data.get("score", 5.0))
            logger.info(
                "Quality score: %.1f/10 – %s",
                score,
                data.get("justification", "N/A")[:100],
            )
            return min(max(score, 0.0), 10.0)  # Clamp to 0-10
        except (json.JSONDecodeError, ValueError):
            logger.warning("Could not parse quality score, using heuristic")

    except Exception as exc:
        logger.warning("Quality scoring failed: %s – falling back to heuristic", exc)

    # Heuristic fallback
    return _heuristic_quality_score(state)


def _heuristic_quality_score(state: ResearchState) -> float:
    """Simple rule-based quality score as fallback."""

    score = 0.0
    if state.final_answer:
        # Length check (expect ~500 words)
        word_count = len(state.final_answer.split())
        if word_count >= 400:
            score += 2.0
        elif word_count >= 200:
            score += 1.0

        # Has structure (headings, bullets)
        if "#" in state.final_answer or "- " in state.final_answer:
            score += 1.5

        # Has citations
        if "[Source" in state.final_answer or "[source" in state.final_answer:
            score += 2.0

    if state.sources:
        score += min(len(state.sources) * 0.5, 2.0)

    if state.analysis_notes:
        score += 1.5

    if not state.errors:
        score += 1.0

    return min(score, 10.0)


def run_benchmark(run_name: str, query: str, runner: Runner) -> tuple[ResearchState, BenchmarkMetrics]:
    """Measure latency, cost, quality, and return comprehensive metrics."""

    started = perf_counter()
    state = runner(query)
    latency = perf_counter() - started

    cost = _estimate_cost_from_state(state)

    # Quality scoring (LLM-as-judge with heuristic fallback)
    quality = _compute_quality_score(query, state)

    # Citation coverage: count [Source X] references in final answer
    citation_count = 0
    if state.final_answer:
        import re
        citation_count = len(re.findall(r"\[Source\s*\d+\]", state.final_answer, re.IGNORECASE))

    metrics = BenchmarkMetrics(
        run_name=run_name,
        latency_seconds=latency,
        estimated_cost_usd=cost if cost > 0 else None,
        quality_score=quality,
        notes=(
            f"iterations={state.iteration}, "
            f"sources={len(state.sources)}, "
            f"citations={citation_count}, "
            f"errors={len(state.errors)}"
        ),
    )
    return state, metrics
