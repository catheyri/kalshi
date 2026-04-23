from __future__ import annotations

import json
from pathlib import Path
from typing import List

from mentions_engine.models import MarketOutcome
from mentions_engine.utils import stable_hash, utc_now_iso


class JsonFileOutcomeImporter:
    name = "json-file"

    def __init__(self, path: Path):
        self.path = path

    def load_outcomes(self) -> List[MarketOutcome]:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        rows = payload.get("outcomes", payload) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("Expected a list of outcomes or an object with an 'outcomes' key")
        return [self._outcome_from_payload(row) for row in rows]

    def _outcome_from_payload(self, payload: dict) -> MarketOutcome:
        market_id = payload["market_id"]
        observed_at = payload.get("observed_at", utc_now_iso())
        resolved_yes = bool(payload["resolved_yes"])
        outcome_id = payload.get("outcome_id") or f"outcome-{stable_hash(market_id + ':' + observed_at)[:16]}"
        return MarketOutcome(
            outcome_id=outcome_id,
            market_id=market_id,
            event_id=payload.get("event_id"),
            observed_at=observed_at,
            resolved_yes=resolved_yes,
            outcome_source=payload.get("outcome_source", "file_import"),
            label_kind=payload.get("label_kind", "kalshi_resolution"),
            notes=payload.get("notes", ""),
            metadata=dict(payload.get("metadata", {})),
        )
