from __future__ import annotations

from typing import Iterable, List

from mentions_engine.kalshi import KalshiPublicClient
from mentions_engine.models import MarketOutcome
from mentions_engine.utils import stable_hash, utc_now_iso


class KalshiMarketOutcomeImporter:
    name = "kalshi-api"

    def __init__(self, market_tickers: Iterable[str], client: KalshiPublicClient):
        self.market_tickers = list(market_tickers)
        self.client = client

    def load_outcomes(self) -> List[MarketOutcome]:
        outcomes = []
        for ticker in self.market_tickers:
            payload = self.client.fetch_market(ticker)
            resolved = resolve_market_yes_no(payload)
            if resolved is None:
                continue
            observed_at = payload.get("settlement_time") or payload.get("close_time") or utc_now_iso()
            outcomes.append(
                MarketOutcome(
                    outcome_id=f"outcome-{stable_hash(ticker + ':' + observed_at)[:16]}",
                    market_id=ticker,
                    event_id=payload.get("event_ticker"),
                    observed_at=observed_at,
                    resolved_yes=resolved,
                    outcome_source="kalshi_api",
                    label_kind="kalshi_resolution",
                    notes="Imported from Kalshi market details.",
                    metadata={"response_payload": payload},
                )
            )
        return outcomes


def resolve_market_yes_no(payload: dict) -> bool | None:
    result = payload.get("result")
    if isinstance(result, str):
        lower = result.lower()
        if lower in {"yes", "y", "true"}:
            return True
        if lower in {"no", "n", "false"}:
            return False

    for key in ("settlement_value", "final_value", "winning_outcome"):
        value = payload.get(key)
        if isinstance(value, str):
            lower = value.lower()
            if lower in {"yes", "y", "true"}:
                return True
            if lower in {"no", "n", "false"}:
                return False
        if value in (1, 1.0, "1", "1.0"):
            return True
        if value in (0, 0.0, "0", "0.0"):
            return False
    return None
