import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mentions_engine.analysis.word_frequencies import (
    build_event_word_frequency_rows,
    build_word_frequency_dataset,
    canonicalize_word,
    market_terms_from_phrase,
    replace_event_word_frequencies,
)
from mentions_engine.config import AppPaths
from mentions_engine.models import Event, Market, SourceArtifact, Transcript, TranscriptSegment
from mentions_engine.profiles import SpeakerProfile
from mentions_engine.storage import Database


class WordFrequencyTests(unittest.TestCase):
    def test_canonicalize_word_handles_common_suffixes(self):
        self.assertEqual(canonicalize_word("tariffs"), "tariff")
        self.assertEqual(canonicalize_word("policies"), "policy")
        self.assertEqual(canonicalize_word("running"), "run")
        self.assertEqual(canonicalize_word("tariffed"), "tariff")
        self.assertEqual(canonicalize_word("states"), "state")
        self.assertEqual(canonicalize_word("united"), "united")

    def test_market_terms_from_phrase_splits_variants_and_drops_parentheticals(self):
        self.assertEqual(market_terms_from_phrase("Gas / Gasoline"), {"gas", "gasoline"})
        self.assertEqual(market_terms_from_phrase("Iran (5+ times)"), {"iran"})
        self.assertEqual(market_terms_from_phrase("America First"), {"america first"})
        self.assertEqual(market_terms_from_phrase("Stupid Question"), {"stupid question"})

    def test_builds_counts_for_custom_speaker_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            db = Database(paths.db_path)
            db.initialize()
            speaker = SpeakerProfile(
                canonical_name="Dr. Smith",
                key="dr_smith",
                aliases=("dr smith",),
                transcript_labels=("DR. SMITH",),
                caption_speaker_markers=(("dr. smith:", "DR. SMITH"),),
                discovery_slug_terms=("dr-smith",),
                stopwords=("smith",),
            )

            event = Event(
                event_id="whitehouse-videos-dr-smith-briefs-members-of-the-media-may-2-2026",
                event_type="white_house_press_briefing",
                title="Dr. Smith Briefs Members of the Media, May 2, 2026",
                category="government",
                subcategory="white_house_press_briefing",
                scheduled_start_time=None,
                scheduled_end_time=None,
                actual_start_time=None,
                actual_end_time=None,
                participants="Dr. Smith",
                broadcast_network="White House",
                league=None,
                season=None,
                venue="White House Briefing Room",
                source_priority="official_first",
                broadcast_priority=None,
                metadata={"speaker_key": speaker.speaker_key},
            )
            artifact = SourceArtifact(
                artifact_id="artifact-custom-speaker",
                event_id=event.event_id,
                artifact_type="closed_captions",
                role="research_source",
                provider="youtube",
                uri=None,
                local_path=None,
                captured_at=None,
                published_at=None,
                start_time=None,
                end_time=None,
                duration_seconds=None,
                checksum=None,
                mime_type="text/xml",
                is_official=False,
                is_settlement_candidate=False,
                feed_label="youtube_caption_track",
                feed_priority=None,
                broadcast_scope="official",
                language="en",
                metadata={},
            )
            transcript = Transcript(
                transcript_id="transcript-custom-speaker",
                artifact_id=artifact.artifact_id,
                transcript_type="captions",
                version="1",
                created_at="2026-05-02T18:00:00+00:00",
                generator="test",
                language="en",
                quality_score=0.75,
                is_machine_generated=True,
                is_human_supplied=False,
                raw_text="",
                normalized_text="",
                metadata={},
            )
            market = Market(
                market_id="KXTEST-26MAY02-GROW",
                event_id="KXTEST-26MAY02",
                series_id="KXTEST",
                title="Will Dr. Smith say Growth at the next briefing?",
                subtitle="Growth",
                status="finalized",
                close_time="2026-05-02T18:00:00Z",
                settlement_time=None,
                yes_bid=None,
                yes_ask=None,
                no_bid=None,
                no_ask=None,
                volume=None,
                open_interest=None,
                rules_text=None,
                rules_summary_text=None,
                source_text=None,
                url=None,
                last_updated_at=None,
                metadata={
                    "market_family": "mention",
                    "source_family": "whitehouse",
                    "event_family": "white_house_press_briefing",
                    "event_type": "white_house_press_briefing",
                    "speaker_key": speaker.speaker_key,
                    "speaker_name": speaker.canonical_name,
                    "target_phrase": "Growth",
                    "response_payload": {"result": "yes", "custom_strike": {"Word": "Growth"}},
                },
            )
            other_event = replace(
                event,
                event_id="whitehouse-videos-press-secretary-karoline-leavitt-briefs-members-of-the-media-may-2-2026",
                title="Press Secretary Karoline Leavitt Briefs Members of the Media, May 2, 2026",
                participants="Karoline Leavitt",
                metadata={"speaker_key": "karoline_leavitt"},
            )
            other_artifact = replace(
                artifact,
                artifact_id="artifact-other-speaker",
                event_id=other_event.event_id,
            )
            other_transcript = replace(
                transcript,
                transcript_id="transcript-other-speaker",
                artifact_id=other_artifact.artifact_id,
            )

            db.upsert_event(event)
            db.upsert_event(other_event)
            db.upsert_source_artifact(artifact)
            db.upsert_source_artifact(other_artifact)
            db.upsert_transcript(transcript)
            db.upsert_transcript(other_transcript)
            db.upsert_market(market)
            db.replace_segments(
                transcript.transcript_id,
                [
                    TranscriptSegment(
                        segment_id="segment-smith",
                        transcript_id=transcript.transcript_id,
                        start_time_seconds=1.0,
                        end_time_seconds=2.0,
                        speaker_id=None,
                        speaker_label="DR. SMITH",
                        channel=None,
                        text="Growth growth for Smith.",
                        normalized_text="growth growth for smith",
                        confidence=None,
                        word_count=4,
                        metadata={},
                    ),
                    TranscriptSegment(
                        segment_id="segment-other",
                        transcript_id=transcript.transcript_id,
                        start_time_seconds=2.0,
                        end_time_seconds=3.0,
                        speaker_id=None,
                        speaker_label="MS. LEAVITT",
                        channel=None,
                        text="Growth.",
                        normalized_text="growth",
                        confidence=None,
                        word_count=1,
                        metadata={},
                    ),
                ],
            )
            db.replace_segments(
                other_transcript.transcript_id,
                [
                    TranscriptSegment(
                        segment_id="segment-other-event",
                        transcript_id=other_transcript.transcript_id,
                        start_time_seconds=1.0,
                        end_time_seconds=2.0,
                        speaker_id=None,
                        speaker_label="DR. SMITH",
                        channel=None,
                        text="Growth.",
                        normalized_text="growth",
                        confidence=None,
                        word_count=1,
                        metadata={},
                    ),
                ],
            )

            rows = build_event_word_frequency_rows(
                db,
                speaker_scope="primary",
                speaker_profile=speaker,
                min_count=1,
            )
            by_term = {row.term: row for row in rows}
            self.assertEqual(by_term["growth"].count, 2)
            self.assertTrue(by_term["growth"].is_kalshi_market)
            self.assertEqual(by_term["growth"].kalshi_market_id, market.market_id)
            self.assertNotIn("smith", by_term)

    def test_builds_event_term_counts_with_kalshi_flags(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            db = Database(paths.db_path)
            db.initialize()

            event = Event(
                event_id="whitehouse-videos-press-secretary-karoline-leavitt-briefs-members-of-the-media-apr-22-2026",
                event_type="white_house_press_briefing",
                title="Press Secretary Karoline Leavitt Briefs Members of the Media, Apr. 22, 2026",
                category="government",
                subcategory="white_house_press_briefing",
                scheduled_start_time=None,
                scheduled_end_time=None,
                actual_start_time=None,
                actual_end_time=None,
                participants="Karoline Leavitt",
                broadcast_network="White House",
                league=None,
                season=None,
                venue="White House Briefing Room",
                source_priority="official_first",
                broadcast_priority=None,
                metadata={},
            )
            artifact = SourceArtifact(
                artifact_id="artifact-1",
                event_id=event.event_id,
                artifact_type="closed_captions",
                role="research_source",
                provider="youtube",
                uri=None,
                local_path=None,
                captured_at=None,
                published_at=None,
                start_time=None,
                end_time=None,
                duration_seconds=None,
                checksum=None,
                mime_type="text/xml",
                is_official=False,
                is_settlement_candidate=False,
                feed_label="youtube_caption_track",
                feed_priority=None,
                broadcast_scope="official",
                language="en",
                metadata={},
            )
            transcript = Transcript(
                transcript_id="transcript-1",
                artifact_id=artifact.artifact_id,
                transcript_type="captions",
                version="1",
                created_at="2026-04-22T18:00:00+00:00",
                generator="test",
                language="en",
                quality_score=0.75,
                is_machine_generated=True,
                is_human_supplied=False,
                raw_text="",
                normalized_text="",
                metadata={},
            )
            market = Market(
                market_id="KXSECPRESSMENTION-26APR22-TARI",
                event_id="KXSECPRESSMENTION-26APR22",
                series_id="KXSECPRESSMENTION",
                title="Will the White House Press Secretary say Tariffs at her next press briefing?",
                subtitle="Tariffs",
                status="finalized",
                close_time="2026-04-22T18:00:00Z",
                settlement_time=None,
                yes_bid=None,
                yes_ask=None,
                no_bid=None,
                no_ask=None,
                volume=None,
                open_interest=None,
                rules_text=None,
                rules_summary_text=None,
                source_text=None,
                url=None,
                last_updated_at=None,
                metadata={
                    "source_family": "whitehouse",
                    "event_family": "white_house_press_briefing",
                    "target_phrase": "Tariffs",
                    "response_payload": {"result": "yes", "custom_strike": {"Word": "Tariffs"}},
                },
            )
            no_market = Market(
                market_id="KXSECPRESSMENTION-26APR22-GOOD",
                event_id="KXSECPRESSMENTION-26APR22",
                series_id="KXSECPRESSMENTION",
                title="Will the White House Press Secretary say Goods at her next press briefing?",
                subtitle="Goods",
                status="finalized",
                close_time="2026-04-22T18:00:00Z",
                settlement_time=None,
                yes_bid=None,
                yes_ask=None,
                no_bid=None,
                no_ask=None,
                volume=None,
                open_interest=None,
                rules_text=None,
                rules_summary_text=None,
                source_text=None,
                url=None,
                last_updated_at=None,
                metadata={
                    "source_family": "whitehouse",
                    "event_family": "white_house_press_briefing",
                    "target_phrase": "Goods",
                    "response_payload": {"result": "no", "custom_strike": {"Word": "Goods"}},
                },
            )
            phrase_market = Market(
                market_id="KXSECPRESSMENTION-26APR22-AF",
                event_id="KXSECPRESSMENTION-26APR22",
                series_id="KXSECPRESSMENTION",
                title="Will the White House Press Secretary say America First at her next press briefing?",
                subtitle="America First",
                status="finalized",
                close_time="2026-04-22T18:00:00Z",
                settlement_time=None,
                yes_bid=None,
                yes_ask=None,
                no_bid=None,
                no_ask=None,
                volume=None,
                open_interest=None,
                rules_text=None,
                rules_summary_text=None,
                source_text=None,
                url=None,
                last_updated_at=None,
                metadata={
                    "source_family": "whitehouse",
                    "event_family": "white_house_press_briefing",
                    "target_phrase": "America First",
                    "response_payload": {"result": "yes", "custom_strike": {"Word": "America First"}},
                },
            )

            db.upsert_event(event)
            db.upsert_source_artifact(artifact)
            db.upsert_transcript(transcript)
            db.replace_segments(
                transcript.transcript_id,
                [
                    TranscriptSegment(
                        segment_id="segment-q",
                        transcript_id=transcript.transcript_id,
                        start_time_seconds=1.0,
                        end_time_seconds=2.0,
                        speaker_id=None,
                        speaker_label="Q",
                        channel=None,
                        text="Will the tariffs change?",
                        normalized_text="will the tariffs change",
                        confidence=None,
                        word_count=4,
                        metadata={},
                    ),
                    TranscriptSegment(
                        segment_id="segment-a",
                        transcript_id=transcript.transcript_id,
                        start_time_seconds=2.0,
                        end_time_seconds=3.0,
                        speaker_id=None,
                        speaker_label="MS. LEAVITT",
                        channel=None,
                        text="The tariff, tariffs, and tariffed goods matter. America's promise matters. America first policy matters.",
                        normalized_text="the tariff tariffs and tariffed goods matter america's promise matters america first policy matters",
                        confidence=None,
                        word_count=14,
                        metadata={},
                    ),
                    TranscriptSegment(
                        segment_id="segment-president",
                        transcript_id=transcript.transcript_id,
                        start_time_seconds=3.0,
                        end_time_seconds=4.0,
                        speaker_id=None,
                        speaker_label="THE PRESIDENT",
                        channel=None,
                        text="Tariffs tariffs tariffs.",
                        normalized_text="tariffs tariffs tariffs",
                        confidence=None,
                        word_count=3,
                        metadata={},
                    ),
                ],
            )
            db.upsert_market(market)
            db.upsert_market(no_market)
            db.upsert_market(phrase_market)

            rows = build_event_word_frequency_rows(db, speaker_scope="primary", min_count=1)
            by_term = {row.term: row for row in rows}

            self.assertNotIn("the", by_term)
            self.assertEqual(by_term["tariff"].count, 3)
            self.assertTrue(by_term["tariff"].is_kalshi_market)
            self.assertEqual(by_term["tariff"].kalshi_result, "yes")
            self.assertEqual(by_term["tariff"].kalshi_market_id, market.market_id)
            self.assertIn("good", by_term)
            self.assertFalse(by_term["good"].is_kalshi_market)
            self.assertIsNone(by_term["good"].kalshi_result)
            self.assertEqual(by_term["america"].count, 2)
            self.assertFalse(by_term["america"].is_kalshi_market)
            self.assertEqual(by_term["america first"].count, 1)
            self.assertTrue(by_term["america first"].is_kalshi_market)
            self.assertEqual(by_term["america first"].kalshi_result, "yes")
            self.assertEqual(by_term["america first"].kalshi_market_id, phrase_market.market_id)

            replace_event_word_frequencies(db, rows)
            with db.connect() as conn:
                stored = conn.execute(
                    """
                    SELECT term, count, is_kalshi_market, kalshi_result, kalshi_market_ids_json
                    FROM event_word_frequencies
                    WHERE term = 'tariff'
                    """
                ).fetchone()
            self.assertEqual(stored["count"], 3)
            self.assertEqual(stored["is_kalshi_market"], 1)
            self.assertEqual(json.loads(stored["kalshi_market_ids_json"]), [market.market_id])

    def test_build_dataset_writes_json_and_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            db = Database(paths.db_path)
            db.initialize()

            event = Event(
                event_id="whitehouse-videos-press-secretary-karoline-leavitt-briefs-members-of-the-media-may-1-2026",
                event_type="white_house_press_briefing",
                title="Press Secretary Karoline Leavitt Briefs Members of the Media, May 1, 2026",
                category="government",
                subcategory="white_house_press_briefing",
                scheduled_start_time=None,
                scheduled_end_time=None,
                actual_start_time=None,
                actual_end_time=None,
                participants="Karoline Leavitt",
                broadcast_network="White House",
                league=None,
                season=None,
                venue="White House Briefing Room",
                source_priority="official_first",
                broadcast_priority=None,
                metadata={},
            )
            artifact = SourceArtifact(
                artifact_id="artifact-2",
                event_id=event.event_id,
                artifact_type="official_transcript",
                role="settlement_source",
                provider="whitehouse.gov",
                uri=None,
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
                feed_label="official_transcript_page",
                feed_priority=None,
                broadcast_scope="official",
                language="en",
                metadata={},
            )
            transcript = Transcript(
                transcript_id="transcript-2",
                artifact_id=artifact.artifact_id,
                transcript_type="official",
                version="1",
                created_at="2026-05-01T18:00:00+00:00",
                generator="test",
                language="en",
                quality_score=1.0,
                is_machine_generated=False,
                is_human_supplied=True,
                raw_text="Border border. God.",
                normalized_text="border border god",
                metadata={},
            )
            no_market = Market(
                market_id="KXSECPRESSMENTION-26MAY01-BORD",
                event_id="KXSECPRESSMENTION-26MAY01",
                series_id="KXSECPRESSMENTION",
                title="Will the White House Press Secretary say Border at her next press briefing?",
                subtitle="Border",
                status="finalized",
                close_time="2026-05-01T18:00:00Z",
                settlement_time=None,
                yes_bid=None,
                yes_ask=None,
                no_bid=None,
                no_ask=None,
                volume=None,
                open_interest=None,
                rules_text=None,
                rules_summary_text=None,
                source_text=None,
                url=None,
                last_updated_at=None,
                metadata={
                    "source_family": "whitehouse",
                    "event_family": "white_house_press_briefing",
                    "target_phrase": "Border",
                    "response_payload": {"result": "no", "custom_strike": {"Word": "Border"}},
                },
            )
            slash_market = Market(
                market_id="KXSECPRESSMENTION-26MAY01-GOD",
                event_id="KXSECPRESSMENTION-26MAY01",
                series_id="KXSECPRESSMENTION",
                title="Will the White House Press Secretary say God / Allah at her next press briefing?",
                subtitle="God / Allah",
                status="finalized",
                close_time="2026-05-01T18:00:00Z",
                settlement_time=None,
                yes_bid=None,
                yes_ask=None,
                no_bid=None,
                no_ask=None,
                volume=None,
                open_interest=None,
                rules_text=None,
                rules_summary_text=None,
                source_text=None,
                url=None,
                last_updated_at=None,
                metadata={
                    "source_family": "whitehouse",
                    "event_family": "white_house_press_briefing",
                    "target_phrase": "God / Allah",
                    "response_payload": {"result": "yes", "custom_strike": {"Word": "God / Allah"}},
                },
            )

            db.upsert_event(event)
            db.upsert_source_artifact(artifact)
            db.upsert_transcript(transcript)
            db.upsert_market(no_market)
            db.upsert_market(slash_market)
            db.replace_segments(
                transcript.transcript_id,
                [
                    TranscriptSegment(
                        segment_id="segment-1",
                        transcript_id=transcript.transcript_id,
                        start_time_seconds=None,
                        end_time_seconds=None,
                        speaker_id=None,
                        speaker_label="MS. LEAVITT",
                        channel=None,
                        text="Border border. God.",
                        normalized_text="border border god",
                        confidence=None,
                        word_count=3,
                        metadata={},
                    )
                ],
            )

            json_path = paths.derived_dir / "features" / "word_frequencies.json"
            html_path = paths.derived_dir / "features" / "word_frequency_explorer.html"
            event_html_path = paths.derived_dir / "features" / "event_word_frequency_explorer.html"
            result = build_word_frequency_dataset(
                db,
                json_path=json_path,
                html_path=html_path,
                event_html_path=event_html_path,
            )

            self.assertEqual(result.rows, 2)
            self.assertTrue(json_path.exists())
            self.assertTrue(html_path.exists())
            self.assertTrue(event_html_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            border_market = next(market for market in payload["markets"] if market["term"] == "border")
            self.assertEqual(border_market["result"], "no")
            slash_markets = [
                market for market in payload["markets"] if market["market_id"] == slash_market.market_id
            ]
            self.assertEqual({market["term"] for market in slash_markets}, {"allah", "god"})
            for market in slash_markets:
                self.assertEqual(market["display_term"], "God / Allah")
                self.assertEqual(market["market_terms"], ["allah", "god"])
                self.assertEqual(market["market_term_key"], "allah|god")
            self.assertIn("Mention Word Frequencies", html_path.read_text(encoding="utf-8"))
            self.assertIn(
                "Mention Event Word Explorer",
                event_html_path.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
