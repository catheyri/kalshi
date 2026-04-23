# White House Caption Handoff

Last synced code state before the next follow-up pass:

- Git commit: `259af72` (`Add White House caption handoff note`)
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

Verified live results before the embedded-caption implementation:

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

Embedded-caption implementation status:

- The official White House video-page backfill now uses:
  - official White House page HTML for the embedded YouTube video ID
  - YouTube watch page for `INNERTUBE_API_KEY`
  - Android `youtubei/v1/player` for caption tracks without the web `exp=xpe` failure mode
  - timedtext `fmt=srv3` XML as the stored caption artifact
- The transcript parser now handles both legacy `<text ...>` captions and current timedtext format 3 XML with `<p>` / `<s>` nodes.

Verified live results after the embedded-caption implementation:

- `backfill-whitehouse-briefing-videos --start-date 2025-01-20`
  - `discovered_events=64`
  - `discovered_artifacts=64`
  - `fetched_artifacts=105`
  - `events_with_text=41`
  - `transcripts_built=41`
  - `official_transcripts_built=0`
  - `caption_transcripts_built=41`
- Clean-run artifact inventory:
  - `video_replay=191`
  - `closed_captions=41`
  - `official_transcript=3`
- Clean-run transcript inventory:
  - `captions=41`
  - `official=3`

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

- 23 of the 64 discovered video events still do not yield caption artifacts.
- At least some later 2025 / 2026 briefings appear to have no retrievable timedtext via the current embedded YouTube path.

Next steps:

1. Audit the 23 missing-caption events and determine whether they fail because:
   - no caption tracks exist
   - only PO-token-gated tracks exist
   - the embedded video differs from the standard path
2. Store more caption-track metadata on `closed_captions` artifacts if that will help downstream auditing.
3. Consider whether `closed_captions` artifacts sourced from the official White House embedded player should be marked `is_official=True`.
4. If needed, add one more fallback for official briefing videos that expose captions through a different official player surface, but do not reintroduce loose White House transcript search.
5. Re-run:
   - `python3 -m unittest discover -s tests`
   - `python3 -m mentions_engine.cli backfill-whitehouse-briefing-videos --start-date 2025-01-20`

Relevant files:

- `mentions_engine/discovery/whitehouse.py`
- `mentions_engine/acquisition/whitehouse.py`
- `mentions_engine/cli.py`
- `mentions_engine/http.py`
- `tests/test_whitehouse_discovery.py`
- `tests/test_whitehouse_acquisition.py`
