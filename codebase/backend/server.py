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
            target = resolve_prototype_target(path)
            self.send_file(target)
            return
        if path.startswith("/api/"):
            pass
        else:
            target = resolve_root_static_target(path)
            if target is not None:
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
            result = agent.ask(
                str(body.get("question", "")),
                conversation=normalize_conversation(body.get("conversation")),
            )
            self.send_json(public_result(result))
            return
        if path == "/api/source":
            source = agent.load_source(
                str(body.get("source", "")),
                title=body.get("title")
            )
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


def resolve_prototype_target(path: str) -> Path:
    if path in ("/", "/prototype", "/prototype/"):
        return PROTOTYPE_DIR / "index.html"
    return PROTOTYPE_DIR / unquote(path.removeprefix("/prototype/"))


def resolve_root_static_target(path: str) -> Path | None:
    relative = unquote(path.removeprefix("/"))
    if not relative:
        return None
    return PROTOTYPE_DIR / relative


def normalize_conversation(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "")).strip()
        content = str(item.get("content", "")).strip()
        if role in {"user", "agent", "assistant"} and content:
            cleaned.append({"role": "assistant" if role == "agent" else role, "content": content})
    return cleaned[-10:]


def public_result(result: Any) -> dict[str, Any]:
    return {
        "route": result.route.value,
        "source_status": result.source_status,
        "answer": result.answer,
        "refusal": result.refusal,
        "suggested_follow_up": result.suggested_follow_up,
        "follow_up_options": result.follow_up_options or [],
    }


def main() -> None:
    port = int(os.getenv("PORT", "8060"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    
    # Lấy IP cục bộ để in ra màn hình cho người dùng dễ chia sẻ
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print(f"Learning OS Support Agent running at:")
    print(f"  - Local:            http://127.0.0.1:{port}")
    print(f"  - On Your Network:  http://{local_ip}:{port}")
    server.serve_forever()



if __name__ == "__main__":
    main()
