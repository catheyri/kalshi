import unittest

from mentions_engine.event_mapping.whitehouse import WhiteHouseEventMapper
from mentions_engine.market_analysis.whitehouse import WhiteHouseMentionMarketParser, WhiteHouseSpeakerRule
from mentions_engine.models import Market


class WhiteHouseMarketParsingTests(unittest.TestCase):
    def test_parser_extracts_speaker_first_metadata(self):
        market = Market(
            market_id="KXWHITEHOUSE-1",
            event_id="WHBRIEF-1",
            series_id=None,
            title='What will Karoline Leavitt say about "border crisis" in the White House press briefing today?',
            subtitle=None,
            status="open",
            close_time="2026-04-22T18:00:00Z",
            settlement_time=None,
            yes_bid=45,
            yes_ask=49,
            no_bid=51,
            no_ask=55,
            volume=100,
            open_interest=10,
            rules_text="Resolves YES if Karoline Leavitt says the phrase border crisis during today's briefing.",
            rules_summary_text=None,
            source_text=None,
            url=None,
            last_updated_at=None,
            metadata={},
        )

        parsed = WhiteHouseMentionMarketParser().parse(market)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.metadata["speaker_name"], "Karoline Leavitt")
        self.assertEqual(parsed.metadata["speaker_key"], "karoline_leavitt")
        self.assertEqual(parsed.metadata["target_phrase"], "border crisis")
        self.assertEqual(parsed.metadata["event_family"], "white_house_press_briefing")
        self.assertEqual(parsed.metadata["briefing_scope"], "today")

    def test_parser_rejects_non_mention_market(self):
        market = Market(
            market_id="KXOTHER-1",
            event_id="WHBRIEF-2",
            series_id=None,
            title="Will the White House release a statement today?",
            subtitle=None,
            status="open",
            close_time="2026-04-22T18:00:00Z",
            settlement_time=None,
            yes_bid=45,
            yes_ask=49,
            no_bid=51,
            no_ask=55,
            volume=100,
            open_interest=10,
            rules_text="Resolves YES if the White House releases a statement.",
            rules_summary_text=None,
            source_text=None,
            url=None,
            last_updated_at=None,
            metadata={},
        )

        self.assertIsNone(WhiteHouseMentionMarketParser().parse(market))

    def test_parser_uses_aliases_and_rules_text_for_target_phrase(self):
        market = Market(
            market_id="KXWHITEHOUSE-ALIAS-1",
            event_id="WHBRIEF-3",
            series_id=None,
            title="Will Leavitt mention tariffs in the White House press briefing today?",
            subtitle=None,
            status="open",
            close_time="2026-04-22T18:00:00Z",
            settlement_time=None,
            yes_bid=41,
            yes_ask=46,
            no_bid=54,
            no_ask=59,
            volume=120,
            open_interest=22,
            rules_text="Resolves YES if Press Secretary Karoline Leavitt says the phrase tariffs during today's briefing.",
            rules_summary_text=None,
            source_text=None,
            url=None,
            last_updated_at=None,
            metadata={},
        )

        parsed = WhiteHouseMentionMarketParser().parse(market)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.metadata["speaker_name"], "Karoline Leavitt")
        self.assertEqual(parsed.metadata["target_phrase"], "tariffs")
        self.assertEqual(parsed.metadata["briefing_scope"], "today")

    def test_parser_uses_subtitle_as_phrase_fallback(self):
        market = Market(
            market_id="KXWHITEHOUSE-SUBTITLE-1",
            event_id="WHBRIEF-3B",
            series_id=None,
            title="What will Karoline Leavitt say during the White House press briefing today?",
            subtitle="border crisis",
            status="open",
            close_time="2026-04-22T18:00:00Z",
            settlement_time=None,
            yes_bid=41,
            yes_ask=46,
            no_bid=54,
            no_ask=59,
            volume=120,
            open_interest=22,
            rules_text=None,
            rules_summary_text=None,
            source_text=None,
            url=None,
            last_updated_at=None,
            metadata={},
        )

        parsed = WhiteHouseMentionMarketParser().parse(market)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.metadata["target_phrase"], "border crisis")

    def test_parser_uses_event_title_context_for_generic_press_secretary_markets(self):
        market = Market(
            market_id="KXSECPRESSMENTION-26MAY07-TARI",
            event_id="KXSECPRESSMENTION-26MAY07",
            series_id="KXSECPRESSMENTION",
            title="Will the White House Press Secretary say Tariff at her next press briefing?",
            subtitle="Tariff",
            status="active",
            close_time="2026-05-07T14:00:00Z",
            settlement_time=None,
            yes_bid=35,
            yes_ask=41,
            no_bid=59,
            no_ask=65,
            volume=75,
            open_interest=12,
            rules_text="Resolves YES if the White House Press Secretary says the phrase Tariff at her next press briefing.",
            rules_summary_text=None,
            source_text=None,
            url=None,
            last_updated_at=None,
            metadata={
                "event_title": "What will Karoline Leavitt say in the next press briefing?",
                "event_subtitle": "Before May 7, 2026",
            },
        )

        parsed = WhiteHouseMentionMarketParser().parse(market)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.metadata["speaker_key"], "karoline_leavitt")
        self.assertEqual(parsed.metadata["target_phrase"], "Tariff")
        self.assertEqual(parsed.metadata["briefing_scope"], "next_briefing")

    def test_parser_accepts_custom_speaker_rule(self):
        market = Market(
            market_id="KXWHITEHOUSE-CUSTOM-1",
            event_id="WHBRIEF-4",
            series_id=None,
            title='What will Harrison Fields say about "energy dominance" in the White House press briefing tomorrow?',
            subtitle=None,
            status="open",
            close_time="2026-04-23T18:00:00Z",
            settlement_time=None,
            yes_bid=33,
            yes_ask=38,
            no_bid=62,
            no_ask=67,
            volume=90,
            open_interest=11,
            rules_text=None,
            rules_summary_text=None,
            source_text=None,
            url=None,
            last_updated_at=None,
            metadata={},
        )

        parser = WhiteHouseMentionMarketParser(
            speaker_rules=[
                WhiteHouseSpeakerRule(
                    canonical_name="Karoline Leavitt",
                    aliases=("karoline leavitt", "press secretary karoline leavitt", "leavitt"),
                ),
                WhiteHouseSpeakerRule(
                    canonical_name="Harrison Fields",
                    aliases=("harrison fields", "white house principal deputy press secretary harrison fields", "fields"),
                ),
            ]
        )
        parsed = parser.parse(market)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.metadata["speaker_name"], "Harrison Fields")
        self.assertEqual(parsed.metadata["speaker_key"], "harrison_fields")
        self.assertEqual(parsed.metadata["target_phrase"], "energy dominance")
        self.assertEqual(parsed.metadata["briefing_scope"], "tomorrow")

    def test_mapper_uses_speaker_key_and_date_for_event_id(self):
        market = Market(
            market_id="KXWHITEHOUSE-2",
            event_id=None,
            series_id=None,
            title="placeholder",
            subtitle=None,
            status="open",
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
                "speaker_name": "Karoline Leavitt",
                "speaker_key": "karoline_leavitt",
                "event_date": "2026-04-22",
                "event_title": "Karoline Leavitt White House press briefing 2026-04-22",
                "target_phrase": "border crisis",
            },
        )

        event = WhiteHouseEventMapper().map(market)
        self.assertIsNotNone(event)
        self.assertEqual(event.event_id, "whitehouse-karoline_leavitt-2026-04-22")
        self.assertEqual(event.participants, "Karoline Leavitt")


if __name__ == "__main__":
    unittest.main()
