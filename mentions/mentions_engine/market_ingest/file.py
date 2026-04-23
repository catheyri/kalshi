from __future__ import annotations

import json
from pathlib import Path
from typing import List

from mentions_engine.models import Market


class JsonFileMarketIngestor:
    name = "json-file"

    def __init__(self, path: Path):
        self.path = path

    def fetch_open_markets(self) -> List[Market]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = payload.get("markets", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("Expected a list of markets or an object with a 'markets' key")
        return [self._market_from_payload(row) for row in rows]

    def _market_from_payload(self, payload: dict) -> Market:
        metadata = dict(payload.get("metadata", {}))
        return Market(
            market_id=payload["market_id"],
            event_id=payload.get("event_id"),
            series_id=payload.get("series_id"),
            title=payload.get("title", payload["market_id"]),
            subtitle=payload.get("subtitle"),
            status=payload.get("status"),
            close_time=payload.get("close_time"),
            settlement_time=payload.get("settlement_time"),
            yes_bid=payload.get("yes_bid"),
            yes_ask=payload.get("yes_ask"),
            no_bid=payload.get("no_bid"),
            no_ask=payload.get("no_ask"),
            volume=payload.get("volume"),
            open_interest=payload.get("open_interest"),
            rules_text=payload.get("rules_text"),
            rules_summary_text=payload.get("rules_summary_text"),
            source_text=payload.get("source_text"),
            url=payload.get("url"),
            last_updated_at=payload.get("last_updated_at"),
            metadata=metadata,
        )
