"""Command-line entrypoint for the lab starter."""

from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from multi_agent_research_lab.core.config import get_settings
from multi_agent_research_lab.core.errors import StudentTodoError
from multi_agent_research_lab.core.schemas import ResearchQuery
from multi_agent_research_lab.core.state import ResearchState
from multi_agent_research_lab.evaluation.benchmark import run_benchmark
from multi_agent_research_lab.evaluation.report import render_markdown_report
from multi_agent_research_lab.graph.workflow import MultiAgentWorkflow
from multi_agent_research_lab.observability.logging import configure_logging
from multi_agent_research_lab.observability.tracing import configure_langsmith_tracing
from multi_agent_research_lab.services.llm_client import LLMClient
from multi_agent_research_lab.services.storage import LocalArtifactStore

app = typer.Typer(help="Multi-Agent Research Lab starter CLI")
console = Console()


def _init() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_langsmith_tracing()


# ── Single-agent baseline runner ─────────────────────────────────────
def _run_baseline(query: str) -> ResearchState:
    """Run a single LLM call as the baseline."""

    llm = LLMClient()
    request = ResearchQuery(query=query)
    state = ResearchState(request=request)

    system_prompt = (
        "You are a research assistant. Given a query, provide a comprehensive, "
        "well-structured research summary of approximately 500 words. "
        "Include key findings, analysis, and conclusions."
    )

    response = llm.complete(system_prompt, query)
    state.final_answer = response.content
    state.add_trace_event("baseline", {
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "cost_usd": response.cost_usd,
    })
    return state


# ── Multi-agent runner ───────────────────────────────────────────────
def _run_multi_agent(query: str) -> ResearchState:
    """Run the full multi-agent workflow."""

    state = ResearchState(request=ResearchQuery(query=query))
    workflow = MultiAgentWorkflow()
    return workflow.run(state)


@app.command()
def baseline(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run a real single-agent baseline with LLM."""

    _init()
    console.print("\n[bold cyan]>> Running Single-Agent Baseline...[/bold cyan]\n")

    state, metrics = run_benchmark("baseline", query, _run_baseline)

    console.print(Panel.fit(state.final_answer or "No answer", title="Single-Agent Baseline"))
    console.print(f"\n[*] Latency: [bold]{metrics.latency_seconds:.2f}s[/bold]")
    if metrics.estimated_cost_usd:
        console.print(f"[$] Cost: [bold]${metrics.estimated_cost_usd:.6f}[/bold]")
    if metrics.quality_score is not None:
        console.print(f"[Q] Quality: [bold]{metrics.quality_score:.1f}/10[/bold]")


@app.command("multi-agent")
def multi_agent(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run the multi-agent workflow."""

    _init()
    console.print("\n[bold cyan]>> Running Multi-Agent Workflow...[/bold cyan]\n")

    try:
        state, metrics = run_benchmark("multi-agent", query, _run_multi_agent)
    except StudentTodoError as exc:
        console.print(Panel.fit(str(exc), title="Expected TODO", style="yellow"))
        raise typer.Exit(code=2) from exc

    console.print(Panel.fit(state.final_answer or "No answer", title="Multi-Agent Result"))
    console.print(f"\n[*] Latency: [bold]{metrics.latency_seconds:.2f}s[/bold]")
    if metrics.estimated_cost_usd:
        console.print(f"[$] Cost: [bold]${metrics.estimated_cost_usd:.6f}[/bold]")
    if metrics.quality_score is not None:
        console.print(f"[Q] Quality: [bold]{metrics.quality_score:.1f}/10[/bold]")
    console.print(f"[~] Iterations: [bold]{state.iteration}[/bold]")
    console.print(f"[#] Sources: [bold]{len(state.sources)}[/bold]")
    if state.errors:
        console.print(f"[!] Errors: [bold red]{len(state.errors)}[/bold red]")
        for err in state.errors:
            console.print(f"    - {err}", style="dim red")


@app.command()
def benchmark(
    query: Annotated[str, typer.Option("--query", "-q", help="Research query")],
) -> None:
    """Run both baseline and multi-agent, then generate a comparison report."""

    _init()
    console.print("\n[bold cyan]>> Running Benchmark Comparison...[/bold cyan]\n")

    # Run baseline
    console.print("[dim]-> Running baseline...[/dim]")
    baseline_state, baseline_metrics = run_benchmark("baseline", query, _run_baseline)
    console.print(f"  [green]OK[/green] Baseline done in {baseline_metrics.latency_seconds:.2f}s")

    # Run multi-agent
    console.print("[dim]-> Running multi-agent...[/dim]")
    multi_state, multi_metrics = run_benchmark("multi-agent", query, _run_multi_agent)
    console.print(f"  [green]OK[/green] Multi-agent done in {multi_metrics.latency_seconds:.2f}s")

    # Generate report
    report = render_markdown_report([baseline_metrics, multi_metrics])
    store = LocalArtifactStore()
    path = store.write_text("benchmark_report.md", report)
    console.print(f"\n[>] Report saved to [bold]{path}[/bold]")

    # Display comparison table
    table = Table(title="Benchmark Comparison")
    table.add_column("Metric", style="cyan")
    table.add_column("Baseline", style="green")
    table.add_column("Multi-Agent", style="magenta")
    table.add_row(
        "Latency",
        f"{baseline_metrics.latency_seconds:.2f}s",
        f"{multi_metrics.latency_seconds:.2f}s",
    )
    table.add_row(
        "Cost",
        f"${baseline_metrics.estimated_cost_usd:.6f}" if baseline_metrics.estimated_cost_usd else "N/A",
        f"${multi_metrics.estimated_cost_usd:.6f}" if multi_metrics.estimated_cost_usd else "N/A",
    )
    table.add_row("Sources", "0", str(len(multi_state.sources)))
    table.add_row("Iterations", "1", str(multi_state.iteration))
    table.add_row(
        "Quality",
        f"{baseline_metrics.quality_score:.1f}/10" if baseline_metrics.quality_score is not None else "N/A",
        f"{multi_metrics.quality_score:.1f}/10" if multi_metrics.quality_score is not None else "N/A",
    )
    console.print(table)


if __name__ == "__main__":
    app()
