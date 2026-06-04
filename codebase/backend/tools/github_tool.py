from __future__ import annotations

from urllib.parse import urlparse
import base64
import json
import os
import urllib.request

from config import load_env


PRIORITY_NAMES = ("readme", "guide", "assignment", "rubric", "spec", "lab", "day")
PRIORITY_EXTS = (".md", ".txt", ".ipynb")
BRANCH_CANDIDATES = ("main", "master", "phuc-dev")
FALLBACK_PRIORITY_PATHS = (
    "README.md",
    "readme.md",
    "spec/README.md",
    "codebase/README.md",
    "hackathon-rules.md",
    "docs/README.md",
    "docs/readme.md",
    "rubric.md",
    "assignment.md",
)


def read_github(url: str) -> dict[str, str]:
    load_env()
    
    # Try using Node.js github-reader-tool if it's a repository
    try:
        parsed = parse_github_url(url)
        if parsed["kind"] == "repo":
            import socket
            import subprocess
            import time
            from pathlib import Path

            def is_port_open(port: int) -> bool:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    return s.connect_ex(('127.0.0.1', port)) == 0

            # If Node.js server is not running on port 3000, start it
            if not is_port_open(3000):
                tool_dir = Path(__file__).resolve().parents[2] / "github-reader-tool"
                server_js = tool_dir / "server.js"
                if server_js.exists():
                    subprocess.Popen(["node", "server.js"], cwd=str(tool_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    for _ in range(40):
                        if is_port_open(3000):
                            break
                        time.sleep(0.1)

            if is_port_open(3000):
                token = os.getenv("GITHUB_TOKEN", "").strip()
                payload = {
                    "githubUrl": url,
                    "githubToken": token
                }
                req = urllib.request.Request(
                    "http://127.0.0.1:3000/api/read-github",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=60) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    if data.get("success"):
                        return {
                            "status": "loaded",
                            "title": data.get("repo", f"{parsed['owner']}/{parsed['repo']}"),
                            "text": data.get("text", ""),
                            "note": f"Read {data.get('fileCount', 0)} files via Node.js github-reader-tool."
                        }
    except Exception as exc:
        # Fallback to native python implementation silently
        pass

    # Native Python Fallback
    try:
        parsed = parse_github_url(url)
        if parsed["kind"] == "file":
            text = fetch_raw_github_file(parsed)
            return {"status": "loaded", "title": parsed["path"], "text": text, "note": url}
        text = fetch_repo_priority_text(parsed["owner"], parsed["repo"], parsed.get("ref") or "main")
        return {
            "status": "loaded" if text else "missing",
            "title": f"{parsed['owner']}/{parsed['repo']}",
            "text": text,
            "note": "Read priority README/docs/rubric/lab files from public GitHub repo.",
        }
    except Exception as exc:
        return {
            "status": "missing",
            "title": "GitHub source unavailable",
            "text": "",
            "note": str(exc),
        }


def parse_github_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parsed.netloc.lower() != "github.com":
        raise ValueError("Not a github.com URL")
    result = {"owner": parts[0], "repo": parts[1], "kind": "repo"}
    if len(parts) >= 5 and parts[2] == "blob":
        result.update({"kind": "file", "ref": parts[3], "path": "/".join(parts[4:])})
    return result


def fetch_raw_github_file(parsed: dict[str, str]) -> str:
    url = f"https://raw.githubusercontent.com/{parsed['owner']}/{parsed['repo']}/{parsed['ref']}/{parsed['path']}"
    return get_text(url)


def fetch_repo_priority_text(owner: str, repo: str, ref: str) -> str:
    try:
        tree = github_api_json(f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1")
        files = [
            item["path"]
            for item in tree.get("tree", [])
            if item.get("type") == "blob" and is_priority_file(item.get("path", ""))
        ][:12]
        chunks: list[str] = []
        for path in files:
            try:
                content = github_api_json(f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}")
                if content.get("encoding") == "base64":
                    text = base64.b64decode(content.get("content", "")).decode("utf-8", errors="ignore")
                else:
                    text = get_text(content.get("download_url", ""))
                chunks.append(f"\n\n# FILE: {path}\n{text[:8000]}")
            except Exception:
                continue
        if chunks:
            return "\n".join(chunks)
    except Exception:
        pass

    return fetch_repo_priority_text_fallback(owner, repo)


def is_priority_file(path: str) -> bool:
    lowered = path.lower()
    return lowered.endswith(PRIORITY_EXTS) and any(name in lowered for name in PRIORITY_NAMES)


def fetch_repo_priority_text_fallback(owner: str, repo: str) -> str:
    chunks: list[str] = []
    for ref in BRANCH_CANDIDATES:
        for path in FALLBACK_PRIORITY_PATHS:
            raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"
            try:
                text = get_text(raw_url)
            except Exception:
                continue
            if not text.strip():
                continue
            chunks.append(f"\n\n# FILE: {path}\n{text[:8000]}")
        if chunks:
            break
    return "\n".join(chunks)


def github_api_json(url: str) -> dict:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str) -> str:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read().decode("utf-8", errors="ignore")


def github_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "learning-os-agent"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
