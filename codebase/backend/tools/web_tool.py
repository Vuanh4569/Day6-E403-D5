from __future__ import annotations

import re
import urllib.request


def read_web(url: str) -> dict[str, str]:
    try:
        with urllib.request.urlopen(url, timeout=12) as response:
            raw = response.read(60000).decode("utf-8", errors="ignore")
        title_match = re.search(r"<title>(.*?)</title>", raw, flags=re.I | re.S)
        title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else "Web source"
        text = re.sub(r"<script.*?</script>", " ", raw, flags=re.I | re.S)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return {"status": "loaded", "title": title, "text": text[:16000], "note": url}
    except Exception as exc:
        return {"status": "missing", "title": "Web source unavailable", "text": "", "note": str(exc)}

