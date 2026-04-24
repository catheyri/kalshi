from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Sequence

from mentions_engine.kalshi import KalshiPublicClient, normalize_market_payload
from mentions_engine.market_analysis import WhiteHouseMentionMarketParser
from mentions_engine.models import Event, Market
from mentions_engine.storage import Database


@dataclass
class WhiteHouseMentionMarketReport:
    speaker_key: str
    speaker_name: str
    historical_markets: List[Market]
    live_markets: List[Market]
    historical_events: List["WhiteHouseMentionEventSummary"]
    live_events: List["WhiteHouseMentionEventSummary"]
    lookback_days: int
    window_days: int
    historical_pages_per_window: int
    open_pages: int
    scanned_historical_windows: int
    scanned_historical_pages: int
    scanned_live_pages: int


@dataclass
class WhiteHouseMentionEventSummary:
    event_ticker: str
    series_ticker: Optional[str]
    title: str
    subtitle: Optional[str]
    category: Optional[str]
    latest_close_time: Optional[str]
    market_count: int
    status_counts: Dict[str, int]


class WhiteHouseMentionMarketReporter:
    _SPEAKER_SERIES_TICKERS: Dict[str, tuple[str, ...]] = {
        "karoline_leavitt": ("KXSECPRESSMENTION",),
    }

    def __init__(
        self,
        client: KalshiPublicClient,
        *,
        parser: Optional[WhiteHouseMentionMarketParser] = None,
        db: Optional[Database] = None,
    ):
        self.client = client
        self.parser = parser or WhiteHouseMentionMarketParser()
        self.db = db

    def build_report(
        self,
        *,
        speaker_key: str = "karoline_leavitt",
        history_limit: int = 10,
        lookback_days: int = 365,
        window_days: int = 30,
        historical_pages_per_window: int = 1,
        open_pages: int = 5,
        now: Optional[datetime] = None,
    ) -> WhiteHouseMentionMarketReport:
        now = now or datetime.now(timezone.utc)
        historical_all: list[Market] = []
        live_all: list[Market] = []
        historical_events: list[WhiteHouseMentionEventSummary] = []
        live_events: list[WhiteHouseMentionEventSummary] = []
        scanned_historical_windows = 0
        scanned_historical_pages = 0
        scanned_live_pages = 0

        targeted_event_payloads, scanned_event_pages = self._discover_series_events_for_speaker(
            speaker_key
        )
        targeted_markets, scanned_market_pages = self._discover_series_markets_for_speaker(
            speaker_key,
            event_payloads=targeted_event_payloads,
        )
        if targeted_event_payloads or targeted_markets:
            all_event_summaries = _summarize_event_payloads(targeted_event_payloads, targeted_markets)
            historical_all, live_all = self._partition_markets(
                targeted_markets,
                now=now,
                lookback_days=lookback_days,
            )
            historical_events, live_events = self._partition_event_summaries(
                all_event_summaries,
                now=now,
                lookback_days=lookback_days,
            )
            self._persist_discovered_events(
                targeted_event_payloads,
                all_event_summaries,
                speaker_key=speaker_key,
            )
            scanned_historical_windows = len(historical_events)
            scanned_historical_pages = scanned_event_pages
            scanned_live_pages = scanned_market_pages
        else:
            historical_all, live_all, scanned_historical_windows, scanned_historical_pages, scanned_live_pages = (
                self._build_report_from_global_scan(
                    speaker_key=speaker_key,
                    history_limit=history_limit,
                    lookback_days=lookback_days,
                    window_days=window_days,
                    historical_pages_per_window=historical_pages_per_window,
                    open_pages=open_pages,
                    now=now,
                )
            )
            historical_events = _summarize_events(historical_all)
            live_events = _summarize_events(live_all)

        historical = historical_all[:history_limit]
        live = live_all
        historical.sort(key=_market_sort_key, reverse=True)
        live.sort(key=_market_sort_key, reverse=True)

        return WhiteHouseMentionMarketReport(
            speaker_key=speaker_key,
            speaker_name=self._speaker_name_from_key(speaker_key),
            historical_markets=historical,
            live_markets=live,
            historical_events=historical_events[:history_limit],
            live_events=live_events,
            lookback_days=lookback_days,
            window_days=window_days,
            historical_pages_per_window=historical_pages_per_window,
            open_pages=open_pages,
            scanned_historical_windows=scanned_historical_windows,
            scanned_historical_pages=scanned_historical_pages,
            scanned_live_pages=scanned_live_pages,
        )

    def _build_report_from_global_scan(
        self,
        *,
        speaker_key: str,
        history_limit: int,
        lookback_days: int,
        window_days: int,
        historical_pages_per_window: int,
        open_pages: int,
        now: datetime,
    ) -> tuple[list[Market], list[Market], int, int, int]:
        historical: list[Market] = []
        live: list[Market] = []
        historical_seen: set[str] = set()
        live_seen: set[str] = set()
        scanned_historical_windows = 0
        scanned_historical_pages = 0
        scanned_live_pages = 0

        oldest = now - timedelta(days=lookback_days)
        window_end = now
        while window_end > oldest and len(historical) < history_limit:
            window_start = max(oldest, window_end - timedelta(days=window_days))
            scanned_historical_windows += 1
            for page in self._iter_market_pages(
                status="closed",
                max_pages=historical_pages_per_window,
                min_close_ts=int(window_start.timestamp()),
                max_close_ts=int(window_end.timestamp()),
            ):
                scanned_historical_pages += 1
                for payload in page.get("markets", []) or []:
                    market = self._parse_market(payload, speaker_key)
                    if market is None or market.market_id in historical_seen:
                        continue
                    historical_seen.add(market.market_id)
                    historical.append(market)
                    if len(historical) >= history_limit:
                        break
                if len(historical) >= history_limit:
                    break
            window_end = window_start - timedelta(seconds=1)

        for page in self._iter_market_pages(status="open", max_pages=open_pages):
            scanned_live_pages += 1
            for payload in page.get("markets", []) or []:
                market = self._parse_market(payload, speaker_key)
                if market is None or market.market_id in live_seen:
                    continue
                live_seen.add(market.market_id)
                live.append(market)

        return historical, live, scanned_historical_windows, scanned_historical_pages, scanned_live_pages

    def _parse_market(self, payload: dict, speaker_key: str) -> Optional[Market]:
        market = self.parser.parse(normalize_market_payload(payload))
        if market is None or market.metadata.get("speaker_key") != speaker_key:
            return None
        if self.db is not None:
            self.db.upsert_market(market)
        return market

    def _discover_series_events_for_speaker(self, speaker_key: str) -> tuple[list[dict], int]:
        events_by_ticker: dict[str, dict] = {}
        scanned_pages = 0
        for series_ticker in self._candidate_series_tickers_for_speaker(speaker_key):
            cursor = None
            while True:
                payload = self.client.fetch_events_page(
                    limit=200,
                    cursor=cursor,
                    series_ticker=series_ticker,
                )
                scanned_pages += 1
                for event in payload.get("events", []) or []:
                    event_ticker = event.get("event_ticker")
                    if event_ticker:
                        events_by_ticker[event_ticker] = event
                cursor = payload.get("cursor")
                if not cursor:
                    break
        return list(events_by_ticker.values()), scanned_pages

    def _discover_series_markets_for_speaker(
        self,
        speaker_key: str,
        *,
        event_payloads: Sequence[dict],
    ) -> tuple[list[Market], int]:
        markets_by_id: dict[str, Market] = {}
        event_payloads_by_ticker = {
            payload.get("event_ticker"): payload
            for payload in event_payloads
            if payload.get("event_ticker")
        }
        scanned_pages = 0
        for series_ticker in self._candidate_series_tickers_for_speaker(speaker_key):
            for page in self._iter_market_pages(series_ticker=series_ticker):
                scanned_pages += 1
                for payload in page.get("markets", []) or []:
                    enriched_payload = dict(payload)
                    event_payload = event_payloads_by_ticker.get(payload.get("event_ticker"))
                    if event_payload is not None:
                        if event_payload.get("title"):
                            enriched_payload.setdefault("event_title", event_payload.get("title"))
                        if event_payload.get("sub_title"):
                            enriched_payload.setdefault("event_subtitle", event_payload.get("sub_title"))
                        if event_payload.get("category"):
                            enriched_payload.setdefault("event_category", event_payload.get("category"))
                        if event_payload.get("series_ticker"):
                            enriched_payload.setdefault("series_ticker", event_payload.get("series_ticker"))
                    market = self._parse_market(enriched_payload, speaker_key)
                    if market is not None:
                        markets_by_id[market.market_id] = market
        return list(markets_by_id.values()), scanned_pages

    def _persist_discovered_events(
        self,
        event_payloads: Sequence[dict],
        event_summaries: Sequence[WhiteHouseMentionEventSummary],
        *,
        speaker_key: str,
    ) -> None:
        if self.db is None:
            return
        summaries_by_ticker = {summary.event_ticker: summary for summary in event_summaries}
        for payload in event_payloads:
            event = _normalize_whitehouse_kalshi_event(
                payload,
                speaker_key=speaker_key,
                summary=summaries_by_ticker.get(payload.get("event_ticker", "")),
            )
            if event is not None:
                self.db.upsert_event(event)

    def _candidate_series_tickers_for_speaker(self, speaker_key: str) -> tuple[str, ...]:
        return self._SPEAKER_SERIES_TICKERS.get(speaker_key, ())

    def _partition_markets(
        self,
        markets: Sequence[Market],
        *,
        now: datetime,
        lookback_days: int,
    ) -> tuple[list[Market], list[Market]]:
        cutoff = now - timedelta(days=lookback_days)
        historical: list[Market] = []
        live: list[Market] = []
        for market in markets:
            if _is_live_market(market, now):
                live.append(market)
                continue
            close_time = _parse_datetime(market.close_time)
            if close_time is not None and close_time < cutoff:
                continue
            historical.append(market)
        historical.sort(key=_market_sort_key, reverse=True)
        live.sort(key=_market_sort_key, reverse=True)
        return historical, live

    def _partition_event_summaries(
        self,
        event_summaries: Sequence[WhiteHouseMentionEventSummary],
        *,
        now: datetime,
        lookback_days: int,
    ) -> tuple[list[WhiteHouseMentionEventSummary], list[WhiteHouseMentionEventSummary]]:
        cutoff = now - timedelta(days=lookback_days)
        historical: list[WhiteHouseMentionEventSummary] = []
        live: list[WhiteHouseMentionEventSummary] = []
        for summary in event_summaries:
            if _is_live_event_summary(summary, now):
                live.append(summary)
                continue
            latest_close_time = _parse_datetime(summary.latest_close_time)
            if latest_close_time is not None and latest_close_time < cutoff:
                continue
            historical.append(summary)
        historical.sort(key=_event_summary_sort_key, reverse=True)
        live.sort(key=_event_summary_sort_key, reverse=True)
        return historical, live

    def _iter_market_pages(
        self,
        *,
        status: Optional[str] = None,
        max_pages: Optional[int] = None,
        min_close_ts: Optional[int] = None,
        max_close_ts: Optional[int] = None,
        series_ticker: Optional[str] = None,
    ) -> Iterable[dict]:
        cursor = None
        pages = 0
        while max_pages is None or pages < max_pages:
            payload = self.client.fetch_markets_page(
                limit=1000,
                cursor=cursor,
                min_close_ts=min_close_ts,
                max_close_ts=max_close_ts,
                status=status,
                series_ticker=series_ticker,
            )
            yield payload
            pages += 1
            cursor = payload.get("cursor")
            if not cursor:
                break

    def _speaker_name_from_key(self, speaker_key: str) -> str:
        for rule in self.parser.speaker_rules:
            if rule.speaker_key == speaker_key:
                return rule.canonical_name
        return speaker_key.replace("_", " ").title()


