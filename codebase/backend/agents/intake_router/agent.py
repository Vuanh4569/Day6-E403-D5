from __future__ import annotations

from enum import Enum


class Route(str, Enum):
    COURSE = "course_grounded"
    GENERAL = "general_learning"
    OPS = "program_operations"
    AMBIGUOUS = "ambiguous"


def _has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


class IntakeRouterAgent:
    def route(self, question: str) -> Route:
        text = question.lower().strip()
        if _has_any(text, ["deadline", "hạn nộp", "nộp repo", "repo cá nhân", "repo nhóm", "grading", "lịch", "mấy giờ"]):
            return Route.OPS
        if _has_any(text, ["bài này", "cái này", "làm sao", "không hiểu"]) and not _has_any(text, ["slide", "day05", "day06", "lab", "rubric"]):
            return Route.AMBIGUOUS
        if _has_any(text, ["trong slide", "theo slide", "day05", "day06", "lab", "rubric", "khóa học", "ai thực chiến", "thầy nói", "mentor nói"]):
            return Route.COURSE
        return Route.GENERAL

