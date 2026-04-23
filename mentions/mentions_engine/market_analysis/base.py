from __future__ import annotations

from typing import Optional, Protocol

from mentions_engine.models import Market


class MarketParser(Protocol):
    name: str

    def parse(self, market: Market) -> Optional[Market]:
        ...
