import unittest

from mentions_engine.transcripts.parsers import (
    infer_briefing_speaker_label,
    parse_official_whitehouse_transcript,
    parse_youtube_captions,
)


class TranscriptParserTests(unittest.TestCase):
    def test_parse_speaker_segments(self):
        html = """
        <html><body>
        <p>MS. LEAVITT: Good afternoon everybody.</p>
        <p>Q: Did the President mention tariffs?</p>
        <p>MS. LEAVITT: The President has been very clear on tariffs.</p>
        </body></html>
        """
        transcript, segments = parse_official_whitehouse_transcript("artifact-1", html)
        self.assertTrue(transcript.raw_text)
        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0].speaker_label, "MS. LEAVITT")
        self.assertIn("good afternoon", segments[0].normalized_text)

    def test_parse_youtube_captions(self):
        xml = """
        <transcript>
          <text start="0.0" dur="1.2">Hello everybody</text>
          <text start="1.2" dur="2.0">Can you clarify the policy?</text>
        </transcript>
        """
        transcript, segments = parse_youtube_captions("artifact-yt", xml)
        self.assertEqual(transcript.transcript_type, "captions")
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0].start_time_seconds, 0.0)
        self.assertIn("hello everybody", segments[0].normalized_text)
        self.assertEqual(segments[0].speaker_label, "MS. LEAVITT")
        self.assertEqual(segments[1].speaker_label, "Q")

    def test_infer_briefing_speaker_label(self):
        self.assertEqual(infer_briefing_speaker_label("Can you clarify that?"), "Q")
        self.assertEqual(infer_briefing_speaker_label("We are here today to discuss tariffs."), "MS. LEAVITT")


if __name__ == "__main__":
    unittest.main()
