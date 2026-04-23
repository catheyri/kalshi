# White House Caption Handoff

Last synced code state before the next caption-ingestion pass:

- Git commit: `086b5f2` (`Backfill official White House briefing sources`)
- Branch pushed: `origin/main`
- Date verified: `2026-04-23`

What is implemented:

- `python3 -m mentions_engine.cli backfill-whitehouse-official-transcripts --start-date 2025-01-20`
  - Discovers standalone official transcript pages from White House post sitemaps.
  - Fetches transcript HTML and builds normalized transcripts.
- `python3 -m mentions_engine.cli backfill-whitehouse-briefing-videos --start-date 2025-01-20`
  - Discovers official White House briefing video pages from `past_event-sitemap*.xml`.
  - Stores official video-page artifacts and fetches raw HTML.
  - Builds transcripts only if the page exposes a directly linked official transcript or machine-readable captions.

Verified live results:

- `backfill-whitehouse-briefing-videos --start-date 2025-01-20`
  - `discovered_events=64`
  - `discovered_artifacts=64`
  - `fetched_artifacts=64`
  - `events_with_text=0`
  - `transcripts_built=0`
  - `official_transcripts_built=0`
  - `caption_transcripts_built=0`
- `backfill-whitehouse-official-transcripts --start-date 2025-01-20`
  - `discovered_events=1`
  - `discovered_artifacts=1`
  - `fetched_artifacts=1`
  - `events_with_transcripts=1`
  - `transcripts_built=1`

Important findings:

- The official White House site currently exposes many more briefing video pages than standalone transcript pages.
- Video pages cannot be allowed to infer transcript pages via loose White House site search.
  - That path produced false positives, including attaching the Jan. 29, 2025 transcript to unrelated briefing videos.
  - The search fallback was removed.
- Event identity now keys off the official White House URL path, not just normalized title text.
  - This prevents collisions like the two different Apr. 1, 2025 briefing URLs.
- Discovery and fetched `video_replay` artifacts now share the same `artifact_id` scheme.
  - This avoids duplicate video artifacts for the same page.
- `HttpClient` now retries transient transport failures like `RemoteDisconnected`.

Known current limitation:

- Official video pages are being inventoried correctly, but the current extractor is not yet pulling usable captions from the embedded player.
- Earlier manual probing showed embedded YouTube IDs on at least some pages, but the current caption path did not yield stored `closed_captions` artifacts.

Next steps for the caption-ingestion pass:

1. Inspect several saved `data/raw/whitehouse/*.video.html` pages and extract the embedded player metadata more directly.
2. Parse the player JSON for:
   - YouTube video ID
   - caption track descriptors
   - any direct caption URLs or timedtext parameters
3. Add a deterministic extractor for caption track metadata from the official page HTML itself.
4. Only fetch captions from explicit embedded-track metadata or other directly exposed official player data.
   - Do not reintroduce loose White House site search.
5. If YouTube caption retrieval still fails:
   - determine whether the failure is due to stale client behavior, blocked timedtext variants, or missing installed tooling
   - prefer an official embedded-caption fetch path before any broader fallback
6. Re-run:
   - `python3 -m unittest discover -s tests`
   - `python3 -m mentions_engine.cli backfill-whitehouse-briefing-videos --start-date 2025-01-20`

Relevant files:

- `mentions_engine/discovery/whitehouse.py`
- `mentions_engine/acquisition/whitehouse.py`
- `mentions_engine/cli.py`
- `mentions_engine/http.py`
- `tests/test_whitehouse_discovery.py`
- `tests/test_whitehouse_acquisition.py`
