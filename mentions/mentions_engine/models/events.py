from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import ModelBase


@dataclass
class Event(ModelBase):
    event_id: str
    event_type: str
    title: str
    category: str
    subcategory: str
    scheduled_start_time: Optional[str]
    scheduled_end_time: Optional[str]
    actual_start_time: Optional[str]
    actual_end_time: Optional[str]
    participants: str
    broadcast_network: Optional[str]
    league: Optional[str]
    season: Optional[str]
    venue: Optional[str]
    source_priority: str
    broadcast_priority: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceArtifact(ModelBase):
    artifact_id: str
    event_id: str
    artifact_type: str
    role: str
    provider: str
    uri: Optional[str]
    local_path: Optional[str]
    captured_at: Optional[str]
    published_at: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    duration_seconds: Optional[float]
    checksum: Optional[str]
    mime_type: Optional[str]
    is_official: bool
    is_settlement_candidate: bool
    feed_label: Optional[str]
    feed_priority: Optional[str]
    broadcast_scope: Optional[str]
    language: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
