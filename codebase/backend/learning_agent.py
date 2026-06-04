from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
import re

from agents.answer_composer.agent import AnswerComposerAgent
from agents.guard.agent import GuardAgent
from agents.intake_router.agent import IntakeRouterAgent, Route
from agents.retriever.agent import RetrieverAgent
from agents.source_intake.agent import Chunk, Source, chunk_text, detect_source_type
from tools.github_tool import read_github
from tools.pdf_tool import read_pdf
from tools.tavily_tool import tavily_search
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
        }


def normalize(text: str) -> str:
    return text.lower().strip()


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
        self.retriever = RetrieverAgent()
        self.composer = AnswerComposerAgent()
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

    def ask(self, question: str) -> AgentResult:
        route = self.detect_route(question)
        self.memory.append({"role": "user", "content": question})

        if route == Route.AMBIGUOUS:
            return AgentResult(
                route=route,
                source_status="waiting_for_clarification",
                answer="Bạn đang hỏi kiến thức chung, hay hỏi theo slide/lab/tài liệu khóa học?",
                trace=["Read question", "Route = Ambiguous", "Ask clarification"],
                tool_calls=[],
                evidence=[],
                suggested_follow_up="Hãy nói rõ: general knowledge hay course-grounded.",
            )

        if route == Route.OPS:
            refusal, draft = self.guard.ops_without_source(question)
            return AgentResult(
                route=route,
                source_status="missing_official_source",
                answer="Mình không trả lời chắc về deadline/rule nội bộ nếu chưa có source chính thức.",
                trace=["Read question", "Route = Program Operations", "Refuse to guess"],
                tool_calls=[],
                evidence=[],
                refusal=refusal,
                suggested_follow_up=draft,
            )

        if route == Route.COURSE:
            if not self.sources:
                refusal, follow_up = self.guard.missing_course_source()
                return AgentResult(
                    route=route,
                    source_status="missing_course_source",
                    answer="Mình cần GitHub/PDF/link/text của khóa học trước khi trả lời câu này.",
                    trace=["Read question", "Route = Course-grounded", "Course source missing"],
                    tool_calls=[],
                    evidence=[],
                    refusal=refusal,
                    suggested_follow_up=follow_up,
                )
            evidence = self.retrieve(question)
            if not evidence:
                refusal, follow_up = self.guard.source_loaded_but_no_match()
                return AgentResult(
                    route=route,
                    source_status="source_loaded_but_no_match",
                    answer="Mình có source khóa học nhưng chưa tìm thấy đoạn liên quan đến câu hỏi.",
                    trace=["Read question", "Route = Course-grounded", "Retrieve course chunks", "No relevant chunk"],
                    tool_calls=["course_retriever"],
                    evidence=[],
                    refusal=refusal,
                    suggested_follow_up=follow_up,
                )
            answer = self.compose_course_answer(question, evidence)
            return AgentResult(
                route=route,
                source_status="found_course_source",
                answer=answer,
                trace=["Read question", "Route = Course-grounded", "Retrieve course chunks", "Compose source-grounded answer"],
                tool_calls=["retriever_agent", self.composer.call_label()],
                evidence=[chunk.__dict__ for chunk in evidence],
            )

        results = tavily_search(question)
        answer = self.compose_general_answer(question, results)
        return AgentResult(
            route=route,
            source_status="public_source_found",
            answer=answer,
            trace=["Read question", "Route = General learning", "Call Tavily search", "Synthesize reasoning"],
            tool_calls=[f"tavily_search_tool({question})", self.composer.call_label()],
            evidence=results,
        )

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
        )
        if llm_answer:
            return llm_answer

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

    def compose_general_answer(self, question: str, results: list[dict[str, str]]) -> str:
        llm_answer = self.composer.compose(route="General learning", question=question, evidence=results)
        if llm_answer:
            return llm_answer

        text = normalize(question)
        if has_any(text, ["build slice", "slice"]):
            return (
                "Build slice là một phần nhỏ của sản phẩm được chọn để học nhanh từ user thật.\n\n"
                "Reasoning: thay vì build cả hệ thống, product team chọn một lát cắt end-to-end để kiểm chứng user, task, decision và output.\n"
                "Gợi ý áp dụng: với Learning OS, slice nhỏ là một câu hỏi học tập đi qua route -> search/source check -> answer/refusal."
            )
        first = results[0]["snippet"] if results else "Không có kết quả public đủ rõ."
        return f"Đây là câu hỏi kiến thức chung nên mình dùng public search trước.\n\nReasoning summary: {first}"

__all__ = ["LearningOSAgent", "AgentResult", "Source", "Chunk"]
