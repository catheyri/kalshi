from __future__ import annotations

from typing import List, Protocol

from mentions_engine.models import Market


class MarketIngestor(Protocol):
    name: str

    def fetch_open_markets(self) -> List[Market]:
        ...
