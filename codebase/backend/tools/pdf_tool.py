from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
import urllib.request


def read_pdf(url_or_path: str) -> dict[str, str]:
    try:
        path = materialize_pdf(url_or_path)
        text = extract_pdf_text(path)
        if not text.strip():
            return {
                "status": "ocr_needed",
                "title": Path(url_or_path).name or "PDF source",
                "text": "",
                "note": "PDF không có text layer; cần OCR hoặc user paste nội dung.",
            }
        return {
            "status": "loaded",
            "title": Path(url_or_path).name or "PDF source",
            "text": text,
            "note": url_or_path,
        }
    except Exception as exc:
        return {
            "status": "missing",
            "title": "PDF source unavailable",
            "text": "",
            "note": str(exc),
        }


def materialize_pdf(url_or_path: str) -> Path:
    if url_or_path.lower().startswith(("http://", "https://")):
        with urllib.request.urlopen(url_or_path, timeout=30) as response:
            data = response.read()
        temp = NamedTemporaryFile(delete=False, suffix=".pdf")
        temp.write(data)
        temp.close()
        return Path(temp.name)
    return Path(url_or_path)


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        return "\n\n".join(
            f"# PAGE {index + 1}\n{page.extract_text() or ''}"
            for index, page in enumerate(reader.pages)
        )
    except Exception:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(path))
            return "\n\n".join(
                f"# PAGE {index + 1}\n{page.extract_text() or ''}"
                for index, page in enumerate(reader.pages)
            )
        except Exception as exc:
            raise RuntimeError("No PDF text extractor available. Install pypdf or PyPDF2.") from exc