def render_whitehouse_mention_market_report(report: WhiteHouseMentionMarketReport) -> str:
    settings = (
        f"speaker={report.speaker_key} "
        f"lookback_days={report.lookback_days} "
        f"window_days={report.window_days} "
        f"historical_pages_per_window={report.historical_pages_per_window} "
        f"open_pages={report.open_pages}"
    )
    sections = [
        f"{report.speaker_name} White House mention markets",
        settings,
        "",
        f"Recent historical markets ({len(report.historical_markets)} found)",
    ]
    if report.historical_markets:
        sections.append(_render_market_table(report.historical_markets))
    else:
        sections.append(
            "No matching historical markets found in the scanned closed windows."
        )

    sections.extend(["", f"Live/upcoming markets ({len(report.live_markets)} found)"])
    if report.live_markets:
        sections.append(_render_market_table(report.live_markets))
    else:
        sections.append("No matching live/upcoming markets found in the scanned open pages.")

    sections.extend(
        [
            "",
            (
                f"Scanned historical windows={report.scanned_historical_windows} "
                f"historical_pages={report.scanned_historical_pages} "
                f"live_pages={report.scanned_live_pages}"
            ),
        ]
    )
    return "\n".join(sections)


def render_whitehouse_mention_event_report(report: WhiteHouseMentionMarketReport) -> str:
    settings = (
        f"speaker={report.speaker_key} "
        f"lookback_days={report.lookback_days} "
        f"window_days={report.window_days} "
        f"historical_pages_per_window={report.historical_pages_per_window} "
        f"open_pages={report.open_pages}"
    )
    sections = [
        f"{report.speaker_name} White House mention events",
        settings,
        "",
        f"Recent historical events ({len(report.historical_events)} found)",
    ]
    if report.historical_events:
        sections.append(_render_event_table(report.historical_events))
    else:
        sections.append("No matching historical events found in the scanned data.")

    sections.extend(["", f"Live/upcoming events ({len(report.live_events)} found)"])
    if report.live_events:
        sections.append(_render_event_table(report.live_events))
    else:
        sections.append("No matching live/upcoming events found in the scanned data.")

    sections.extend(
        [
            "",
            (
                f"Scanned historical windows={report.scanned_historical_windows} "
                f"historical_pages={report.scanned_historical_pages} "
                f"live_pages={report.scanned_live_pages}"
            ),
        ]
    )
    return "\n".join(sections)


