from __future__ import annotations

from typing import Iterable, List

from mentions_engine.models import (
    CandidateMention,
    CompiledRule,
    EvidenceBundle,
    MentionDecision,
    TranscriptSegment,
)
from mentions_engine.utils import stable_hash, utc_now_iso


def find_candidates(
    market_id: str,
    rule: CompiledRule,
    event_id: str,
    transcript_id: str,
    segments: Iterable[TranscriptSegment],
) -> List[CandidateMention]:
    phrases = [value.lower() for value in (rule.target_terms + rule.allowed_variants)]
    blocked = [value.lower() for value in rule.disallowed_variants]
    candidates: List[CandidateMention] = []

    for segment in segments:
        haystack = segment.normalized_text
        if rule.speaker_scope and "primary_speaker" in rule.speaker_scope:
            if segment.speaker_label and segment.speaker_label.upper().startswith("Q"):
                continue

        for phrase in phrases:
            if phrase not in haystack:
                continue
            if any(disallowed in haystack for disallowed in blocked):
                continue
            candidates.append(
                CandidateMention(
                    candidate_id=f"candidate-{stable_hash(segment.segment_id + ':' + phrase)[:16]}",
                    market_id=market_id,
                    compiled_rule_id=rule.compiled_rule_id,
                    event_id=event_id,
                    transcript_id=transcript_id,
                    segment_id=segment.segment_id,
                    speaker_id=segment.speaker_id,
                    matched_text=phrase,
                    normalized_match=phrase,
                    start_time_seconds=segment.start_time_seconds,
                    end_time_seconds=segment.end_time_seconds,
                    match_type="exact" if phrase in [v.lower() for v in rule.target_terms] else "variant",
                    confidence=1.0,
                    metadata={"speaker_label": segment.speaker_label},
                )
            )
    return candidates


def make_decisions(candidates: Iterable[CandidateMention]) -> List[MentionDecision]:
    decisions: List[MentionDecision] = []
    for candidate in candidates:
        decisions.append(
            MentionDecision(
                decision_id=f"decision-{stable_hash(candidate.candidate_id)[:16]}",
                candidate_id=candidate.candidate_id,
                market_id=candidate.market_id,
                counts=True,
                decision_status="accepted",
                reason_code="matched_phrase",
                explanation=f"Matched '{candidate.normalized_match}' in segment {candidate.segment_id}.",
                review_status="auto",
                reviewed_by=None,
                reviewed_at=None,
                created_at=utc_now_iso(),
            )
        )
    return decisions


def build_evidence(
    artifact_id: str,
    transcript_id: str,
    segments: List[TranscriptSegment],
    candidate: CandidateMention,
    decision: MentionDecision,
) -> EvidenceBundle:
    matched_segment = next(segment for segment in segments if segment.segment_id == candidate.segment_id)
    speaker_ids = [value for value in [matched_segment.speaker_id] if value]
    return EvidenceBundle(
        evidence_bundle_id=f"evidence-{stable_hash(decision.decision_id)[:16]}",
        market_id=candidate.market_id,
        decision_id=decision.decision_id,
        artifact_ids=[artifact_id],
        transcript_ids=[transcript_id],
        segment_ids=[candidate.segment_id],
        speaker_ids=speaker_ids,
        source_excerpt=matched_segment.text,
        normalized_excerpt=matched_segment.normalized_text,
        timestamp_reference=None if matched_segment.start_time_seconds is None else str(matched_segment.start_time_seconds),
        feed_reference=None,
        export_payload={
            "matched_text": candidate.matched_text,
            "speaker_label": matched_segment.speaker_label,
        },
        created_at=utc_now_iso(),
    )
