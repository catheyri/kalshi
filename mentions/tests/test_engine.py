import json
import tempfile
import unittest
from pathlib import Path

from mentions_engine.acquisition.base import AcquisitionResult
from mentions_engine.config import AppPaths
from mentions_engine.discovery.base import DiscoveryResult
from mentions_engine.engine import Engine
from mentions_engine.models import Event, Market, SourceArtifact, Transcript, TranscriptSegment
from mentions_engine.prediction.simple import (
    HistoricalFrequencyPricingModel,
    HistoricalOutcomeFeatureExtractor,
    SimpleOpportunityScorer,
)
from mentions_engine.rules import compile_rule_from_json
from mentions_engine.storage import Database
from mentions_engine.transcripts.builders import TranscriptBuildResult


class EngineTests(unittest.TestCase):
    def test_engine_uses_registered_components_and_persists_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            db = Database(paths.db_path)
            db.initialize()

            event = Event(
                event_id="event-1",
                event_type="test_event",
                title="Test Event",
                category="test",
                subcategory="test_event",
                scheduled_start_time=None,
                scheduled_end_time=None,
                actual_start_time=None,
                actual_end_time=None,
                participants="Speaker",
                broadcast_network=None,
                league=None,
                season=None,
                venue=None,
                source_priority="official_first",
                broadcast_priority=None,
                metadata={},
            )
            seed_artifact = SourceArtifact(
                artifact_id="artifact-seed",
                event_id="event-1",
                artifact_type="video_replay",
                role="research_source",
                provider="seed",
                uri="https://example.com/source",
                local_path=None,
                captured_at=None,
                published_at=None,
                start_time=None,
                end_time=None,
                duration_seconds=None,
                checksum=None,
                mime_type="text/html",
                is_official=True,
                is_settlement_candidate=True,
                feed_label=None,
                feed_priority=None,
                broadcast_scope=None,
                language="en",
                metadata={},
            )

            class FakeDiscovery:
                name = "fake"

                def discover_events(self):
                    return DiscoveryResult(events=[event], artifacts=[seed_artifact])

            class FakeAcquisition:
                event_type = "test_event"

                def fetch_sources(self, event, known_artifacts):
                    local_path = paths.raw_dir / "test_source.txt"
                    local_path.write_text("Tariffs are on the agenda.", encoding="utf-8")
                    artifact = SourceArtifact(
                        artifact_id="artifact-transcript",
                        event_id=event.event_id,
                        artifact_type="official_transcript",
                        role="settlement_source",
                        provider="test",
                        uri=None,
                        local_path=str(local_path),
                        captured_at=None,
                        published_at=None,
                        start_time=None,
                        end_time=None,
                        duration_seconds=None,
                        checksum=None,
                        mime_type="text/plain",
                        is_official=True,
                        is_settlement_candidate=True,
                        feed_label=None,
                        feed_priority=None,
                        broadcast_scope=None,
                        language="en",
                        metadata={},
                    )
                    return AcquisitionResult(artifacts=[artifact])

            class FakeBuilder:
                name = "fake"

                def supports(self, event, artifact):
                    return event.event_type == "test_event" and artifact.artifact_type == "official_transcript"

                def build(self, event, artifact, raw_text):
                    transcript = Transcript(
                        transcript_id="transcript-1",
                        artifact_id=artifact.artifact_id,
                        transcript_type="official",
                        version="1",
                        created_at="2026-01-01T00:00:00+00:00",
                        generator="fake",
                        language="en",
                        quality_score=1.0,
                        is_machine_generated=False,
                        is_human_supplied=True,
                        raw_text=raw_text,
                        normalized_text=raw_text.lower(),
                        metadata={},
                    )
                    segments = [
                        TranscriptSegment(
                            segment_id="segment-1",
                            transcript_id=transcript.transcript_id,
                            start_time_seconds=None,
                            end_time_seconds=None,
                            speaker_id=None,
                            speaker_label="HOST",
                            channel=None,
                            text=raw_text,
                            normalized_text=raw_text.lower(),
                            confidence=None,
                            word_count=5,
                            metadata={},
                        )
                    ]
                    return TranscriptBuildResult(transcript=transcript, segments=segments)

            engine = Engine(
                paths=paths,
                db=db,
                discovery_adapters={"fake": FakeDiscovery()},
                acquisition_adapters={"test_event": FakeAcquisition()},
                transcript_builders=[FakeBuilder()],
                event_mappers=[],
                feature_extractor=HistoricalOutcomeFeatureExtractor(db),
                pricing_model=HistoricalFrequencyPricingModel(),
                opportunity_scorer=SimpleOpportunityScorer(),
            )

            sync_result = engine.sync_events("fake")
            self.assertEqual(sync_result["events"], 1)

            fetch_result = engine.fetch_sources("event-1")
            self.assertEqual(fetch_result["artifacts"], 1)

            build_result = engine.build_transcript("artifact-transcript")
            self.assertEqual(build_result["transcript_id"], "transcript-1")
            canonical_path = paths.canonical_dir / "transcripts" / "transcript-1.json"
            self.assertTrue(canonical_path.exists())

            rule = compile_rule_from_json(
                {
                    "market_id": "market-1",
                    "target_terms": ["tariffs"],
                    "speaker_scope": [],
                }
            )
            run_result = engine.run_rule("event-1", "artifact-transcript", "transcript-1", rule)

            self.assertEqual(len(run_result["candidates"]), 1)
            stored_candidates = db.list_candidate_mentions(rule.compiled_rule_id, "transcript-1")
            stored_decisions = db.list_mention_decisions_for_rule(rule.compiled_rule_id, "transcript-1")
            stored_evidence = db.list_evidence_bundles_for_rule(rule.compiled_rule_id, "transcript-1")

            self.assertEqual(len(stored_candidates), 1)
            self.assertEqual(len(stored_decisions), 1)
            self.assertEqual(len(stored_evidence), 1)
            self.assertEqual(json.loads(stored_candidates[0]["metadata_json"])["speaker_label"], "HOST")

    def test_prediction_flow_prefers_recorded_market_outcomes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            db = Database(paths.db_path)
            db.initialize()

            class FakeMapper:
                name = "fake-mapper"

                def supports(self, market):
                    return market.metadata.get("event_type") == "test_event"

                def map(self, market):
                    return Event(
                        event_id=market.metadata["mapped_event_id"],
                        event_type="test_event",
                        title=market.title,
                        category="test",
                        subcategory="test_event",
                        scheduled_start_time=market.metadata.get("scheduled_start_time"),
                        scheduled_end_time=None,
                        actual_start_time=None,
                        actual_end_time=None,
                        participants="Speaker",
                        broadcast_network=None,
                        league=None,
                        season=None,
                        venue=None,
                        source_priority="official_first",
                        broadcast_priority=None,
                        metadata={},
                    )

            engine = Engine(
                paths=paths,
                db=db,
                discovery_adapters={},
                acquisition_adapters={},
                transcript_builders=[],
                event_mappers=[FakeMapper()],
                feature_extractor=HistoricalOutcomeFeatureExtractor(db),
                pricing_model=HistoricalFrequencyPricingModel(),
                opportunity_scorer=SimpleOpportunityScorer(),
            )

            historical_markets = [
                Market(
                    market_id="m-hist-yes",
                    event_id="event-hist-yes",
                    series_id=None,
                    title="Will speaker mention tariffs?",
                    subtitle=None,
                    status="resolved",
                    close_time=None,
                    settlement_time=None,
                    yes_bid=55,
                    yes_ask=60,
                    no_bid=40,
                    no_ask=45,
                    volume=100,
                    open_interest=10,
                    rules_text=None,
                    rules_summary_text=None,
                    source_text=None,
                    url=None,
                    last_updated_at=None,
                    metadata={"event_type": "test_event", "mapped_event_id": "event-hist-yes"},
                ),
                Market(
                    market_id="m-hist-no",
                    event_id="event-hist-no",
                    series_id=None,
                    title="Will speaker mention tariffs?",
                    subtitle=None,
                    status="resolved",
                    close_time=None,
                    settlement_time=None,
                    yes_bid=20,
                    yes_ask=25,
                    no_bid=75,
                    no_ask=80,
                    volume=100,
                    open_interest=10,
                    rules_text=None,
                    rules_summary_text=None,
                    source_text=None,
                    url=None,
                    last_updated_at=None,
                    metadata={"event_type": "test_event", "mapped_event_id": "event-hist-no"},
                ),
                Market(
                    market_id="m-open",
                    event_id=None,
                    series_id=None,
                    title="Will speaker mention tariffs tomorrow?",
                    subtitle=None,
                    status="open",
                    close_time="2026-01-03T00:00:00+00:00",
                    settlement_time=None,
                    yes_bid=48,
                    yes_ask=52,
                    no_bid=48,
                    no_ask=52,
                    volume=200,
                    open_interest=20,
                    rules_text=None,
                    rules_summary_text=None,
                    source_text=None,
                    url=None,
                    last_updated_at=None,
                    metadata={"event_type": "test_event", "mapped_event_id": "event-future"},
                ),
            ]

            rule = compile_rule_from_json(
                {
                    "market_id": "m-hist-yes",
                    "target_terms": ["tariffs"],
                    "speaker_scope": [],
                }
            )
            for market in historical_markets:
                db.upsert_market(market)
            db.upsert_event(
                Event(
                    event_id="event-hist-yes",
                    event_type="test_event",
                    title="Hist yes",
                    category="test",
                    subcategory="test_event",
                    scheduled_start_time=None,
                    scheduled_end_time=None,
                    actual_start_time=None,
                    actual_end_time=None,
                    participants="Speaker",
                    broadcast_network=None,
                    league=None,
                    season=None,
                    venue=None,
                    source_priority="official_first",
                    broadcast_priority=None,
                    metadata={},
                )
            )
            db.upsert_event(
                Event(
                    event_id="event-hist-no",
                    event_type="test_event",
                    title="Hist no",
                    category="test",
                    subcategory="test_event",
                    scheduled_start_time=None,
                    scheduled_end_time=None,
                    actual_start_time=None,
                    actual_end_time=None,
                    participants="Speaker",
                    broadcast_network=None,
                    league=None,
                    season=None,
                    venue=None,
                    source_priority="official_first",
                    broadcast_priority=None,
                    metadata={},
                )
            )
            for market_id in ["m-hist-yes", "m-hist-no", "m-open"]:
                market_rule = compile_rule_from_json(
                    {
                        "market_id": market_id,
                        "target_terms": ["tariffs"],
                        "speaker_scope": [],
                    }
                )
                db.upsert_compiled_rule(market_rule)

            engine.record_market_outcome("m-hist-yes", True, observed_at="2026-01-01T00:00:00+00:00")
            engine.record_market_outcome("m-hist-no", False, observed_at="2026-01-02T00:00:00+00:00")

            result = engine.estimate_market("m-open")

            self.assertEqual(result["features"]["source"], "market_outcomes")
            self.assertEqual(result["features"]["sample_size"], 2)
            self.assertEqual(result["estimate"]["fair_yes_price"], 50)
            self.assertEqual(result["opportunity"]["side"], "none")

            export_result = engine.export_market_dataset(status="open")
            self.assertEqual(export_result["rows"], 1)
            export_path = Path(export_result["output_path"])
            self.assertTrue(export_path.exists())
            lines = export_path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 1)
            row = json.loads(lines[0])
            self.assertEqual(row["market"]["market_id"], "m-open")
            self.assertEqual(row["latest_estimate"]["fair_yes_price"], 50)


if __name__ == "__main__":
    unittest.main()
