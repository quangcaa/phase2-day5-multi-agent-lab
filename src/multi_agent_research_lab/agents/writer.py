"""Writer agent – produces the final answer from research and analysis."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

WRITER_SYSTEM_PROMPT = """\
You are a professional technical writer. Your task is to produce a clear, \
well-structured final answer based on research notes and analysis.

Requirements:
- Write approximately 500 words.
- Use clear headings and bullet points where appropriate.
- Include inline citations referencing the sources (e.g., [Source 1]).
- Start with a brief executive summary.
- End with key takeaways or recommendations.
- Tailor the tone and depth for the specified audience.
"""


class WriterAgent(BaseAgent):
    """Produces final answer from research and analysis notes."""

    name = "writer"

    def __init__(self) -> None:
        self._llm = LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate ``state.final_answer``."""

        if not state.research_notes and not state.analysis_notes:
            state.errors.append("Writer: no notes available to write from")
            logger.warning("Writer skipped – no notes")
            return state

        logger.info("Writer starting")

        # Build source references
        source_refs = "\n".join(
            f"[Source {i + 1}] {s.title} – {s.url or 'N/A'}"
            for i, s in enumerate(state.sources)
        )

        user_prompt = (
            f"Query: {state.request.query}\n"
            f"Audience: {state.request.audience}\n\n"
            f"Research Notes:\n{state.research_notes or 'N/A'}\n\n"
            f"Analysis:\n{state.analysis_notes or 'N/A'}\n\n"
            f"Available Sources:\n{source_refs or 'None'}"
        )

        response = self._llm.complete(WRITER_SYSTEM_PROMPT, user_prompt)
        state.final_answer = response.content

        state.agent_results.append(
            AgentResult(
                agent=AgentName.WRITER,
                content=response.content,
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("writer", {"answer_len": len(response.content)})

        logger.info("Writer done  answer_len=%d", len(response.content))
        return state
