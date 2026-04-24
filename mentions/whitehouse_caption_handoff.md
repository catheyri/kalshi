# Kalshi White House Mentions Handoff

Date verified: `2026-04-23`

Current state:

- White House briefing transcript ingestion is already in place and populated in the real datastore.
- Kalshi White House mention child markets are already stored in the real datastore.
- Kalshi parent-event persistence was corrected so parent events are now discovered from `/events?series_ticker=KXSECPRESSMENTION` instead of only inferring them from `/markets`.
- The real DB now contains:
  - `59` `kalshi_whitehouse_mention_event` rows
  - `281` White House mention child-market rows
  - `9` parent events with `market_count > 0`
  - `50` parent events with `market_count = 0`

Important finding:

- The Kalshi public Trade API appears incomplete for older `KXSECPRESSMENTION` events.
- Example: `KXSECPRESSMENTION-26FEB10`
  - The browser-visible Kalshi page appears to show child markets.
  - But the public API currently returns:
    - `/events/KXSECPRESSMENTION-26FEB10?with_nested_markets=true` -> `markets: []`
    - `/markets?event_ticker=KXSECPRESSMENTION-26FEB10` -> `[]`
- This suggests a web-view/API mismatch rather than a local parsing bug.

What was just changed in code:

- `mentions_engine/kalshi.py`
  - `fetch_events_page()` now supports `series_ticker`.
- `mentions_engine/whitehouse_markets.py`
  - parent-event discovery now uses Kalshi `/events`
  - event persistence now includes parent event shells with `market_count`
  - event summaries distinguish between market-bearing events and empty shells
- `tests/test_whitehouse_market_report.py`
  - updated to cover event discovery from `/events`
  - updated to cover persisted zero-market parent events

Verification completed:

- `python3 -m unittest discover -s tests` passes.
- Real DB was refreshed so parent Kalshi events now reflect the corrected count of `59`.

Next steps:

1. Do not trust the public Trade API alone for older `KXSECPRESSMENTION` history.
2. Use a real browser-backed session against a known problematic event page such as:
   - `https://kalshi.com/markets/kxsecpressmention/sec-press-mentions/kxsecpressmention-26feb10`
3. Inspect the page network traffic and identify how the web app obtains the visible market list.
   - likely hydrated JSON in page data, or
   - a non-public/internal JSON endpoint called by the frontend
4. Prefer capturing that underlying JSON source rather than scraping rendered HTML.
5. Add a fallback fetch path for “event exists in web UI but Trade API returns no markets”.
6. Only fall back to HTML scraping if browser-network inspection does not expose a cleaner JSON source.

Goal of the next pass:

- Recover older White House mention child markets that are visible in the Kalshi web UI but absent from the public Trade API.
