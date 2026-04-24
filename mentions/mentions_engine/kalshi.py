from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode

from mentions_engine.http import HttpClient
from mentions_engine.models import Market


def load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def parse_price_to_cents(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value) * 100))
    except ValueError:
        return None


def parse_intish(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(round(float(value)))
    except ValueError:
        return None


class KalshiPublicClient:
    def __init__(self, base_url: Optional[str] = None, client: Optional[HttpClient] = None):
        self.base_url = (base_url or os.environ.get("KALSHI_API_BASE_URL") or "https://api.elections.kalshi.com/trade-api/v2").rstrip("/")
        self.client = client or HttpClient()

    def get_json(self, path: str, params: Optional[Dict[str, str]] = None) -> dict:
        query = f"?{urlencode(params)}" if params else ""
        text = self.client.get_text(f"{self.base_url}{path}{query}")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            snippet = text.strip().replace("\n", " ")[:160]
            raise RuntimeError(
                f"Expected JSON from {self.base_url}{path}{query}, got non-JSON response: {snippet}"
            ) from exc

    def fetch_market(self, ticker: str) -> dict:
        return self.get_json(f"/markets/{ticker}").get("market", {})

    def fetch_event(self, event_ticker: str, *, with_nested_markets: bool = False) -> dict:
        params = {"with_nested_markets": "true"} if with_nested_markets else None
        return self.get_json(f"/events/{event_ticker}", params=params).get("event", {})

    def fetch_markets_page(
        self,
        *,
        limit: int = 100,
        cursor: Optional[str] = None,
        event_ticker: Optional[str] = None,
        series_ticker: Optional[str] = None,
        min_close_ts: Optional[int] = None,
        max_close_ts: Optional[int] = None,
        status: Optional[str] = None,
        tickers: Optional[Iterable[str]] = None,
    ) -> dict:
        params: Dict[str, str] = {"limit": str(limit)}
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if min_close_ts is not None:
            params["min_close_ts"] = str(min_close_ts)
        if max_close_ts is not None:
            params["max_close_ts"] = str(max_close_ts)
        if status:
            params["status"] = status
        if tickers:
            params["tickers"] = ",".join(tickers)
        return self.get_json("/markets", params=params)

    def fetch_events_page(
        self,
        *,
        category: Optional[str] = None,
        status: Optional[str] = None,
        series_ticker: Optional[str] = None,
        limit: int = 200,
        cursor: Optional[str] = None,
    ) -> dict:
        params: Dict[str, str] = {"limit": str(limit)}
        if category:
            params["category"] = category
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker
        if cursor:
            params["cursor"] = cursor
        return self.get_json("/events", params=params)


class KalshiAuthClient(KalshiPublicClient):
    def __init__(self, env_path: Optional[Path] = None, client: Optional[HttpClient] = None):
        env_path = env_path or Path.cwd().parent / ".env"
        load_dotenv(env_path)
        super().__init__(client=client)

    def get_json(self, path: str, params: Optional[Dict[str, str]] = None) -> dict:
        query = f"?{urlencode(params)}" if params else ""
        headers = self._build_headers("GET", path)
        text = self.client.get_text(f"{self.base_url}{path}{query}", headers=headers)
        return json.loads(text)

    def _build_headers(self, method: str, path: str) -> Dict[str, str]:
        api_key_id = _require_env("KALSHI_API_KEY_ID")
        private_key_path = _require_env("KALSHI_PRIVATE_KEY_PATH")
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{method.upper()}{path}"
        signature = _sign_message(private_key_path, message)
        return {
            "KALSHI-ACCESS-KEY": api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json",
            "User-Agent": "mentions-engine/0.1",
        }


def normalize_market_payload(payload: dict) -> Market:
    title = payload.get("title") or payload.get("ticker") or "unknown"
    subtitle = payload.get("subtitle") or payload.get("yes_sub_title")
    metadata = {
        "event_ticker": payload.get("event_ticker"),
        "market_ticker": payload.get("ticker"),
        "kalshi_status": payload.get("status"),
    }
    optional_metadata = {
        "yes_sub_title": payload.get("yes_sub_title"),
        "series_ticker": payload.get("series_ticker"),
        "result": payload.get("result"),
        "event_title": payload.get("event_title"),
        "event_subtitle": payload.get("event_subtitle"),
        "event_category": payload.get("event_category"),
        "scheduled_start_time": payload.get("strike_date"),
        "response_payload": payload,
    }
    for key, value in optional_metadata.items():
        if value is not None:
            metadata[key] = value
    return Market(
        market_id=payload.get("ticker", title),
        event_id=payload.get("event_ticker"),
        series_id=payload.get("series_ticker"),
        title=title,
        subtitle=subtitle,
        status=payload.get("status"),
        close_time=payload.get("close_time"),
        settlement_time=payload.get("settlement_time"),
        yes_bid=parse_price_to_cents(payload.get("yes_bid_dollars")),
        yes_ask=parse_price_to_cents(payload.get("yes_ask_dollars")),
        no_bid=parse_price_to_cents(payload.get("no_bid_dollars")),
        no_ask=parse_price_to_cents(payload.get("no_ask_dollars")),
        volume=parse_intish(payload.get("volume_fp")),
        open_interest=parse_intish(payload.get("open_interest")),
        rules_text=payload.get("rules_primary"),
        rules_summary_text=payload.get("rules_primary"),
        source_text=payload.get("source_text"),
        url=payload.get("url"),
        last_updated_at=payload.get("updated_time"),
        metadata=metadata,
    )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _sign_message(private_key_path: str, message: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as message_file:
        message_file.write(message.encode("utf-8"))
        message_file.flush()
        message_path = message_file.name
    try:
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                private_key_path,
                "-sigopt",
                "rsa_padding_mode:pss",
                "-sigopt",
                "rsa_pss_saltlen:digest",
                message_path,
            ],
            check=True,
            capture_output=True,
        )
    finally:
        Path(message_path).unlink(missing_ok=True)
    return base64.b64encode(result.stdout).decode("utf-8")
