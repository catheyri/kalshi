from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import ModelBase


@dataclass
class Transcript(ModelBase):
    transcript_id: str
    artifact_id: str
    transcript_type: str
    version: str
    created_at: str
    generator: str
    language: str
    quality_score: Optional[float]
    is_machine_generated: bool
    is_human_supplied: bool
    raw_text: str
    normalized_text: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TranscriptSegment(ModelBase):
    segment_id: str
    transcript_id: str
    start_time_seconds: Optional[float]
    end_time_seconds: Optional[float]
    speaker_id: Optional[str]
    speaker_label: Optional[str]
    channel: Optional[str]
    text: str
    normalized_text: str
    confidence: Optional[float]
    word_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)
