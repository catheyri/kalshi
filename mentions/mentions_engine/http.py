from __future__ import annotations

import http.client
import json
import ssl
import time
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi


USER_AGENT = "mentions-engine/0.1 (+https://github.com/openai/codex)"


class HttpClient:
    def __init__(
        self,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        allow_insecure_ssl: bool = False,
    ):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.ssl_context = (
            ssl._create_unverified_context()
            if allow_insecure_ssl
            else ssl.create_default_context(cafile=certifi.where())
        )

    def get_text(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        request = Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        return self._send_text(request)

    def post_json(
        self,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                **(headers or {}),
            },
            method="POST",
        )
        return json.loads(self._send_text(request))

    def _send_text(self, request: Request) -> str:
        url = request.full_url
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(
                    request,
                    timeout=self.timeout_seconds,
                    context=self.ssl_context,
                ) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    return response.read().decode(charset, errors="replace")
            except HTTPError as exc:
                if exc.code == 429 and attempt < self.max_retries:
                    time.sleep(float(attempt + 1))
                    continue
                raise RuntimeError(f"HTTP {exc.code} for {url}") from exc
            except URLError as exc:
                if attempt < self.max_retries and _is_retryable_transport_error(exc.reason):
                    time.sleep(float(attempt + 1))
                    continue
                raise RuntimeError(f"Request failed for {url}: {exc.reason}") from exc
            except _RETRYABLE_TRANSPORT_ERRORS as exc:
                if attempt < self.max_retries:
                    time.sleep(float(attempt + 1))
                    continue
                raise RuntimeError(f"Request failed for {url}: {exc}") from exc
        raise RuntimeError(f"Request failed for {url}")


_RETRYABLE_TRANSPORT_ERRORS = (
    ConnectionResetError,
    TimeoutError,
    http.client.IncompleteRead,
    http.client.RemoteDisconnected,
    ssl.SSLEOFError,
)


def _is_retryable_transport_error(reason: object) -> bool:
    if isinstance(reason, _RETRYABLE_TRANSPORT_ERRORS):
        return True
    if isinstance(reason, ssl.SSLError):
        return True
    return False
