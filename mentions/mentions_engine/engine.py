from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from mentions_engine.acquisition import AcquisitionAdapter
from mentions_engine.config import AppPaths
from mentions_engine.datasets import DatasetExporter
from mentions_engine.event_mapping import EventMapper
from mentions_engine.discovery import DiscoveryAdapter
from mentions_engine.matcher import build_evidence, find_candidates, make_decisions
from mentions_engine.market_ingest import MarketIngestor
from mentions_engine.models import (
    CandidateMention,
    CompiledRule,
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
from mentions_engine.prediction import FeatureExtractor, OpportunityScorer, PricingModel, snapshot_from_market
from mentions_engine.storage import Database
from mentions_engine.transcripts import TranscriptBuilder, read_artifact_text
from mentions_engine.utils import stable_hash, utc_now_iso


class Engine:
    def __init__(
        self,
        paths: AppPaths,
        db: Database,
        *,
        discovery_adapters: Dict[str, DiscoveryAdapter],
        acquisition_adapters: Dict[str, AcquisitionAdapter],
        transcript_builders: List[TranscriptBuilder],
        event_mappers: List[EventMapper],
        feature_extractor: Optional[FeatureExtractor] = None,
        pricing_model: Optional[PricingModel] = None,
        opportunity_scorer: Optional[OpportunityScorer] = None,
    ):
        self.paths = paths
        self.db = db
        self._discovery_adapters = discovery_adapters
        self._acquisition_adapters = acquisition_adapters
        self._transcript_builders = transcript_builders
        self._event_mappers = event_mappers
        self._feature_extractor = feature_extractor
        self._pricing_model = pricing_model
        self._opportunity_scorer = opportunity_scorer

    def ingest_markets(self, ingestor: MarketIngestor) -> Dict[str, int | str]:
        markets = ingestor.fetch_open_markets()
        for market in markets:
            self.db.upsert_market(market)
        return {"ingestor": ingestor.name, "markets": len(markets)}

    def import_outcomes(self, importer) -> Dict[str, int | str]:
        outcomes = importer.load_outcomes()
        for outcome in outcomes:
            self.db.upsert_market_outcome(outcome)
        return {"importer": importer.name, "outcomes": len(outcomes)}

    def map_market(self, market_id: str) -> Dict[str, Optional[str]]:
        market = self._get_market_model(market_id)
        mapper = next((candidate for candidate in self._event_mappers if candidate.supports(market)), None)
        if mapper is None:
            raise ValueError(f"No event mapper registered for market_id={market_id}")
        event = mapper.map(market)
        if event is None:
            return {"market_id": market_id, "event_id": None, "mapper": mapper.name}
        self.db.upsert_event(event)
        market.event_id = event.event_id
        self.db.upsert_market(market)
        return {"market_id": market_id, "event_id": event.event_id, "mapper": mapper.name}

    def sync_events(self, adapter_name: str) -> Dict[str, int | str]:
        adapter = self._discovery_adapters.get(adapter_name)
        if adapter is None:
            raise ValueError(f"Unknown discovery adapter: {adapter_name}")
        result = adapter.discover_events()
        for event in result.events:
            self.db.upsert_event(event)
        for artifact in result.artifacts:
            self.db.upsert_source_artifact(artifact)
        return {"adapter": adapter_name, "events": len(result.events), "artifacts": len(result.artifacts)}

    def fetch_sources(self, event_id: str) -> Dict[str, int | str]:
        event = self._get_event_model(event_id)
        adapter = self._acquisition_adapters.get(event.event_type)
        if adapter is None:
            raise ValueError(f"No acquisition adapter registered for event_type={event.event_type}")
        known_artifacts = [self._artifact_from_row(row) for row in self.db.list_artifacts_for_event(event_id)]
        result = adapter.fetch_sources(event, known_artifacts)
        for artifact in result.artifacts:
            self.db.upsert_source_artifact(artifact)
        return {"event_id": event_id, "artifacts": len(result.artifacts)}

    def build_transcript(self, artifact_id: str) -> Dict[str, int | str]:
        artifact = self._get_artifact_model(artifact_id)
        event = self._get_event_model(artifact.event_id)
        raw_text = read_artifact_text(artifact)
        builder = next(
            (candidate for candidate in self._transcript_builders if candidate.supports(event, artifact)),
            None,
        )
        if builder is None:
            raise ValueError(
                f"No transcript builder registered for event_type={event.event_type} artifact_type={artifact.artifact_type}"
            )
        result = builder.build(event, artifact, raw_text)
        self.db.upsert_transcript(result.transcript)
        self.db.replace_segments(result.transcript.transcript_id, result.segments)
        self._write_canonical_transcript(event, artifact, result.transcript, result.segments)
        return {"transcript_id": result.transcript.transcript_id, "segments": len(result.segments)}

    def compile_rule(
        self,
        rule: CompiledRule,
        market: Optional[Market] = None,
    ) -> None:
        if market is not None:
            self.db.upsert_market(market)
        self.db.upsert_compiled_rule(rule)

    def record_market_outcome(
        self,
        market_id: str,
        resolved_yes: bool,
        *,
        observed_at: Optional[str] = None,
        outcome_source: str = "manual",
        label_kind: str = "kalshi_resolution",
        notes: str = "",
    ) -> MarketOutcome:
        market = self._get_market_model(market_id)
        outcome = MarketOutcome(
            outcome_id=f"outcome-{stable_hash(market_id + ':' + str(resolved_yes) + ':' + (observed_at or utc_now_iso()))[:16]}",
            market_id=market_id,
            event_id=market.event_id,
            observed_at=observed_at or utc_now_iso(),
            resolved_yes=resolved_yes,
            outcome_source=outcome_source,
            label_kind=label_kind,
            notes=notes,
            metadata={},
        )
        self.db.upsert_market_outcome(outcome)
        return outcome

    def run_rule(
        self,
        event_id: str,
        artifact_id: str,
        transcript_id: str,
        rule: CompiledRule,
        *,
        persist: bool = True,
    ) -> Dict[str, List[dict]]:
        transcript = self._get_transcript_model(transcript_id)
        artifact = self._get_artifact_model(artifact_id)
        segments = [self._segment_from_row(row) for row in self.db.list_segments(transcript_id)]

        candidates = find_candidates(
            market_id=rule.market_id,
            rule=rule,
            event_id=event_id,
            transcript_id=transcript_id,
            segments=segments,
        )
        decisions = make_decisions(candidates)
        evidence = [
            build_evidence(
                artifact_id=artifact.artifact_id,
                transcript_id=transcript.transcript_id,
                segments=segments,
                candidate=candidate,
                decision=decision,
            )
            for candidate, decision in zip(candidates, decisions)
        ]
        if persist:
            self.db.replace_match_results(rule, transcript_id, candidates, decisions, evidence)

        return {
            "candidates": [candidate.to_dict() for candidate in candidates],
            "decisions": [decision.to_dict() for decision in decisions],
            "evidence": [bundle.to_dict() for bundle in evidence],
        }

    def estimate_market(self, market_id: str) -> Dict[str, dict]:
        if self._feature_extractor is None or self._pricing_model is None or self._opportunity_scorer is None:
            raise ValueError("Prediction components are not configured")
        market = self._get_market_model(market_id)
        if not market.event_id:
            self.map_market(market_id)
            market = self._get_market_model(market_id)
        if not market.event_id:
            raise ValueError(f"Market {market_id} is not mapped to an event")
        event = self._get_event_model(market.event_id)
        snapshot = snapshot_from_market(market)
        features = self._feature_extractor.extract(market, event)
        estimate = self._pricing_model.estimate(market, event, features)
        opportunity = self._opportunity_scorer.score(market, estimate, snapshot)
        self.db.upsert_price_snapshot(snapshot)
        self.db.upsert_probability_estimate(estimate)
        self.db.upsert_opportunity(opportunity)
        return {
            "snapshot": snapshot.to_dict(),
            "features": features,
            "estimate": estimate.to_dict(),
            "opportunity": opportunity.to_dict(),
        }

    def list_markets_with_latest_estimates(self, status: Optional[str] = None) -> List[dict]:
        payload = []
        for row in self.db.list_markets(status=status):
            market = self._market_from_row(row)
            estimate = self.db.latest_probability_estimate(market.market_id)
            opportunity = self.db.latest_opportunity(market.market_id)
            payload.append(
                {
                    "market": market.to_dict(),
                    "latest_estimate": None if estimate is None else dict(estimate),
                    "latest_opportunity": None if opportunity is None else dict(opportunity),
                }
            )
        return payload

    def export_market_dataset(
        self,
        output_path: Optional[Path] = None,
        *,
        status: Optional[str] = None,
    ) -> Dict[str, object]:
        exporter = DatasetExporter(self.db, self.paths)
        path = output_path or (self.paths.derived_dir / "datasets" / f"markets-{status or 'all'}.jsonl")
        return exporter.export_market_dataset(path, status=status)

    def _get_event_model(self, event_id: str) -> Event:
        row = self.db.get_event(event_id)
        if row is None:
            raise ValueError(f"Event not found: {event_id}")
        return self._event_from_row(row)

    def _get_artifact_model(self, artifact_id: str) -> SourceArtifact:
        row = self.db.get_artifact(artifact_id)
        if row is None:
            raise ValueError(f"Artifact not found: {artifact_id}")
        return self._artifact_from_row(row)

    def _get_market_model(self, market_id: str) -> Market:
        row = self.db.get_market(market_id)
        if row is None:
            raise ValueError(f"Market not found: {market_id}")
        return self._market_from_row(row)

    def _get_transcript_model(self, transcript_id: str) -> Transcript:
        row = self.db.get_transcript(transcript_id)
        if row is None:
            raise ValueError(f"Transcript not found: {transcript_id}")
        return self._transcript_from_row(row)

    def _event_from_row(self, row) -> Event:
        return Event(
            event_id=row["event_id"],
            event_type=row["event_type"],
            title=row["title"],
            category=row["category"],
            subcategory=row["subcategory"],
            scheduled_start_time=row["scheduled_start_time"],
            scheduled_end_time=row["scheduled_end_time"],
            actual_start_time=row["actual_start_time"],
            actual_end_time=row["actual_end_time"],
            participants=row["participants"],
            broadcast_network=row["broadcast_network"],
            league=row["league"],
            season=row["season"],
            venue=row["venue"],
            source_priority=row["source_priority"],
            broadcast_priority=row["broadcast_priority"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _market_from_row(self, row) -> Market:
        return Market(
            market_id=row["market_id"],
            event_id=row["event_id"],
            series_id=row["series_id"],
            title=row["title"],
            subtitle=row["subtitle"],
            status=row["status"],
            close_time=row["close_time"],
            settlement_time=row["settlement_time"],
            yes_bid=row["yes_bid"],
            yes_ask=row["yes_ask"],
            no_bid=row["no_bid"],
            no_ask=row["no_ask"],
            volume=row["volume"],
            open_interest=row["open_interest"],
            rules_text=row["rules_text"],
            rules_summary_text=row["rules_summary_text"],
            source_text=row["source_text"],
            url=row["url"],
            last_updated_at=row["last_updated_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _artifact_from_row(self, row) -> SourceArtifact:
        return SourceArtifact(
            artifact_id=row["artifact_id"],
            event_id=row["event_id"],
            artifact_type=row["artifact_type"],
            role=row["role"],
            provider=row["provider"],
            uri=row["uri"],
            local_path=row["local_path"],
            captured_at=row["captured_at"],
            published_at=row["published_at"],
            start_time=row["start_time"],
            end_time=row["end_time"],
            duration_seconds=row["duration_seconds"],
            checksum=row["checksum"],
            mime_type=row["mime_type"],
            is_official=bool(row["is_official"]),
            is_settlement_candidate=bool(row["is_settlement_candidate"]),
            feed_label=row["feed_label"],
            feed_priority=row["feed_priority"],
            broadcast_scope=row["broadcast_scope"],
            language=row["language"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _transcript_from_row(self, row) -> Transcript:
        return Transcript(
            transcript_id=row["transcript_id"],
            artifact_id=row["artifact_id"],
            transcript_type=row["transcript_type"],
            version=row["version"],
            created_at=row["created_at"],
            generator=row["generator"],
            language=row["language"],
            quality_score=row["quality_score"],
            is_machine_generated=bool(row["is_machine_generated"]),
            is_human_supplied=bool(row["is_human_supplied"]),
            raw_text=row["raw_text"],
            normalized_text=row["normalized_text"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _segment_from_row(self, row) -> TranscriptSegment:
        return TranscriptSegment(
            segment_id=row["segment_id"],
            transcript_id=row["transcript_id"],
            start_time_seconds=row["start_time_seconds"],
            end_time_seconds=row["end_time_seconds"],
            speaker_id=row["speaker_id"],
            speaker_label=row["speaker_label"],
            channel=row["channel"],
            text=row["text"],
            normalized_text=row["normalized_text"],
            confidence=row["confidence"],
            word_count=row["word_count"],
            metadata=json.loads(row["metadata_json"]),
        )

    def _write_canonical_transcript(
        self,
        event: Event,
        artifact: SourceArtifact,
        transcript: Transcript,
        segments: List[TranscriptSegment],
    ) -> None:
        payload = {
            "event": event.to_dict(),
            "artifact": artifact.to_dict(),
            "transcript": transcript.to_dict(),
            "segments": [segment.to_dict() for segment in segments],
        }
        path = self.paths.canonical_dir / "transcripts" / f"{transcript.transcript_id}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
