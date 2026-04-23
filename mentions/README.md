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
python3 -m mentions_engine.cli ingest-whitehouse-mention-category Government 2
python3 -m mentions_engine.cli import-outcomes path/to/outcomes.json
python3 -m mentions_engine.cli import-kalshi-outcomes <ticker> [ticker...]
python3 -m mentions_engine.cli map-market <market_id>
python3 -m mentions_engine.cli estimate-market <market_id>
python3 -m mentions_engine.cli list-markets open
python3 -m mentions_engine.cli list-whitehouse-mention-markets
python3 -m mentions_engine.cli list-whitehouse-mention-markets --view events
python3 -m mentions_engine.cli list-whitehouse-mention-markets --insecure-ssl
python3 -m mentions_engine.cli list-whitehouse-mention-markets --speaker-key karoline_leavitt --history-limit 10 --lookback-days 365
python3 -m mentions_engine.cli export-dataset data/derived/datasets/open.jsonl open
```

For the White House vertical, prefer the `ingest-whitehouse-mention-*` commands. They filter to briefing mention markets and enrich stored `Market` records with parsed metadata like `speaker_name`, `speaker_key`, `target_phrase`, and `event_family`.

`list-whitehouse-mention-markets` performs a bounded live Kalshi scan, stores any matching White House mention markets in the local DB, and prints separate tables for recent historical markets and live/upcoming markets. Pass `--view events` to collapse matching child markets into parent briefing events. Use `--insecure-ssl` only on machines with broken local certificate chains.

Project config lives in [`pyproject.toml`](pyproject.toml).
