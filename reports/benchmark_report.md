# Benchmark Report

**Query**: "Research GraphRAG state-of-the-art and write a 500-word summary"

**LangSmith Trace**: https://smith.langchain.com/public/797e3a36-18db-452c-9dc7-1eddd2a69f82/r

**Failure Mode Analysis**: See [`docs/failure_mode_analysis.md`](../docs/failure_mode_analysis.md)

## Summary Table

| Run | Latency (s) | Cost (USD) | Quality (0-10) | Notes |
|---|---:|---:|---:|---|
| baseline | 12.75 | $0.0004 | 6.0 | iterations=0, sources=0, citations=0, errors=0 |
| multi-agent | 47.33 | $0.0021 | 8.0 | iterations=4, sources=5, citations=12, errors=0 |

## Comparative Analysis

- **Latency**: Multi-agent is **3.7x** slower than baseline
- **Cost**: Multi-agent costs **5.1x** more than baseline
- **Quality**: Multi-agent scored **+2.0** points higher (8.0 vs 6.0)

## Trade-off Analysis

| Aspect | Single-Agent (Baseline) | Multi-Agent | Winner |
|---|---|---|---|
| Speed | 12.75s | 47.33s | Baseline |
| Cost | $0.0004 | $0.0021 | Baseline |
| Quality | 6.0 | 8.0 | Multi-Agent |

## Recommendations

**Use Single-Agent when:**
- Speed is the top priority
- Budget is constrained
- The query is simple and doesn't require multi-step reasoning

**Use Multi-Agent when:**
- Quality and depth matter more than speed
- The task requires search, analysis, and synthesis as distinct steps
- You need citations and structured evidence-based answers
- Traceability and explainability are important
