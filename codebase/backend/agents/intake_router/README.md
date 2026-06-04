# Intake Router Agent

## Vị trí

`backend/agents/intake_router/`

## Nhiệm vụ

Agent này là cửa đầu tiên của hệ thống. Nó không trả lời câu hỏi cuối cùng. Nó chỉ quyết định câu hỏi của user thuộc route nào:

- `course_grounded`: hỏi theo slide, lab, rubric, Day05/Day06, khóa học.
- `general_learning`: kiến thức chung có thể search web.
- `program_operations`: deadline, nộp repo, grading, lịch, rule nội bộ.
- `ambiguous`: câu hỏi thiếu ngữ cảnh.

## Input

```text
user_question
conversation_memory
loaded_source_status
```

## Output

```text
route
reason
missing_info
next_agent
```

