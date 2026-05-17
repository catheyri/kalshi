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
from mentions_engine.profiles import (
    EventSourceProfile,
    SpeakerProfile,
    KAROLINE_LEAVITT,
    WHITE_HOUSE_PRESS_BRIEFING,
)
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

    def __init__(
        self,
        client: Optional[HttpClient] = None,
        *,
        speaker_profile: SpeakerProfile = KAROLINE_LEAVITT,
        event_profile: EventSourceProfile = WHITE_HOUSE_PRESS_BRIEFING,
    ):
        self.client = client or HttpClient()
        self.speaker_profile = speaker_profile
        self.event_profile = event_profile

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
            if not self.speaker_profile.matches_text(title):
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
        participants = self.speaker_profile.canonical_name
        metadata = {
            "source_url": url,
            "speaker_key": self.speaker_profile.speaker_key,
            "speaker_name": self.speaker_profile.canonical_name,
            "event_profile_key": self.event_profile.key,
        }
        if published_at:
            metadata["published_label"] = published_at
            metadata["published_at"] = published_at

        return Event(
            event_id=event_id,
            event_type=self.event_profile.event_type,
            title=title,
            category=self.event_profile.category,
            subcategory=self.event_profile.subcategory,
            scheduled_start_time=None,
            scheduled_end_time=None,
            actual_start_time=published_at,
            actual_end_time=None,
            participants=participants,
            broadcast_network=self.event_profile.broadcast_network,
            league=None,
            season=None,
            venue=self.event_profile.venue,
            source_priority=self.event_profile.source_priority,
            broadcast_priority=self.event_profile.broadcast_priority,
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
        if "/briefings-statements/" not in low or not self.speaker_profile.matches_slug(low):
            return False
        return any(pattern in low for pattern in self.event_profile.transcript_url_patterns)

    def _looks_like_briefing_video_url(self, url: str) -> bool:
        low = url.lower()
        if "/videos/" not in low or not self.speaker_profile.matches_slug(low):
            return False
        return any(pattern in low for pattern in self.event_profile.video_url_patterns)

    def _looks_like_transcript_title(self, title: str) -> bool:
        normalized = normalize_text(title)
        return self.speaker_profile.matches_text(normalized) and any(
            pattern in normalized for pattern in self.event_profile.transcript_title_patterns
        )

    def _looks_like_briefing_video_title(self, title: str) -> bool:
        normalized = normalize_text(title)
        if not self.speaker_profile.matches_text(normalized):
            return False
        return any(pattern in normalized for pattern in self.event_profile.video_title_patterns)

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

        metadata["published_at"] = _extract_published_at(html)
        return metadata

    def _build_transcript_event(
        self,
        url: str,
        title: str,
        published_at: Optional[str],
    ) -> Event:
        event_id = _whitehouse_event_id(url)
        metadata = {
            "source_url": url,
            "transcript_url": url,
            "speaker_key": self.speaker_profile.speaker_key,
            "speaker_name": self.speaker_profile.canonical_name,
            "event_profile_key": self.event_profile.key,
        }
        if published_at:
            metadata["published_at"] = published_at

        return Event(
            event_id=event_id,
            event_type=self.event_profile.event_type,
            title=title,
            category=self.event_profile.category,
            subcategory=self.event_profile.subcategory,
            scheduled_start_time=None,
            scheduled_end_time=None,
            actual_start_time=published_at,
            actual_end_time=None,
            participants=self.speaker_profile.canonical_name,
            broadcast_network=self.event_profile.broadcast_network,
            league=None,
            season=None,
            venue=self.event_profile.venue,
            source_priority=self.event_profile.source_priority,
            broadcast_priority=self.event_profile.broadcast_priority,
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


def _extract_published_at(html: str) -> Optional[str]:
    patterns = (
        r'article:published_time" content="([^"]+)"',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"dateCreated"\s*:\s*"([^"]+)"',
        r'<time[^>]+datetime="([^"]+)"',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None


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
