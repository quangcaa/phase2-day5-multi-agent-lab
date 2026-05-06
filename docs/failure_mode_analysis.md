# Failure Mode Analysis

## Trace link

- **LangSmith Public Trace**: https://smith.langchain.com/public/797e3a36-18db-452c-9dc7-1eddd2a69f82/r

## Các failure mode đã xác định và cách xử lý

### 1. LLM trả format JSON sai (Supervisor routing)

**Mô tả**: Supervisor yêu cầu LLM trả `{"next": "researcher", "reason": "..."}` nhưng đôi khi LLM trả plain text hoặc JSON không hợp lệ.

**Cách fix**: Thêm keyword fallback parsing. Nếu `json.loads()` fail, scan nội dung response tìm keyword `researcher`, `analyst`, `writer`, `done`. Nếu không tìm thấy keyword nào → mặc định route `done`.

**Code**: `supervisor.py` → `_parse_route()` method.

---

### 2. Tavily API timeout / rate limit

**Mô tả**: Tavily search có thể fail do network issues, rate limit, hoặc invalid API key.

**Cách fix**: `SearchClient` kiểm tra `tavily_api_key` lúc init. Nếu không có key hoặc API call fail → trả về mock results để workflow vẫn tiếp tục được.

**Code**: `search_client.py` → `_mock_search()` fallback.

---

### 3. Agent crash giữa chừng

**Mô tả**: Bất kỳ agent nào (Researcher, Analyst, Writer) có thể crash do LLM timeout, invalid response, hoặc bug logic.

**Cách fix**: Mọi agent node trong workflow đều được wrap bởi `_safe_run()` — một try/except handler ghi lỗi vào `state.errors` thay vì crash toàn bộ workflow. Supervisor vẫn tiếp tục routing.

**Code**: `workflow.py` → `_safe_run()` function.

---

### 4. Vòng lặp vô hạn (infinite loop)

**Mô tả**: Nếu supervisor liên tục route cùng một agent (ví dụ: researcher → supervisor → researcher → ...), workflow sẽ chạy mãi.

**Cách fix**: 
- **Max iterations**: Supervisor kiểm tra `state.iteration >= max_iterations` (mặc định 6) → force `done`.
- **Workflow timeout**: `threading.Timer` giới hạn tổng thời gian chạy (mặc định 60s).

**Code**: `supervisor.py` → guardrail check ở đầu `run()`. `workflow.py` → `threading.Timer` trong `run()`.

---

### 5. Output validation fail

**Mô tả**: Agent có thể trả về content rỗng hoặc quá ngắn (ví dụ: LLM trả "I don't know").

**Cách fix**: `_safe_run()` kiểm tra output length tối thiểu:
- `research_notes` ≥ 20 ký tự
- `analysis_notes` ≥ 20 ký tự  
- `final_answer` ≥ 50 ký tự

Nếu quá ngắn → ghi warning vào `state.errors`.

---

### 6. OpenAI API rate limit / timeout

**Mô tả**: Khi gọi nhiều LLM call liên tục (4 agent × 1-2 calls/agent), có thể bị rate limit.

**Cách fix**: `LLMClient` sử dụng `tenacity` retry với exponential backoff: retry tối đa 3 lần, chờ 1s → 2s → 4s giữa các lần retry.

**Code**: `llm_client.py` → `@retry` decorator.

## Tổng kết

| Failure mode | Guardrail | Severity |
|---|---|---|
| LLM format sai | Keyword fallback parsing | Low |
| Search API fail | Mock search fallback | Low |
| Agent crash | try/except + error logging | Medium |
| Infinite loop | max_iterations + timeout | High |
| Output quá ngắn | Length validation | Low |
| LLM rate limit | Tenacity retry 3x | Medium |
