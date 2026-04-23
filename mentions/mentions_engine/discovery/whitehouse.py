from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin

from mentions_engine.http import HttpClient
from mentions_engine.models import Event, SourceArtifact
from mentions_engine.utils import slugify, stable_hash


WHITE_HOUSE_VIDEO_LIBRARY_URL = (
    "https://www.whitehouse.gov/videos/?query-inherit-playlist_term=press-briefings"
)


@dataclass
class DiscoveryResult:
    events: List[Event]
    artifacts: List[SourceArtifact]


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
    def __init__(self, client: Optional[HttpClient] = None):
        self.client = client or HttpClient()

    def discover_press_briefings(self) -> DiscoveryResult:
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
        event_id = f"whitehouse-{slugify(title)}"
        participants = "Karoline Leavitt"
        metadata = {"source_url": url}
        if published_at:
            metadata["published_label"] = published_at

        return Event(
            event_id=event_id,
            event_type="white_house_press_briefing",
            title=title,
            category="government",
            subcategory="white_house_press_briefing",
            scheduled_start_time=None,
            scheduled_end_time=None,
            actual_start_time=None,
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
        artifact_key = f"{event_id}:{url}:video_page"
        return SourceArtifact(
            artifact_id=f"artifact-{stable_hash(artifact_key)[:16]}",
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
