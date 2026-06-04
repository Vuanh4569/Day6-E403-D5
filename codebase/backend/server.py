from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
import json
import mimetypes
import os

from learning_agent import LearningOSAgent
from config import get_llm_settings, load_env


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE_DIR = ROOT / "prototype"
agent = LearningOSAgent()


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/prototype", "/prototype/") or path.startswith("/prototype/"):
            if path in ("/", "/prototype", "/prototype/"):
                target = PROTOTYPE_DIR / "index.html"
            else:
                target = PROTOTYPE_DIR / unquote(path.removeprefix("/prototype/"))
            self.send_file(target)
            return
        if path == "/api/health":
            load_env()
            settings = get_llm_settings()
            self.send_json(
                {
                    "ok": True,
                    "sources": len(agent.sources),
                    "llm_provider": settings.provider,
                    "llm_model": settings.model,
                    "has_llm_key": bool(settings.api_key),
                    "has_tavily_key": bool(__import__("os").getenv("TAVILY_API_KEY", "").strip()),
                }
            )
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self.read_json()
        if path == "/api/ask":
            result = agent.ask(str(body.get("question", "")))
            self.send_json(result.to_dict())
            return
        if path == "/api/source":
            source = agent.load_source(str(body.get("source", "")))
            self.send_json(
                {
                    "title": source.title,
                    "type": source.source_type,
                    "status": source.status,
                    "note": source.note,
                    "chunks": len(source.chunks),
                }
            )
            return
        if path == "/api/tools/tavily":
            result = agent.ask(str(body.get("query", "")))
            self.send_json({"evidence": result.evidence})
            return
        self.send_error(404)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw_bytes = self.rfile.read(length)
        raw = decode_request_body(raw_bytes)
        return json.loads(raw)

    def send_json(self, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, target: Path) -> None:
        if not target.exists() or not target.is_file() or not target.resolve().is_relative_to(PROTOTYPE_DIR):
            self.send_error(404)
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def decode_request_body(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp1258", "cp1252"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def main() -> None:
    port = int(os.getenv("PORT", "8060"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Learning OS Support Agent running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
