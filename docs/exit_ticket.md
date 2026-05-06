# Exit Ticket

## 1. Case nào nên dùng multi-agent? Vì sao?

**Nên dùng multi-agent khi task có nhiều bước chuyên biệt cần xử lý tuần tự hoặc song song**, ví dụ:

- **Research tasks phức tạp**: Khi cần tìm kiếm thông tin từ nhiều nguồn (web, database), phân tích, rồi tổng hợp thành báo cáo. Mỗi bước đòi hỏi prompt và kỹ năng khác nhau → chia cho agent chuyên biệt sẽ cho output tốt hơn.

- **Khi cần traceability**: Multi-agent cho phép trace rõ ràng agent nào làm gì, tốn bao nhiêu token, sai ở bước nào. Rất quan trọng cho production systems.

- **Khi quality quan trọng hơn speed**: Benchmark cho thấy multi-agent đạt 8-9/10 quality so với 6/10 của baseline, dù chậm hơn 3-4x.

- **Khi cần citations và evidence-based answers**: Multi-agent có Researcher tìm nguồn thật từ web, Writer trích dẫn → output đáng tin cậy hơn.

**Ví dụ thực tế**: Due diligence reports, competitive analysis, literature reviews, technical documentation.

## 2. Case nào không nên dùng multi-agent? Vì sao?

**Không nên dùng multi-agent khi task đơn giản hoặc khi tốc độ/chi phí là ưu tiên hàng đầu**, ví dụ:

- **Simple Q&A**: "Thủ đô Việt Nam là gì?" — Một LLM call duy nhất là đủ. Thêm agent chỉ tốn thêm token và thời gian vô ích.

- **Chatbot real-time**: Người dùng kỳ vọng response < 2s. Multi-agent mất 30-50s thì UX rất tệ.

- **Budget constrained**: Multi-agent tốn gấp 4-5x chi phí. Nếu chạy hàng triệu queries/ngày, chi phí sẽ rất lớn.

- **Khi không cần external data**: Nếu LLM đã có đủ knowledge để trả lời (ví dụ: code generation, translation), thì Researcher agent là thừa.

- **Khi complexity không justify the overhead**: Theo nguyên tắc "Không thêm agent nếu không có lý do rõ ràng" — nếu single-agent cho output đạt yêu cầu, thêm agent chỉ tạo thêm điểm failure.

**Nguyên tắc**: Bắt đầu với single-agent, benchmark, chỉ chuyển sang multi-agent khi có evidence rõ ràng rằng quality cần cải thiện.
