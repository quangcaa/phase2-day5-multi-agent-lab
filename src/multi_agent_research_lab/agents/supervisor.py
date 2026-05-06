"""Supervisor / router with LLM-based decision making."""

import json
import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

ROUTING_SYSTEM_PROMPT = """\
You are a research project supervisor. Your job is to decide which agent should \
work next based on the current state of the research project.

Available agents:
- researcher: Searches the web and collects source documents and research notes.
- analyst: Analyzes the research notes, extracts key claims, compares viewpoints.
- writer: Writes a polished final answer from the research and analysis notes.
- done: All work is complete.

Rules:
1. If there are no research_notes yet, route to "researcher".
2. If there are research_notes but no analysis_notes, route to "analyst".
3. If there are analysis_notes but no final_answer, route to "writer".
4. If there is a final_answer, route to "done".
5. Never route to the same agent more than 2 times consecutively.
6. Always respond with ONLY a JSON object: {"next": "<agent_name>", "reason": "<brief explanation>"}
"""


def _build_state_summary(state: ResearchState) -> str:
    """Build a concise summary of current state for the LLM."""

    parts = [
        f"Query: {state.request.query}",
        f"Iteration: {state.iteration}",
        f"Route history: {state.route_history}",
        f"Has research_notes: {state.research_notes is not None}",
        f"Has analysis_notes: {state.analysis_notes is not None}",
        f"Has final_answer: {state.final_answer is not None}",
        f"Number of sources: {len(state.sources)}",
        f"Errors: {state.errors}",
    ]
    return "\n".join(parts)


class SupervisorAgent(BaseAgent):
    """Decides which worker should run next and when to stop."""

    name = "supervisor"

    def __init__(self) -> None:
        self._llm = LLMClient()
        self._settings = get_settings()

    def run(self, state: ResearchState) -> ResearchState:
        """Use LLM to decide the next route and update state."""

        # Guardrail: max iterations
        if state.iteration >= self._settings.max_iterations:
            logger.warning("Max iterations (%d) reached – forcing done", self._settings.max_iterations)
            state.record_route("done")
            if state.final_answer is None:
                state.final_answer = (
                    "Research could not be completed within the maximum number of iterations. "
                    f"Partial notes: {state.research_notes or 'N/A'}"
                )
            state.add_trace_event("supervisor", {"action": "force_done", "reason": "max_iterations"})
            return state

        # Ask LLM for routing decision
        state_summary = _build_state_summary(state)
        response = self._llm.complete(ROUTING_SYSTEM_PROMPT, state_summary)

        # Parse routing decision
        next_agent = self._parse_route(response.content)
        reason = self._parse_reason(response.content)

        logger.info("Supervisor decision: next=%s reason=%s", next_agent, reason)

        state.record_route(next_agent)
        state.agent_results.append(
            AgentResult(
                agent=AgentName.SUPERVISOR,
                content=f"Route to {next_agent}: {reason}",
                metadata={
                    "next_agent": next_agent,
                    "reason": reason,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("supervisor", {"next": next_agent, "reason": reason})
        return state

    @staticmethod
    def _parse_route(content: str) -> str:
        """Extract the 'next' field from LLM JSON response with fallback."""

        try:
            data = json.loads(content.strip())
            route = data.get("next", "done")
            if route in ("researcher", "analyst", "writer", "done"):
                return route
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: look for known keywords
        lower = content.lower()
        for keyword in ("researcher", "analyst", "writer", "done"):
            if keyword in lower:
                return keyword
        return "done"

    @staticmethod
    def _parse_reason(content: str) -> str:
        """Extract the 'reason' field from LLM JSON response."""

        try:
            data = json.loads(content.strip())
            return data.get("reason", "no reason provided")
        except (json.JSONDecodeError, AttributeError):
            return content[:200]
