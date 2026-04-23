# Performance Plan

This document defines a focused performance plan for the current Kalshi dashboard implementation.

The primary goal is faster time-to-useful-data. Rendering performance matters, but only after the data path stops dominating end-to-end latency.

## Performance Priorities

Order of importance:

1. Reduce time to first useful market data
2. Reduce refresh latency for active views
3. Reduce request count and serialized network work
4. Reduce avoidable frontend recomputation and render cost
5. Add instrumentation so every optimization can be verified

## Current Performance Risks

## 1. `Positions` and `Watching` are request-heavy and mostly serialized

Current behavior:

- `fetch_positions_command` first fetches paginated positions
- It then fetches each market individually
- It then fetches event metadata for each distinct event
- `fetch_watch_markets_command` repeats the same per-market and per-event pattern

Why this is expensive:

- Total latency scales roughly with the number of positions and watched tickers
- Most of this work is on the critical path
- Even moderate portfolio sizes will feel slow

Expected impact:

- This is likely the single largest latency bottleneck in the app today

## 2. Authenticated requests use external OpenSSL per request

Current behavior:

- Each authenticated request writes a temp file
- The app spawns `openssl`
- The app reads the signature result back into Rust

Why this is expensive:

- Process startup and disk I/O are high fixed costs
- This overhead repeats for every authenticated page fetch
- It also makes instrumentation noisier because signing cost is mixed into request cost

Expected impact:

- High for `Positions`
- Moderate anywhere future authenticated polling is added

## 3. HTTP clients are rebuilt per command

Current behavior:

- Each Tauri command builds a new `reqwest::Client`

Why this is expensive:

- Connection reuse is weakened across invocations
- TLS and pool setup costs are paid more often than necessary
- Polling workloads benefit heavily from long-lived clients

Expected impact:

- Moderate, especially on repeated refreshes

## 4. Category loading walks full pagination sequentially

Current behavior:

- The app fetches standard and multivariate first pages in parallel
- Remaining pages are then fetched in sequence
- Auto-refresh refetches the selected categories from the beginning

Why this is expensive:

- Load time scales with total selected-category size, not visible content
- Refresh cost scales with total category size again
- The app pays network cost for data the user may never inspect

Expected impact:

- High for market scanning with several categories selected

## 5. Market sorting recomputes aggregates repeatedly

Current behavior:

- Event groups are rebuilt from summaries plus detail cache
- Sort comparators recompute `max` and `sum` values from row arrays

Why this is expensive:

- Comparator work is repeated many times during sort
- Cost grows as more event details are loaded
- This is unnecessary because aggregates are stable until the cache entry changes

Expected impact:

- Moderate
- More noticeable as caches grow and page size increases

## 6. View-state and render hot paths do avoidable work

Current behavior:

- `JSON.stringify` is used for state equality and default-view checks
- `Intl` formatters are recreated per call
- `includes` checks on arrays are repeated across rows

Why this is expensive:

- These are synchronous hot-path allocations
- They increase UI cost during typing, sorting, and row rendering

Expected impact:

- Low to moderate today
- Worth cleaning up after fetch-path issues

## 7. Rendering scales linearly with expanded rows

Current behavior:

- Current pages render all visible rows directly
- Expanded grouped views render every child row in the page

Why this is expensive:

- Large expanded pages increase DOM size and formatting work
- Pagination helps, but expanded grouped views can still become heavy

Expected impact:

- Secondary today
- More important after backend fetches get faster

## Optimization Plan

## Phase 1: Add Instrumentation First

We should not start by optimizing blind. Add measurement first, then optimize the highest-latency path with before/after comparisons.

Deliverables:

- End-to-end timings for each Tauri command
- Per-upstream-request timings in Rust
- Counts for HTTP requests by screen action
- Frontend timings for major derived-data computations
- Basic render timing around tab switches and filter changes

Success criteria:

- We can answer:
  - How long did the whole command take?
  - How many upstream Kalshi requests did it issue?
  - Which request types dominated?
  - How much time was spent in React-side derivation after data arrived?

## Phase 2: Fix Data Path Bottlenecks

### 2.1 Rework `Positions`

Target:

- Eliminate or sharply reduce per-position `market` and `event` fetches

Options:

- Prefer a Kalshi endpoint or query shape that already returns enough market and event fields
- If that does not exist, batch by event where possible instead of per position
- If individual fetches remain necessary, parallelize them with bounded concurrency

Success criteria:

- Request count grows much more slowly than position count
- Time to load positions drops substantially for medium and large portfolios

### 2.2 Rework `Watching`

Target:

- Avoid one market request plus one event request per watched ticker

Options:

- Group watched tickers by event when possible
- Add bounded-concurrency fetching if batching is unavailable
- Cache event metadata aggressively

Success criteria:

- Watchlist refresh remains fast even with many watched markets

### 2.3 Replace external signing

Target:

- Sign Kalshi auth messages inside Rust

Options:

- Use a Rust crypto library for RSA-PSS signing with the existing private key format

Success criteria:

- No temp files
- No `openssl` subprocesses
- Lower and more stable auth request overhead

### 2.4 Reuse shared HTTP clients

Target:

- Keep long-lived public and authenticated `reqwest::Client`s

Options:

- Build clients once at app startup and store them in Tauri state

Success criteria:

- Better connection reuse
- Lower repeated refresh latency

## Phase 3: Improve Market Data Strategy

### 3.1 Reduce full-category refresh cost

Target:

- Avoid refetching full selected categories from scratch on every timer tick

Options:

- Refresh only currently visible categories first
- Refresh visible pages before background pages
- Keep category freshness metadata and skip recent categories
- Consider stale-while-revalidate behavior

Success criteria:

- Auto-refresh updates visible data quickly even when many categories are selected

### 3.2 Make detail fetching more intentional

Target:

- Only load event details when they materially improve the current view

Options:

- Keep current expand-to-load behavior for grouped mode
- In ungrouped mode, preload only current-page detail rows
- Add prefetch only for likely-next items, not all possible items

Success criteria:

- Lower bandwidth and faster perceived responsiveness

## Phase 4: Reduce Frontend Compute Cost

### 4.1 Precompute event aggregates

Target:

- Compute event-level sort metrics once when details are loaded

Examples:

- max yes bid
- max no bid
- total volume

Success criteria:

- Sorting cost is closer to `O(n log n)` on simple keys, not `O(n log n * rows_per_group)`

### 4.2 Remove hot-path avoidable work

Target:

- Make common UI paths cheaper

Changes:

- Replace `JSON.stringify` equality checks with explicit comparisons or dirty flags
- Hoist `Intl.NumberFormat` and `Intl.DateTimeFormat` instances
- Convert watched and expanded ID lists to `Set` lookups during render

Success criteria:

- Less synchronous work during typing and view changes

### 4.3 Consider list virtualization later

Target:

- Only render visible rows when row counts become large enough

When to do it:

- After instrumentation shows render time is material
- After backend fetch latency is no longer dominant

Success criteria:

- Stable scroll and expand performance on large pages

## Instrumentation Plan

Instrumentation should be built into both Rust and React. It should be lightweight in normal development, easy to turn on, and structured enough to compare runs.

## Principles

- Measure real user flows, not just isolated functions
- Record both latency and request counts
- Separate upstream API time from local compute time
- Keep instrumentation off or minimal in normal UI flow unless explicitly enabled

## Rust Instrumentation

Add a small timing utility in the Tauri layer.

Suggested metrics:

- command name
- command start/end time
- total command duration
- upstream request URL category
- upstream request duration
- response status
- signing duration
- JSON parse duration
- request count per command

Suggested implementation:

- Wrap each Tauri command with a timing helper
- Wrap outbound Kalshi requests with a request-timing helper
- Emit structured logs as JSON lines or concise tagged text
- Add a debug flag like `KALSHI_PERF=1`

Example event shapes:

```json
{"kind":"command","name":"fetch_positions_command","duration_ms":1840,"request_count":27}
{"kind":"http","command":"fetch_positions_command","target":"market_details","duration_ms":96,"status":200}
{"kind":"sign","command":"fetch_positions_command","duration_ms":18}
```

Recommended code points:

- `authenticated_get`
- `fetch_event_page`
- `fetch_market_details`
- `fetch_event_metadata`
- each Tauri command entrypoint

Useful derived summaries:

- average request duration by request type
- p95 command duration
- request count per loaded tab
- signing overhead as a percentage of total command time

## Frontend Instrumentation

Add lightweight timing around the expensive derived-data paths and major interaction flows.

Suggested metrics:

- tab-switch duration until data-ready state
- filter-change duration until next paint
- time spent in:
  - `allSelectedEvents`
  - `filteredEvents`
  - `sortedEvents`
  - `flatMarketRows`
  - `filteredPositions`
  - `sortedPositions`
  - `groupedPositions`

Suggested implementation:

- Use `performance.now()` around major derivations in development mode
- Use `performance.mark` / `performance.measure` for interaction-level timings
- Add a small helper so instrumentation code is not repeated everywhere
- Optionally use React `Profiler` around the main table body

Example measurements:

- `markets:filter-change-to-render`
- `positions:load-to-render`
- `watching:refresh-to-render`
- `derive:sortedEvents`

Useful derived summaries:

- median and p95 derivation time by function
- render duration after filter typing
- render duration after toggling grouped mode

## Manual Test Flows

We need repeatable flows for measurement.

## Flow A: Market startup

1. Launch the app
2. Select one small category
3. Measure:
   - categories load time
   - first event page load time
   - first grouped render time

## Flow B: Large market selection

1. Select several high-volume categories
2. Measure:
   - total event-summary load time
   - request count
   - auto-refresh latency

## Flow C: Positions

1. Open `Positions`
2. Measure:
   - total command time
   - total upstream requests
   - time spent in signing
   - time to first render

## Flow D: Watching

1. Add a small watchlist
2. Add a large watchlist
3. Measure:
   - refresh time
   - request count
   - render time by watchlist size

## Flow E: UI compute stress

1. Use a loaded dataset
2. Type into keyword search quickly
3. Toggle sort repeatedly
4. Toggle grouped mode
5. Measure:
   - derivation times
   - paint delay
   - any long tasks

## Benchmark Harness Options

We should support at least one low-friction manual path and one repeatable scripted path.

## Option 1: Structured logging plus manual runs

Pros:

- Quickest to add
- Good enough for early iteration

Needs:

- Consistent perf log format
- A short script to summarize log files

## Option 2: Development-only benchmark commands

Add Tauri commands that execute representative data flows without the UI.

Examples:

- `benchmark_positions_command`
- `benchmark_watchlist_command`
- `benchmark_category_command`

Pros:

- Lets us compare backend changes directly
- Easier to automate

Needs:

- Fixed input parameters
- Stable output summary

## Option 3: Browser/Tauri interaction benchmark script

Use a UI automation tool later to run fixed flows and record timings.

Pros:

- Measures real user-visible performance

Needs:

- More setup
- Best deferred until core metrics already exist

## Recommended Execution Order

1. Add Rust command/request instrumentation
2. Add frontend derivation and interaction instrumentation
3. Benchmark current baseline and save results
4. Optimize `Positions`
5. Optimize `Watching`
6. Replace OpenSSL subprocess signing
7. Reuse shared HTTP clients
8. Improve category refresh strategy
9. Reduce frontend derivation costs
10. Re-measure after each step

## Initial Success Targets

These should be refined after the first baseline run.

- `Positions`: reduce request count and cut total load time by at least 50% on a representative portfolio
- `Watching`: keep refresh time near-constant for small to medium watchlists
- `Markets` auto-refresh: visible-data refresh should feel immediate even with multiple categories selected
- frontend derivations: no routine interaction should cause noticeable blocking on a typical loaded page

## Recent Findings

We now have a working closed-loop headless benchmark for the Rust data path.

Artifacts added:

- [`src-tauri/src/bin/benchmark_positions.rs`](src-tauri/src/bin/benchmark_positions.rs)
- [`src-tauri/src/bin/debug_auth.rs`](src-tauri/src/bin/debug_auth.rs)

This benchmark can run the `Positions` flow repeatedly without launching the desktop UI and reports end-to-end timing plus request counts.

### Auth Issue Found And Fixed

During benchmark bring-up, Rust authenticated requests were failing with:

- `401 Unauthorized`
- `INCORRECT_API_KEY_SIGNATURE`

Root cause:

- The Rust code signed only the request suffix such as `/portfolio/positions`
- Kalshi expects the full parsed URL path from the configured base URL, such as `/trade-api/v2/portfolio/positions`
- The existing Python client already handled this correctly

Fix applied:

- `authenticated_get` now parses the full URL and signs the correct path before sending the request

Implication:

- The benchmark and future authenticated Rust profiling are now trustworthy

### Current Positions Baseline

Benchmark command used:

```bash
cd dashboard/src-tauri
set -a; source ../.env; export KALSHI_PERF=1; set +a
cargo run --bin benchmark_positions -- 3
```

Observed baseline:

- average duration: `1721ms`
- average request count: `21`
- average summed upstream request time: `1585ms`
- average signing time: `11ms`
- row count: `10`

Per-run results:

- run 1: `1611ms`, `21` requests, `1561ms` request time, `6ms` signing
- run 2: `1698ms`, `21` requests, `1581ms` request time, `14ms` signing
- run 3: `1855ms`, `21` requests, `1613ms` request time, `15ms` signing

### What The Baseline Means

The benchmark confirms the earlier hypothesis:

- Signing overhead is negligible
- The initial authenticated positions request is not the main cost
- The dominant cost is the serialized N+1 fan-out after positions load

For `10` returned rows, the current implementation issued:

- `1` authenticated `positions` request
- `10` market detail requests
- `10` event metadata requests

That means almost all meaningful latency is in follow-up enrichment requests rather than the portfolio endpoint itself.

### Additional API Findings

Live inspection of `/portfolio/positions` showed:

- the response includes both `market_positions` and `event_positions`
- `market_positions` is present and usable for the current UI model
- the earlier discrepancy came from only printing a truncated Python response body

This means the current parser shape is valid, and the main problem remains fetch strategy rather than schema mismatch.

### Positions Improvement: Bounded-Concurrency Enrichment

Change applied:

- the `Positions` enrichment path now fetches market details and event metadata with bounded parallelism instead of fully serialized follow-up requests
- public enrichment fetches now retry briefly on `429 Too Many Requests`

Observed follow-up benchmark:

- average duration: `801ms`
- average request count: `21`
- average summed upstream request time: `2238ms`
- average signing time: `8ms`
- row count: `10`

Per-run results:

- run 1: `838ms`, `21` requests, `2351ms` request time, `4ms` signing
- run 2: `788ms`, `21` requests, `2034ms` request time, `9ms` signing
- run 3: `777ms`, `21` requests, `2330ms` request time, `11ms` signing

Interpretation:

- end-to-end `Positions` latency improved by about `53%`
- request count did not change yet
- summed upstream request time increased because more work now overlaps instead of sitting on the critical path
- the next highest-value step is reducing request count, not increasing concurrency further

### Positions Improvement: Event-Level Hydration

Change applied:

- `Positions` now uses `event_positions` from `/portfolio/positions` to discover the relevant events
- it hydrates each event once via `/events/{event_ticker}?with_nested_markets=true`
- that single event-details call now replaces both:
  - per-market detail requests
  - per-event metadata requests
- event-details hydration uses bounded parallelism and short retry/backoff on `429`

Observed follow-up benchmark:

- average duration: `477ms`
- average request count: `11`
- average summed upstream request time: `1362ms`
- average signing time: `11ms`
- row count: `10`

Per-run results:

- run 1: `457ms`, `11` requests, `1375ms` request time, `9ms` signing
- run 2: `458ms`, `11` requests, `1495ms` request time, `9ms` signing
- run 3: `516ms`, `11` requests, `1218ms` request time, `15ms` signing

Interpretation:

- end-to-end `Positions` latency improved by about `72%` versus the original `1721ms` baseline
- request count dropped from `21` to `11`
- summed upstream request time also improved, which means this is not just a critical-path overlap win
- this is the strongest `Positions` result so far and should replace the earlier `21`-request parallel-market baseline as the working comparison point

### Watching Benchmark And Optimization

Artifacts added:

- [`src-tauri/src/bin/benchmark_watching.rs`](src-tauri/src/bin/benchmark_watching.rs)

Change applied:

- extracted the watch refresh path into a reusable Rust helper
- replaced the serialized market-by-market watch refresh with:
  - bounded-concurrency market detail fetches
  - followed by bounded-concurrency event metadata fetches

Benchmark command used:

```bash
cd dashboard/src-tauri
set -a; source ../.env; export KALSHI_PERF=1; set +a
cargo run --bin benchmark_watching -- 3 KXFDAAPPROVALPSYCHEDELIC-27-ANYPSYCH KXALIENS-27 KXCLAUDE-MYTH-26JUL01 KXNEWGLENN-26B-MAY KXNBA1STTEAM-26-LDON
```

Observed baseline for this `5`-ticker sample:

- average duration: `354ms`
- average request count: `10`
- average summed upstream request time: `1390ms`
- average signing time: `0ms`
- row count: `5`

Per-run results:

- run 1: `381ms`, `10` requests, `1174ms` request time
- run 2: `241ms`, `10` requests, `1084ms` request time
- run 3: `440ms`, `10` requests, `1912ms` request time

Additional finding:

- an attempted watch optimization that inferred event tickers and hydrated via event-details reduced request count from `10` to `6` on this sample
- despite the lower request count, it was much slower in practice because the event-details payloads were heavier and included `404` fallback work
- conclusion: for `Watching`, lower request count was not the right optimization target for this flow

### Markets Benchmark And Findings

Artifacts added:

- [`src-tauri/src/bin/benchmark_category.rs`](src-tauri/src/bin/benchmark_category.rs)

Change applied:

- extracted a reusable Rust helper for full category/event loading
- the helper mirrors the frontend strategy:
  - first standard and multivariate pages in parallel
  - then sequential follow-up pagination
- added retry/backoff for `fetch_event_page` so category loads can survive `429 Too Many Requests`
- added a benchmark-only `--max-pages-per-source` option because some full categories are too large for a practical single-turn benchmark

Observed live category findings:

- `Science and Technology` is large enough that a full benchmark run becomes dominated by multivariate pagination and is impractical as an uncapped baseline in-session
- even `Economics` can hit repeated `429`s on the standard event path

Observed capped benchmark:

```bash
cd dashboard/src-tauri
set -a; source ../.env; export KALSHI_PERF=1; set +a
cargo run --bin benchmark_category -- 1 --max-pages-per-source 5 Economics
```

Result:

- duration: `5875ms`
- event count: `66`
- pages per source: `5`
- request count: `14`
- summed upstream request time: `2039ms`

Interpretation:

- `Markets` category loading is now the clearest remaining backend hotspot
- the main issue is not just raw request count; it is large multivariate pagination volume plus rate limiting
- visible-data-first refresh strategy is likely a higher-value next step than simply trying to parallelize harder

### Markets Refresh Strategy Changes

Changes applied in the frontend:

- `Markets` auto-refresh is now visible-data-first
- currently visible categories refresh before any off-screen selected categories
- off-screen selected categories now use stale-while-revalidate head refreshes:
  - only the first standard page
  - plus the first multivariate page
  - merged back into the existing category cache
- selected categories now track freshness timestamps in the cache
- background category refreshes are skipped when the cached data is still fresh relative to the chosen auto-refresh interval
- the filter pane now shows per-selected-category refresh state:
  - `loading`
  - `fresh`
  - `stale`
  - `pending`

Testing completed:

- `npm run check`
- `cargo check`
- live `benchmark_category -- --list-categories`
- live `benchmark_category -- 1 --max-pages-per-source 5 Economics`

Additional live findings:

- a capped `Economics` sample completed successfully after stronger retry/backoff was added to category page fetches
- result:
  - `5875ms` total duration
  - `66` events
  - `14` requests
  - `2039ms` summed upstream request time
- larger uncapped category runs can continue for a very long time and are a real operational concern, not just a benchmark inconvenience

Implication:

- the current `Markets` work now prioritizes user-visible responsiveness over full immediate consistency for all selected categories
- this is the correct direction for large category sets given the measured rate limiting and pagination cost

## Planned Next Steps

These are the next execution steps, in order, but should not be started automatically from this document alone.

## 1. Validate `Positions` On Larger Samples

This is now the highest-confidence performance target because we have a measured baseline.

Immediate goals:

- verify the new event-level hydration path remains stable on larger portfolios
- look for any remaining avoidable event-detail payload cost
- preserve current data fidelity

Implementation directions:

- benchmark against larger portfolios if available
- inspect whether Kalshi exposes a lighter event shape that still includes the needed market fields
- only revisit this path if larger real-world portfolios expose a new bottleneck

Success criteria:

- keep the request count near `1 + distinct_event_count`
- keep measured latency near the new `477ms` baseline or better on the current sample

## 2. Re-benchmark After Each Positions Change

For every positions optimization:

- rerun the headless benchmark for at least `3` iterations
- compare request count
- compare average total duration
- compare average summed request duration

This is the main guardrail against “optimizations” that only shift cost around.

## 3. Push `Watching` Only If Larger Lists Need It

Current state:

- `Watching` now has a headless benchmark
- the faster path is parallel market-details plus event-metadata hydration
- lower request count alone was not a win for this flow

Goal:

- keep refresh time stable on medium watchlists without switching to heavier payloads

Next directions:

- benchmark with larger and more clustered watchlists
- look for a lighter batch market endpoint, if Kalshi exposes one
- avoid event-details hydration unless a future dataset proves it wins end-to-end

## 4. Add A Benchmark For `Markets`

Goal:

- get the same closed-loop measurement ability for category and event loading in `Markets`

Status:

- done for category/event loading
- benchmark supports both uncapped and capped category samples

Next directions:

- benchmark a few representative categories with small and medium page caps
- measure the visible-data-first and stale-while-revalidate behavior in the UI with perf logging enabled
- consider adding per-category freshness thresholds or refresh budgets that vary by category size
- consider pausing or deferring full category walks unless the user explicitly drills into that category

## 5. Keep Frontend Optimization Deferred Until Backend Cost Drops

Current evidence says backend fetch strategy dominates.

So:

- keep existing frontend instrumentation
- do not prioritize render-layer optimization yet
- revisit frontend hot paths only after the backend request fan-out is reduced

## Open Questions

- Which Kalshi endpoints can return richer market and event data in fewer calls?
- Are there server-side rate limits that change the best concurrency strategy?
- What is the representative size of:
  - selected categories
  - open positions
  - watchlists
- Do we want perf logging only in development, or also in optional production debug builds?
