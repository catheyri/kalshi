from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from mentions_engine.analysis import build_word_frequency_dataset
from mentions_engine.discovery.whitehouse import WhiteHouseDiscovery
from mentions_engine.config import default_paths
from mentions_engine.engine import Engine
from mentions_engine.http import HttpClient
from mentions_engine.kalshi import KalshiPublicClient
from mentions_engine.market_analysis import WhiteHouseMentionMarketParser
from mentions_engine.market_ingest import JsonFileMarketIngestor
from mentions_engine.market_ingest import (
    KalshiCategoryMarketIngestor,
    KalshiEventTickerIngestor,
    KalshiMarketTickerIngestor,
)
from mentions_engine.models import Event
from mentions_engine.outcomes import JsonFileOutcomeImporter, KalshiMarketOutcomeImporter
from mentions_engine.profiles import get_event_source_profile, get_speaker_profile
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
from mentions_engine.whitehouse_markets import (
    WhiteHouseMentionMarketReporter,
    render_whitehouse_mention_event_report,
    render_whitehouse_mention_market_report,
)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "Usage: python3 -m mentions_engine.cli <command> [args]\n"
            "Commands: init-db, ingest-markets, ingest-kalshi-market-tickers, ingest-kalshi-event-tickers, "
            "ingest-kalshi-category, ingest-whitehouse-mention-market-tickers, "
            "ingest-whitehouse-mention-event-tickers, ingest-whitehouse-mention-category, map-market, "
            "record-outcome, import-outcomes, import-kalshi-outcomes, estimate-market, list-markets, "
            "list-whitehouse-mention-markets, backfill-whitehouse-official-transcripts, export-dataset, "
            "backfill-whitehouse-briefing-videos, sync-events, fetch-sources, build-transcript, "
            "compile-rule, run-rule, build-word-frequencies, ingest-whitehouse-mention-historical-events",
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
        parser = _build_ingest_whitehouse_mention_market_tickers_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)
        ingestor = KalshiMarketTickerIngestor(
            args.tickers,
            KalshiPublicClient(),
            parser=_whitehouse_mention_market_parser_for_args(args),
        )
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-whitehouse-mention-event-tickers":
        db.initialize()
        parser = _build_ingest_whitehouse_mention_event_tickers_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)
        ingestor = KalshiEventTickerIngestor(
            args.event_tickers,
            KalshiPublicClient(),
            parser=_whitehouse_mention_market_parser_for_args(args),
        )
        print(json.dumps(engine.ingest_markets(ingestor), indent=2))
        return 0

    if command == "ingest-whitehouse-mention-historical-events":
        db.initialize()
        parser = _build_ingest_whitehouse_mention_historical_events_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)

        event_tickers = list(args.event_tickers)
        if not event_tickers:
            event_tickers = _local_whitehouse_mention_event_tickers(
                db,
                missing_only=not args.all_local_events,
                limit=args.limit,
            )
        if not event_tickers:
            print(
                json.dumps(
                    {
                        "ingestor": "kalshi-historical-whitehouse-mention-events",
                        "event_tickers": 0,
                        "markets": 0,
                        "updated_events": 0,
                    },
                    indent=2,
                )
            )
            return 0

        ingestor = KalshiEventTickerIngestor(
            event_tickers,
            KalshiPublicClient(client=HttpClient(allow_insecure_ssl=args.insecure_ssl)),
            open_only=False,
            parser=_whitehouse_mention_market_parser_for_args(args),
            include_historical=True,
            historical_only=not args.live_too,
            historical_pages_per_event=args.historical_pages_per_event,
        )
        result = engine.ingest_markets(ingestor)
        updated_events = _refresh_kalshi_whitehouse_mention_event_counts(db, event_tickers)
        payload = {
            "ingestor": "kalshi-historical-whitehouse-mention-events",
            "event_tickers": len(event_tickers),
            "markets": result["markets"],
            "updated_events": updated_events,
            "speaker_key": args.speaker_key,
            "event_profile": args.event_profile,
            "historical_pages_per_event": args.historical_pages_per_event,
            "event_ticker_sample": event_tickers[:10],
        }
        print(json.dumps(payload, indent=2))
        return 0

    if command == "ingest-whitehouse-mention-category":
        db.initialize()
        parser = _build_ingest_whitehouse_mention_category_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)
        ingestor = KalshiCategoryMarketIngestor(
            args.category,
            KalshiPublicClient(),
            max_pages=args.max_pages,
            parser=_whitehouse_mention_market_parser_for_args(args),
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

    if command == "list-whitehouse-mention-markets":
        db.initialize()
        parser = _build_list_whitehouse_mention_markets_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)
        try:
            report = WhiteHouseMentionMarketReporter(
                KalshiPublicClient(client=HttpClient(allow_insecure_ssl=args.insecure_ssl)),
                db=db,
            ).build_report(
                speaker_key=args.speaker_key,
                history_limit=args.history_limit,
                lookback_days=args.lookback_days,
                window_days=args.window_days,
                historical_pages_per_window=args.historical_pages_per_window,
                open_pages=args.open_pages,
            )
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(
                json.dumps(
                    {
                        "view": args.view,
                        "speaker_key": report.speaker_key,
                        "speaker_name": report.speaker_name,
                        "historical_markets": [market.to_dict() for market in report.historical_markets],
                        "live_markets": [market.to_dict() for market in report.live_markets],
                        "historical_events": [
                            {
                                "event_ticker": event.event_ticker,
                                "series_ticker": event.series_ticker,
                                "title": event.title,
                                "subtitle": event.subtitle,
                                "category": event.category,
                                "latest_close_time": event.latest_close_time,
                                "market_count": event.market_count,
                                "status_counts": event.status_counts,
                            }
                            for event in report.historical_events
                        ],
                        "live_events": [
                            {
                                "event_ticker": event.event_ticker,
                                "series_ticker": event.series_ticker,
                                "title": event.title,
                                "subtitle": event.subtitle,
                                "category": event.category,
                                "latest_close_time": event.latest_close_time,
                                "market_count": event.market_count,
                                "status_counts": event.status_counts,
                            }
                            for event in report.live_events
                        ],
                        "lookback_days": report.lookback_days,
                        "window_days": report.window_days,
                        "historical_pages_per_window": report.historical_pages_per_window,
                        "open_pages": report.open_pages,
                        "scanned_historical_windows": report.scanned_historical_windows,
                        "scanned_historical_pages": report.scanned_historical_pages,
                        "scanned_live_pages": report.scanned_live_pages,
                    },
                    indent=2,
                )
            )
        else:
            if args.view == "events":
                print(render_whitehouse_mention_event_report(report))
            else:
                print(render_whitehouse_mention_market_report(report))
        return 0

    if command == "backfill-whitehouse-official-transcripts":
        db.initialize()
        parser = _build_backfill_whitehouse_official_transcripts_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)

        client = HttpClient(allow_insecure_ssl=args.insecure_ssl)
        discovery = WhiteHouseDiscovery(
            client=client,
            speaker_profile=get_speaker_profile(args.speaker_key),
            event_profile=get_event_source_profile(args.event_profile),
        )
        result = discovery.discover_official_transcript_events(start_date=args.start_date)
        events = result.events[: args.limit] if args.limit is not None else result.events
        artifacts = result.artifacts[: len(events)]

        discovered_event_ids = []
        for event in events:
            db.upsert_event(event)
            discovered_event_ids.append(event.event_id)
        for artifact in artifacts:
            db.upsert_source_artifact(artifact)

        fetched_artifacts = 0
        transcripts_built = 0
        events_with_transcripts = 0

        for event_id in discovered_event_ids:
            fetch_result = engine.fetch_sources(event_id)
            fetched_artifacts += int(fetch_result["artifacts"])
            built_for_event = 0
            for row in db.list_artifacts_for_event(event_id):
                if row["artifact_type"] != "official_transcript" or not row["local_path"]:
                    continue
                engine.build_transcript(row["artifact_id"])
                transcripts_built += 1
                built_for_event += 1
            if built_for_event:
                events_with_transcripts += 1

        payload = {
            "start_date": args.start_date,
            "speaker_key": args.speaker_key,
            "event_profile": args.event_profile,
            "discovered_events": len(discovered_event_ids),
            "discovered_artifacts": len(artifacts),
            "fetched_artifacts": fetched_artifacts,
            "events_with_transcripts": events_with_transcripts,
            "transcripts_built": transcripts_built,
            "event_ids": discovered_event_ids,
        }
        print(json.dumps(payload, indent=2))
        return 0

    if command == "backfill-whitehouse-briefing-videos":
        db.initialize()
        parser = _build_backfill_whitehouse_briefing_videos_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)

        client = HttpClient(allow_insecure_ssl=args.insecure_ssl)
        discovery = WhiteHouseDiscovery(
            client=client,
            speaker_profile=get_speaker_profile(args.speaker_key),
            event_profile=get_event_source_profile(args.event_profile),
        )
        result = discovery.discover_official_briefing_video_events(start_date=args.start_date)
        events = result.events[: args.limit] if args.limit is not None else result.events
        artifacts = result.artifacts[: len(events)]

        discovered_event_ids = []
        for event in events:
            db.upsert_event(event)
            discovered_event_ids.append(event.event_id)
        for artifact in artifacts:
            db.upsert_source_artifact(artifact)

        fetched_artifacts = 0
        transcripts_built = 0
        official_transcripts_built = 0
        caption_transcripts_built = 0
        events_with_text = 0

        for event_id in discovered_event_ids:
            fetch_result = engine.fetch_sources(event_id)
            fetched_artifacts += int(fetch_result["artifacts"])
            built_for_event = 0
            for row in db.list_artifacts_for_event(event_id):
                if row["artifact_type"] not in {"official_transcript", "closed_captions"} or not row["local_path"]:
                    continue
                engine.build_transcript(row["artifact_id"])
                transcripts_built += 1
                built_for_event += 1
                if row["artifact_type"] == "official_transcript":
                    official_transcripts_built += 1
                elif row["artifact_type"] == "closed_captions":
                    caption_transcripts_built += 1
            if built_for_event:
                events_with_text += 1

        payload = {
            "start_date": args.start_date,
            "speaker_key": args.speaker_key,
            "event_profile": args.event_profile,
            "discovered_events": len(discovered_event_ids),
            "discovered_artifacts": len(artifacts),
            "fetched_artifacts": fetched_artifacts,
            "events_with_text": events_with_text,
            "transcripts_built": transcripts_built,
            "official_transcripts_built": official_transcripts_built,
            "caption_transcripts_built": caption_transcripts_built,
            "event_ids": discovered_event_ids,
        }
        print(json.dumps(payload, indent=2))
        return 0

    if command == "export-dataset":
        db.initialize()
        output_path = None if not argv else Path(argv[0])
        status = argv[1] if len(argv) > 1 else None
        print(json.dumps(engine.export_market_dataset(output_path, status=status), indent=2))
        return 0

    if command == "build-word-frequencies":
        db.initialize()
        parser = _build_word_frequencies_parser()
        try:
            args = parser.parse_args(argv)
        except SystemExit as exc:
            return int(exc.code)
        json_path = Path(args.json_out) if args.json_out else paths.derived_dir / "features" / "word_frequencies.json"
        html_path = Path(args.html_out) if args.html_out else paths.derived_dir / "features" / "word_frequency_explorer.html"
        event_html_path = (
            Path(args.event_html_out)
            if args.event_html_out
            else paths.derived_dir / "features" / "event_word_frequency_explorer.html"
        )
        result = build_word_frequency_dataset(
            db,
            json_path=json_path,
            html_path=html_path,
            event_html_path=event_html_path,
            speaker_scope=args.speaker_scope,
            speaker_key=args.speaker_key,
            event_profile_key=args.event_profile,
            min_count=args.min_count,
        )
        print(json.dumps(result.__dict__, indent=2))
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


