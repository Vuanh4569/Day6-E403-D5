from __future__ import annotations


class GuardAgent:
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

