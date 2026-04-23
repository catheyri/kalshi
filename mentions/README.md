# Mentions Engine

This directory contains the mentions-market tool as a self-contained project:

- `mentions_engine/`: the Python package
- `mentionsengine.md`: the main product and architecture spec
- `briefings_mvp_plan.md`: the White House briefings MVP plan
- `tests/`: unit tests
- `examples/`: sample rule payloads
- `data/`: local SQLite/database artifacts and fetched source material

Typical workflow:

```bash
cd mentions
python3 -m mentions_engine.cli init-db
python3 -m mentions_engine.cli sync-whitehouse
```

Project config lives in [`pyproject.toml`](pyproject.toml).