def _build_list_whitehouse_mention_markets_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli list-whitehouse-mention-markets",
        description="List historical and live White House mention markets for a speaker.",
    )
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--view", choices=("markets", "events"), default="markets")
    parser.add_argument("--history-limit", type=int, default=10)
    parser.add_argument("--lookback-days", type=int, default=365)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--historical-pages-per-window", type=int, default=1)
    parser.add_argument("--open-pages", type=int, default=5)
    parser.add_argument("--insecure-ssl", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def _whitehouse_mention_market_parser_for_args(args: argparse.Namespace) -> WhiteHouseMentionMarketParser:
    return WhiteHouseMentionMarketParser(
        speaker_rules=(get_speaker_profile(args.speaker_key),),
        event_profile=get_event_source_profile(args.event_profile),
    )


def _build_ingest_whitehouse_mention_market_tickers_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli ingest-whitehouse-mention-market-tickers",
        description="Ingest specific Kalshi White House mention market tickers.",
    )
    parser.add_argument("tickers", nargs="+")
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--event-profile", default="white_house_press_briefing")
    return parser


def _build_ingest_whitehouse_mention_event_tickers_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli ingest-whitehouse-mention-event-tickers",
        description="Ingest Kalshi White House mention markets from parent event tickers.",
    )
    parser.add_argument("event_tickers", nargs="+")
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--event-profile", default="white_house_press_briefing")
    return parser


