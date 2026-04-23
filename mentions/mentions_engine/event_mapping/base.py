from __future__ import annotations

from typing import Optional, Protocol

from mentions_engine.models import Event, Market


class EventMapper(Protocol):
    name: str

    def supports(self, market: Market) -> bool:
        ...

    def map(self, market: Market) -> Optional[Event]:
        ...
