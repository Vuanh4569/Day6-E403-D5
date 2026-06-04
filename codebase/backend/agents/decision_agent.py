from __future__ import annotations

from dataclasses import dataclass
import json
import unicodedata

from llm_provider import LLMClient


@dataclass
class Decision:
    route: str
    mode: str
    reason: str


DECISION_SYSTEM_PROMPT = """
Bạn là Decision Agent của Learning OS Agent.

Nhiệm vụ:
- Đọc câu hỏi user, memory gần đây và trạng thái source hiện tại.
- Quyết định hệ thống nên xử lý theo mode nào.
- Không trả lời câu hỏi của user.

Các mode hợp lệ:
- `small_talk`: chào hỏi, cảm ơn, giới thiệu bản thân, hỏi agent làm được gì
- `clarify`: câu quá mơ hồ, chưa đủ context
- `ops`: hỏi deadline, grading, lịch, quy định nội bộ
- `course`: câu hỏi bám theo slide, lab, repo, rubric, tài liệu khóa học
- `general_model`: kiến thức chung cơ bản, model có thể trả lời trực tiếp
- `general_search`: kiến thức chung nhưng cần tìm thêm nguồn hoặc kiểm chứng

Nguyên tắc:
- Không dùng search cho mọi câu hỏi.
- Câu cơ bản như "AI agent là gì?" thường là `general_model`.
- Follow-up như "chi tiết hơn", "ví dụ đi" phải nhìn vào chủ đề trước đó thay vì coi là câu mới.
- Nếu chưa rõ user đang hỏi kiến thức chung hay course-specific thì chọn `clarify`.
- Nếu câu hỏi nhắc source, repo, pdf, slide, day05, day06, rubric, bài lab thì nghiêng mạnh về `course`.
- Nếu user hỏi thông tin có thể thay đổi hoặc cần nguồn thật thì chọn `general_search`.

Trả về JSON:
{
  "route": "general_learning|course_grounded|program_operations|ambiguous",
  "mode": "small_talk|clarify|ops|course|general_model|general_search",
  "reason": "short reason"
}
""".strip()


class DecisionAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    def decide(self, question: str, conversation: list[dict[str, str]], has_sources: bool) -> Decision:
        heuristic = self._heuristic(question, conversation, has_sources)
        if self._should_trust_heuristic(question, conversation, heuristic):
            return heuristic
        payload = {
            "question": question,
            "has_sources": has_sources,
            "recent_conversation": conversation[-6:],
            "heuristic_guess": {
                "route": heuristic.route,
                "mode": heuristic.mode,
                "reason": heuristic.reason,
            },
        }
        response = self.llm.generate(
            system=DECISION_SYSTEM_PROMPT,
            prompt=f"Đầu vào JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2)}",
        )
        if response.used_mock:
            return heuristic
        parsed = self._parse_json(response.text)
        if not parsed:
            return heuristic
        route = str(parsed.get("route", heuristic.route)).strip() or heuristic.route
        mode = str(parsed.get("mode", heuristic.mode)).strip() or heuristic.mode
        reason = str(parsed.get("reason", heuristic.reason)).strip() or heuristic.reason
        if mode not in {"small_talk", "clarify", "ops", "course", "general_model", "general_search"}:
            return heuristic
        if self._would_break_context(question, conversation, heuristic, mode):
            return heuristic
        return Decision(route=route, mode=mode, reason=reason)

    def call_label(self) -> str:
        settings = self.llm.settings
        return f"decision_agent_llm(provider={settings.provider}, model={settings.model})"

    def _heuristic(self, question: str, conversation: list[dict[str, str]], has_sources: bool) -> Decision:
        text = question.lower().strip()
        plain = self._plain(question)
        if self._is_small_talk(plain):
            return Decision("general_learning", "small_talk", "casual or assistant-intro question")
        if self._contains_any(plain, ["deadline", "han nop", "nop repo", "repo ca nhan", "repo nhom", "grading", "lich", "may gio"]):
            return Decision("program_operations", "ops", "operations or internal rule question")
        if self._contains_any(plain, ["day05", "day06", "slide", "lab", "rubric", "repo", "pdf", "khoa hoc", "ai thuc chien", "mentor", "thay noi"]):
            return Decision("course_grounded", "course", "course-specific source-oriented question")
        if self._is_follow_up(plain):
            previous = self._previous_user_topic(conversation)
            if previous and self._contains_any(self._plain(previous), ["day05", "day06", "slide", "lab", "rubric", "repo", "pdf"]):
                return Decision("course_grounded", "course", "follow-up to course-specific topic")
            return Decision("general_learning", "general_model", "follow-up to prior topic")
        if self._is_ambiguous(plain):
            return Decision("ambiguous", "clarify", "question is too vague")
        if self._needs_public_search(plain):
            return Decision("general_learning", "general_search", "needs broader or fresher public evidence")
        return Decision("general_learning", "general_model", "basic general question can be answered directly")

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

    def _plain(self, text: str) -> str:
        lowered = text.lower().strip()
        return "".join(
            ch for ch in unicodedata.normalize("NFD", lowered)
            if unicodedata.category(ch) != "Mn"
        )

    def _contains_any(self, text: str, needles: list[str]) -> bool:
        return any(item in text for item in needles)

    def _is_follow_up(self, plain: str) -> bool:
        markers = [
            "chi tiet hon", "noi ro hon", "giai thich them", "cu the hon",
            "vi du di", "them vi du", "y la sao", "chua hieu",
            "trong day ban vua noi", "ban vua noi", "nói rõ và chi tiết hơn",
            "trong day", "chi tiet ve no", "ve no khong",
        ]
        return self._contains_any(plain, [self._plain(marker) for marker in markers])

    def _is_ambiguous(self, plain: str) -> bool:
        if len(plain) > 48:
            return False
        return self._contains_any(plain, [
            "bai nay", "cai nay", "cai do", "lam sao", "the nao", "duoc khong", "nen lam gi",
        ])

    def _needs_public_search(self, plain: str) -> bool:
        return self._contains_any(plain, [
            "moi nhat", "gan day", "hien nay", "xu huong", "nguon", "source",
            "tham khao", "thong ke", "study", "paper", "benchmark",
        ])

    def _is_small_talk(self, plain: str) -> bool:
        short_greetings = ["hello", "hi", "helo", "xin chao", "chao", "cam on"]
        if len(plain) <= 20 and any(plain == marker or plain.startswith(marker + " ") for marker in short_greetings):
            return True
        # Exact capability/intro phrases (original)
        exact_intros = ["ban la ai", "ban lam duoc gi", "giup duoc gi"]
        if any(marker in plain for marker in exact_intros) and len(plain) <= 40:
            return True
        # Broader capability / topic questions about the bot itself
        capability_patterns = [
            "co the tra loi", "tra loi duoc", "tra loi cau hoi nao",
            "chu de nao", "chu de gi", "co the noi chuyen", "noi chuyen ve",
            "ban biet gi", "ban hieu gi", "ban gioi gi",
            "ho tro gi", "lam duoc nhung gi", "lam duoc nhung cai gi",
            "chuc nang gi", "tinh nang gi", "kha nang",
            "ban co the", "bạn có thể",
            "ban ho tro", "ho tro duoc gi",
            "toi co the hoi", "co the hoi gi",
            "nhung chu de", "những chu de",
        ]
        return any(kw in plain for kw in capability_patterns)

    def _previous_user_topic(self, conversation: list[dict[str, str]]) -> str:
        for item in reversed(conversation):
            if item.get("role") != "user":
                continue
            content = str(item.get("content", "")).strip()
            if content and not self._is_follow_up(self._plain(content)):
                return content
        return ""

    def _should_trust_heuristic(self, question: str, conversation: list[dict[str, str]], heuristic: Decision) -> bool:
        plain = self._plain(question)
        if heuristic.mode in {"small_talk", "ops", "course", "clarify"}:
            return True
        if self._is_follow_up(plain) and bool(self._previous_user_topic(conversation)):
            return True
        return False

    def _would_break_context(self, question: str, conversation: list[dict[str, str]], heuristic: Decision, mode: str) -> bool:
        plain = self._plain(question)
        if self._is_follow_up(plain) and bool(self._previous_user_topic(conversation)):
            return mode in {"small_talk", "clarify"}
        if heuristic.mode == "ops" and mode != "ops":
            return True
        if heuristic.mode == "course" and mode in {"small_talk", "general_model"}:
            return True
        return False
