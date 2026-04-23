import tempfile
import unittest
from pathlib import Path

from mentions_engine.acquisition.whitehouse import WhiteHouseAcquisition
from mentions_engine.config import AppPaths
from mentions_engine.models import Event, SourceArtifact
from mentions_engine.utils import stable_hash


class WhiteHouseAcquisitionTests(unittest.TestCase):
    def test_fetch_sources_from_known_official_transcript_artifact(self):
        transcript_html = """
        <html>
          <head>
            <meta property="og:title" content="Press Briefing by Press Secretary Karoline Leavitt" />
          </head>
          <body>MS. LEAVITT: Good afternoon.</body>
        </html>
        """

        class StubClient:
            def get_text(self, url):
                return transcript_html

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            acquisition = WhiteHouseAcquisition(paths=paths, client=StubClient())
            event = Event(
                event_id="whitehouse-press-briefing-by-press-secretary-karoline-leavitt",
                event_type="white_house_press_briefing",
                title="Press Briefing by Press Secretary Karoline Leavitt",
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
                source_priority="official_transcript_then_official_video_then_third_party_transcript_then_asr",
                broadcast_priority="official_transcript_first",
                metadata={},
            )
            known_artifacts = [
                SourceArtifact(
                    artifact_id="artifact-known",
                    event_id=event.event_id,
                    artifact_type="official_transcript",
                    role="settlement_source",
                    provider="whitehouse.gov",
                    uri="https://www.whitehouse.gov/briefings-statements/2025/01/press-briefing-by-press-secretary-karoline-leavitt/",
                    local_path=None,
                    captured_at=None,
                    published_at="2025-01-29T14:20:46+00:00",
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
            ]

            result = acquisition.fetch_sources(event, known_artifacts)
            self.assertEqual(len(result.artifacts), 1)
            artifact = result.artifacts[0]
            self.assertEqual(artifact.artifact_type, "official_transcript")
            self.assertIsNotNone(artifact.local_path)
            self.assertTrue(Path(artifact.local_path).exists())

    def test_fetch_event_sources_does_not_guess_transcript_from_site_search(self):
        video_html = """
        <html>
          <head>
            <meta property="og:title" content="Press Secretary Karoline Leavitt and Scott Bessent Brief Members of the Media, Apr. 29, 2025" />
          </head>
          <body>
            <a href="/briefings-statements/">Briefings &amp; Statements</a>
          </body>
        </html>
        """

        class StubClient:
            def get_text(self, url):
                return video_html

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            acquisition = WhiteHouseAcquisition(paths=paths, client=StubClient())
            event_id = "whitehouse-videos-press-secretary-karoline-leavitt-and-scott-bessent-brief-members-of-the-media-apr-29-2025"
            video_url = (
                "https://www.whitehouse.gov/videos/"
                "press-secretary-karoline-leavitt-and-scott-bessent-brief-members-of-the-media-apr-29-2025/"
            )

            result = acquisition.fetch_event_sources(event_id, video_url)

            self.assertEqual(len(result.artifacts), 1)
            artifact = result.artifacts[0]
            self.assertEqual(artifact.artifact_type, "video_replay")
            self.assertEqual(
                artifact.artifact_id,
                f"artifact-{stable_hash(event_id + ':official-video-page')[:16]}",
            )
            self.assertIsNotNone(artifact.local_path)
            self.assertTrue(Path(artifact.local_path).exists())

    def test_fetch_event_sources_fetches_embedded_youtube_captions_via_innertube(self):
        video_html = """
        <html>
          <body>
            <iframe src="https://www.youtube.com/embed/xJOgsQQYDY4?feature=oembed&amp;enablejsapi=1"></iframe>
          </body>
        </html>
        """
        watch_html = """
        <html>
          <script>var ytcfg = {"INNERTUBE_API_KEY":"test-api-key"};</script>
        </html>
        """
        timedtext_xml = """
        <?xml version="1.0" encoding="utf-8" ?>
        <timedtext format="3">
          <body>
            <p t="0" d="1000"><s>good</s><s t="200"> afternoon</s></p>
          </body>
        </timedtext>
        """

        class StubClient:
            def get_text(self, url, headers=None):
                if url == "https://www.whitehouse.gov/videos/test-briefing/":
                    return video_html
                if url == "https://www.youtube.com/watch?v=xJOgsQQYDY4":
                    return watch_html
                if url == "https://www.youtube.com/api/timedtext?v=xJOgsQQYDY4&lang=en-US&fmt=srv3":
                    return timedtext_xml
                raise AssertionError(f"Unexpected get_text url: {url}")

            def post_json(self, url, payload, headers=None):
                self.last_post = {"url": url, "payload": payload, "headers": headers}
                return {
                    "captions": {
                        "playerCaptionsTracklistRenderer": {
                            "captionTracks": [
                                {
                                    "baseUrl": "https://www.youtube.com/api/timedtext?v=xJOgsQQYDY4&lang=en-US&fmt=srv3",
                                    "languageCode": "en-US",
                                    "name": {"simpleText": "English (United States)"},
                                }
                            ]
                        }
                    }
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            acquisition = WhiteHouseAcquisition(paths=paths, client=StubClient())

            result = acquisition.fetch_event_sources(
                "whitehouse-videos-test-briefing",
                "https://www.whitehouse.gov/videos/test-briefing/",
            )

            self.assertEqual(len(result.artifacts), 2)
            captions_artifact = next(
                artifact for artifact in result.artifacts if artifact.artifact_type == "closed_captions"
            )
            self.assertEqual(captions_artifact.mime_type, "text/xml")
            self.assertIsNotNone(captions_artifact.local_path)
            self.assertTrue(Path(captions_artifact.local_path).exists())
            self.assertIn(".captions.xml", captions_artifact.local_path)


if __name__ == "__main__":
    unittest.main()
