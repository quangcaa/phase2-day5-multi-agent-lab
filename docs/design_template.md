# Design Template

## Problem

Xây dựng một hệ thống research assistant tự động: nhận câu hỏi nghiên cứu từ người dùng, tìm kiếm thông tin trên web, phân tích nguồn, và viết câu trả lời tổng hợp có trích dẫn (~500 từ). Hệ thống cần hỗ trợ so sánh giữa cách tiếp cận single-agent và multi-agent.

## Why multi-agent?

Single-agent (1 LLM call duy nhất) có các hạn chế sau:

1. **Không có nguồn thực tế**: LLM trả lời từ knowledge sẵn có, không tìm kiếm web → dễ hallucinate, không có citations.
2. **Thiếu chuyên sâu**: Một prompt phải vừa tìm kiếm, vừa phân tích, vừa viết → output thường nông và thiếu cấu trúc.
3. **Không trace được**: Không biết LLM đã "suy nghĩ" gì, khó debug khi output sai.
4. **Không kiểm soát chất lượng**: Không có bước review/validate kết quả.

Multi-agent giải quyết bằng cách chia nhỏ thành các bước chuyên biệt, mỗi agent có responsibility rõ ràng.

## Agent roles

| Agent | Responsibility | Input | Output | Failure mode |
|---|---|---|---|---|
| Supervisor | Quyết định agent tiếp theo (LLM-based routing), enforce max iterations | `ResearchState` hiện tại | Route decision (researcher/analyst/writer/done) | LLM trả format sai → fallback keyword parsing; vượt max_iter → force done |
| Researcher | Tìm kiếm web (Tavily), tổng hợp research notes | Query + max_sources | `state.sources` + `state.research_notes` | Tavily API fail → mock fallback; LLM fail → tenacity retry 3 lần |
| Analyst | Phân tích research notes: key claims, evidence strength, knowledge gaps | `state.research_notes` | `state.analysis_notes` | Không có research_notes → skip + ghi error; LLM fail → retry |
| Writer | Viết final answer ~500 từ có citations từ sources | `research_notes` + `analysis_notes` + `sources` | `state.final_answer` | Không có notes → skip + ghi error; Output quá ngắn → validation warning |

## Shared state

`ResearchState` (Pydantic BaseModel) chứa các fields:

| Field | Type | Lý do cần |
|---|---|---|
| `request` | `ResearchQuery` | Giữ query gốc + config (max_sources, audience) xuyên suốt workflow |
| `iteration` | `int` | Đếm số vòng lặp để enforce max_iterations guardrail |
| `route_history` | `list[str]` | Lịch sử routing để supervisor tránh lặp vô hạn + debug |
| `sources` | `list[SourceDocument]` | Researcher ghi, Writer đọc để tạo citations |
| `research_notes` | `str \| None` | Researcher ghi, Analyst đọc → handoff chính |
| `analysis_notes` | `str \| None` | Analyst ghi, Writer đọc → handoff chính |
| `final_answer` | `str \| None` | Writer ghi, Supervisor kiểm tra để quyết định done |
| `agent_results` | `list[AgentResult]` | Mỗi agent ghi kết quả + metadata (tokens, cost) → dùng cho benchmark |
| `trace` | `list[dict]` | Ghi trace events cho mỗi bước → dùng cho observability |
| `errors` | `list[str]` | Thu thập lỗi không-fatal thay vì crash → dùng cho failure analysis |

## Routing policy

```
START → Supervisor
Supervisor → Researcher   (nếu research_notes == None)
Supervisor → Analyst       (nếu analysis_notes == None)
Supervisor → Writer        (nếu final_answer == None)
Supervisor → END           (nếu final_answer != None HOẶC iteration >= max_iterations)

Researcher → Supervisor
Analyst    → Supervisor
Writer     → Supervisor
```

Supervisor sử dụng **LLM-based routing**: gửi state summary cho LLM, LLM trả JSON `{"next": "...", "reason": "..."}`. Nếu LLM trả format sai, fallback sang keyword matching.

## Guardrails

- **Max iterations**: 6 (configurable qua `MAX_ITERATIONS` env var). Supervisor force `done` khi đạt limit.
- **Timeout**: 60s workflow-level timeout (configurable qua `TIMEOUT_SECONDS`). Dùng `threading.Timer`.
- **Retry**: `tenacity` retry 3 lần với exponential backoff (1s → 2s → 4s) cho mọi LLM call.
- **Fallback**: (1) Supervisor JSON parse fail → keyword fallback. (2) Tavily API fail → mock search. (3) Agent crash → `_safe_run()` try/except, ghi error, tiếp tục workflow.
- **Validation**: Kiểm tra output length tối thiểu (research_notes ≥ 20 chars, analysis_notes ≥ 20 chars, final_answer ≥ 50 chars).

## Benchmark plan

| Query | Metric đo | Expected outcome |
|---|---|---|
| "Research GraphRAG state-of-the-art and write a 500-word summary" | Latency, Cost, Quality (0-10), Citations | Multi-agent chậm hơn ~3-4x, đắt hơn ~4-5x, quality cao hơn ~2-3 điểm |
| "Compare single-agent and multi-agent workflows for customer support" | Latency, Cost, Quality, Citations | Tương tự pattern trên |
| "Summarize production guardrails for LLM agents" | Latency, Cost, Quality, Citations | Tương tự pattern trên |

**Metrics thu thập:**
- **Latency**: `perf_counter()` wall-clock time
- **Cost**: Tổng `cost_usd` từ tất cả agent_results (tính theo pricing gpt-4o-mini)
- **Quality**: LLM-as-judge scoring (5 tiêu chí: relevance, completeness, accuracy, citations, clarity) + heuristic fallback
- **Citation coverage**: `re.findall(r"\[Source\s*\d+\]")` trong final_answer
- **Failure rate**: `len(state.errors)` / tổng queries
