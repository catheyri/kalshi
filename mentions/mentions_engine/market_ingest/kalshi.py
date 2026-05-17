from __future__ import annotations

from typing import Iterable, List, Optional

from mentions_engine.kalshi import KalshiPublicClient, normalize_market_payload
from mentions_engine.market_analysis import MarketParser
from mentions_engine.models import Market


class KalshiMarketTickerIngestor:
    name = "kalshi-market-tickers"

    def __init__(
        self,
        market_tickers: Iterable[str],
        client: KalshiPublicClient,
        *,
        parser: Optional[MarketParser] = None,
    ):
        self.market_tickers = list(market_tickers)
        self.client = client
        self.parser = parser

    def fetch_open_markets(self) -> List[Market]:
        return [
            market
            for ticker in self.market_tickers
            for market in [_maybe_parse_market(self.parser, normalize_market_payload(self.client.fetch_market(ticker)))]
            if market is not None
        ]


class KalshiEventTickerIngestor:
    name = "kalshi-event-tickers"

    def __init__(
        self,
        event_tickers: Iterable[str],
        client: KalshiPublicClient,
        *,
        open_only: bool = True,
        parser: Optional[MarketParser] = None,
        include_historical: bool = False,
        historical_only: bool = False,
        historical_pages_per_event: Optional[int] = None,
    ):
        self.event_tickers = list(event_tickers)
        self.client = client
        self.open_only = open_only
        self.parser = parser
        self.include_historical = include_historical
        self.historical_only = historical_only
        self.historical_pages_per_event = historical_pages_per_event

    def fetch_open_markets(self) -> List[Market]:
        markets_by_id: dict[str, Market] = {}
        for event_ticker in self.event_tickers:
            event = self.client.fetch_event(
                event_ticker,
                with_nested_markets=not self.historical_only,
            )
            if not self.historical_only:
                for market_payload in event.get("markets", []) or []:
                    maybe_market = self._parse_event_market(
                        market_payload,
                        event=event,
                        ingestion_source="kalshi_live_event",
                        source_endpoint=f"/events/{event_ticker}",
                    )
                    if maybe_market is not None:
                        markets_by_id[maybe_market.market_id] = maybe_market
            if self.include_historical:
                for market_payload in self._iter_historical_event_market_payloads(event_ticker):
                    maybe_market = self._parse_event_market(
                        market_payload,
                        event=event,
                        ingestion_source="kalshi_historical_api",
                        source_endpoint="/historical/markets",
                    )
                    if maybe_market is not None:
                        markets_by_id[maybe_market.market_id] = maybe_market
        return list(markets_by_id.values())

    def _iter_historical_event_market_payloads(self, event_ticker: str) -> Iterable[dict]:
        cursor = None
        pages = 0
        while self.historical_pages_per_event is None or pages < self.historical_pages_per_event:
            page = self.client.fetch_historical_markets_page(
                limit=1000,
                cursor=cursor,
                event_ticker=event_ticker,
            )
            yield from page.get("markets", []) or []
            pages += 1
            cursor = page.get("cursor")
            if not cursor:
                break

    def _parse_event_market(
        self,
        market_payload: dict,
        *,
        event: dict,
        ingestion_source: str,
        source_endpoint: str,
    ) -> Optional[Market]:
        if self.open_only and not _is_open_like_market(market_payload.get("status")):
            return None
        enriched = dict(market_payload)
        enriched.setdefault("series_ticker", event.get("series_ticker"))
        enriched.setdefault("event_title", event.get("title"))
        enriched.setdefault("event_subtitle", event.get("sub_title"))
        enriched.setdefault("event_category", event.get("category"))
        enriched.setdefault("strike_date", event.get("strike_date"))
        enriched.setdefault("ingestion_source", ingestion_source)
        enriched.setdefault("source_endpoint", source_endpoint)
        return _maybe_parse_market(self.parser, normalize_market_payload(enriched))


class KalshiCategoryMarketIngestor:
    name = "kalshi-category"

    def __init__(
        self,
        category: str,
        client: KalshiPublicClient,
        *,
        open_only: bool = True,
        max_pages: int = 1,
        parser: Optional[MarketParser] = None,
    ):
        self.category = category
        self.client = client
        self.open_only = open_only
        self.max_pages = max_pages
        self.parser = parser

    def fetch_open_markets(self) -> List[Market]:
        event_tickers: List[str] = []
        cursor = None
        pages = 0
        while pages < self.max_pages:
            payload = self.client.fetch_events_page(
                category=self.category,
                status="open" if self.open_only else None,
                cursor=cursor,
            )
            event_tickers.extend(event["event_ticker"] for event in payload.get("events", []) or [])
            cursor = payload.get("cursor")
            pages += 1
            if not cursor:
                break
        return KalshiEventTickerIngestor(
            event_tickers,
            self.client,
            open_only=self.open_only,
            parser=self.parser,
        ).fetch_open_markets()


def _maybe_parse_market(parser: Optional[MarketParser], market: Market) -> Optional[Market]:
    if parser is None:
        return market
    return parser.parse(market)


def _is_open_like_market(status: str | None) -> bool:
    return status not in {"closed", "settled", "finalized"}
