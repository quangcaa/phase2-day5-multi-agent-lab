"""Researcher agent – collects sources and creates research notes."""

import logging

from multi_agent_research_lab.agents.base import BaseAgent
from multi_agent_research_lab.core.schemas import AgentName, AgentResult
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.search_client import SearchClient

logger = logging.getLogger(__name__)

RESEARCHER_SYSTEM_PROMPT = """\
You are a research specialist. Given a query and search results, create well-organized \
research notes that capture the most important information.

Guidelines:
- Summarize key findings from each source.
- Include source references (e.g., [Source 1], [Source 2]).
- Organize notes by theme or subtopic.
- Flag any conflicting information between sources.
- Keep notes concise but thorough (300-500 words).
"""


class ResearcherAgent(BaseAgent):
    """Collects sources and creates concise research notes."""

    name = "researcher"

    def __init__(self) -> None:
        self._llm = LLMClient()
        self._search = SearchClient()

    def run(self, state: ResearchState) -> ResearchState:
        """Populate ``state.sources`` and ``state.research_notes``."""

        logger.info("Researcher starting  query=%r", state.request.query)

        # Step 1: Search for sources
        sources = self._search.search(state.request.query, max_results=state.request.max_sources)
        state.sources.extend(sources)

        # Step 2: Format sources for LLM
        source_text = "\n\n".join(
            f"[Source {i + 1}] {s.title}\nURL: {s.url or 'N/A'}\n{s.snippet}"
            for i, s in enumerate(sources)
        )

        user_prompt = (
            f"Research query: {state.request.query}\n"
            f"Target audience: {state.request.audience}\n\n"
            f"Search results:\n{source_text}"
        )

        # Step 3: Generate research notes
        response = self._llm.complete(RESEARCHER_SYSTEM_PROMPT, user_prompt)
        state.research_notes = response.content

        state.agent_results.append(
            AgentResult(
                agent=AgentName.RESEARCHER,
                content=response.content,
                metadata={
                    "sources_found": len(sources),
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost_usd": response.cost_usd,
                },
            )
        )
        state.add_trace_event("researcher", {"sources_found": len(sources)})

        logger.info("Researcher done  sources=%d  notes_len=%d", len(sources), len(response.content))
        return state
