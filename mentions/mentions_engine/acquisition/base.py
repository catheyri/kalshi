from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol

from mentions_engine.models import Event, SourceArtifact


@dataclass
class AcquisitionResult:
    artifacts: List[SourceArtifact]


class AcquisitionAdapter(Protocol):
    event_type: str

    def fetch_sources(
        self,
        event: Event,
        known_artifacts: List[SourceArtifact],
    ) -> AcquisitionResult:
        ...