def _build_ingest_whitehouse_mention_historical_events_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli ingest-whitehouse-mention-historical-events",
        description="Backfill White House mention child markets from Kalshi's historical market endpoint.",
    )
    parser.add_argument("event_tickers", nargs="*")
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--event-profile", default="white_house_press_briefing")
    parser.add_argument(
        "--all-local-events",
        action="store_true",
        help="Scan every locally stored Kalshi White House mention parent event instead of only events with no stored child markets.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--historical-pages-per-event",
        type=int,
        help="Maximum historical market pages to request per event ticker.",
    )
    parser.add_argument(
        "--live-too",
        action="store_true",
        help="Also read nested markets from the live event endpoint before querying historical markets.",
    )
    parser.add_argument("--insecure-ssl", action="store_true")
    return parser


def _build_ingest_whitehouse_mention_category_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli ingest-whitehouse-mention-category",
        description="Ingest Kalshi White House mention markets from a category scan.",
    )
    parser.add_argument("category", nargs="?", default="Government")
    parser.add_argument("max_pages", nargs="?", type=int, default=1)
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--event-profile", default="white_house_press_briefing")
    return parser


def _local_whitehouse_mention_event_tickers(
    db: Database,
    *,
    missing_only: bool,
    limit: int | None,
) -> list[str]:
    sql = """
        SELECT e.event_id, COUNT(m.market_id) AS stored_markets
        FROM events e
        LEFT JOIN markets m ON m.event_id = e.event_id
        WHERE e.event_type = 'kalshi_whitehouse_mention_event'
        GROUP BY e.event_id
    """
    params: list[object] = []
    if missing_only:
        sql += " HAVING COUNT(m.market_id) = 0"
    sql += """
        ORDER BY COALESCE(
            e.scheduled_end_time,
            json_extract(e.metadata_json, '$.latest_close_time'),
            e.scheduled_start_time,
            ''
        ) DESC, e.event_id DESC
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with db.connect() as conn:
        return [row["event_id"] for row in conn.execute(sql, tuple(params)).fetchall()]


def _refresh_kalshi_whitehouse_mention_event_counts(db: Database, event_tickers: list[str]) -> int:
    updated = 0
    for event_ticker in event_tickers:
        event_row = db.get_event(event_ticker)
        if event_row is None:
            continue
        with db.connect() as conn:
            market_rows = conn.execute(
                """
                SELECT status, close_time
                FROM markets
                WHERE event_id = ?
                """,
                (event_ticker,),
            ).fetchall()
        if not market_rows:
            continue

        status_counts: dict[str, int] = {}
        latest_close_time = None
        for row in market_rows:
            status = (row["status"] or "unknown").lower()
            status_counts[status] = status_counts.get(status, 0) + 1
            close_time = row["close_time"]
            if close_time and (latest_close_time is None or close_time > latest_close_time):
                latest_close_time = close_time

        metadata = json.loads(event_row["metadata_json"])
        metadata["market_count"] = len(market_rows)
        metadata["status_counts"] = status_counts
        if latest_close_time is not None:
            metadata["latest_close_time"] = latest_close_time

        db.upsert_event(
            Event(
                event_id=event_row["event_id"],
                event_type=event_row["event_type"],
                title=event_row["title"],
                category=event_row["category"],
                subcategory=event_row["subcategory"],
                scheduled_start_time=event_row["scheduled_start_time"],
                scheduled_end_time=latest_close_time or event_row["scheduled_end_time"],
                actual_start_time=event_row["actual_start_time"],
                actual_end_time=(
                    latest_close_time
                    if latest_close_time is not None and _all_closed_statuses(status_counts)
                    else event_row["actual_end_time"]
                ),
                participants=event_row["participants"],
                broadcast_network=event_row["broadcast_network"],
                league=event_row["league"],
                season=event_row["season"],
                venue=event_row["venue"],
                source_priority=event_row["source_priority"],
                broadcast_priority=event_row["broadcast_priority"],
                metadata=metadata,
            )
        )
        updated += 1
    return updated


def _all_closed_statuses(status_counts: dict[str, int]) -> bool:
    return bool(status_counts) and all(
        status in {"closed", "settled", "finalized"} for status in status_counts
    )


def _build_backfill_whitehouse_official_transcripts_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli backfill-whitehouse-official-transcripts",
        description="Backfill official White House press briefing transcripts from whitehouse.gov.",
    )
    parser.add_argument("--start-date", default="2025-01-20")
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--event-profile", default="white_house_press_briefing")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--insecure-ssl", action="store_true")
    return parser


def _build_backfill_whitehouse_briefing_videos_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli backfill-whitehouse-briefing-videos",
        description="Backfill official White House briefing video pages and any obtainable transcript text.",
    )
    parser.add_argument("--start-date", default="2025-01-20")
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--event-profile", default="white_house_press_briefing")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--insecure-ssl", action="store_true")
    return parser


def _build_word_frequencies_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mentions_engine.cli build-word-frequencies",
        description="Build per-event word-frequency features and a browser explorer.",
    )
    parser.add_argument("--speaker-scope", choices=("primary", "all"), default="primary")
    parser.add_argument("--speaker-key", default="karoline_leavitt")
    parser.add_argument("--event-profile", default="white_house_press_briefing")
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--json-out")
    parser.add_argument("--html-out")
    parser.add_argument("--event-html-out")
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
