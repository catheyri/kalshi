from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from mentions_engine.models import (
    CompiledRule,
    CandidateMention,
    Event,
    EvidenceBundle,
    Market,
    MarketOutcome,
    MentionDecision,
    Opportunity,
    PriceSnapshot,
    ProbabilityEstimate,
    SourceArtifact,
    Transcript,
    TranscriptSegment,
)


class Database:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT NOT NULL,
                    scheduled_start_time TEXT,
                    scheduled_end_time TEXT,
                    actual_start_time TEXT,
                    actual_end_time TEXT,
                    participants TEXT NOT NULL,
                    broadcast_network TEXT,
                    league TEXT,
                    season TEXT,
                    venue TEXT,
                    source_priority TEXT NOT NULL,
                    broadcast_priority TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS markets (
                    market_id TEXT PRIMARY KEY,
                    event_id TEXT,
                    series_id TEXT,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    status TEXT,
                    close_time TEXT,
                    settlement_time TEXT,
                    yes_bid INTEGER,
                    yes_ask INTEGER,
                    no_bid INTEGER,
                    no_ask INTEGER,
                    volume INTEGER,
                    open_interest INTEGER,
                    rules_text TEXT,
                    rules_summary_text TEXT,
                    source_text TEXT,
                    url TEXT,
                    last_updated_at TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS source_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    event_id TEXT NOT NULL REFERENCES events(event_id),
                    artifact_type TEXT NOT NULL,
                    role TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    uri TEXT,
                    local_path TEXT,
                    captured_at TEXT,
                    published_at TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds REAL,
                    checksum TEXT,
                    mime_type TEXT,
                    is_official INTEGER NOT NULL,
                    is_settlement_candidate INTEGER NOT NULL,
                    feed_label TEXT,
                    feed_priority TEXT,
                    broadcast_scope TEXT,
                    language TEXT,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS transcripts (
                    transcript_id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL REFERENCES source_artifacts(artifact_id),
                    transcript_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    generator TEXT NOT NULL,
                    language TEXT NOT NULL,
                    quality_score REAL,
                    is_machine_generated INTEGER NOT NULL,
                    is_human_supplied INTEGER NOT NULL,
                    raw_text TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS transcript_segments (
                    segment_id TEXT PRIMARY KEY,
                    transcript_id TEXT NOT NULL REFERENCES transcripts(transcript_id),
                    start_time_seconds REAL,
                    end_time_seconds REAL,
                    speaker_id TEXT,
                    speaker_label TEXT,
                    channel TEXT,
                    text TEXT NOT NULL,
                    normalized_text TEXT NOT NULL,
                    confidence REAL,
                    word_count INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS compiled_rules (
                    compiled_rule_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS candidate_mentions (
                    candidate_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    compiled_rule_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    transcript_id TEXT NOT NULL,
                    segment_id TEXT NOT NULL,
                    speaker_id TEXT,
                    matched_text TEXT NOT NULL,
                    normalized_match TEXT NOT NULL,
                    start_time_seconds REAL,
                    end_time_seconds REAL,
                    match_type TEXT NOT NULL,
                    confidence REAL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mention_decisions (
                    decision_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    counts INTEGER NOT NULL,
                    decision_status TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    explanation TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS evidence_bundles (
                    evidence_bundle_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    artifact_ids_json TEXT NOT NULL,
                    transcript_ids_json TEXT NOT NULL,
                    segment_ids_json TEXT NOT NULL,
                    speaker_ids_json TEXT NOT NULL,
                    source_excerpt TEXT NOT NULL,
                    normalized_excerpt TEXT NOT NULL,
                    timestamp_reference TEXT,
                    feed_reference TEXT,
                    export_payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    event_id TEXT,
                    observed_at TEXT NOT NULL,
                    resolved_yes INTEGER NOT NULL,
                    outcome_source TEXT NOT NULL,
                    label_kind TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS price_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    yes_bid INTEGER,
                    yes_ask INTEGER,
                    no_bid INTEGER,
                    no_ask INTEGER,
                    last_price INTEGER,
                    volume INTEGER,
                    open_interest INTEGER,
                    orderbook_depth INTEGER,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS probability_estimates (
                    estimate_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    event_id TEXT,
                    generated_at TEXT NOT NULL,
                    probability_yes REAL NOT NULL,
                    fair_yes_price INTEGER NOT NULL,
                    fair_no_price INTEGER NOT NULL,
                    model_name TEXT NOT NULL,
                    model_version TEXT NOT NULL,
                    input_summary TEXT NOT NULL,
                    uncertainty_score REAL,
                    confidence_band_low REAL,
                    confidence_band_high REAL,
                    notes TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS opportunities (
                    opportunity_id TEXT PRIMARY KEY,
                    market_id TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    side TEXT NOT NULL,
                    market_price INTEGER,
                    fair_price INTEGER NOT NULL,
                    edge_cents INTEGER,
                    liquidity_score REAL,
                    execution_risk_score REAL,
                    data_quality_score REAL,
                    rule_risk_score REAL,
                    priority_score REAL,
                    notes TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                """
            )

    def upsert_market(self, market: Market) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO markets (
                    market_id, event_id, series_id, title, subtitle, status, close_time, settlement_time,
                    yes_bid, yes_ask, no_bid, no_ask, volume, open_interest, rules_text, rules_summary_text,
                    source_text, url, last_updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                    event_id=excluded.event_id,
                    series_id=excluded.series_id,
                    title=excluded.title,
                    subtitle=excluded.subtitle,
                    status=excluded.status,
                    close_time=excluded.close_time,
                    settlement_time=excluded.settlement_time,
                    yes_bid=excluded.yes_bid,
                    yes_ask=excluded.yes_ask,
                    no_bid=excluded.no_bid,
                    no_ask=excluded.no_ask,
                    volume=excluded.volume,
                    open_interest=excluded.open_interest,
                    rules_text=excluded.rules_text,
                    rules_summary_text=excluded.rules_summary_text,
                    source_text=excluded.source_text,
                    url=excluded.url,
                    last_updated_at=excluded.last_updated_at,
                    metadata_json=excluded.metadata_json
                """,
                (
                    market.market_id,
                    market.event_id,
                    market.series_id,
                    market.title,
                    market.subtitle,
                    market.status,
                    market.close_time,
                    market.settlement_time,
                    market.yes_bid,
                    market.yes_ask,
                    market.no_bid,
                    market.no_ask,
                    market.volume,
                    market.open_interest,
                    market.rules_text,
                    market.rules_summary_text,
                    market.source_text,
                    market.url,
                    market.last_updated_at,
                    json.dumps(market.metadata, sort_keys=True),
                ),
            )

    def upsert_event(self, event: Event) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    event_id, event_type, title, category, subcategory,
                    scheduled_start_time, scheduled_end_time, actual_start_time, actual_end_time,
                    participants, broadcast_network, league, season, venue,
                    source_priority, broadcast_priority, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO UPDATE SET
                    event_type=excluded.event_type,
                    title=excluded.title,
                    category=excluded.category,
                    subcategory=excluded.subcategory,
                    scheduled_start_time=excluded.scheduled_start_time,
                    scheduled_end_time=excluded.scheduled_end_time,
                    actual_start_time=excluded.actual_start_time,
                    actual_end_time=excluded.actual_end_time,
                    participants=excluded.participants,
                    broadcast_network=excluded.broadcast_network,
                    league=excluded.league,
                    season=excluded.season,
                    venue=excluded.venue,
                    source_priority=excluded.source_priority,
                    broadcast_priority=excluded.broadcast_priority,
                    metadata_json=excluded.metadata_json
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.title,
                    event.category,
                    event.subcategory,
                    event.scheduled_start_time,
                    event.scheduled_end_time,
                    event.actual_start_time,
                    event.actual_end_time,
                    event.participants,
                    event.broadcast_network,
                    event.league,
                    event.season,
                    event.venue,
                    event.source_priority,
                    event.broadcast_priority,
                    json.dumps(event.metadata, sort_keys=True),
                ),
            )

    def upsert_source_artifact(self, artifact: SourceArtifact) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO source_artifacts (
                    artifact_id, event_id, artifact_type, role, provider, uri, local_path,
                    captured_at, published_at, start_time, end_time, duration_seconds, checksum,
                    mime_type, is_official, is_settlement_candidate, feed_label, feed_priority,
                    broadcast_scope, language, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    event_id=excluded.event_id,
                    artifact_type=excluded.artifact_type,
                    role=excluded.role,
                    provider=excluded.provider,
                    uri=excluded.uri,
                    local_path=excluded.local_path,
                    captured_at=excluded.captured_at,
                    published_at=excluded.published_at,
                    start_time=excluded.start_time,
                    end_time=excluded.end_time,
                    duration_seconds=excluded.duration_seconds,
                    checksum=excluded.checksum,
                    mime_type=excluded.mime_type,
                    is_official=excluded.is_official,
                    is_settlement_candidate=excluded.is_settlement_candidate,
                    feed_label=excluded.feed_label,
                    feed_priority=excluded.feed_priority,
                    broadcast_scope=excluded.broadcast_scope,
                    language=excluded.language,
                    metadata_json=excluded.metadata_json
                """,
                (
                    artifact.artifact_id,
                    artifact.event_id,
                    artifact.artifact_type,
                    artifact.role,
                    artifact.provider,
                    artifact.uri,
                    artifact.local_path,
                    artifact.captured_at,
                    artifact.published_at,
                    artifact.start_time,
                    artifact.end_time,
                    artifact.duration_seconds,
                    artifact.checksum,
                    artifact.mime_type,
                    int(artifact.is_official),
                    int(artifact.is_settlement_candidate),
                    artifact.feed_label,
                    artifact.feed_priority,
                    artifact.broadcast_scope,
                    artifact.language,
                    json.dumps(artifact.metadata, sort_keys=True),
                ),
            )

    def upsert_transcript(self, transcript: Transcript) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO transcripts (
                    transcript_id, artifact_id, transcript_type, version, created_at, generator,
                    language, quality_score, is_machine_generated, is_human_supplied, raw_text,
                    normalized_text, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(transcript_id) DO UPDATE SET
                    artifact_id=excluded.artifact_id,
                    transcript_type=excluded.transcript_type,
                    version=excluded.version,
                    created_at=excluded.created_at,
                    generator=excluded.generator,
                    language=excluded.language,
                    quality_score=excluded.quality_score,
                    is_machine_generated=excluded.is_machine_generated,
                    is_human_supplied=excluded.is_human_supplied,
                    raw_text=excluded.raw_text,
                    normalized_text=excluded.normalized_text,
                    metadata_json=excluded.metadata_json
                """,
                (
                    transcript.transcript_id,
                    transcript.artifact_id,
                    transcript.transcript_type,
                    transcript.version,
                    transcript.created_at,
                    transcript.generator,
                    transcript.language,
                    transcript.quality_score,
                    int(transcript.is_machine_generated),
                    int(transcript.is_human_supplied),
                    transcript.raw_text,
                    transcript.normalized_text,
                    json.dumps(transcript.metadata, sort_keys=True),
                ),
            )

    def replace_segments(
        self,
        transcript_id: str,
        segments: Iterable[TranscriptSegment],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM transcript_segments WHERE transcript_id = ?",
                (transcript_id,),
            )
            conn.executemany(
                """
                INSERT INTO transcript_segments (
                    segment_id, transcript_id, start_time_seconds, end_time_seconds, speaker_id,
                    speaker_label, channel, text, normalized_text, confidence, word_count, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        segment.segment_id,
                        segment.transcript_id,
                        segment.start_time_seconds,
                        segment.end_time_seconds,
                        segment.speaker_id,
                        segment.speaker_label,
                        segment.channel,
                        segment.text,
                        segment.normalized_text,
                        segment.confidence,
                        segment.word_count,
                        json.dumps(segment.metadata, sort_keys=True),
                    )
                    for segment in segments
                ],
            )

    def upsert_compiled_rule(self, rule: CompiledRule) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO compiled_rules (compiled_rule_id, market_id, payload_json)
                VALUES (?, ?, ?)
                ON CONFLICT(compiled_rule_id) DO UPDATE SET
                    market_id=excluded.market_id,
                    payload_json=excluded.payload_json
                """,
                (rule.compiled_rule_id, rule.market_id, json.dumps(rule.to_dict(), sort_keys=True)),
            )

    def upsert_market_outcome(self, outcome: MarketOutcome) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO market_outcomes (
                    outcome_id, market_id, event_id, observed_at, resolved_yes, outcome_source,
                    label_kind, notes, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(outcome_id) DO UPDATE SET
                    market_id=excluded.market_id,
                    event_id=excluded.event_id,
                    observed_at=excluded.observed_at,
                    resolved_yes=excluded.resolved_yes,
                    outcome_source=excluded.outcome_source,
                    label_kind=excluded.label_kind,
                    notes=excluded.notes,
                    metadata_json=excluded.metadata_json
                """,
                (
                    outcome.outcome_id,
                    outcome.market_id,
                    outcome.event_id,
                    outcome.observed_at,
                    int(outcome.resolved_yes),
                    outcome.outcome_source,
                    outcome.label_kind,
                    outcome.notes,
                    json.dumps(outcome.metadata, sort_keys=True),
                ),
            )

    def upsert_price_snapshot(self, snapshot: PriceSnapshot) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO price_snapshots (
                    snapshot_id, market_id, captured_at, yes_bid, yes_ask, no_bid, no_ask,
                    last_price, volume, open_interest, orderbook_depth, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    market_id=excluded.market_id,
                    captured_at=excluded.captured_at,
                    yes_bid=excluded.yes_bid,
                    yes_ask=excluded.yes_ask,
                    no_bid=excluded.no_bid,
                    no_ask=excluded.no_ask,
                    last_price=excluded.last_price,
                    volume=excluded.volume,
                    open_interest=excluded.open_interest,
                    orderbook_depth=excluded.orderbook_depth,
                    metadata_json=excluded.metadata_json
                """,
                (
                    snapshot.snapshot_id,
                    snapshot.market_id,
                    snapshot.captured_at,
                    snapshot.yes_bid,
                    snapshot.yes_ask,
                    snapshot.no_bid,
                    snapshot.no_ask,
                    snapshot.last_price,
                    snapshot.volume,
                    snapshot.open_interest,
                    snapshot.orderbook_depth,
                    json.dumps(snapshot.metadata, sort_keys=True),
                ),
            )

    def upsert_probability_estimate(self, estimate: ProbabilityEstimate) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO probability_estimates (
                    estimate_id, market_id, event_id, generated_at, probability_yes, fair_yes_price,
                    fair_no_price, model_name, model_version, input_summary, uncertainty_score,
                    confidence_band_low, confidence_band_high, notes, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(estimate_id) DO UPDATE SET
                    market_id=excluded.market_id,
                    event_id=excluded.event_id,
                    generated_at=excluded.generated_at,
                    probability_yes=excluded.probability_yes,
                    fair_yes_price=excluded.fair_yes_price,
                    fair_no_price=excluded.fair_no_price,
                    model_name=excluded.model_name,
                    model_version=excluded.model_version,
                    input_summary=excluded.input_summary,
                    uncertainty_score=excluded.uncertainty_score,
                    confidence_band_low=excluded.confidence_band_low,
                    confidence_band_high=excluded.confidence_band_high,
                    notes=excluded.notes,
                    metadata_json=excluded.metadata_json
                """,
                (
                    estimate.estimate_id,
                    estimate.market_id,
                    estimate.event_id,
                    estimate.generated_at,
                    estimate.probability_yes,
                    estimate.fair_yes_price,
                    estimate.fair_no_price,
                    estimate.model_name,
                    estimate.model_version,
                    estimate.input_summary,
                    estimate.uncertainty_score,
                    estimate.confidence_band_low,
                    estimate.confidence_band_high,
                    estimate.notes,
                    json.dumps(estimate.metadata, sort_keys=True),
                ),
            )

    def upsert_opportunity(self, opportunity: Opportunity) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO opportunities (
                    opportunity_id, market_id, generated_at, side, market_price, fair_price, edge_cents,
                    liquidity_score, execution_risk_score, data_quality_score, rule_risk_score,
                    priority_score, notes, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(opportunity_id) DO UPDATE SET
                    market_id=excluded.market_id,
                    generated_at=excluded.generated_at,
                    side=excluded.side,
                    market_price=excluded.market_price,
                    fair_price=excluded.fair_price,
                    edge_cents=excluded.edge_cents,
                    liquidity_score=excluded.liquidity_score,
                    execution_risk_score=excluded.execution_risk_score,
                    data_quality_score=excluded.data_quality_score,
                    rule_risk_score=excluded.rule_risk_score,
                    priority_score=excluded.priority_score,
                    notes=excluded.notes,
                    metadata_json=excluded.metadata_json
                """,
                (
                    opportunity.opportunity_id,
                    opportunity.market_id,
                    opportunity.generated_at,
                    opportunity.side,
                    opportunity.market_price,
                    opportunity.fair_price,
                    opportunity.edge_cents,
                    opportunity.liquidity_score,
                    opportunity.execution_risk_score,
                    opportunity.data_quality_score,
                    opportunity.rule_risk_score,
                    opportunity.priority_score,
                    opportunity.notes,
                    json.dumps(opportunity.metadata, sort_keys=True),
                ),
            )

    def replace_match_results(
        self,
        rule: CompiledRule,
        transcript_id: str,
        candidates: Iterable[CandidateMention],
        decisions: Iterable[MentionDecision],
        evidence_bundles: Iterable[EvidenceBundle],
    ) -> None:
        candidate_rows = list(candidates)
        decision_rows = list(decisions)
        evidence_rows = list(evidence_bundles)
        with self.connect() as conn:
            conn.execute(
                """
                DELETE FROM evidence_bundles
                WHERE decision_id IN (
                    SELECT decision_id FROM mention_decisions
                    WHERE candidate_id IN (
                        SELECT candidate_id FROM candidate_mentions
                        WHERE compiled_rule_id = ? AND transcript_id = ?
                    )
                )
                """,
                (rule.compiled_rule_id, transcript_id),
            )
            conn.execute(
                """
                DELETE FROM mention_decisions
                WHERE candidate_id IN (
                    SELECT candidate_id FROM candidate_mentions
                    WHERE compiled_rule_id = ? AND transcript_id = ?
                )
                """,
                (rule.compiled_rule_id, transcript_id),
            )
            conn.execute(
                "DELETE FROM candidate_mentions WHERE compiled_rule_id = ? AND transcript_id = ?",
                (rule.compiled_rule_id, transcript_id),
            )
            conn.executemany(
                """
                INSERT INTO candidate_mentions (
                    candidate_id, market_id, compiled_rule_id, event_id, transcript_id, segment_id,
                    speaker_id, matched_text, normalized_match, start_time_seconds, end_time_seconds,
                    match_type, confidence, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        candidate.candidate_id,
                        candidate.market_id,
                        candidate.compiled_rule_id,
                        candidate.event_id,
                        candidate.transcript_id,
                        candidate.segment_id,
                        candidate.speaker_id,
                        candidate.matched_text,
                        candidate.normalized_match,
                        candidate.start_time_seconds,
                        candidate.end_time_seconds,
                        candidate.match_type,
                        candidate.confidence,
                        json.dumps(candidate.metadata, sort_keys=True),
                    )
                    for candidate in candidate_rows
                ],
            )
            conn.executemany(
                """
                INSERT INTO mention_decisions (
                    decision_id, candidate_id, market_id, counts, decision_status, reason_code, explanation,
                    review_status, reviewed_by, reviewed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        decision.decision_id,
                        decision.candidate_id,
                        decision.market_id,
                        int(decision.counts),
                        decision.decision_status,
                        decision.reason_code,
                        decision.explanation,
                        decision.review_status,
                        decision.reviewed_by,
                        decision.reviewed_at,
                        decision.created_at,
                    )
                    for decision in decision_rows
                ],
            )
            conn.executemany(
                """
                INSERT INTO evidence_bundles (
                    evidence_bundle_id, market_id, decision_id, artifact_ids_json, transcript_ids_json,
                    segment_ids_json, speaker_ids_json, source_excerpt, normalized_excerpt, timestamp_reference,
                    feed_reference, export_payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        bundle.evidence_bundle_id,
                        bundle.market_id,
                        bundle.decision_id,
                        json.dumps(bundle.artifact_ids, sort_keys=True),
                        json.dumps(bundle.transcript_ids, sort_keys=True),
                        json.dumps(bundle.segment_ids, sort_keys=True),
                        json.dumps(bundle.speaker_ids, sort_keys=True),
                        bundle.source_excerpt,
                        bundle.normalized_excerpt,
                        bundle.timestamp_reference,
                        bundle.feed_reference,
                        json.dumps(bundle.export_payload, sort_keys=True),
                        bundle.created_at,
                    )
                    for bundle in evidence_rows
                ],
            )

    def list_events(self) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM events ORDER BY COALESCE(scheduled_start_time, '') DESC, event_id DESC"
            ).fetchall()

    def get_market(self, market_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM markets WHERE market_id = ?",
                (market_id,),
            ).fetchone()

    def list_markets(self, status: Optional[str] = None) -> List[sqlite3.Row]:
        with self.connect() as conn:
            if status is None:
                return conn.execute(
                    "SELECT * FROM markets ORDER BY COALESCE(close_time, '') ASC, market_id ASC"
                ).fetchall()
            return conn.execute(
                "SELECT * FROM markets WHERE status = ? ORDER BY COALESCE(close_time, '') ASC, market_id ASC",
                (status,),
            ).fetchall()

    def get_event(self, event_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM events WHERE event_id = ?",
                (event_id,),
            ).fetchone()

    def get_compiled_rule_for_market(self, market_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM compiled_rules WHERE market_id = ? ORDER BY compiled_rule_id DESC LIMIT 1",
                (market_id,),
            ).fetchone()

    def list_artifacts_for_event(self, event_id: str) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM source_artifacts WHERE event_id = ? ORDER BY artifact_id",
                (event_id,),
            ).fetchall()

    def get_artifact(self, artifact_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM source_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()

    def list_transcripts(self) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM transcripts ORDER BY created_at DESC, transcript_id DESC"
            ).fetchall()

    def get_transcript(self, transcript_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM transcripts WHERE transcript_id = ?",
                (transcript_id,),
            ).fetchone()

    def list_transcripts_for_event(self, event_id: str) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT t.*
                FROM transcripts t
                JOIN source_artifacts sa ON sa.artifact_id = t.artifact_id
                WHERE sa.event_id = ?
                ORDER BY t.created_at DESC, t.transcript_id DESC
                """,
                (event_id,),
            ).fetchall()

    def list_segments(self, transcript_id: str) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM transcript_segments WHERE transcript_id = ? ORDER BY segment_id",
                (transcript_id,),
            ).fetchall()

    def count_segments(self, transcript_id: str) -> int:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM transcript_segments WHERE transcript_id = ?",
                (transcript_id,),
            ).fetchone()
            return int(row["count"]) if row is not None else 0

    def list_candidate_mentions(
        self,
        compiled_rule_id: str,
        transcript_id: str,
    ) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM candidate_mentions
                WHERE compiled_rule_id = ? AND transcript_id = ?
                ORDER BY candidate_id
                """,
                (compiled_rule_id, transcript_id),
            ).fetchall()

    def list_mention_decisions_for_rule(
        self,
        compiled_rule_id: str,
        transcript_id: str,
    ) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT md.*
                FROM mention_decisions md
                JOIN candidate_mentions cm ON cm.candidate_id = md.candidate_id
                WHERE cm.compiled_rule_id = ? AND cm.transcript_id = ?
                ORDER BY md.decision_id
                """,
                (compiled_rule_id, transcript_id),
            ).fetchall()

    def list_evidence_bundles_for_rule(
        self,
        compiled_rule_id: str,
        transcript_id: str,
    ) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT eb.*
                FROM evidence_bundles eb
                JOIN mention_decisions md ON md.decision_id = eb.decision_id
                JOIN candidate_mentions cm ON cm.candidate_id = md.candidate_id
                WHERE cm.compiled_rule_id = ? AND cm.transcript_id = ?
                ORDER BY eb.evidence_bundle_id
                """,
                (compiled_rule_id, transcript_id),
            ).fetchall()

    def list_market_outcomes(self, market_id: str) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM market_outcomes WHERE market_id = ? ORDER BY observed_at DESC",
                (market_id,),
            ).fetchall()

    def list_market_outcomes_for_market_family(
        self,
        excluded_market_event_id: Optional[str],
        event_type: str,
        compiled_rule_id: Optional[str],
    ) -> List[sqlite3.Row]:
        with self.connect() as conn:
            params = [event_type]
            sql = """
                SELECT mo.*
                FROM market_outcomes mo
                JOIN markets m ON m.market_id = mo.market_id
                JOIN events e ON e.event_id = COALESCE(m.event_id, mo.event_id)
                LEFT JOIN compiled_rules cr ON cr.market_id = m.market_id
                WHERE e.event_type = ?
            """
            if excluded_market_event_id is not None:
                sql += " AND COALESCE(m.event_id, mo.event_id) != ?"
                params.append(excluded_market_event_id)
            if compiled_rule_id is not None:
                sql += " AND cr.compiled_rule_id = ?"
                params.append(compiled_rule_id)
            sql += " ORDER BY mo.observed_at DESC"
            return conn.execute(sql, tuple(params)).fetchall()

    def list_market_outcome_training_rows(self, event_type: str) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT mo.*, m.event_id AS market_event_id, cr.payload_json AS rule_payload_json
                FROM market_outcomes mo
                JOIN markets m ON m.market_id = mo.market_id
                JOIN events e ON e.event_id = COALESCE(m.event_id, mo.event_id)
                LEFT JOIN compiled_rules cr ON cr.market_id = m.market_id
                WHERE e.event_type = ?
                ORDER BY mo.observed_at DESC
                """,
                (event_type,),
            ).fetchall()

    def list_accepted_decisions_for_rule_family(
        self,
        compiled_rule_id: str,
        event_type: str,
    ) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT cm.*, e.event_id
                FROM candidate_mentions cm
                JOIN mention_decisions md ON md.candidate_id = cm.candidate_id
                JOIN events e ON e.event_id = cm.event_id
                WHERE cm.compiled_rule_id = ? AND e.event_type = ? AND md.counts = 1
                ORDER BY cm.candidate_id
                """,
                (compiled_rule_id, event_type),
            ).fetchall()

    def list_accepted_decision_training_rows(self, event_type: str) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT cm.*, e.event_id, cr.payload_json AS rule_payload_json
                FROM candidate_mentions cm
                JOIN mention_decisions md ON md.candidate_id = cm.candidate_id
                JOIN events e ON e.event_id = cm.event_id
                JOIN compiled_rules cr ON cr.compiled_rule_id = cm.compiled_rule_id
                WHERE e.event_type = ? AND md.counts = 1
                ORDER BY cm.candidate_id
                """,
                (event_type,),
            ).fetchall()

    def latest_probability_estimate(self, market_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM probability_estimates
                WHERE market_id = ?
                ORDER BY generated_at DESC, estimate_id DESC
                LIMIT 1
                """,
                (market_id,),
            ).fetchone()

    def latest_opportunity(self, market_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM opportunities
                WHERE market_id = ?
                ORDER BY generated_at DESC, opportunity_id DESC
                LIMIT 1
                """,
                (market_id,),
            ).fetchone()
