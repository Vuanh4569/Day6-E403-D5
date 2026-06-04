# Retriever Agent

## Vị trí

`backend/agents/retriever/`

## Nhiệm vụ

Agent này tìm evidence liên quan từ source đã load hoặc public search result.

Nó không tự viết câu trả lời cuối cùng.

## Input

```text
question
sources/chunks
```

## Output

```text
top_relevant_chunks
source_status
```

