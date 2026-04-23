from __future__ import annotations

import ssl
from typing import Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USER_AGENT = "mentions-engine/0.1 (+https://github.com/openai/codex)"


class HttpClient:
    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds
        self.ssl_context = ssl.create_default_context()

    def get_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        request = Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
                context=self.ssl_context,
            ) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read().decode(charset, errors="replace")
        except HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
        except URLError as exc:
            raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc
