# Answer Composer Agent

## Vị trí

`backend/agents/answer_composer/`

## Nhiệm vụ

Agent này là nơi LLM provider được gọi.

Nó chỉ chạy sau khi:

```text
router -> tool/retriever -> source check
```

Không dùng nó để đoán khi thiếu source khóa học.

## Input

```text
route
question
evidence
```

## Output

```text
answer_summary
reasoning_summary
checklist
unknown_note
citations
```

