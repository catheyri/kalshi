# Mentions Engine

This directory contains the mentions-market prediction tool as a self-contained project:

- `mentions_engine/`: the Python package
- `mentionsengine.md`: the main product and architecture spec, now framed around predicting future Kalshi mention-market outcomes
- `briefings_mvp_plan.md`: the White House briefings MVP plan
- `tests/`: unit tests
- `examples/`: sample rule payloads
- `data/`: local SQLite/database artifacts and fetched source material

Data layout:

- `data/raw/`: original fetched artifacts and source files
- `data/canonical/`: durable normalized transcripts and dataset-ready canonical objects
- `data/derived/`: rebuildable features, estimates, and exported datasets

Typical workflow:

```bash
cd mentions
python3 -m mentions_engine.cli init-db
python3 -m mentions_engine.cli sync-events whitehouse
```

Prediction-oriented workflow:

```bash
cd mentions
python3 -m mentions_engine.cli ingest-markets path/to/markets.json
python3 -m mentions_engine.cli ingest-kalshi-market-tickers <ticker> [ticker...]
python3 -m mentions_engine.cli ingest-kalshi-event-tickers <event_ticker> [event_ticker...]
python3 -m mentions_engine.cli ingest-kalshi-category Government 2
python3 -m mentions_engine.cli ingest-whitehouse-mention-market-tickers <ticker> [ticker...]
python3 -m mentions_engine.cli ingest-whitehouse-mention-event-tickers <event_ticker> [event_ticker...]
python3 -m mentions_engine.cli ingest-whitehouse-mention-historical-events
python3 -m mentions_engine.cli ingest-whitehouse-mention-category Government 2
python3 -m mentions_engine.cli ingest-whitehouse-mention-historical-events --speaker-key karoline_leavitt --event-profile white_house_press_briefing
python3 -m mentions_engine.cli import-outcomes path/to/outcomes.json
python3 -m mentions_engine.cli import-kalshi-outcomes <ticker> [ticker...]
python3 -m mentions_engine.cli map-market <market_id>
python3 -m mentions_engine.cli estimate-market <market_id>
python3 -m mentions_engine.cli list-markets open
python3 -m mentions_engine.cli list-whitehouse-mention-markets
python3 -m mentions_engine.cli list-whitehouse-mention-markets --view events
python3 -m mentions_engine.cli backfill-whitehouse-official-transcripts --start-date 2025-01-20
python3 -m mentions_engine.cli backfill-whitehouse-briefing-videos --start-date 2025-01-20
python3 -m mentions_engine.cli backfill-whitehouse-briefing-videos --speaker-key karoline_leavitt --event-profile white_house_press_briefing --start-date 2025-01-20
python3 -m mentions_engine.cli list-whitehouse-mention-markets --insecure-ssl
python3 -m mentions_engine.cli list-whitehouse-mention-markets --speaker-key karoline_leavitt --history-limit 10 --lookback-days 365
python3 -m mentions_engine.cli export-dataset data/derived/datasets/open.jsonl open
python3 -m mentions_engine.cli build-word-frequencies --speaker-key karoline_leavitt
```

Speaker and event assumptions are centralized in `mentions_engine/profiles.py`. To add another recurring speaker, add a `SpeakerProfile` with aliases, transcript labels, caption markers, discovery slug terms, speaker stopwords, and any Kalshi series tickers. The White House discovery, market parsing, transcript parsing, and word-frequency build all consume the same profile instead of hardcoding Leavitt-specific rules.

For the White House vertical, prefer the `ingest-whitehouse-mention-*` commands. They filter to briefing mention markets and enrich stored `Market` records with parsed metadata like `speaker_name`, `speaker_key`, `target_phrase`, and `event_family`. These commands accept `--speaker-key` and `--event-profile` when you want to parse markets for a different configured profile pair.

`ingest-whitehouse-mention-historical-events` backfills child markets from Kalshi's historical market endpoint. With no positional event tickers, it targets locally stored White House mention parent events that do not yet have any child markets; pass explicit event tickers to probe a smaller set, or `--all-local-events` to refresh every local parent event.

`list-whitehouse-mention-markets` performs a bounded live Kalshi scan, stores any matching White House mention markets in the local DB, and prints separate tables for recent historical markets and live/upcoming markets. Pass `--view events` to collapse matching child markets into parent briefing events. Use `--insecure-ssl` only on machines with broken local certificate chains.

`backfill-whitehouse-official-transcripts` discovers official White House press-briefing transcript pages from the White House sitemap, stores the matching events and transcript artifacts, fetches the raw HTML, and builds normalized transcripts into the local database. Pass `--speaker-key` and `--event-profile` to use a non-default configured profile pair.

`backfill-whitehouse-briefing-videos` discovers official White House briefing video pages from the White House `past_event` sitemaps, stores the matching events and official video-page artifacts, fetches the raw HTML, and builds transcripts when the page exposes a directly linked official transcript page or retrievable embedded caption tracks. Pass `--speaker-key` and `--event-profile` to use a non-default configured profile pair.

`build-word-frequencies` creates a post-processed per-event word-frequency table in SQLite, exports `data/derived/features/word_frequencies.json`, and writes self-contained browser explorers to `data/derived/features/word_frequency_explorer.html` and `data/derived/features/event_word_frequency_explorer.html`. By default it counts the selected speaker profile's primary transcript labels and marks terms that had a same-day Kalshi mention market plus the stored market result when available. Use `--speaker-key` and `--event-profile` to select a different configured profile pair.

Project config lives in [`pyproject.toml`](pyproject.toml).
