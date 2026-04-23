from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

from mentions_engine.config import AppPaths
from mentions_engine.http import HttpClient
from mentions_engine.models import SourceArtifact
from mentions_engine.utils import normalize_text, stable_hash, utc_now_iso


@dataclass
class AcquisitionResult:
    artifacts: List[SourceArtifact]


class WhiteHouseAcquisition:
    def __init__(self, paths: AppPaths, client: Optional[HttpClient] = None):
        self.paths = paths
        self.client = client or HttpClient()

    def fetch_event_sources(self, event_id: str, video_page_url: str) -> AcquisitionResult:
        html = self.client.get_text(video_page_url)
        html_path = self.paths.raw_dir / "whitehouse" / f"{event_id}.video.html"
        html_path.write_text(html, encoding="utf-8")

        artifacts: List[SourceArtifact] = [
            SourceArtifact(
                artifact_id=f"artifact-{stable_hash(event_id + ':official-video-page')[:16]}",
                event_id=event_id,
                artifact_type="video_replay",
                role="research_source",
                provider="whitehouse.gov",
                uri=video_page_url,
                local_path=str(html_path),
                captured_at=utc_now_iso(),
                published_at=None,
                start_time=None,
                end_time=None,
                duration_seconds=None,
                checksum=stable_hash(html),
                mime_type="text/html",
                is_official=True,
                is_settlement_candidate=True,
                feed_label="white_house_video_page",
                feed_priority=None,
                broadcast_scope="official",
                language="en",
                metadata={},
            )
        ]

        transcript_url = self._extract_transcript_url(html, event_id)
        if transcript_url:
            transcript_html = self.client.get_text(transcript_url)
            transcript_path = self.paths.raw_dir / "whitehouse" / f"{event_id}.transcript.html"
            transcript_path.write_text(transcript_html, encoding="utf-8")
            artifacts.append(
                SourceArtifact(
                    artifact_id=f"artifact-{stable_hash(event_id + ':official-transcript')[:16]}",
                    event_id=event_id,
                    artifact_type="official_transcript",
                    role="settlement_source",
                    provider="whitehouse.gov",
                    uri=transcript_url,
                    local_path=str(transcript_path),
                    captured_at=utc_now_iso(),
                    published_at=None,
                    start_time=None,
                    end_time=None,
                    duration_seconds=None,
                    checksum=stable_hash(transcript_html),
                    mime_type="text/html",
                    is_official=True,
                    is_settlement_candidate=True,
                    feed_label="official_transcript_page",
                    feed_priority=None,
                    broadcast_scope="official",
                    language="en",
                    metadata={},
                )
            )

        youtube_id = self._extract_youtube_video_id(html)
        if youtube_id:
            captions = self._fetch_youtube_captions(youtube_id)
            if captions is not None:
                captions_path = self.paths.raw_dir / "whitehouse" / f"{event_id}.captions.json"
                captions_path.write_text(captions, encoding="utf-8")
                artifacts.append(
                    SourceArtifact(
                        artifact_id=f"artifact-{stable_hash(event_id + ':youtube-captions')[:16]}",
                        event_id=event_id,
                        artifact_type="closed_captions",
                        role="research_source",
                        provider="youtube",
                        uri=f"https://www.youtube.com/watch?v={youtube_id}",
                        local_path=str(captions_path),
                        captured_at=utc_now_iso(),
                        published_at=None,
                        start_time=None,
                        end_time=None,
                        duration_seconds=None,
                        checksum=stable_hash(captions),
                        mime_type="application/json",
                        is_official=False,
                        is_settlement_candidate=False,
                        feed_label="youtube_auto_captions",
                        feed_priority=None,
                        broadcast_scope="official",
                        language="en",
                        metadata={"youtube_id": youtube_id},
                    )
                )

        return AcquisitionResult(artifacts=artifacts)

    def _extract_transcript_url(self, html: str, event_id: str) -> Optional[str]:
        title = self._extract_page_title(html)

        direct_candidates = self._extract_briefing_links(html, title or event_id)
        if direct_candidates:
            return direct_candidates[0]

        if title:
            search_candidates = self._search_briefings(title)
            if search_candidates:
                return search_candidates[0]

        fallback_query = event_id.replace("whitehouse-", "").replace("-", " ")
        search_candidates = self._search_briefings(fallback_query)
        if search_candidates:
            return search_candidates[0]

        return None

    def _extract_page_title(self, html: str) -> Optional[str]:
        match = re.search(r'<meta property="og:title" content="([^"]+)"', html)
        if match:
            return unescape(match.group(1)).strip()
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            return unescape(re.sub(r"<[^>]+>", " ", match.group(1))).strip()
        return None

    def _extract_briefing_links(self, html: str, title: str) -> List[str]:
        title_tokens = set(normalize_text(title).split())
        candidates = []
        seen = set()

        for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL):
            if "/briefings-statements/" not in href:
                continue
            resolved = urljoin("https://www.whitehouse.gov", href)
            if resolved.rstrip("/") == "https://www.whitehouse.gov/briefings-statements":
                continue
            if resolved in seen:
                continue

            clean_text = unescape(re.sub(r"<[^>]+>", " ", text))
            clean_tokens = set(normalize_text(clean_text).split())
            score = len(title_tokens & clean_tokens)
            if title_tokens and score == 0:
                continue

            candidates.append((score, resolved))
            seen.add(resolved)

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [url for _, url in candidates]

    def _search_briefings(self, query: str) -> List[str]:
        search_url = f"https://www.whitehouse.gov/?s={quote_plus(query)}"
        html = self.client.get_text(search_url)
        return self._extract_briefing_links(html, query)

    def _extract_youtube_video_id(self, html: str) -> Optional[str]:
        match = re.search(r"https://www\.youtube\.com/embed/([A-Za-z0-9_-]{11})", html)
        if match:
            return match.group(1)
        return None

    def _fetch_youtube_captions(self, youtube_id: str) -> Optional[str]:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            api = YouTubeTranscriptApi()
            transcript = api.fetch(youtube_id, languages=["en", "en-US"])
            rows = [
                {
                    "text": item.text,
                    "start": item.start,
                    "duration": item.duration,
                }
                for item in transcript
            ]
            if rows:
                return json.dumps(rows, indent=2)
        except Exception:
            pass

        watch_html = self.client.get_text(f"https://www.youtube.com/watch?v={youtube_id}")
        match = re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\});", watch_html)
        if not match:
            return None

        payload = json.loads(match.group(1))
        tracks = (
            payload.get("captions", {})
            .get("playerCaptionsTracklistRenderer", {})
            .get("captionTracks", [])
        )
        if not tracks:
            return None

        preferred = None
        for track in tracks:
            if track.get("languageCode") in {"en", "en-US"}:
                preferred = track
                break
        if preferred is None:
            preferred = tracks[0]

        base_url = preferred.get("baseUrl")
        if not base_url:
            return None
        text = self.client.get_text(base_url + "&fmt=srv3")
        return text or None
