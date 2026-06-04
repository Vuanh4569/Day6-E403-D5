from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import re
import unicodedata

from agents.answer_composer.agent import AnswerComposerAgent
from agents.decision_agent import DecisionAgent
from agents.guard.agent import GuardAgent
from agents.intake_router.agent import IntakeRouterAgent, Route
from agents.query_planner.agent import QueryPlan, QueryPlannerAgent
from agents.retriever.agent import RetrieverAgent
from agents.source_intake.agent import Chunk, Source, chunk_text, detect_source_type
from tools.github_tool import read_github
from tools.pdf_tool import read_pdf
from tools.tavily_tool import tavily_multi_search, tavily_search
from tools.web_tool import read_web

try:
    from langchain_core.tools import tool
except Exception:  # LangChain is optional in the local classroom demo runtime.
    def tool(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.name = fn.__name__
        fn.description = fn.__doc__ or ""
        return fn


@dataclass
class AgentResult:
    route: Route
    source_status: str
    answer: str
    trace: list[str]
    tool_calls: list[str]
    evidence: list[dict[str, Any]]
    refusal: str = ""
    suggested_follow_up: str = ""
    follow_up_options: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.value,
            "source_status": self.source_status,
            "answer": self.answer,
            "trace": self.trace,
            "tool_calls": self.tool_calls,
            "evidence": self.evidence,
            "refusal": self.refusal,
            "suggested_follow_up": self.suggested_follow_up,
            "follow_up_options": self.follow_up_options or [],
        }


def normalize(text: str) -> str:
    return text.lower().strip()


def normalize_plain(text: str) -> str:
    lowered = text.lower().strip()
    return "".join(
        ch for ch in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(ch) != "Mn"
    )


def has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


@tool
def tavily_search_tool(query: str) -> list[dict[str, str]]:
    """Search public web for a general learning question."""
    return tavily_search(query)


@tool
def github_reader_tool(url: str) -> dict[str, str]:
    """Read public GitHub source content. Teammate implementation can replace this stub."""
    return read_github(url)


@tool
def pdf_reader_tool(url: str) -> dict[str, str]:
    """Read PDF text by page. Teammate implementation can replace this stub."""
    return read_pdf(url)


@tool
def web_reader_tool(url: str) -> dict[str, str]:
    """Read basic public web text from a URL."""
    return read_web(url)


