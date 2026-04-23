from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

from mentions_engine.models import Event, SourceArtifact


@dataclass
class DiscoveryResult:
    events: List[Event]
    artifacts: List[SourceArtifact]


class DiscoveryAdapter(Protocol):
    name: str

    def discover_events(self) -> DiscoveryResult:
        ...
