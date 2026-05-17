# Browser Automation Plan For Missing Kalshi Mention Markets

Date drafted: `2026-05-17`

## Goal

Recover older `KXSECPRESSMENTION` child markets that are missing from the current local database but appear to exist on Kalshi event pages.

The concrete target is the White House press secretary mention-market series:

- series ticker: `KXSECPRESSMENTION`
- known problematic example: `KXSECPRESSMENTION-26FEB10`
- browser page pattern observed earlier:
  - `https://kalshi.com/markets/kxsecpressmention/sec-press-mentions/kxsecpressmention-26feb10`

The desired output is normalized `Market` rows with the same shape as current public-API-ingested rows, including:

- market ticker
- event ticker
- target phrase
- rules text
- close/settlement timing
- result when available
- raw source payload retained in `metadata.response_payload`
- provenance showing whether the row came from live API, historical API, browser network capture, or DOM fallback

## Current Local State

The local datastore currently has:

- `59` `kalshi_whitehouse_mention_event` parent rows
- `281` White House mention child-market rows
- `9` parent events with stored child markets
- `50` parent events with `market_count = 0`

The only stored child-market event before 2026 is:

- `KXSECPRESSMENTION-25MAR06`
  - `15` child markets
  - `status = closed`
  - no stored `result`

The next stored child-market event is:

- `KXSECPRESSMENTION-26MAR08`
  - child markets closed on `2026-02-18`
  - finalized rows include `response_payload.result`

So the data gap is real, but it is not only a browser problem. It is an archival market-data problem.

## Updated Research Finding

Before implementing browser automation, we should try Kalshi's historical API.

Kalshi's current API docs state that:

- old events and series remain available through the original endpoints
- older market data is partitioned into historical endpoints
- live endpoints like `GET /markets` and `GET /events?with_nested_markets=true` stop returning markets older than the historical cutoff
- historical markets are available through `GET /historical/markets`
- `GET /historical/markets` supports `event_ticker` and `series_ticker` filters

Relevant docs:

- Kalshi Historical Data: https://docs.kalshi.com/getting_started/historical_data
- Kalshi Get Event: https://docs.kalshi.com/api-reference/events/get-event
- Kalshi Get Historical Markets: https://docs.kalshi.com/api-reference/historical/get-historical-markets
- Kalshi Get Historical Cutoff: https://docs.kalshi.com/api-reference/historical/get-historical-cutoff-timestamps

This means the first implementation should be an API fallback, not browser scraping. Browser automation should remain the contingency path for cases where:

- historical API still returns no child markets for a parent event visible in the web UI
- the web UI exposes richer payloads than the historical API
- the historical API requires unavailable market tickers and cannot enumerate by event

## Preferred Acquisition Order

For each parent event ticker:

1. Try live API:
   - `GET /events/{event_ticker}?with_nested_markets=true`
   - `GET /markets?event_ticker={event_ticker}`
2. If no markets are returned, try historical API:
   - `GET /historical/markets?event_ticker={event_ticker}`
3. If still no markets are returned, inspect browser network data from the event page.
4. Only if no JSON source is available, fall back to rendered DOM scraping.

This preserves a clean hierarchy:

- official documented API first
- browser-discovered JSON second
- visual HTML scraping last

## Proposed API-First Work

Add a historical Kalshi market path before adding browser code.

### Client Changes

Extend `KalshiPublicClient` with:

- `fetch_historical_cutoff()`
- `fetch_historical_markets_page(...)`

Likely method signature:

```python
def fetch_historical_markets_page(
    self,
    *,
    limit: int = 1000,
    cursor: Optional[str] = None,
    event_ticker: Optional[str] = None,
    series_ticker: Optional[str] = None,
) -> dict:
    ...
```

The historical endpoint should use the same `normalize_market_payload()` path where possible.

### Ingestor Changes

Add either:

- `KalshiHistoricalEventTickerIngestor`, or
- a `use_historical_fallback` option on `KalshiEventTickerIngestor`

For the White House vertical, the preferred behavior is:

1. fetch parent events from `/events?series_ticker=KXSECPRESSMENTION`
2. for each parent event:
   - try live nested markets
   - try live `/markets`
   - try historical `/historical/markets`
3. persist child markets when any source returns them
4. update parent-event `market_count` and `status_counts` from the actually stored children

