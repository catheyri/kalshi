import unittest

from mentions_engine.kalshi import normalize_market_payload
from mentions_engine.market_analysis.whitehouse import WhiteHouseMentionMarketParser
from mentions_engine.market_ingest.kalshi import KalshiEventTickerIngestor
from mentions_engine.outcomes.kalshi import KalshiMarketOutcomeImporter, resolve_market_yes_no


class KalshiIngestionTests(unittest.TestCase):
    def test_normalize_market_payload(self):
        market = normalize_market_payload(
            {
                "ticker": "KXTEST-1",
                "event_ticker": "EVENT-1",
                "series_ticker": "SERIES-1",
                "title": "Will tariffs be mentioned?",
                "subtitle": "Yes",
                "status": "open",
                "yes_bid_dollars": "0.42",
                "yes_ask_dollars": "0.47",
                "no_bid_dollars": "0.53",
                "no_ask_dollars": "0.58",
                "volume_fp": "1234.0",
                "rules_primary": "Resolves YES if tariffs are mentioned.",
                "close_time": "2026-05-01T00:00:00Z",
            }
        )
        self.assertEqual(market.market_id, "KXTEST-1")
        self.assertEqual(market.event_id, "EVENT-1")
        self.assertEqual(market.yes_bid, 42)
        self.assertEqual(market.volume, 1234)

    def test_event_ticker_ingestor_fetches_nested_markets(self):
        class StubClient:
            def fetch_event(self, event_ticker, with_nested_markets=False):
                self.last = (event_ticker, with_nested_markets)
                return {
                    "event_ticker": event_ticker,
                    "series_ticker": "SERIES-1",
                    "markets": [
                        {
                            "ticker": "KXTEST-1",
                            "event_ticker": event_ticker,
                            "title": "Will tariffs be mentioned?",
                            "status": "open",
                            "yes_bid_dollars": "0.42",
                            "yes_ask_dollars": "0.47",
                        },
                        {
                            "ticker": "KXTEST-2",
                            "event_ticker": event_ticker,
                            "title": "Closed market",
                            "status": "settled",
                            "yes_bid_dollars": "1.0",
                            "yes_ask_dollars": "1.0",
                        },
                    ],
                }

        client = StubClient()
        ingestor = KalshiEventTickerIngestor(["EVENT-1"], client)
        markets = ingestor.fetch_open_markets()
        self.assertEqual(client.last, ("EVENT-1", True))
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].market_id, "KXTEST-1")

    def test_event_ticker_ingestor_can_filter_with_parser(self):
        class StubClient:
            def fetch_event(self, event_ticker, with_nested_markets=False):
                return {
                    "event_ticker": event_ticker,
                    "series_ticker": "SERIES-1",
                    "title": "White House press briefing",
                    "category": "Government",
                    "strike_date": "2026-04-22T18:00:00Z",
                    "markets": [
                        {
                            "ticker": "MENTION-1",
                            "event_ticker": event_ticker,
                            "title": 'What will Karoline Leavitt say about "border crisis" in the White House press briefing today?',
                            "status": "open",
                        },
                        {
                            "ticker": "OTHER-1",
                            "event_ticker": event_ticker,
                            "title": "Will the White House release a statement today?",
                            "status": "open",
                        },
                    ],
                }

        ingestor = KalshiEventTickerIngestor(
            ["EVENT-1"],
            StubClient(),
            parser=WhiteHouseMentionMarketParser(),
        )
        markets = ingestor.fetch_open_markets()
        self.assertEqual(len(markets), 1)
        self.assertEqual(markets[0].market_id, "MENTION-1")
        self.assertEqual(markets[0].metadata["speaker_name"], "Karoline Leavitt")

    def test_resolve_market_yes_no(self):
        self.assertTrue(resolve_market_yes_no({"result": "yes"}))
        self.assertFalse(resolve_market_yes_no({"winning_outcome": "no"}))
        self.assertTrue(resolve_market_yes_no({"settlement_value": 1}))
        self.assertIsNone(resolve_market_yes_no({"status": "open"}))

    def test_kalshi_outcome_importer_skips_unresolved(self):
        class StubClient:
            def fetch_market(self, ticker):
                if ticker == "YES-1":
                    return {
                        "ticker": ticker,
                        "event_ticker": "EVENT-1",
                        "result": "yes",
                        "settlement_time": "2026-01-01T00:00:00Z",
                    }
                return {"ticker": ticker, "event_ticker": "EVENT-2", "status": "open"}

        importer = KalshiMarketOutcomeImporter(["YES-1", "OPEN-1"], StubClient())
        outcomes = importer.load_outcomes()
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0].market_id, "YES-1")
        self.assertTrue(outcomes[0].resolved_yes)


if __name__ == "__main__":
    unittest.main()
