from __future__ import annotations

from enum import Enum
import unicodedata


class Route(str, Enum):
    COURSE = "course_grounded"
    GENERAL = "general_learning"
    OPS = "program_operations"
    AMBIGUOUS = "ambiguous"


def _has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _normalize(text: str) -> str:
    lowered = text.lower().strip()
    return "".join(
        ch for ch in unicodedata.normalize("NFD", lowered)
        if unicodedata.category(ch) != "Mn"
    )


class IntakeRouterAgent:
    def route(self, question: str) -> Route:
        text = question.lower().strip()
        plain = _normalize(question)
        if _has_any(text, ["deadline", "hạn nộp", "nộp repo", "repo cá nhân", "repo nhóm", "grading", "lịch", "mấy giờ"]) or _has_any(plain, ["han nop", "nop repo", "repo ca nhan", "repo nhom", "lich", "may gio"]):
            return Route.OPS
        if (_has_any(text, ["bài này", "cái này", "làm sao", "không hiểu"]) or _has_any(plain, ["bai nay", "cai nay", "lam sao", "khong hieu"])) and not (_has_any(text, ["slide", "day05", "day06", "lab", "rubric"]) or _has_any(plain, ["slide", "day05", "day06", "lab", "rubric"])):
            return Route.AMBIGUOUS
        if _has_any(text, ["trong slide", "theo slide", "day05", "day06", "lab", "rubric", "khóa học", "ai thực chiến", "thầy nói", "mentor nói"]) or _has_any(plain, ["trong slide", "theo slide", "day05", "day06", "lab", "rubric", "khoa hoc", "ai thuc chien", "thay noi", "mentor noi"]):
            return Route.COURSE
        return Route.GENERAL