### Provenance

Each stored market should include metadata such as:

```json
{
  "ingestion_source": "kalshi_historical_api",
  "source_endpoint": "/historical/markets",
  "source_event_ticker": "KXSECPRESSMENTION-26FEB10",
  "captured_at": "..."
}
```

For live rows, we should similarly mark:

```json
{
  "ingestion_source": "kalshi_live_api"
}
```

This will make later audits easier when browser and API sources disagree.

## Browser Automation Contingency

If historical API does not recover the missing markets, use Playwright for browser-backed discovery.

Official Playwright docs used for this plan:

- Playwright Python authentication and `storage_state`: https://playwright.dev/python/docs/auth
- Playwright Python network inspection and `page.expect_response()`: https://playwright.dev/python/docs/network
- Playwright Python `BrowserContext`: https://playwright.dev/python/docs/api/class-browsercontext

### Browser Automation Objectives

The browser automation phase should answer one question first:

> How does Kalshi's web app obtain the child-market list for a parent event page when the public live API returns no markets?

We should not start by scraping visible HTML. We should inspect network and page state first.

Possible data locations:

- documented historical API call
- internal API call made by Kalshi's frontend
- GraphQL or batched JSON endpoint
- server-rendered or hydrated page JSON
- embedded Next.js-style page data
- rendered DOM only

### Reconnaissance Script

Build a read-only diagnostic script first, not a production ingestor.

Inputs:

- event ticker, e.g. `KXSECPRESSMENTION-26FEB10`
- optional full Kalshi event page URL
- optional `--headed`
- optional `--storage-state`
- optional `--output-dir`

Outputs:

```text
data/raw/kalshi_web/
  KXSECPRESSMENTION-26FEB10/
    page.html
    responses.jsonl
    candidate_payloads.json
    console.jsonl
    screenshot.png
    network.har.zip
```

The script should:

1. launch Chromium
2. create an isolated context
3. optionally load stored auth state
4. navigate to the Kalshi event page
5. listen to all responses
6. save JSON responses that mention:
   - the event ticker
   - `KXSECPRESSMENTION`
   - child market tickers
   - `yes_sub_title`
   - `rules_primary`
7. save page HTML after network idle or after a known event-page marker appears
8. emit a summary of candidate JSON sources

### Authentication Handling

Start unauthenticated.

If the page requires login or hides archived markets unless logged in, support Playwright storage state.

Important safety rule:

- never commit storage-state files
- never write auth state under a tracked path

Recommended local-only path:

```text
mentions/data/private/browser_state/kalshi.json
```

Playwright's docs warn that storage-state files can contain sensitive cookies and tokens. If we use this, it must remain local and gitignored.

### Network Capture Details

Use:

- `page.on("response", handler)` for broad passive capture
- `page.expect_response(predicate)` when we identify the exact endpoint
- browser context HAR recording for debugging
- `service_workers="block"` if requests disappear behind a service worker

The response handler should avoid saving large static assets. It should focus on:

- JSON content type
- URLs containing `market`, `event`, `series`, `trpc`, `graphql`, or `api`
- response bodies that contain the event ticker

### Browser JSON Extractor

Once reconnaissance identifies the source, build a parser for the cleanest JSON payload.

Preferred parser order:

1. Parse a direct JSON API payload.
2. Parse hydrated page data from script tags.
3. Parse rendered HTML as a last resort.

The parser should return raw Kalshi-like market dictionaries that can flow through:

```python
normalize_market_payload(payload)
WhiteHouseMentionMarketParser().parse(market)
db.upsert_market(market)
```

### DOM Fallback

DOM scraping should be treated as a last resort because it is brittle.

If required, it should extract:

- market ticker, if present in links or data attributes
- target phrase from card text
- displayed result or settlement state
- link URL
- title/subtitle text

The fallback rows should be clearly marked:

```json
{
  "ingestion_source": "kalshi_browser_dom",
  "source_quality": "fallback_dom_scrape"
}
```

DOM-derived rows should not overwrite richer API-derived rows unless explicitly requested.

## Integration Plan

### Phase 1: Historical API Probe

Add a small manual command or script to test:

```bash
python3 -m mentions_engine.cli probe-kalshi-historical-event KXSECPRESSMENTION-26FEB10
```

Expected output:

- live nested count
- live markets count
- historical markets count
- first few tickers/phrases/results

If historical API works, implement historical fallback and skip browser automation for now.

### Phase 2: Historical API Ingest

Add an ingest path:

```bash
python3 -m mentions_engine.cli ingest-whitehouse-mention-events-with-history
```

or extend:

```bash
python3 -m mentions_engine.cli list-whitehouse-mention-markets --include-historical-api
```

Target behavior:

- fill child markets for zero-market parent events
- preserve existing live API behavior
- refresh parent summaries

### Phase 3: Browser Reconnaissance

Only if Phase 1 fails for known browser-visible events:

```bash
python3 -m mentions_engine.cli inspect-kalshi-event-page KXSECPRESSMENTION-26FEB10 --headed
```

This command should produce raw artifacts only. It should not mutate the main database.

### Phase 4: Browser JSON Ingest

Once the frontend payload is identified:

```bash
python3 -m mentions_engine.cli ingest-kalshi-event-page KXSECPRESSMENTION-26FEB10
```

This can persist rows, but only after parser tests exist against saved fixtures.

### Phase 5: Dataset Refresh

After market recovery:

```bash
python3 -m mentions_engine.cli build-word-frequencies
```

Then validate that older historical Kalshi market flags appear in the browser visualizer.

## Testing Plan

### Unit Tests

Use saved JSON fixtures for:

- historical API market page
- browser network payload, if needed
- browser hydrated page payload, if needed
- DOM fallback HTML, only if needed

Test requirements:

- target phrase parsing works
- `result` is preserved
- event ticker is preserved
- source provenance is preserved
- live and historical rows normalize to the same `Market` schema

### Integration Tests

Network-dependent tests should be opt-in.

Possible pattern:

```bash
RUN_KALSHI_LIVE_TESTS=1 python3 -m unittest tests.test_kalshi_historical_live
```

Avoid making routine unit tests depend on Kalshi availability.

### Validation Queries

After ingest:

```sql
select
  e.event_id,
  json_extract(e.metadata_json, '$.market_count') as parent_market_count,
  count(m.market_id) as stored_child_markets
from events e
left join markets m on m.event_id = e.event_id
where e.event_type = 'kalshi_whitehouse_mention_event'
group by e.event_id
order by e.event_id;
```

And:

```sql
select
  min(close_time),
  max(close_time),
  count(*)
from markets
where market_id like 'KXSECPRESSMENTION%';
```

## Operational Constraints

- Keep all browser automation read-only.
- Do not place trades.
- Do not bypass authentication, rate limits, CAPTCHA, or bot protections.
- Prefer official documented APIs.
- Use bounded concurrency and pauses between browser page loads.
- Persist raw artifacts so parser behavior can be audited.
- Keep auth state and cookies outside git.

## Risks

### Historical API May Already Solve The Problem

This is the best-case outcome. If so, browser automation is unnecessary for this task.

### Browser UI May Use Internal Endpoints

If the web app calls private endpoints, we should treat those as less stable than documented APIs. Use them only as a fallback and preserve payloads for audit.

### DOM Scraping May Be Fragile

Market-card layouts can change. DOM scraping should be isolated behind fixture tests and should not be the first recovery method.

### Event Date Mapping Still Needs Work

Even with recovered markets, Kalshi event dates and transcript dates may not match exactly.

Example:

- Kalshi event: `Before Mar 6, 2025`
- actual briefing transcript: `Mar. 5, 2025`

The word-frequency visualizer currently has a simple same-day market flag. A better mapping layer should match each Kalshi parent event to the nearest eligible White House briefing before the market close time.

## Success Criteria

Phase 1 success:

- historical API returns child markets for known zero-market parent events
- at least `KXSECPRESSMENTION-26FEB10` is recovered without browser automation

Full success:

- most or all zero-market parent events are filled with child markets
- recovered rows include target phrases and results where available
- parent event summaries reflect stored children
- word-frequency visualizer shows older Kalshi-market flags
- source provenance makes it clear which rows came from live API, historical API, or browser fallback

## Recommended Next Step

Do not start with Playwright.

First implement a very small historical API probe for `KXSECPRESSMENTION-26FEB10` and one or two 2025 parent events. If that recovers child markets, add the historical endpoint as the standard fallback. Use browser automation only for any parent events that remain empty despite the historical API.