class LearningOSAgent:
    def __init__(self) -> None:
        self.sources: list[Source] = []
        self.memory: list[dict[str, str]] = []
        self.router = IntakeRouterAgent()
        self.decision_agent = DecisionAgent()
        self.retriever = RetrieverAgent()
        self.composer = AnswerComposerAgent()
        self.query_planner = QueryPlannerAgent()
        self.guard = GuardAgent()

    def detect_route(self, question: str) -> Route:
        return self.router.route(question)

    def load_source(self, raw: str) -> Source:
        source_type = detect_source_type(raw)
        if source_type == "github_repo" or source_type == "github_file":
            result = read_github(raw)
        elif source_type == "pdf":
            result = read_pdf(raw)
        elif source_type == "web":
            result = read_web(raw)
        else:
            result = {"status": "loaded", "title": "Pasted course text", "text": raw, "note": "Pasted by user"}

        source = Source(
            title=result.get("title", "Course source"),
            source_type=source_type,
            source_url=raw if source_type != "pasted_text" else "pasted-text",
            status=result.get("status", "loaded"),
            note=result.get("note", ""),
            chunks=chunk_text(
                result.get("text", ""),
                result.get("title", "Course source"),
                source_type,
                raw if source_type != "pasted_text" else "pasted-text",
            ),
        )
        self.sources.append(source)
        return source

    def retrieve(self, question: str) -> list[Chunk]:
        chunks = [chunk for source in self.sources for chunk in source.chunks]
        return self.retriever.retrieve(question, chunks)

    def keywords(self, question: str) -> list[str]:
        text = normalize(question)
        groups = [
            ["build slice", "slice", "lát cắt"],
            ["thin spec", "spec"],
            ["failure path", "failure"],
            ["happy path", "happy"],
            ["evidence", "evidence pack"],
            ["rag", "retrieval"],
            ["workflow", "agentic", "agent"],
            ["rubric", "checklist"],
        ]
        matches = [word for group in groups for word in group if word in text]
        if matches:
            return matches
        return [word for word in re.split(r"\W+", text) if len(word) > 3][:8]

    def ask(self, question: str, conversation: list[dict[str, str]] | None = None) -> AgentResult:
        active_conversation = list(conversation or self.memory)
        resolved_question = self.resolve_question(question, active_conversation)
        self.memory = active_conversation
        if not self.memory or self.memory[-1].get("role") != "user" or self.memory[-1].get("content") != question:
            self.memory.append({"role": "user", "content": question})
        decision = self.decision_agent.decide(question, active_conversation, has_sources=bool(self.sources))
        route = self.route_from_decision(decision.mode, decision.route)

        if decision.mode == "clarify" or route == Route.AMBIGUOUS:
            return AgentResult(
                route=Route.AMBIGUOUS,
                source_status="waiting_for_clarification",
                answer=(
                    "Mình cần rõ hơn một chút để trả lời đúng ý bạn.\n\n"
                    "**Bạn đang hỏi theo hướng nào?**\n"
                    "1. Kiến thức chung về khái niệm này\n"
                    "2. Nội dung trong slide, lab, rubric hoặc tài liệu khóa học\n"
                    "3. Cách áp dụng ngay vào bài đang làm"
                ),
                trace=["Read question", "Decision = clarify", "Ask clarification"],
                tool_calls=self.decision_tool_calls(),
                evidence=[],
                suggested_follow_up="Hãy nói rõ: general knowledge hay course-grounded.",
                follow_up_options=[
                    "Đây là kiến thức chung",
                    "Đây là nội dung trong slide hoặc lab",
                    "Tôi muốn checklist áp dụng",
                ],
            )

        if decision.mode == "small_talk":
            return AgentResult(
                route=Route.GENERAL,
                source_status="model_knowledge_only",
                answer=self.answer_small_talk(question),
                trace=["Read question", "Decision = small_talk", "Answer directly without search"],
                tool_calls=self.decision_tool_calls(),
                evidence=[],
            )

        if decision.mode == "ops" or route == Route.OPS:
            refusal, draft = self.guard.ops_without_source(resolved_question)
            return AgentResult(
                route=Route.OPS,
                source_status="missing_official_source",
                answer="Mình không trả lời chắc về deadline/rule nội bộ nếu chưa có source chính thức.",
                trace=["Read question", "Decision = ops", "Refuse to guess"],
                tool_calls=self.decision_tool_calls(),
                evidence=[],
                refusal=refusal,
                suggested_follow_up=draft,
            )

        if decision.mode == "course" or route == Route.COURSE:
            if not self.sources:
                refusal, follow_up = self.guard.missing_course_source()
                return AgentResult(
                    route=Route.COURSE,
                    source_status="missing_course_source",
                    answer=(
                        "Mình chưa muốn đoán sai phần này, nên mình cần source khóa học trước đã.\n\n"
                        "**Bạn có thể gửi một trong các nguồn sau:**\n"
                        "- GitHub repo hoặc file\n"
                        "- PDF hoặc slide link\n"
                        "- Đoạn text từ README, rubric, hoặc slide"
                    ),
                    trace=["Read question", "Decision = course", "Course source missing"],
                    tool_calls=self.decision_tool_calls(),
                    evidence=[],
                    refusal=refusal,
                    suggested_follow_up=follow_up,
                    follow_up_options=[
                        "Mình sẽ gửi GitHub repo",
                        "Mình sẽ gửi PDF hoặc slide",
                        "Mình sẽ paste đoạn text liên quan",
                    ],
                )
            evidence = self.retrieve(resolved_question)
            if not evidence:
                refusal, follow_up = self.guard.source_loaded_but_no_match()
                return AgentResult(
                    route=Route.COURSE,
                    source_status="source_loaded_but_no_match",
                    answer=(
                        "Mình đã có source, nhưng chưa tìm thấy đoạn đủ khớp với câu hỏi hiện tại.\n\n"
                        "**Bạn thử làm rõ thêm theo một trong các cách này nhé:**\n"
                        "- nói rõ Day05 hay Day06\n"
                        "- nói rõ slide, lab hoặc rubric nào\n"
                        "- paste đúng đoạn text liên quan"
                    ),
                    trace=["Read question", "Decision = course", "Retrieve course chunks", "No relevant chunk"],
                    tool_calls=self.decision_tool_calls() + ["course_retriever"],
                    evidence=[],
                    refusal=refusal,
                    suggested_follow_up=follow_up,
                    follow_up_options=[
                        "Đây là Day05",
                        "Đây là Day06",
                        "Mình sẽ paste đúng đoạn text",
                    ],
                )
            answer = self.compose_course_answer(resolved_question, evidence)
            return AgentResult(
                route=Route.COURSE,
                source_status="found_course_source",
                answer=answer,
                trace=["Read question", "Decision = course", "Retrieve course chunks", "Compose source-grounded answer"],
                tool_calls=self.decision_tool_calls() + ["retriever_agent", self.composer.call_label()],
                evidence=[chunk.__dict__ for chunk in evidence],
            )

        search_seed = self.search_seed(question, active_conversation)
        query_plan = self.query_planner.plan(search_seed)
        if decision.mode == "general_model" or not query_plan.search_queries:
            answer = self.compose_general_answer_from_model(resolved_question, query_plan)
            return AgentResult(
                route=Route.GENERAL,
                source_status="model_knowledge_only",
                answer=answer,
                trace=[
                    "Read question",
                    f"Decision = {decision.mode}",
                    "Use model knowledge first",
                    "Skip search because question is basic or conversational",
                ],
                tool_calls=self.decision_tool_calls() + [self.composer.call_label()],
                evidence=[],
            )
        results = tavily_multi_search(query_plan.search_queries)
        answer = self.compose_general_answer(resolved_question, results, query_plan)
        tool_calls = self.decision_tool_calls()
        settings = self.query_planner.llm.settings
        if settings.provider != "mock":
            tool_calls.append(self.query_planner.call_label())
        tool_calls.append(f"tavily_multi_search({query_plan.search_queries})")
        tool_calls.append(self.composer.call_label())
        return AgentResult(
            route=Route.GENERAL,
            source_status="public_source_found",
            answer=answer,
            trace=[
                "Read question",
                f"Decision = {decision.mode}",
                "Expand question into multi-query search plan",
                "Search across public domains",
                "Synthesize grounded answer",
            ],
            tool_calls=tool_calls,
            evidence=results,
        )

    def route_from_decision(self, mode: str, fallback_route: str) -> Route:
        mapping = {
            "small_talk": Route.GENERAL,
            "clarify": Route.AMBIGUOUS,
            "ops": Route.OPS,
            "course": Route.COURSE,
            "general_model": Route.GENERAL,
            "general_search": Route.GENERAL,
        }
        if mode in mapping:
            return mapping[mode]
        try:
            return Route(fallback_route)
        except Exception:
            return Route.GENERAL

    def decision_tool_calls(self) -> list[str]:
        settings = self.decision_agent.llm.settings
        if settings.provider == "mock":
            return []
        return [self.decision_agent.call_label()]

    def resolve_question(self, question: str, conversation: list[dict[str, str]]) -> str:
        text = normalize(question)
        if not self.is_follow_up(text):
            return question

        previous_topic = self.find_previous_user_topic(conversation)
        if not previous_topic:
            return question

        return (
            f"Chủ đề đang nói tới: {previous_topic}\n"
            f"Người dùng muốn bạn giải thích sâu hơn hoặc cụ thể hơn về đúng chủ đề này.\n"
            f"Câu follow-up hiện tại: {question}"
        )

    def is_follow_up(self, text: str) -> bool:
        follow_up_markers = [
            "chi tiết hơn",
            "nói rõ hơn",
            "giải thích thêm",
            "cụ thể hơn",
            "ví dụ đi",
            "thêm ví dụ",
            "ý là sao",
            "là gì vậy",
            "mình chưa hiểu",
            "chưa hiểu",
            "trong đây bạn vừa nói",
            "bạn vừa nói",
            "chi tiết về nó",
        ]
        plain = normalize_plain(text)
        return any(marker in text for marker in follow_up_markers) or any(
            normalize_plain(marker) in plain for marker in follow_up_markers
        )

    def is_small_talk(self, question: str) -> bool:
        plain = normalize_plain(question)
        short_greetings = ["hello", "hi", "helo", "xin chao", "chao", "cam on"]
        if len(plain) <= 20 and any(plain == marker or plain.startswith(marker + " ") for marker in short_greetings):
            return True
        exact_intros = ["ban la ai", "ban lam duoc gi", "giup duoc gi"]
        return any(marker in plain for marker in exact_intros) and len(plain) <= 40

    def answer_small_talk(self, question: str) -> str:
        text = normalize(question)
        if "cảm ơn" in text or "cam on" in text:
            return "Không có gì, mình ở đây để giúp bạn học nhanh hơn và đỡ phải mò tài liệu một mình."
        if "bạn là ai" in text or "ban la ai" in text:
            return (
                "Mình là Learning OS Agent. Mình hỗ trợ bạn theo hai kiểu chính:\n\n"
                "- giải thích kiến thức chung bằng ngôn ngữ dễ hiểu\n"
                "- đọc repo, PDF hoặc tài liệu khóa học để trả lời bám đúng source\n\n"
                "Nếu bạn muốn, cứ hỏi một khái niệm hoặc gửi source luôn là mình xử lý tiếp."
            )
        if "bạn làm được gì" in text or "ban lam duoc gi" in text or "giúp được gì" in text or "giup duoc gi" in text:
            return (
                "Mình có thể giúp bạn giải thích khái niệm, tóm tắt tài liệu, đọc repo hoặc PDF, và chỉ ra phần nào còn thiếu source trước khi trả lời chắc."
            )
        return "Chào bạn, mình sẵn sàng hỗ trợ. Bạn có thể hỏi kiến thức chung hoặc gửi repo/PDF để mình đọc cùng."

    def is_under_specified(self, question: str) -> bool:
        text = normalize(question)
        plain = normalize_plain(question)
        if self.is_follow_up(text):
            return False
        if len(text) > 40:
            return False
        vague_markers = [
            "bài này",
            "cái này",
            "cái đó",
            "làm sao",
            "sao nhỉ",
            "thế nào",
            "được không",
            "nên làm gì",
        ]
        return any(marker in text for marker in vague_markers) or any(
            normalize_plain(marker) in plain for marker in vague_markers
        )

    def search_seed(self, question: str, conversation: list[dict[str, str]]) -> str:
        text = normalize(question)
        if self.is_follow_up(text):
            previous_topic = self.find_previous_user_topic(conversation)
            if previous_topic:
                return previous_topic
        return question

    def find_previous_user_topic(self, conversation: list[dict[str, str]]) -> str:
        for message in reversed(conversation):
            if message.get("role") != "user":
                continue
            content = message.get("content", "").strip()
            if content and not self.is_follow_up(normalize(content)):
                return content
        return ""

    def compose_course_answer(self, question: str, evidence: list[Chunk]) -> str:
        llm_answer = self.composer.compose(
            route="Course-grounded",
            question=question,
            evidence=[
                {
                    "title": chunk.title,
                    "url": chunk.source_url,
                    "chunk_id": chunk.chunk_id,
                    "text": chunk.text,
                }
                for chunk in evidence
            ],
            context={
                "source_status": "found_course_source",
                "answer_intent": "course_explain",
            },
        )
        if llm_answer:
            return self.attach_sources(llm_answer, [
                {"title": chunk.title, "url": chunk.source_url}
                for chunk in evidence
            ])

        text = normalize(question)
        if has_any(text, ["build slice", "slice"]):
            summary = "Build slice là lát cắt nhỏ đủ để demo: một user, một task, một AI decision và một output."
        elif has_any(text, ["thin spec", "spec"]):
            summary = "Thin SPEC là bản mô tả đủ để build prototype, không cần PRD đầy đủ."
        elif has_any(text, ["failure"]):
            summary = "Failure path là tình huống AI sai, thiếu nguồn hoặc không đủ tự tin; sản phẩm phải có recovery."
        else:
            summary = "Mình tìm thấy source khóa học liên quan và tổng hợp câu trả lời dựa trên source đó."

        citations = "; ".join(f"{chunk.title} chunk {chunk.chunk_id}" for chunk in evidence)
        return (
            f"{summary}\n\n"
            "Checklist áp dụng:\n"
            "1. Xác định khái niệm/lab đang hỏi.\n"
            "2. Đối chiếu với source đã load.\n"
            "3. Viết output thành checklist hoặc decision ngắn.\n"
            "4. Nếu source thiếu hoặc mâu thuẫn, hỏi mentor thay vì tự đoán.\n\n"
            f"Evidence: {citations}"
        )

    def compose_general_answer(self, question: str, results: list[dict[str, str]], query_plan: QueryPlan) -> str:
        llm_answer = self.composer.compose(
            route="General learning",
            question=question,
            evidence=results,
            context={
                "source_status": "public_source_found",
                "query_plan": {
                    "topic": query_plan.topic,
                    "search_queries": query_plan.search_queries,
                    "answer_intent": query_plan.answer_intent,
                },
            },
        )
        if llm_answer:
            return self.attach_sources(llm_answer, results)

        text = normalize(question)
        if has_any(text, ["build slice", "slice"]):
            return (
                "Build slice là một phần nhỏ nhưng hoàn chỉnh của sản phẩm, đủ để mình đem đi test với user thật.\n\n"
                "**Điểm chính**\n"
                "- Nó không phải bản thu nhỏ ngẫu nhiên, mà là một flow end-to-end.\n"
                "- Một build slice tốt thường có: một user, một task, một AI decision và một output nhìn thấy được.\n"
                "- Mục tiêu là học nhanh xem flow đó có tạo giá trị thật không.\n\n"
                "**Bạn có thể áp dụng ngay**\n"
                "1. Chọn một câu hỏi học tập cụ thể.\n"
                "2. Cho agent route câu hỏi, tìm source, rồi trả lời hoặc từ chối.\n"
                "3. Test happy path và một path thiếu context."
            )
        first = results[0]["snippet"] if results else "Không có kết quả public đủ rõ."
        return (
            f"{query_plan.topic} là chủ đề mình đang bám vào để trả lời.\n\n"
            "**Điểm chính**\n"
            f"- {first}\n"
            f"- Mình đã mở rộng câu hỏi theo các hướng: {', '.join(query_plan.search_queries[:3])}.\n"
            "- Nếu bạn muốn, mình có thể giải thích tiếp theo hướng định nghĩa, cách hoạt động, ví dụ hoặc so sánh.\n\n"
            "**Nguồn tham khảo**\n"
            + "\n".join(
                f"- [{item.get('title', 'Nguồn tham khảo')}]({item.get('url', '')})"
                for item in results[:3]
                if item.get("url")
            )
        ).strip()

    def compose_general_answer_from_model(self, question: str, query_plan: QueryPlan) -> str:
        llm_answer = self.composer.compose(
            route="General learning",
            question=question,
            evidence=[],
            context={
                "source_status": "model_knowledge_only",
                "use_model_knowledge": True,
                "query_plan": {
                    "topic": query_plan.topic,
                    "search_queries": [],
                    "answer_intent": query_plan.answer_intent,
                },
            },
        )
        if llm_answer:
            return llm_answer

        return (
            f"{query_plan.topic} là phần mình có thể giải thích trực tiếp bằng kiến thức sẵn của model.\n\n"
            "**Điểm chính**\n"
            "- Đây là câu hỏi cơ bản nên chưa cần đi search ngay.\n"
            "- Nếu bạn muốn, mình có thể giải thích sâu hơn, cho ví dụ hoặc so sánh với khái niệm gần nó.\n"
        )

    def attach_sources(self, answer: str, evidence: list[dict[str, Any]]) -> str:
        cleaned = self.strip_generated_sources(answer)
        lines = [cleaned.strip()]
        source_lines = self.build_source_lines(evidence)
        if source_lines:
            lines.append("**Nguồn tham khảo**")
            lines.extend(source_lines)
        return "\n\n".join(part for part in ["\n".join(lines[:1]), "\n".join(lines[1:])] if part).strip()

    def strip_generated_sources(self, answer: str) -> str:
        marker = "\n**Nguồn tham khảo**"
        if marker in answer:
            return answer.split(marker, 1)[0].strip()
        marker_plain = "\nSources:"
        if marker_plain in answer:
            return answer.split(marker_plain, 1)[0].strip()
        return answer.strip()

    def build_source_lines(self, evidence: list[dict[str, Any]]) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()
        for item in evidence:
            url = str(item.get("url", "")).strip()
            title = str(item.get("title", "")).strip() or "Nguồn tham khảo"
            if not url or url in seen:
                continue
            seen.add(url)
            lines.append(f"- [{title}]({url})")
            if len(lines) >= 4:
                break
        return lines

__all__ = ["LearningOSAgent", "AgentResult", "Source", "Chunk"]
