import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mentions_engine.config import AppPaths
from mentions_engine.storage import Database
from mentions_engine.whitehouse_markets import (
    WhiteHouseMentionMarketReporter,
    render_whitehouse_mention_event_report,
    render_whitehouse_mention_market_report,
)


class WhiteHouseMentionMarketReportTests(unittest.TestCase):
    def test_reporter_lists_historical_and_live_markets_and_persists_matches(self):
        class StubClient:
            def __init__(self):
                self.calls = []

            def fetch_events_page(
                self,
                *,
                category=None,
                status=None,
                series_ticker=None,
                limit=200,
                cursor=None,
            ):
                self.calls.append(
                    {
                        "limit": limit,
                        "cursor": cursor,
                        "series_ticker": series_ticker,
                        "category": category,
                        "status": status,
                        "kind": "events",
                    }
                )
                if series_ticker == "KXSECPRESSMENTION":
                    return {
                        "cursor": None,
                        "events": [
                            {
                                "event_ticker": "KXSECPRESSMENTION-26APR24",
                                "series_ticker": "KXSECPRESSMENTION",
                                "title": "What will Karoline Leavitt say in the next press briefing?",
                                "sub_title": "Before Apr 24, 2026",
                                "category": "Mentions",
                            },
                            {
                                "event_ticker": "KXSECPRESSMENTION-26APR22",
                                "series_ticker": "KXSECPRESSMENTION",
                                "title": "What will Karoline Leavitt say in the next press briefing?",
                                "sub_title": "Before Apr 22, 2026",
                                "category": "Mentions",
                            },
                            {
                                "event_ticker": "KXSECPRESSMENTION-26APR20",
                                "series_ticker": "KXSECPRESSMENTION",
                                "title": "What will Karoline Leavitt say in the next press briefing?",
                                "sub_title": "Before Apr 20, 2026",
                                "category": "Mentions",
                            },
                        ],
                    }
                return {"cursor": None, "events": []}

            def fetch_markets_page(
                self,
                *,
                limit=100,
                cursor=None,
                event_ticker=None,
                series_ticker=None,
                min_close_ts=None,
                max_close_ts=None,
                status=None,
                tickers=None,
            ):
                self.calls.append(
                    {
                        "limit": limit,
                        "cursor": cursor,
                        "series_ticker": series_ticker,
                        "min_close_ts": min_close_ts,
                        "max_close_ts": max_close_ts,
                        "status": status,
                        "kind": "markets",
                    }
                )
                if series_ticker == "KXSECPRESSMENTION":
                    return {
                        "cursor": None,
                        "markets": [
                            {
                                "ticker": "WH-1",
                                "event_ticker": "KXSECPRESSMENTION-26APR22",
                                "title": "Will the White House Press Secretary say border crisis at her next press briefing?",
                                "yes_sub_title": "border crisis",
                                "status": "finalized",
                                "close_time": "2026-04-22T18:00:00Z",
                                "rules_primary": "Resolves YES if the White House Press Secretary says the phrase border crisis at her next press briefing.",
                                "yes_bid_dollars": "0.44",
                                "yes_ask_dollars": "0.49",
                                "volume_fp": "120",
                                "result": "yes",
                            },
                            {
                                "ticker": "WH-OPEN-1",
                                "event_ticker": "KXSECPRESSMENTION-26APR24",
                                "title": "Will the White House Press Secretary say tariffs at her next press briefing?",
                                "yes_sub_title": "tariffs",
                                "status": "active",
                                "close_time": "2026-04-24T18:00:00Z",
                                "rules_primary": "Resolves YES if the White House Press Secretary says the phrase tariffs at her next press briefing.",
                                "yes_bid_dollars": "0.35",
                                "yes_ask_dollars": "0.41",
                                "volume_fp": "75",
                            },
                        ],
                    }
                return {"cursor": None, "markets": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            paths = AppPaths.from_root(Path(tmpdir))
            paths.ensure()
            db = Database(paths.db_path)
            db.initialize()

            reporter = WhiteHouseMentionMarketReporter(StubClient(), db=db)
            report = reporter.build_report(
                speaker_key="karoline_leavitt",
                history_limit=10,
                lookback_days=30,
                window_days=30,
                historical_pages_per_window=1,
                open_pages=1,
                now=datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(len(report.historical_markets), 1)
            self.assertEqual(report.historical_markets[0].metadata["target_phrase"], "border crisis")
            self.assertEqual(len(report.live_markets), 1)
            self.assertEqual(report.live_markets[0].market_id, "WH-OPEN-1")
            self.assertEqual(report.live_markets[0].metadata["briefing_scope"], "next_briefing")
            self.assertEqual(len(report.historical_events), 2)
            self.assertEqual(report.historical_events[1].event_ticker, "KXSECPRESSMENTION-26APR20")
            self.assertEqual(report.historical_events[1].market_count, 0)
            self.assertEqual(len(db.list_markets()), 2)
            with db.connect() as conn:
                stored_events = conn.execute(
                    """
                    select event_id, event_type, title
                    from events
                    where event_id in ('KXSECPRESSMENTION-26APR20', 'KXSECPRESSMENTION-26APR22', 'KXSECPRESSMENTION-26APR24')
                    order by event_id
                    """
                ).fetchall()
            self.assertEqual(len(stored_events), 3)
            self.assertEqual(stored_events[0]["event_type"], "kalshi_whitehouse_mention_event")
            self.assertIn("Karoline Leavitt", stored_events[0]["title"])

            rendered = render_whitehouse_mention_market_report(report)
            self.assertIn("Karoline Leavitt White House mention markets", rendered)
            self.assertIn("border crisis", rendered)
            self.assertIn("WH-OPEN-1", rendered)
            event_rendered = render_whitehouse_mention_event_report(report)
            self.assertIn("Karoline Leavitt White House mention events", event_rendered)
            self.assertIn("KXSECPRESSMENTION-26APR22", event_rendered)
            self.assertIn("KXSECPRESSMENTION-26APR20", event_rendered)
            self.assertIn("0", event_rendered)
            self.assertIn("active:1", event_rendered)
            self.assertTrue(any(call["series_ticker"] == "KXSECPRESSMENTION" for call in reporter.client.calls))


if __name__ == "__main__":
    unittest.main()