def _render_market_table(markets: Sequence[Market]) -> str:
    columns = [
        ("Close", 16, lambda market: _format_timestamp(market.close_time)),
        ("Status", 8, lambda market: market.status or ""),
        ("Result", 6, lambda market: _format_result(market)),
        ("Phrase", 18, lambda market: market.metadata.get("target_phrase", "")),
        ("Scope", 12, lambda market: market.metadata.get("briefing_scope", "")),
        ("YesBid", 6, lambda market: _format_cents(market.yes_bid)),
        ("YesAsk", 6, lambda market: _format_cents(market.yes_ask)),
        ("Vol", 7, lambda market: "" if market.volume is None else str(market.volume)),
        ("Ticker", 36, lambda market: market.market_id),
        ("Title", 52, lambda market: market.title),
    ]
    header = " | ".join(_pad(label, width) for label, width, _ in columns)
    divider = "-+-".join("-" * width for _, width, _ in columns)
    rows = []
    for market in markets:
        rows.append(
            " | ".join(
                _pad(_truncate(getter(market), width), width)
                for _, width, getter in columns
            )
        )
    return "\n".join([header, divider, *rows])


def _render_event_table(events: Sequence[WhiteHouseMentionEventSummary]) -> str:
    columns = [
        ("LatestClose", 16, lambda event: _format_timestamp(event.latest_close_time)),
        ("Category", 10, lambda event: event.category or ""),
        ("Markets", 7, lambda event: str(event.market_count)),
        ("Statuses", 18, lambda event: _format_status_counts(event.status_counts)),
        ("Ticker", 28, lambda event: event.event_ticker),
        ("Subtitle", 18, lambda event: event.subtitle or ""),
        ("Title", 48, lambda event: event.title),
    ]
    header = " | ".join(_pad(label, width) for label, width, _ in columns)
    divider = "-+-".join("-" * width for _, width, _ in columns)
    rows = []
    for event in events:
        rows.append(
            " | ".join(
                _pad(_truncate(getter(event), width), width)
                for _, width, getter in columns
            )
        )
    return "\n".join([header, divider, *rows])


def _market_sort_key(market: Market) -> tuple[str, str]:
    return (
        market.close_time or market.metadata.get("event_date") or "",
        market.market_id,
    )


def _format_timestamp(value: Optional[str]) -> str:
    parsed = _parse_datetime(value)
    if parsed is None:
        return ""
    return parsed.strftime("%Y-%m-%d %H:%M")


def _format_result(market: Market) -> str:
    result = market.metadata.get("result")
    if result in (None, ""):
        return ""
    return str(result).upper()


def _format_cents(value: Optional[int]) -> str:
    if value is None:
        return ""
    return f"{value}c"


def _summarize_events(markets: Sequence[Market]) -> list[WhiteHouseMentionEventSummary]:
    summaries: dict[str, WhiteHouseMentionEventSummary] = {}
    for market in markets:
        event_ticker = market.metadata.get("event_ticker") or market.event_id
        if not event_ticker:
            continue
        summary = summaries.get(event_ticker)
        if summary is None:
            summary = WhiteHouseMentionEventSummary(
                event_ticker=event_ticker,
                series_ticker=market.metadata.get("series_ticker") or market.series_id,
                title=market.metadata.get("event_title") or market.title,
                subtitle=market.metadata.get("event_subtitle"),
                category=market.metadata.get("event_category"),
                latest_close_time=market.close_time,
                market_count=0,
                status_counts={},
            )
            summaries[event_ticker] = summary
        summary.market_count += 1
        status = (market.status or "").lower() or "unknown"
        summary.status_counts[status] = summary.status_counts.get(status, 0) + 1
        if (market.close_time or "") > (summary.latest_close_time or ""):
            summary.latest_close_time = market.close_time
    return sorted(
        summaries.values(),
        key=_event_summary_sort_key,
        reverse=True,
    )


