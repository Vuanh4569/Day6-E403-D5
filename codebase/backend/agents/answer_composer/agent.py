from __future__ import annotations

from typing import Any
import json

from llm_provider import LLMClient

ANSWER_COMPOSER_SYSTEM_PROMPT = """
Bạn là Answer Composer của Learning OS Agent.

Nguyên tắc vận hành:
- Ưu tiên trả lời đúng ý user trước, không báo cáo dài dòng.
- Với câu hỏi general cơ bản, bạn có thể dùng kiến thức sẵn của model để giải thích rõ ràng, tự nhiên.
- Evidence từ search hoặc source chỉ là phần bổ sung và kiểm chứng, không phải lúc nào cũng bắt buộc.
- Với câu hỏi bám theo course/repo/pdf/rubric thì chỉ kết luận trong phạm vi source được đưa vào.
- Nếu thiếu dữ kiện cho câu hỏi course-specific hoặc rule nội bộ, hãy nói chưa chắc và hướng user bổ sung source.
- Không tự bịa link nguồn. Hệ thống sẽ tự gắn phần nguồn thật sau.

Cách trả lời:
- Trả lời bằng tiếng Việt tự nhiên, như một trợ lý học tập thông minh.
- Không dùng các nhãn kiểu "Answer summary", "Reasoning summary", "Unknown note".
- Ưu tiên cấu trúc:
  1. một đoạn trả lời trực tiếp
  2. **Điểm chính**
  3. nếu phù hợp thì **Hiểu nhanh** hoặc **Bạn có thể làm tiếp**
- Chỉ dùng bullet khi thực sự giúp dễ đọc hơn.
- Không lộ chain-of-thought.

Nếu context cho biết `use_model_knowledge = true`:
- Hãy trả lời dựa trên kiến thức sẵn của model.
- Không giả vờ như bạn đã đọc nguồn nếu evidence rỗng.

Nếu evidence có mặt:
- Gộp các ý giống nhau lại, bỏ trùng, nêu 2-4 điểm thực sự quan trọng.
- Nếu có nhiều nguồn, ưu tiên điều ổn định và khớp giữa các nguồn.
""".strip()


class AnswerComposerAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.prompt = ANSWER_COMPOSER_SYSTEM_PROMPT

    def compose(
        self,
        route: str,
        question: str,
        evidence: list[dict[str, Any]],
        context: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "route": route,
            "question": question,
            "evidence": evidence,
            "context": context or {},
        }
        response = self.llm.generate(
            system=self.prompt,
            prompt=(
                f"Dau vao JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
                "Hãy tạo câu trả lời theo format trong system prompt."
            ),
        )
        if response.used_mock:
            return ""
        return self._clean_response(response.text)

    def call_label(self) -> str:
        settings = self.llm.settings
        return f"answer_composer_llm(provider={settings.provider}, model={settings.model})"

    def _clean_response(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned
