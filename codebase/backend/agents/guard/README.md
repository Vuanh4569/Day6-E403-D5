# Guard / Refusal Agent

## Vị trí

`backend/agents/guard/`

## Nhiệm vụ

Agent này quyết định khi nào không được trả lời chắc.

Nó chặn:

- course-grounded question nhưng thiếu source khóa học;
- source đã load nhưng không tìm thấy evidence liên quan;
- program operations không có source chính thức;
- source conflict/outdated risk;
- user yêu cầu agent đoán.

## Output

```text
refusal
unknown_note
suggested_follow_up
```

