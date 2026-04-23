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
    ):
        self.event_tickers = list(event_tickers)
        self.client = client
        self.open_only = open_only
        self.parser = parser

    def fetch_open_markets(self) -> List[Market]:
        markets: List[Market] = []
        for event_ticker in self.event_tickers:
            event = self.client.fetch_event(event_ticker, with_nested_markets=True)
            for market_payload in event.get("markets", []) or []:
                if self.open_only and not _is_open_like_market(market_payload.get("status")):
                    continue
                enriched = dict(market_payload)
                enriched.setdefault("series_ticker", event.get("series_ticker"))
                enriched.setdefault("event_title", event.get("title"))
                enriched.setdefault("event_subtitle", event.get("sub_title"))
                enriched.setdefault("event_category", event.get("category"))
                enriched.setdefault("strike_date", event.get("strike_date"))
                maybe_market = _maybe_parse_market(self.parser, normalize_market_payload(enriched))
                if maybe_market is not None:
                    markets.append(maybe_market)
        return markets


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
