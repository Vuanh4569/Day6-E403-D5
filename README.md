# Day 06 - 2A202600802 - Phạm Đình Phúc

## Idea

**Learning Content Intake Agent** cho học viên AI Thực Chiến / AI in Action hỏi về nội dung bài học, khái niệm, lab, rubric, ví dụ, hoặc cách áp dụng kiến thức vào bài làm.

Painpoint: tài liệu học nằm rải rác ở public repo, README, slide, rubric, notebook, PDF/link và ghi chú mentor. Nếu user hỏi mơ hồ hoặc hỏi một khái niệm khó, agent phải biết khi nào cần hỏi thêm, khi nào đi search/crawl ngay, khi nào nói không biết vì thiếu source. Prototype tập trung vào Learning Content, không đoán deadline/rule nội bộ nếu không có source chính thức.

## Cấu trúc nộp bài

```text
Day6-E403-D5
├── 01-invidual-workshop/
│   └── app-teardown.md
├── 02-group-spec/
│   ├── evidence-pack.md
│   ├── thin-spec.md
│   ├── workflow.md
│   └── README.md
├── prototype/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── backend/
    ├── agents/
    │   ├── intake_router/
    │   │   ├── agent.py
    │   │   ├── prompt.md
    │   │   └── README.md
    │   ├── source_intake/
    │   ├── retriever/
    │   ├── answer_composer/
    │   └── guard/
    ├── learning_agent.py
    ├── server.py
    ├── run_demo.py
    └── requirements.txt
```

## Prototype

Mở `prototype/index.html` trong browser để demo:

- user paste source text, GitHub link, PDF link hoặc web link,
- agent detect source type và chuẩn bị source ingestion,
- user hỏi trong chat,
- nếu là kiến thức chung, agent dùng Tavily/public search flow rồi tổng hợp reasoning,
- nếu là câu hỏi bám theo bài học/slide/lab, agent yêu cầu source khóa học nếu chưa có,
- nếu đã có source khóa học, agent retrieve chunk rồi trả explanation + example + checklist,
- agent từ chối/unknown khi thiếu nguồn hoặc user hỏi sang deadline/rule nội bộ.

## Tool plan cho bản build

```text
Tavily:
  - search public web / docs / GitHub public pages nếu cần.

GitHub reader:
  - khi user paste repo/file link, đọc README/docs/rubric/notebook markdown trước.

PDF reader:
  - khi user paste PDF link/file, extract text theo page rồi chunk.
  - nếu PDF scan ảnh thì báo cần OCR hoặc user paste text.

GitHub:
  - `GITHUB_TOKEN` là optional, chỉ dùng để tăng rate limit khi đọc public repo.
```

## Prototype adapter contract

`prototype/app.js` đã có sẵn 3 adapter để cắm tool thật:

```js
window.learningAgentAdapters = {
  tavilySearch: async (query) => [
    { title: "Source title", url: "https://...", snippet: "Relevant snippet" }
  ],
  readGitHub: async (url) => ({
    status: "loaded",
    title: "GitHub source title",
    text: "README/docs/rubric/notebook text",
    note: "Optional note"
  }),
  readPdf: async (url) => ({
    status: "loaded",
    title: "PDF title",
    text: "Extracted text by pages/sections",
    note: "Optional note"
  })
};
```

Nếu chưa cắm tool thật, app dùng mock/stub để demo được route, ask loop, source check, answer và refusal.

## LangChain backend

Backend nằm trong `backend/`. Core chính là `LearningOSAgent`:

- route câu hỏi thành `course_grounded`, `general_learning`, `program_operations`, hoặc `ambiguous`;
- dùng LangChain-style tools cho Tavily, GitHub reader, PDF reader, web reader;
- nếu máy chưa cài LangChain, code có fallback để vẫn chạy demo;
- khi cài `requirements.txt`, có thể thay stub Git/PDF bằng tool thật của teammate.

## Agent architecture

Agent orchestrator nằm ở [backend/learning_agent.py](backend/learning_agent.py). Các agent con nằm trong [backend/agents](backend/agents).

Đây là **1 user-facing agent**, bên trong chia thành 5 agent role:

| Step | Vị trí trong code | Nhiệm vụ |
|---|---|---|
| Intake Router | `backend/agents/intake_router/` | Đọc câu hỏi và phân loại: course-grounded, general learning, program operations, ambiguous. |
| Source Intake | `backend/agents/source_intake/` | Nhận GitHub/PDF/web/text source, gọi reader tương ứng, chunk tài liệu. |
| Retriever | `backend/agents/retriever/` | Tìm chunk liên quan trong course source đã load. |
| LLM Composer | `backend/agents/answer_composer/` + `backend/llm_provider.py` | Gọi OpenAI/Groq/Gemini để tổng hợp answer khi đã có route + evidence. |
| Guard / Refusal | `backend/agents/guard/` | Chặn đoán khi thiếu source, ops/deadline/rule nội bộ, hoặc source không match. |

Mỗi folder agent có:

```text
agent.py   -> logic của role
prompt.md -> prompt/policy rõ ràng
README.md -> input/output + nhiệm vụ
```

LLM **không tự quyết định tất cả**. LLM chỉ được dùng ở bước compose sau khi agent đã:

```text
route question -> call tool/retrieve evidence -> source check -> compose answer
```

Nếu thiếu source, agent không gọi LLM để bịa câu trả lời.

## Environment

Tạo file `.env` từ [.env.example](.env.example):

```powershell
Copy-Item "Day6-E403-D5\.env.example" "Day6-E403-D5\.env"
```

Chọn provider:

```text
LLM_PROVIDER=auto
LLM_PROVIDER=openai
LLM_PROVIDER=groq
LLM_PROVIDER=gemini
LLM_PROVIDER=mock
```

Điền key tương ứng trong `.env`. Nếu dùng `auto`, backend sẽ tự ưu tiên OpenAI -> Groq -> Gemini theo key đang có. Không commit `.env`.

Chạy demo logic:

```powershell
& "C:\Users\Phucc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -B "Day6-E403-D5\backend\run_demo.py"
```

Chạy local server:

```powershell
& "C:\Users\Phucc\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" "Day6-E403-D5\backend\server.py"
```

Sau đó mở:

```text
http://127.0.0.1:8060
```

Kiểm tra backend đã đọc key chưa, không lộ key:

```text
http://127.0.0.1:8060/api/health
```

Kết quả sẽ có:

```json
{
  "llm_provider": "openai|groq|gemini|mock",
  "llm_model": "...",
  "has_llm_key": true,
  "has_tavily_key": true
}
```

## Tool modules

Các API/tool nằm ở [backend/tools](backend/tools):

| Tool file | Nhiệm vụ |
|---|---|
| `tavily_tool.py` | Gọi Tavily Search API cho câu hỏi general learning. |
| `github_tool.py` | Đọc public GitHub repo/file, ưu tiên README/docs/rubric/lab/notebook. |
| `pdf_tool.py` | Đọc PDF text layer bằng `pypdf`/`PyPDF2`; nếu scan thì báo cần OCR. |
| `web_tool.py` | Đọc text cơ bản từ web link public. |
