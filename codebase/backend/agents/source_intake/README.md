# Source Intake Agent

## Vị trí

`backend/agents/source_intake/`

## Nhiệm vụ

Agent này nhận tài liệu đầu vào và biến thành source có thể search.

Nó xử lý:

- pasted text;
- GitHub repo/file link;
- PDF link;
- web link.

Git/PDF hiện là adapter chờ teammate cắm tool thật.

## Input

```text
source_raw
```

## Output

```text
source_type
source_status
chunks
metadata
```

