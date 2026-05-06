"""Analyst agent – turns research notes into structured insights."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

ANALYST_SYSTEM_PROMPT = """\
You are a critical analyst. Given research notes, perform a structured analysis.

Your analysis must include:
1. **Key Claims**: List the main claims or findings (numbered).
2. **Evidence Strength**: Rate each claim as Strong / Moderate / Weak with justification.
3. **Conflicting Viewpoints**: Note any contradictions between sources.
4. **Knowledge Gaps**: Identify areas that need more research.
5. **Synthesis**: Provide a brief overall assessment (2-3 sentences).

Be objective, precise, and cite source references where applicable.
"""


class AnalystAgent(BaseAgent):
    """Turns research notes into structured insights."""

    name = "analyst"

    def __init__(self) -> None:
        self._llm = LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate ``state.analysis_notes``."""

        if not state.research_notes:
            state.errors.append("Analyst: no research_notes available to analyze")
            logger.warning("Analyst skipped – no research_notes")
            return state

        logger.info("Analyst starting  notes_len=%d", len(state.research_notes))

        user_prompt = (
            f"Query: {state.request.query}\n"
            f"Audience: {state.request.audience}\n\n"
            f"Research Notes:\n{state.research_notes}"
        )

        response = self._llm.complete(ANALYST_SYSTEM_PROMPT, user_prompt)
        state.analysis_notes = response.content

        state.agent_results.append(
            AgentResult(
                agent=AgentName.ANALYST,
                content=response.content,
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("analyst", {"analysis_len": len(response.content)})

        logger.info("Analyst done  analysis_len=%d", len(response.content))
        return state
