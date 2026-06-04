# Agents Folder

Folder này tách rõ từng role của hệ thống. Mỗi agent có:

- `README.md`: giải thích vị trí, nhiệm vụ, input/output.
- `prompt.md`: prompt/policy chi tiết gồm role, input contract, decision rules, output contract, examples.
- `agent.py`: logic tối thiểu của role đó.

## Flow tổng thể

```text
LearningOSAgent orchestrator
  -> Intake Router Agent
       route = course_grounded | general_learning | program_operations | ambiguous

  -> Source Intake Agent
       load GitHub/PDF/web/text source
       chunk tài liệu

  -> Retriever Agent
       tìm evidence liên quan

  -> Guard Agent
       chặn đoán khi thiếu source/rule nội bộ

  -> Answer Composer Agent
       nhận toàn bộ route/tool/evidence/guard context
       gọi OpenAI/Groq/Gemini để viết câu trả lời cuối cùng
```

## Agent ownership

| Agent folder | Có LLM không? | Có tool không? | Nhiệm vụ |
|---|---|---|---|
| `intake_router/` | Có thể, hiện rule-based | Không | Route câu hỏi. |
| `source_intake/` | Không | Có | Nhận source và chunk. |
| `retriever/` | Không | Có thể thay bằng vector search | Tìm evidence. |
| `guard/` | Có thể, hiện rule-based | Không | Refusal/unknown policy. |
| `answer_composer/` | Có | Không trực tiếp | Viết answer từ evidence. |

Điểm quan trọng: `answer_composer` không được chạy nếu `guard` đã xác định thiếu source.

## Prompt quality rules

Các prompt đã được thiết kế để agent chạy theo contract:

- Router trả route, reason, missing_info, next_agent.
- Source Intake trả source_status và chunks có metadata.
- Retriever trả selected_chunks và source_status.
- Guard trả allow_answer/refusal/required_user_action.
- Answer Composer là final reasoning layer, tổng hợp context nhưng không vượt evidence.

Nếu muốn tối ưu tiếp, ưu tiên tối ưu prompt theo thứ tự:

1. `guard/prompt.md` để giảm hallucination.
2. `answer_composer/prompt.md` để câu trả lời rõ và có sources.
3. `intake_router/prompt.md` để route đúng.
4. `retriever/prompt.md` để evidence chính xác hơn.
5. `source_intake/prompt.md` để metadata nhất quán hơn.
