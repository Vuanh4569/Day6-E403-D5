from __future__ import annotations

import json
import unicodedata
from agents.prompt_loader import load_prompt
from llm_provider import LLMClient


class GuardAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def check(
        self,
        route: str,
        question: str,
        source_status: str,
        retrieved_evidence: list[str] | None = None,
        tool_errors: list[str] | None = None,
        conversation_memory: list[str] | None = None,
    ) -> dict:
        prompt = load_prompt("guard")
        payload = {
            "route": route,
            "user_question": question,
            "source_status": source_status,
            "retrieved_evidence": retrieved_evidence or [],
            "tool_errors": tool_errors or [],
            "conversation_memory": conversation_memory or [],
        }

        # Fast heuristic fallback for common off-topic categories to save API calls
        text = question.lower().strip()
        plain = "".join(
            ch for ch in unicodedata.normalize("NFD", text)
            if unicodedata.category(ch) != "Mn"
        )
        if self._is_off_topic_plain(plain):
            return {
                "allow_answer": False,
                "risk_level": "high",
                "unknown_note": "off_topic",
                "refusal": "Câu hỏi này nằm ngoài phạm vi cho phép. Mình chỉ hỗ trợ các chủ đề liên quan đến học tập, lập trình và AI.",
                "required_user_action": "",
                "draft_question_to_mentor": ""
            }

        response = self.llm.generate(
            system=prompt,
            prompt=f"Đầu vào JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
        )
        if response.used_mock:
            return {
                "allow_answer": True,
                "risk_level": "low",
                "unknown_note": "",
                "refusal": "",
                "required_user_action": "",
                "draft_question_to_mentor": ""
            }

        try:
            parsed = self._parse_json(response.text)
            if parsed:
                return parsed
        except Exception:
            pass

        return {
            "allow_answer": True,
            "risk_level": "low",
            "unknown_note": "",
            "refusal": "",
            "required_user_action": "",
            "draft_question_to_mentor": ""
        }

    def _parse_json(self, text: str) -> dict | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            return None

    def missing_course_source(self) -> tuple[str, str]:
        return (
            "Không đoán nội dung slide/lab/rubric khi chưa có source khóa học.",
            "Paste GitHub repo/file, PDF/slide link, hoặc đoạn text liên quan.",
        )

    def ops_without_source(self, question: str) -> tuple[str, str]:
        draft = f'Mentor/TA ơi, thông tin chính thức mới nhất về "{question}" là gì và nguồn nào nên dùng để kiểm chứng?'
        return ("Không đoán deadline, grading, nộp repo hoặc lịch.", draft)

    def source_loaded_but_no_match(self) -> tuple[str, str]:
        return (
            "Không tìm thấy evidence liên quan trong source đã load, nên không đoán.",
            "Paste đúng slide/rubric/README hoặc hỏi mentor.",
        )

    def is_off_topic(self, question: str) -> bool:
        """Public early-exit check — call before routing to avoid false clarify/small_talk responses."""
        plain = "".join(
            ch for ch in unicodedata.normalize("NFD", question.lower().strip())
            if unicodedata.category(ch) != "Mn"
        )
        return self._is_off_topic_plain(plain)

    def _is_off_topic_plain(self, plain: str) -> bool:
        off_topic_keywords = [
            # Ẩm thực / đồ ăn
            "nau an", "mon an", "nau lau", "cong thuc nau", "nau xoi", "luoc rau",
            "lam banh", "com ngon", "pho ngon", "bun bo", "banh mi", "an ngon",
            "com hay pho", "pho hay com", "ngon hon", "do an ngon", "quan an",
            "nha hang", "mon ngon", "an uong",
            # Giải trí / thể thao
            "da bong", "bong da", "xem phim", "ca nhac", "hat karaoke",
            "choi game", "phim hay", "nghe nhac", "xem bong",
            # Khác hoàn toàn ngoài phạm vi
            "thoi tiet", "du lich", "thoi trang", "danh de", "so xo",
            "tin tuc", "showbiz", "giai tri",
        ]
        return any(kw in plain for kw in off_topic_keywords)

