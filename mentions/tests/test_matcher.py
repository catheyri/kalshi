import unittest

from mentions_engine.matcher.simple import find_candidates, make_decisions
from mentions_engine.models import TranscriptSegment
from mentions_engine.rules import compile_rule_from_json


class MatcherTests(unittest.TestCase):
    def test_primary_speaker_scope_skips_questions(self):
        rule = compile_rule_from_json(
            {
                "market_id": "demo",
                "target_terms": ["tariffs"],
                "allowed_variants": [],
                "speaker_scope": ["primary_speaker"],
            }
        )
        segments = [
            TranscriptSegment(
                segment_id="seg-q",
                transcript_id="tx-1",
                start_time_seconds=None,
                end_time_seconds=None,
                speaker_id=None,
                speaker_label="Q",
                channel=None,
                text="Did the President mention tariffs?",
                normalized_text="did the president mention tariffs?",
                confidence=None,
                word_count=5,
                metadata={},
            ),
            TranscriptSegment(
                segment_id="seg-a",
                transcript_id="tx-1",
                start_time_seconds=None,
                end_time_seconds=None,
                speaker_id=None,
                speaker_label="MS. LEAVITT",
                channel=None,
                text="The President has been clear on tariffs.",
                normalized_text="the president has been clear on tariffs.",
                confidence=None,
                word_count=7,
                metadata={},
            ),
        ]
        candidates = find_candidates("demo", rule, "event-1", "tx-1", segments)
        decisions = make_decisions(candidates)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].segment_id, "seg-a")
        self.assertEqual(decisions[0].decision_status, "accepted")


if __name__ == "__main__":
    unittest.main()
