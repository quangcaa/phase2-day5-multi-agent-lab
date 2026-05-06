"""Benchmark report rendering with rich analysis."""

from multi_agent_research_lab.core.schemas import BenchmarkMetrics


def render_markdown_report(metrics: list[BenchmarkMetrics]) -> str:
    """Render benchmark metrics to a detailed markdown report."""

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────
    lines.append("# Benchmark Report")
    lines.append("")
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| Run | Latency (s) | Cost (USD) | Quality (0-10) | Notes |")
    lines.append("|---|---:|---:|---:|---|")
    for item in metrics:
        cost = "" if item.estimated_cost_usd is None else f"${item.estimated_cost_usd:.4f}"
        quality = "" if item.quality_score is None else f"{item.quality_score:.1f}"
        lines.append(
            f"| {item.run_name} | {item.latency_seconds:.2f} | {cost} | {quality} | {item.notes} |"
        )

    # ── Analysis section ──────────────────────────────────────────────
    if len(metrics) >= 2:
        baseline = metrics[0]
        multi = metrics[1]

        lines.append("")
        lines.append("## Comparative Analysis")
        lines.append("")

        # Latency comparison
        latency_ratio = multi.latency_seconds / baseline.latency_seconds if baseline.latency_seconds > 0 else 0
        lines.append(f"- **Latency**: Multi-agent is **{latency_ratio:.1f}x** slower than baseline")

        # Cost comparison
        if baseline.estimated_cost_usd and multi.estimated_cost_usd:
            cost_ratio = multi.estimated_cost_usd / baseline.estimated_cost_usd
            lines.append(f"- **Cost**: Multi-agent costs **{cost_ratio:.1f}x** more than baseline")

        # Quality comparison
        if baseline.quality_score is not None and multi.quality_score is not None:
            diff = multi.quality_score - baseline.quality_score
            direction = "higher" if diff > 0 else "lower" if diff < 0 else "equal"
            lines.append(
                f"- **Quality**: Multi-agent scored **{diff:+.1f}** points {direction} "
                f"({multi.quality_score:.1f} vs {baseline.quality_score:.1f})"
            )

        # Trade-off analysis
        lines.append("")
        lines.append("## Trade-off Analysis")
        lines.append("")
        lines.append(
            "| Aspect | Single-Agent (Baseline) | Multi-Agent | Winner |"
        )
        lines.append("|---|---|---|---|")

        # Latency winner
        lat_winner = "Baseline" if baseline.latency_seconds < multi.latency_seconds else "Multi-Agent"
        lines.append(
            f"| Speed | {baseline.latency_seconds:.2f}s | {multi.latency_seconds:.2f}s | {lat_winner} |"
        )

        # Cost winner
        b_cost = f"${baseline.estimated_cost_usd:.4f}" if baseline.estimated_cost_usd else "N/A"
        m_cost = f"${multi.estimated_cost_usd:.4f}" if multi.estimated_cost_usd else "N/A"
        cost_winner = "Baseline" if (baseline.estimated_cost_usd or 999) < (multi.estimated_cost_usd or 999) else "Multi-Agent"
        lines.append(f"| Cost | {b_cost} | {m_cost} | {cost_winner} |")

        # Quality winner
        b_q = f"{baseline.quality_score:.1f}" if baseline.quality_score is not None else "N/A"
        m_q = f"{multi.quality_score:.1f}" if multi.quality_score is not None else "N/A"
        q_winner = "Multi-Agent" if (multi.quality_score or 0) >= (baseline.quality_score or 0) else "Baseline"
        lines.append(f"| Quality | {b_q} | {m_q} | {q_winner} |")

    # ── When to use which ─────────────────────────────────────────────
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    lines.append("**Use Single-Agent when:**")
    lines.append("- Speed is the top priority")
    lines.append("- Budget is constrained")
    lines.append("- The query is simple and doesn't require multi-step reasoning")
    lines.append("")
    lines.append("**Use Multi-Agent when:**")
    lines.append("- Quality and depth matter more than speed")
    lines.append("- The task requires search, analysis, and synthesis as distinct steps")
    lines.append("- You need citations and structured evidence-based answers")
    lines.append("- Traceability and explainability are important")

    return "\n".join(lines) + "\n"
