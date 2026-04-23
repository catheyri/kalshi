from __future__ import annotations

from typing import List, Protocol

from mentions_engine.models import MarketOutcome


class OutcomeImporter(Protocol):
    name: str

    def load_outcomes(self) -> List[MarketOutcome]:
        ...
