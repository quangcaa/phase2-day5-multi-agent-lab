"""Critic agent – optional fact-checking and quality review."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient

logger = logging.getLogger(__name__)

CRITIC_SYSTEM_PROMPT = """\
You are a fact-checker and quality reviewer. Given a final answer and the sources \
it was based on, evaluate its quality.

Check for:
1. **Factual Accuracy**: Are claims supported by the provided sources?
2. **Citation Coverage**: Are all major claims properly cited?
3. **Hallucination Risk**: Are there statements not backed by any source?
4. **Completeness**: Does the answer fully address the original query?
5. **Clarity**: Is the writing clear and well-structured?

Provide a quality score (0-10) and specific feedback.
Format: {"score": <0-10>, "issues": [...], "suggestions": [...]}
"""


class CriticAgent(BaseAgent):
    """Optional fact-checking and safety-review agent."""

    name = "critic"

    def __init__(self) -> None:
        self._llm = LLMClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Validate final answer and append findings."""

        if not state.final_answer:
            state.errors.append("Critic: no final_answer to review")
            logger.warning("Critic skipped – no final_answer")
            return state

        logger.info("Critic starting review")

        source_refs = "\n".join(
            f"[Source {i + 1}] {s.title}: {s.snippet[:100]}"
            for i, s in enumerate(state.sources)
        )

        user_prompt = (
            f"Original query: {state.request.query}\n\n"
            f"Final answer to review:\n{state.final_answer}\n\n"
            f"Sources used:\n{source_refs or 'None'}"
        )

        response = self._llm.complete(CRITIC_SYSTEM_PROMPT, user_prompt)

        state.agent_results.append(
            AgentResult(
                agent=AgentName.CRITIC,
                content=response.content,
                metadata={
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("critic", {"review": response.content[:200]})

        logger.info("Critic done")
        return state
