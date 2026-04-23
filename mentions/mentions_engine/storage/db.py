from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from mentions_engine.models import (
    CompiledRule,
    Event,
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
                """
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

    def list_events(self) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM events ORDER BY COALESCE(scheduled_start_time, '') DESC, event_id DESC"
            ).fetchall()

    def get_event(self, event_id: str) -> Optional[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM events WHERE event_id = ?",
                (event_id,),
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

    def list_segments(self, transcript_id: str) -> List[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM transcript_segments WHERE transcript_id = ? ORDER BY segment_id",
                (transcript_id,),
            ).fetchall()