def _summarize_event_payloads(
    event_payloads: Sequence[dict],
    markets: Sequence[Market],
) -> list[WhiteHouseMentionEventSummary]:
    summaries: dict[str, WhiteHouseMentionEventSummary] = {}
    for payload in event_payloads:
        event_ticker = payload.get("event_ticker")
        if not event_ticker:
            continue
        summaries[event_ticker] = WhiteHouseMentionEventSummary(
            event_ticker=event_ticker,
            series_ticker=payload.get("series_ticker"),
            title=payload.get("title") or event_ticker,
            subtitle=payload.get("sub_title"),
            category=payload.get("category"),
            latest_close_time=_infer_event_reference_time(payload.get("sub_title")),
            market_count=0,
            status_counts={},
        )

    for market in markets:
        event_ticker = market.metadata.get("event_ticker") or market.event_id
        if not event_ticker:
            continue
        summary = summaries.get(event_ticker)
        if summary is None:
            summary = WhiteHouseMentionEventSummary(
                event_ticker=event_ticker,
                series_ticker=market.metadata.get("series_ticker") or market.series_id,
                title=market.metadata.get("event_title") or market.title,
                subtitle=market.metadata.get("event_subtitle"),
                category=market.metadata.get("event_category"),
                latest_close_time=market.close_time,
                market_count=0,
                status_counts={},
            )
            summaries[event_ticker] = summary
        summary.market_count += 1
        status = (market.status or "").lower() or "unknown"
        summary.status_counts[status] = summary.status_counts.get(status, 0) + 1
        if (market.close_time or "") > (summary.latest_close_time or ""):
            summary.latest_close_time = market.close_time

    return sorted(summaries.values(), key=_event_summary_sort_key, reverse=True)


