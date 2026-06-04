from __future__ import annotations

from dataclasses import dataclass

from llm_provider import LLMClient
import unicodedata

QUERY_PLANNER_SYSTEM_PROMPT = """
Bạn là Query Planner Agent.

Mục tiêu:
- Chỉ tạo truy vấn search khi thật sự cần.
- Không biến mọi câu hỏi thành search query.

Khi nào KHÔNG cần search:
- câu chào hỏi, cảm ơn, giới thiệu bản thân
- câu hỏi rất cơ bản mà model có thể tự giải thích tốt
- follow-up kiểu "giải thích kỹ hơn", "cho ví dụ", nếu chủ đề trước đã rõ

Khi nào NÊN search:
- user hỏi thông tin cần nguồn hoặc kiểm chứng
- user hỏi kiến thức có thể thay đổi theo thời gian
- user nhắc tới source, tài liệu, bài báo, link, website, repo
- user hỏi chủ đề hẹp hoặc cần ví dụ thực tế hơn

Nếu không cần search, trả JSON với:
- `search_queries`: []
- `answer_intent`: một trong `direct_explain|compare|how_to|troubleshoot|source_lookup`

Nếu cần search:
- tạo 2-4 truy vấn ngắn, mỗi truy vấn là một góc nhìn khác nhau
- ưu tiên tiếng Việt nếu câu hỏi gốc là tiếng Việt
- tránh tạo truy vấn rác từ câu quá mơ hồ
""".strip()


@dataclass
class QueryPlan:
    topic: str
    search_queries: list[str]
    answer_intent: str


class QueryPlannerAgent:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.prompt = QUERY_PLANNER_SYSTEM_PROMPT

    def plan(self, question: str) -> QueryPlan:
        response = self.llm.generate(
            system=self.prompt,
            prompt=(
                f"Cau hoi goc: {question}\n\n"
                "Hay tra ve JSON voi topic, search_queries, answer_intent."
            ),
        )
        if response.used_mock:
            return self._fallback(question)

        parsed = self._parse_json_block(response.text)
        if not parsed:
            return self._fallback(question)

        topic = str(parsed.get("topic", question)).strip() or question
        search_queries = [
            str(item).strip()
            for item in parsed.get("search_queries", [])
            if str(item).strip()
        ][:4]
        if not search_queries:
            return self._fallback(question)

        answer_intent = str(parsed.get("answer_intent", "explain")).strip() or "explain"
        return QueryPlan(topic=topic, search_queries=search_queries, answer_intent=answer_intent)

    def call_label(self) -> str:
        settings = self.llm.settings
        return f"query_planner_llm(provider={settings.provider}, model={settings.model})"

    def _fallback(self, question: str) -> QueryPlan:
        clean = question.strip()
        lowered = clean.lower()
        if self._looks_basic_or_conversational(lowered):
            return QueryPlan(topic=clean, search_queries=[], answer_intent="direct_explain")
        variants = [clean]
        if "la gi" in lowered or "là gì" in lowered:
            variants.append(clean.replace("là gì", "hoạt động như thế nào").replace("la gi", "hoat dong nhu the nao"))
            variants.append(clean.replace("là gì", "ví dụ ứng dụng").replace("la gi", "vi du ung dung"))
        else:
            variants.append(f"{clean} la gi")
            variants.append(f"{clean} vi du ung dung")
        return QueryPlan(topic=clean, search_queries=variants[:3], answer_intent="explain")

    def _looks_basic_or_conversational(self, lowered: str) -> bool:
        plain = "".join(
            ch for ch in unicodedata.normalize("NFD", lowered)
            if unicodedata.category(ch) != "Mn"
        )
        casual_markers = [
            "hello", "hi", "helo", "xin chao", "chao", "cam on", "cảm ơn",
            "ban la ai", "bạn là ai", "ban lam duoc gi", "bạn làm được gì",
        ]
        basic_markers = ["là gì", "la gi", "nghĩa là gì", "nghia la gi", "khác gì", "khac gi", "ví dụ", "vi du"]
        force_search_markers = ["moi nhat", "mới nhất", "source", "nguon", "nguồn", "tai lieu", "tài liệu", "repo", "pdf", "link", "website"]
        if any(marker in lowered for marker in force_search_markers) or any(
            "".join(ch for ch in unicodedata.normalize("NFD", marker) if unicodedata.category(ch) != "Mn") in plain
            for marker in force_search_markers
        ):
            return False
        if any(marker in lowered for marker in casual_markers) or any(
            "".join(ch for ch in unicodedata.normalize("NFD", marker) if unicodedata.category(ch) != "Mn") in plain
            for marker in casual_markers
        ):
            return True
        return len(lowered) < 60 and (
            any(marker in lowered for marker in basic_markers) or any(
                "".join(ch for ch in unicodedata.normalize("NFD", marker) if unicodedata.category(ch) != "Mn") in plain
                for marker in basic_markers
            )
        )

    def _parse_json_block(self, text: str) -> dict | None:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            import json

            return json.loads(cleaned)
        except Exception:
            return None
