from __future__ import annotations

import json
import re
from datetime import date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

from mentions_engine.discovery.base import DiscoveryResult
from mentions_engine.http import HttpClient
from mentions_engine.models import Event, SourceArtifact
from mentions_engine.utils import normalize_text, slugify, stable_hash


WHITE_HOUSE_VIDEO_LIBRARY_URL = (
    "https://www.whitehouse.gov/videos/?query-inherit-playlist_term=press-briefings"
)
WHITE_HOUSE_SITEMAP_INDEX_URL = "https://www.whitehouse.gov/sitemap_index.xml"
WHITE_HOUSE_TRANSCRIPT_START_DATE = date(2025, 1, 20)
SITEMAP_NAMESPACE = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


class _AnchorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current_href: Optional[str] = None
        self.current_text: List[str] = []
        self.links: List[Dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        href = attrs_map.get("href")
        if href:
            self.current_href = href
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href is not None:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_href is not None:
            text = unescape(" ".join(self.current_text)).strip()
            self.links.append({"href": self.current_href, "text": text})
            self.current_href = None
            self.current_text = []


class WhiteHouseDiscovery:
    name = "whitehouse"

    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def discover_events(self) -> DiscoveryResult:
        html = self.client.get_text(WHITE_HOUSE_VIDEO_LIBRARY_URL)
        links = self._extract_video_links(html)
        events: List[Event] = []
        artifacts: List[SourceArtifact] = []

        for link in links:
            event = self._build_event(link["url"], link["title"], link.get("published_at"))
            artifact = self._build_video_artifact(event.event_id, link["url"], link.get("published_at"))
            events.append(event)
            artifacts.append(artifact)

        return DiscoveryResult(events=events, artifacts=artifacts)

    def discover_official_transcript_events(
        self,
        *,
        start_date: str | date = WHITE_HOUSE_TRANSCRIPT_START_DATE,
    ) -> DiscoveryResult:
        threshold = _coerce_date(start_date)
        events: List[Event] = []
        artifacts: List[SourceArtifact] = []
        seen_urls: set[str] = set()

        for sitemap_url in self._iter_post_sitemap_urls():
            for entry in self._iter_sitemap_entries(sitemap_url):
                url = entry["loc"]
                if url in seen_urls:
                    continue
                if not self._looks_like_transcript_url(url):
                    continue
                if _coerce_date(entry.get("lastmod")) and _coerce_date(entry.get("lastmod")) < threshold:
                    continue

                html = self.client.get_text(url)
                metadata = self._extract_page_metadata(html, url)
                published_date = _coerce_date(metadata.get("published_at"))
                if published_date and published_date < threshold:
                    continue
                if not self._looks_like_transcript_title(metadata["title"]):
                    continue

                event = self._build_transcript_event(url, metadata["title"], metadata.get("published_at"))
                artifact = self._build_transcript_artifact(
                    event.event_id,
                    url=url,
                    published_at=metadata.get("published_at"),
                )
                events.append(event)
                artifacts.append(artifact)
                seen_urls.add(url)

        return DiscoveryResult(events=events, artifacts=artifacts)

    def discover_official_briefing_video_events(
        self,
        *,
        start_date: str | date = WHITE_HOUSE_TRANSCRIPT_START_DATE,
    ) -> DiscoveryResult:
        threshold = _coerce_date(start_date)
        events: List[Event] = []
        artifacts: List[SourceArtifact] = []
        seen_urls: set[str] = set()

        for sitemap_url in self._iter_past_event_sitemap_urls():
            for entry in self._iter_sitemap_entries(sitemap_url):
                url = entry["loc"]
                if url in seen_urls or not self._looks_like_briefing_video_url(url):
                    continue
                if _coerce_date(entry.get("lastmod")) and _coerce_date(entry.get("lastmod")) < threshold:
                    continue

                html = self.client.get_text(url)
                metadata = self._extract_page_metadata(html, url)
                published_date = _coerce_date(metadata.get("published_at"))
                if published_date and published_date < threshold:
                    continue
                if not self._looks_like_briefing_video_title(metadata["title"]):
                    continue

                event = self._build_event(url, metadata["title"], metadata.get("published_at"))
                artifact = self._build_video_artifact(event.event_id, url, metadata.get("published_at"))
                events.append(event)
                artifacts.append(artifact)
                seen_urls.add(url)

        return DiscoveryResult(events=events, artifacts=artifacts)

    def _extract_video_links(self, html: str) -> List[Dict[str, str]]:
        links: List[Dict[str, str]] = []

        json_candidates = re.findall(
            r'"url":"(https:\\/\\/www\.whitehouse\.gov\\/videos\\/[^"]+)".+?"headline":"([^"]+)"',
            html,
        )
        seen = set()
        for url, headline in json_candidates:
            parsed_url = url.replace("\\/", "/")
            if parsed_url in seen:
                continue
            seen.add(parsed_url)
            links.append(
                {
                    "url": parsed_url,
                    "title": headline,
                }
            )

        if links:
            return self._attach_dates(html, links)

        parser = _AnchorParser()
        parser.feed(html)
        for link in parser.links:
            href = link["href"]
            title = link["text"]
            if "/videos/" not in href:
                continue
            if "press secretary karoline leavitt" not in title.lower():
                continue
            url = urljoin("https://www.whitehouse.gov", href)
            if url in seen:
                continue
            seen.add(url)
            links.append({"url": url, "title": title})
        return self._attach_dates(html, links)

    def _attach_dates(self, html: str, links: List[Dict[str, str]]) -> List[Dict[str, str]]:
        for link in links:
            title_pattern = re.escape(link["title"])
            match = re.search(title_pattern + r".{0,120}?(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}", html, re.DOTALL)
            if match:
                date_match = re.search(
                    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}",
                    match.group(0),
                )
                if date_match:
                    link["published_at"] = date_match.group(0)
        return links

    def _build_event(self, url: str, title: str, published_at: Optional[str]) -> Event:
        event_id = _whitehouse_event_id(url)
        participants = "Karoline Leavitt"
        metadata = {"source_url": url}
        if published_at:
            metadata["published_label"] = published_at
            metadata["published_at"] = published_at

        return Event(
            event_id=event_id,
            event_type="white_house_press_briefing",
            title=title,
            category="government",
            subcategory="white_house_press_briefing",
            scheduled_start_time=None,
            scheduled_end_time=None,
            actual_start_time=published_at,
            actual_end_time=None,
            participants=participants,
            broadcast_network="White House",
            league=None,
            season=None,
            venue="White House Briefing Room",
            source_priority="official_transcript_then_official_video_then_third_party_transcript_then_asr",
            broadcast_priority="official_transcript_first",
            metadata=metadata,
        )

    def _build_video_artifact(
        self,
        event_id: str,
        url: str,
        published_at: Optional[str],
    ) -> SourceArtifact:
        return SourceArtifact(
            artifact_id=f"artifact-{stable_hash(event_id + ':official-video-page')[:16]}",
            event_id=event_id,
            artifact_type="video_replay",
            role="research_source",
            provider="whitehouse.gov",
            uri=url,
            local_path=None,
            captured_at=None,
            published_at=published_at,
            start_time=None,
            end_time=None,
            duration_seconds=None,
            checksum=None,
            mime_type="text/html",
            is_official=True,
            is_settlement_candidate=True,
            feed_label="white_house_video_page",
            feed_priority=None,
            broadcast_scope="official",
            language="en",
            metadata={},
        )

    def _iter_post_sitemap_urls(self) -> List[str]:
        xml = self.client.get_text(WHITE_HOUSE_SITEMAP_INDEX_URL)
        root = ET.fromstring(xml)
        sitemap_urls: List[str] = []
        for node in root.findall("sm:sitemap", SITEMAP_NAMESPACE):
            loc = node.findtext("sm:loc", default="", namespaces=SITEMAP_NAMESPACE)
            if "post-sitemap" in loc:
                sitemap_urls.append(loc)
        return sitemap_urls

    def _iter_past_event_sitemap_urls(self) -> List[str]:
        xml = self.client.get_text(WHITE_HOUSE_SITEMAP_INDEX_URL)
        root = ET.fromstring(xml)
        sitemap_urls: List[str] = []
        for node in root.findall("sm:sitemap", SITEMAP_NAMESPACE):
            loc = node.findtext("sm:loc", default="", namespaces=SITEMAP_NAMESPACE)
            if "past_event-sitemap" in loc:
                sitemap_urls.append(loc)
        return sitemap_urls

    def _iter_sitemap_entries(self, sitemap_url: str) -> List[Dict[str, str]]:
        xml = self.client.get_text(sitemap_url)
        root = ET.fromstring(xml)
        entries: List[Dict[str, str]] = []
        for node in root.findall("sm:url", SITEMAP_NAMESPACE):
            loc = node.findtext("sm:loc", default="", namespaces=SITEMAP_NAMESPACE)
            lastmod = node.findtext("sm:lastmod", default="", namespaces=SITEMAP_NAMESPACE)
            if loc:
                entries.append({"loc": loc, "lastmod": lastmod})
        return entries

    def _looks_like_transcript_url(self, url: str) -> bool:
        low = url.lower()
        if "/briefings-statements/" not in low:
            return False
        return "press-briefing" in low and "karoline-leavitt" in low

    def _looks_like_briefing_video_url(self, url: str) -> bool:
        low = url.lower()
        if "/videos/" not in low or "karoline-leavitt" not in low:
            return False
        include_patterns = (
            "briefs-members-of-the-media",
            "brief-members-of-the-media",
            "briefs-members-of-the-new-media",
            "press-briefing-by-press-secretary-karoline-leavitt",
            "press-briefing-by-the-white-house-press-secretary-karoline-leavitt",
            "holds-a-press-briefing",
        )
        return any(pattern in low for pattern in include_patterns)

    def _looks_like_transcript_title(self, title: str) -> bool:
        normalized = normalize_text(title)
        return "press briefing" in normalized and "karoline leavitt" in normalized

    def _looks_like_briefing_video_title(self, title: str) -> bool:
        normalized = normalize_text(title)
        if "karoline leavitt" not in normalized:
            return False
        include_patterns = (
            "briefs members of the media",
            "brief members of the media",
            "briefs members of the new media",
            "press briefing by press secretary karoline leavitt",
            "press briefing by the white house press secretary karoline leavitt",
            "holds a press briefing",
        )
        return any(pattern in normalized for pattern in include_patterns)

    def _extract_page_metadata(self, html: str, url: str) -> Dict[str, Optional[str]]:
        metadata: Dict[str, Optional[str]] = {"url": url}
        title_match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if title_match:
            metadata["title"] = unescape(title_match.group(1)).strip()
        else:
            title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
            metadata["title"] = (
                unescape(re.sub(r"<[^>]+>", " ", title_match.group(1))).strip()
                if title_match
                else url.rstrip("/").rsplit("/", 1)[-1]
            )

        published_match = re.search(r'article:published_time" content="([^"]+)"', html)
        if published_match:
            metadata["published_at"] = published_match.group(1)
        else:
            metadata["published_at"] = None
        return metadata

    def _build_transcript_event(
        self,
        url: str,
        title: str,
        published_at: Optional[str],
    ) -> Event:
        event_id = _whitehouse_event_id(url)
        metadata = {"source_url": url, "transcript_url": url}
        if published_at:
            metadata["published_at"] = published_at

        return Event(
            event_id=event_id,
            event_type="white_house_press_briefing",
            title=title,
            category="government",
            subcategory="white_house_press_briefing",
            scheduled_start_time=None,
            scheduled_end_time=None,
            actual_start_time=published_at,
            actual_end_time=None,
            participants="Karoline Leavitt",
            broadcast_network="White House",
            league=None,
            season=None,
            venue="White House Briefing Room",
            source_priority="official_transcript_then_official_video_then_third_party_transcript_then_asr",
            broadcast_priority="official_transcript_first",
            metadata=metadata,
        )

    def _build_transcript_artifact(
        self,
        event_id: str,
        *,
        url: str,
        published_at: Optional[str],
    ) -> SourceArtifact:
        return SourceArtifact(
            artifact_id=f"artifact-{stable_hash(event_id + ':official-transcript')[:16]}",
            event_id=event_id,
            artifact_type="official_transcript",
            role="settlement_source",
            provider="whitehouse.gov",
            uri=url,
            local_path=None,
            captured_at=None,
            published_at=published_at,
            start_time=None,
            end_time=None,
            duration_seconds=None,
            checksum=None,
            mime_type="text/html",
            is_official=True,
            is_settlement_candidate=True,
            feed_label="official_transcript_page",
            feed_priority=None,
            broadcast_scope="official",
            language="en",
            metadata={},
        )


def _coerce_date(value: str | date | None) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _whitehouse_event_id(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return f"whitehouse-{slugify(path)}"
