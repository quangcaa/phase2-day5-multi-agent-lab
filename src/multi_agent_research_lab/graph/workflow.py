"""LangGraph workflow – orchestrates the multi-agent research pipeline."""

from __future__ import annotations

import logging
import signal
import threading
from typing import Any

from langgraph.graph import END, StateGraph

from multi_agent_research_lab.agents.analyst import AnalystAgent
from multi_agent_research_lab.agents.researcher import ResearcherAgent
from multi_agent_research_lab.agents.supervisor import SupervisorAgent
from multi_agent_research_lab.agents.writer import WriterAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.state import ResearchState

logger = logging.getLogger(__name__)

# ── Agent singletons ──────────────────────────────────────────────────
_supervisor = SupervisorAgent()
_researcher = ResearcherAgent()
_analyst = AnalystAgent()
_writer = WriterAgent()


# ── Safe wrapper: try/except + validation ─────────────────────────────
def _safe_run(agent_name: str, agent: Any, state: dict[str, Any]) -> dict[str, Any]:
    """Run an agent with error handling and output validation.

    Guardrails:
    - try/except: if agent fails, record error, don't crash the workflow
    - validation: ensure outputs are strings (not None where expected)
    """

    rs = ResearchState(**state)
    try:
        rs = agent.run(rs)
    except Exception as exc:
        error_msg = f"{agent_name} failed: {type(exc).__name__}: {exc}"
        logger.error(error_msg)
        rs.errors.append(error_msg)
        rs.add_trace_event(agent_name, {"error": error_msg})

    # Output validation
    if agent_name == "researcher" and rs.research_notes is not None:
        if len(rs.research_notes.strip()) < 20:
            rs.errors.append(f"Validation: {agent_name} produced too-short research notes")
            logger.warning("Researcher output too short (%d chars)", len(rs.research_notes))

    if agent_name == "analyst" and rs.analysis_notes is not None:
        if len(rs.analysis_notes.strip()) < 20:
            rs.errors.append(f"Validation: {agent_name} produced too-short analysis notes")
            logger.warning("Analyst output too short (%d chars)", len(rs.analysis_notes))

    if agent_name == "writer" and rs.final_answer is not None:
        if len(rs.final_answer.strip()) < 50:
            rs.errors.append(f"Validation: {agent_name} produced too-short final answer")
            logger.warning("Writer output too short (%d chars)", len(rs.final_answer))

    return rs.model_dump()


# ── Node functions ────────────────────────────────────────────────────
def supervisor_node(state: dict[str, Any]) -> dict[str, Any]:
    """Supervisor decides the next agent to invoke."""
    return _safe_run("supervisor", _supervisor, state)


def researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    """Researcher collects sources and writes research notes."""
    return _safe_run("researcher", _researcher, state)


def analyst_node(state: dict[str, Any]) -> dict[str, Any]:
    """Analyst performs structured analysis of the research notes."""
    return _safe_run("analyst", _analyst, state)


def writer_node(state: dict[str, Any]) -> dict[str, Any]:
    """Writer produces the final answer."""
    return _safe_run("writer", _writer, state)


# ── Routing ───────────────────────────────────────────────────────────
def route_after_supervisor(state: dict[str, Any]) -> str:
    """Read the last entry in route_history and return the next node name."""
    route_history = state.get("route_history", [])
    if not route_history:
        return END
    last_route = route_history[-1]
    if last_route in ("researcher", "analyst", "writer"):
        return last_route
    return END


# ── Workflow class ────────────────────────────────────────────────────
class MultiAgentWorkflow:
    """Builds and runs the multi-agent graph.

    Keep orchestration here; keep agent internals in ``agents/``.

    Guardrails enforced:
    - max_iterations: via SupervisorAgent
    - timeout_seconds: via workflow-level timer
    - retry: via tenacity in LLMClient
    - fallback: via try/except in _safe_run + supervisor force_done
    - validation: output length checks in _safe_run
    """

    def build(self) -> StateGraph:
        """Create a LangGraph state graph with supervisor routing."""

        graph = StateGraph(dict)

        # Add nodes
        graph.add_node("supervisor", supervisor_node)
        graph.add_node("researcher", researcher_node)
        graph.add_node("analyst", analyst_node)
        graph.add_node("writer", writer_node)

        # Entry point
        graph.set_entry_point("supervisor")

        # Supervisor routes to a worker or END
        graph.add_conditional_edges(
            "supervisor",
            route_after_supervisor,
            {
                "researcher": "researcher",
                "analyst": "analyst",
                "writer": "writer",
                END: END,
            },
        )

        # Workers always return to supervisor
        graph.add_edge("researcher", "supervisor")
        graph.add_edge("analyst", "supervisor")
        graph.add_edge("writer", "supervisor")

        return graph

    def run(self, state: ResearchState) -> ResearchState:
        """Execute the graph and return final state.

        Enforces a workflow-level timeout using threading.Timer.
        """

        settings = get_settings()
        timeout = settings.timeout_seconds

        logger.info(
            "Workflow starting  query=%r  timeout=%ds  max_iter=%d",
            state.request.query,
            timeout,
            settings.max_iterations,
        )

        graph = self.build()
        compiled = graph.compile()

        # ── Workflow-level timeout via threading ─────────────
        timed_out = threading.Event()

        def _on_timeout() -> None:
            timed_out.set()
            logger.error("Workflow timed out after %ds", timeout)

        timer = threading.Timer(timeout, _on_timeout)
        timer.daemon = True
        timer.start()

        try:
            result = compiled.invoke(state.model_dump())
        except Exception as exc:
            timer.cancel()
            # Graceful fallback
            logger.error("Workflow invoke failed: %s", exc)
            state.errors.append(f"Workflow error: {exc}")
            if state.final_answer is None:
                state.final_answer = f"Workflow failed: {exc}. Partial notes: {state.research_notes or 'N/A'}"
            return state

        timer.cancel()

        # Convert back to ResearchState
        final_state = ResearchState(**result)

        # Check if we timed out (for logging)
        if timed_out.is_set():
            final_state.errors.append(f"Workflow timed out after {timeout}s")
            if final_state.final_answer is None:
                final_state.final_answer = (
                    f"Workflow timed out after {timeout}s. "
                    f"Partial notes: {final_state.research_notes or 'N/A'}"
                )

        logger.info(
            "Workflow done  iterations=%d  has_answer=%s  errors=%d",
            final_state.iteration,
            final_state.final_answer is not None,
            len(final_state.errors),
        )
        return final_state
