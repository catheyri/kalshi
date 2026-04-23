from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .base import ModelBase


@dataclass
class CandidateMention(ModelBase):
    candidate_id: str
    market_id: str
    compiled_rule_id: str
    event_id: str
    transcript_id: str
    segment_id: str
    speaker_id: Optional[str]
    matched_text: str
    normalized_match: str
    start_time_seconds: Optional[float]
    end_time_seconds: Optional[float]
    match_type: str
    confidence: Optional[float]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MentionDecision(ModelBase):
    decision_id: str
    candidate_id: str
    market_id: str
    counts: bool
    decision_status: str
    reason_code: str
    explanation: str
    review_status: str
    reviewed_by: Optional[str]
    reviewed_at: Optional[str]
    created_at: str


@dataclass
class EvidenceBundle(ModelBase):
    evidence_bundle_id: str
    market_id: str
    decision_id: str
    artifact_ids: List[str]
    transcript_ids: List[str]
    segment_ids: List[str]
    speaker_ids: List[str]
    source_excerpt: str
    normalized_excerpt: str
    timestamp_reference: Optional[str]
    feed_reference: Optional[str]
    export_payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
