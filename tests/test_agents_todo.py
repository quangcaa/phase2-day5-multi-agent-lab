"""Tests for the implemented agents."""

from multi_agent_research_lab.agents import SupervisorAgent
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState


def test_supervisor_routes_to_researcher_first() -> None:
    """Supervisor should route to researcher when no research_notes exist."""

    state = ResearchState(request=ResearchQuery(query="Explain multi-agent systems"))
    result = SupervisorAgent().run(state)

    # Should have recorded a route
    assert len(result.route_history) == 1
    # First route should be researcher (no research_notes yet)
    assert result.route_history[0] == "researcher"
    assert result.iteration == 1


def test_supervisor_respects_max_iterations() -> None:
    """Supervisor should force 'done' when max iterations reached."""

    state = ResearchState(
        request=ResearchQuery(query="Explain multi-agent systems"),
        iteration=6,  # Already at max
    )
    result = SupervisorAgent().run(state)

    assert result.route_history[-1] == "done"
    # Should have a fallback final_answer
    assert result.final_answer is not None