def _format_status_counts(status_counts: Dict[str, int]) -> str:
    return ",".join(f"{status}:{count}" for status, count in sorted(status_counts.items()))


def _is_live_market(market: Market, now: datetime) -> bool:
    status = (market.status or "").lower()
    if status in {"active", "open"}:
        return True
    close_time = _parse_datetime(market.close_time)
    return close_time is not None and close_time >= now


def _is_live_event_summary(summary: WhiteHouseMentionEventSummary, now: datetime) -> bool:
    if any(status in {"active", "open"} for status in summary.status_counts):
        return True
    close_time = _parse_datetime(summary.latest_close_time)
    return close_time is not None and close_time >= now


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _infer_event_reference_time(subtitle: Optional[str]) -> Optional[str]:
    if not subtitle:
        return None
    cleaned = subtitle.strip()
    for prefix in ("Before ", "On "):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            parsed = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
            return parsed.isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return None


def _truncate(value: object, width: int) -> str:
    text = str(value)
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def _pad(value: str, width: int) -> str:
    return value.ljust(width)


def _normalize_whitehouse_kalshi_event(
    payload: dict,
    *,
    speaker_key: str,
    summary: Optional[WhiteHouseMentionEventSummary] = None,
) -> Optional[Event]:
    event_ticker = payload.get("event_ticker")
    title = payload.get("title")
    if not event_ticker or not title:
        return None

    latest_close_time = None
    statuses: Dict[str, int] = {}
    market_count = 0
    if summary is not None:
        latest_close_time = summary.latest_close_time
        statuses = dict(summary.status_counts)
        market_count = summary.market_count
    else:
        markets = payload.get("markets", []) or []
        close_times = [market.get("close_time") for market in markets if market.get("close_time")]
        latest_close_time = max(close_times) if close_times else _infer_event_reference_time(
            payload.get("sub_title")
        )
        for market in markets:
            status = market.get("status")
            if not status:
                continue
            statuses[status] = statuses.get(status, 0) + 1
        market_count = len(markets)

    metadata = {
        "provider": "kalshi",
        "source_family": "whitehouse",
        "speaker_key": speaker_key,
        "speaker_name": speaker_key.replace("_", " ").title(),
        "event_ticker": event_ticker,
        "series_ticker": payload.get("series_ticker"),
        "event_subtitle": payload.get("sub_title"),
        "event_category": payload.get("category"),
        "kalshi_status": payload.get("status"),
        "status_counts": statuses,
        "market_count": market_count,
    }
    if latest_close_time is not None:
        metadata["latest_close_time"] = latest_close_time

    return Event(
        event_id=event_ticker,
        event_type="kalshi_whitehouse_mention_event",
        title=title,
        category="prediction_market",
        subcategory="white_house_press_briefing_mentions",
        scheduled_start_time=payload.get("strike_date"),
        scheduled_end_time=latest_close_time,
        actual_start_time=None,
        actual_end_time=latest_close_time if market_count and _all_markets_closed(statuses) else None,
        participants=_speaker_name_from_key(speaker_key),
        broadcast_network="Kalshi",
        league=None,
        season=None,
        venue=None,
        source_priority="kalshi_event_first",
        broadcast_priority=None,
        metadata=metadata,
    )


def _all_markets_closed(status_counts: Dict[str, int]) -> bool:
    if not status_counts:
        return False
    return all(status in {"closed", "settled", "finalized"} for status in status_counts)


def _event_summary_sort_key(event: WhiteHouseMentionEventSummary) -> tuple[str, str]:
    return (event.latest_close_time or "", event.event_ticker)


def _speaker_name_from_key(speaker_key: str) -> str:
    return speaker_key.replace("_", " ").title()
