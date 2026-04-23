from __future__ import annotations

import json
import sys
from pathlib import Path

from mentions_engine.config import default_paths
from mentions_engine.engine import Engine
from mentions_engine.kalshi import KalshiPublicClient
from mentions_engine.market_analysis import WhiteHouseMentionMarketParser
from mentions_engine.market_ingest import JsonFileMarketIngestor
from mentions_engine.market_ingest import (
    KalshiCategoryMarketIngestor,
    KalshiEventTickerIngestor,
    KalshiMarketTickerIngestor,
)
from mentions_engine.outcomes import JsonFileOutcomeImporter, KalshiMarketOutcomeImporter
from mentions_engine.registry import (
    acquisition_adapters,
    discovery_adapters,
    event_mappers,
    feature_extractor,
    opportunity_scorer,
    pricing_model,
    transcript_builders,
)
from mentions_engine.rules import compile_bundle_from_json
from mentions_engine.storage import Database
from mentions_engine.utils import dump_json


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "Usage: python3 -m mentions_engine.cli <command> [args]\n"
            "Commands: init-db, ingest-markets, ingest-kalshi-market-tickers, ingest-kalshi-event-tickers, "
            "ingest-kalshi-category, ingest-whitehouse-mention-market-tickers, "
            "ingest-whitehouse-mention-event-tickers, ingest-whitehouse-mention-category, map-market, "
            "record-outcome, import-outcomes, import-kalshi-outcomes, estimate-market, list-markets, export-dataset, sync-events, fetch-sources, build-transcript, "
            "compile-rule, run-rule",
            file=sys.stderr,
        )
        return 1

    command = argv.pop(0)
    paths = default_paths()
    paths.ensure()
    db = Database(paths.db_path)
    engine = Engine(
        paths=paths,
        db=db,
        discovery_adapters=discovery_adapters(),
        acquisition_adapters=acquisition_adapters(paths),
        transcript_builders=transcript_builders(),
        event_mappers=event_mappers(),
        feature_extractor=feature_extractor(db),
        pricing_model=pricing_model(),
        opportunity_scorer=opportunity_scorer(),
    )

    if command == "init-db":
        db.initialize()
        print(paths.db_path)
        return 0

    if command == "ingest-markets":
        db.initialize()
        if not argv:
            print("ingest-markets requires <markets_json_path>", file=sys.stderr)
            return 1
        ingestor = JsonFileMarketIngestor(Path(argv[0]))
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-kalshi-market-tickers":
        db.initialize()
        if not argv:
            print("ingest-kalshi-market-tickers requires <ticker> [ticker...]", file=sys.stderr)
            return 1
        ingestor = KalshiMarketTickerIngestor(argv, KalshiPublicClient())
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-kalshi-event-tickers":
        db.initialize()
        if not argv:
            print("ingest-kalshi-event-tickers requires <event_ticker> [event_ticker...]", file=sys.stderr)
            return 1
        ingestor = KalshiEventTickerIngestor(argv, KalshiPublicClient())
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-kalshi-category":
        db.initialize()
        if not argv:
            print("ingest-kalshi-category requires <category> [max_pages]", file=sys.stderr)
            return 1
        category = argv[0]
        max_pages = int(argv[1]) if len(argv) > 1 else 1
        ingestor = KalshiCategoryMarketIngestor(category, KalshiPublicClient(), max_pages=max_pages)
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-whitehouse-mention-market-tickers":
        db.initialize()
        if not argv:
            print("ingest-whitehouse-mention-market-tickers requires <ticker> [ticker...]", file=sys.stderr)
            return 1
        ingestor = KalshiMarketTickerIngestor(
            argv,
            KalshiPublicClient(),
            parser=WhiteHouseMentionMarketParser(),
        )
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-whitehouse-mention-event-tickers":
        db.initialize()
        if not argv:
            print("ingest-whitehouse-mention-event-tickers requires <event_ticker> [event_ticker...]", file=sys.stderr)
            return 1
        ingestor = KalshiEventTickerIngestor(
            argv,
            KalshiPublicClient(),
            parser=WhiteHouseMentionMarketParser(),
        )
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-whitehouse-mention-category":
        db.initialize()
        category = argv[0] if argv else "Government"
        max_pages = int(argv[1]) if len(argv) > 1 else 1
        ingestor = KalshiCategoryMarketIngestor(
            category,
            KalshiPublicClient(),
            max_pages=max_pages,
            parser=WhiteHouseMentionMarketParser(),
        )
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "map-market":
        db.initialize()
        if not argv:
            print("map-market requires <market_id>", file=sys.stderr)
            return 1
        print(json.dumps(engine.map_market(argv[0]), indent=2))
        return 0

    if command == "record-outcome":
        db.initialize()
        if len(argv) < 2:
            print("record-outcome requires <market_id> <yes|no>", file=sys.stderr)
            return 1
        market_id, outcome_text = argv[:2]
        if outcome_text not in {"yes", "no"}:
            print("record-outcome outcome must be 'yes' or 'no'", file=sys.stderr)
            return 1
        outcome = engine.record_market_outcome(market_id, resolved_yes=outcome_text == "yes")
        print(json.dumps(outcome.to_dict(), indent=2))
        return 0

    if command == "import-outcomes":
        db.initialize()
        if not argv:
            print("import-outcomes requires <outcomes_json_path>", file=sys.stderr)
            return 1
        importer = JsonFileOutcomeImporter(Path(argv[0]))
        print(json.dumps(engine.import_outcomes(importer), indent=2))
        return 0

    if command == "import-kalshi-outcomes":
        db.initialize()
        if not argv:
            print("import-kalshi-outcomes requires <ticker> [ticker...]", file=sys.stderr)
            return 1
        importer = KalshiMarketOutcomeImporter(argv, KalshiPublicClient())
        print(json.dumps(engine.import_outcomes(importer), indent=2))
        return 0

    if command == "estimate-market":
        db.initialize()
        if not argv:
            print("estimate-market requires <market_id>", file=sys.stderr)
            return 1
        print(json.dumps(engine.estimate_market(argv[0]), indent=2))
        return 0

    if command == "list-markets":
        db.initialize()
        status = argv[0] if argv else None
        print(json.dumps(engine.list_markets_with_latest_estimates(status=status), indent=2))
        return 0

    if command == "export-dataset":
        db.initialize()
        output_path = None if not argv else Path(argv[0])
        status = argv[1] if len(argv) > 1 else None
        print(json.dumps(engine.export_market_dataset(output_path, status=status), indent=2))
        return 0

    if command in {"sync-events", "sync-whitehouse"}:
        db.initialize()
        adapter_name = argv[0] if argv else ("whitehouse" if command == "sync-whitehouse" else None)
        if not adapter_name:
            print("sync-events requires <adapter_name>", file=sys.stderr)
            return 1
        print(json.dumps(engine.sync_events(adapter_name), indent=2))
        return 0

    if command in {"fetch-sources", "fetch-whitehouse-sources"}:
        db.initialize()
        if not argv:
            print(f"{command} requires <event_id>", file=sys.stderr)
            return 1
        event_id = argv.pop(0)
        print(json.dumps(engine.fetch_sources(event_id), indent=2))
        return 0

    if command == "build-transcript":
        db.initialize()
        if not argv:
            print("build-transcript requires <artifact_id>", file=sys.stderr)
            return 1
        artifact_id = argv.pop(0)
        print(json.dumps(engine.build_transcript(artifact_id), indent=2))
        return 0

    if command == "compile-rule":
        db.initialize()
        if len(argv) < 2:
            print("compile-rule requires <rule_json_path> <output_path>", file=sys.stderr)
            return 1
        rule_path = Path(argv[0])
        output_path = Path(argv[1])
        payload = json.loads(rule_path.read_text(encoding="utf-8"))
        rule, market = compile_bundle_from_json(payload)
        engine.compile_rule(rule, market)
        output_payload = {"compiled_rule": rule.to_dict()}
        if market is not None:
            output_payload["market"] = market.to_dict()
        dump_json(output_path, output_payload)
        print(output_path)
        return 0

    if command == "run-rule":
        db.initialize()
        if len(argv) < 4:
            print("run-rule requires <event_id> <artifact_id> <transcript_id> <rule_json_path>", file=sys.stderr)
            return 1
        event_id, artifact_id, transcript_id, rule_path = argv[:4]
        rule_payload = json.loads(Path(rule_path).read_text(encoding="utf-8"))
        rule, market = compile_bundle_from_json(rule_payload)
        engine.compile_rule(rule, market)
        print(
            json.dumps(
                engine.run_rule(
                    event_id=event_id,
                    artifact_id=artifact_id,
                    transcript_id=transcript_id,
                    rule=rule,
                    persist=True,
                ),
                indent=2,
            )
        )
        return 0

    print(f"Unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
