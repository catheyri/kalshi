from __future__ import annotations

import json
import re
from html import unescape
from typing import Dict, List, Optional
from urllib.parse import urljoin

from mentions_engine.acquisition.base import AcquisitionResult
from mentions_engine.config import AppPaths
from mentions_engine.http import HttpClient
from mentions_engine.models import Event, SourceArtifact
from mentions_engine.utils import normalize_text, stable_hash, utc_now_iso


YOUTUBE_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
YOUTUBE_ANDROID_USER_AGENT = "com.google.android.youtube/20.10.38"
YOUTUBE_ANDROID_CONTEXT = {"client": {"clientName": "ANDROID", "clientVersion": "20.10.38"}}


class WhiteHouseAcquisition:
    event_type = "white_house_press_briefing"

    def __init__(self, paths: AppPaths, client: Optional[HttpClient] = None):
        self.paths = paths
        self.client = client or HttpClient()

    def fetch_sources(
        self,
        event: Event,
        known_artifacts: List[SourceArtifact],
    ) -> AcquisitionResult:
        artifacts: List[SourceArtifact] = []

        transcript_artifact = next(
            (
                artifact
                for artifact in known_artifacts
                if artifact.provider == "whitehouse.gov"
                and artifact.artifact_type == "official_transcript"
                and artifact.uri
            ),
            None,
        )
        if transcript_artifact is not None and transcript_artifact.uri:
            artifacts.append(
                self._fetch_official_transcript_artifact(
                    event_id=event.event_id,
                    transcript_url=transcript_artifact.uri,
                    published_at=transcript_artifact.published_at,
                )
            )

        video_artifact = next(
            (
                artifact
                for artifact in known_artifacts
                if artifact.provider == "whitehouse.gov" and artifact.artifact_type == "video_replay" and artifact.uri
            ),
            None,
        )
        if video_artifact is not None and video_artifact.uri:
            result = self.fetch_event_sources(event.event_id, video_artifact.uri)
            deduped = {artifact.artifact_id: artifact for artifact in artifacts}
            deduped.update({artifact.artifact_id: artifact for artifact in result.artifacts})
            return AcquisitionResult(artifacts=list(deduped.values()))

        if artifacts:
            return AcquisitionResult(artifacts=artifacts)

        raise ValueError(f"No fetchable White House source artifact found for {event.event_id}")

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
                captions_path = self.paths.raw_dir / "whitehouse" / f"{event_id}.captions.xml"
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
                        mime_type="text/xml",
                        is_official=False,
                        is_settlement_candidate=False,
                        feed_label="youtube_caption_track",
                        feed_priority=None,
                        broadcast_scope="official",
                        language="en",
                        metadata={"youtube_id": youtube_id},
                    )
                )

        return AcquisitionResult(artifacts=artifacts)

    def _fetch_official_transcript_artifact(
        self,
        *,
        event_id: str,
        transcript_url: str,
        published_at: Optional[str],
    ) -> SourceArtifact:
        transcript_html = self.client.get_text(transcript_url)
        transcript_path = self.paths.raw_dir / "whitehouse" / f"{event_id}.transcript.html"
        transcript_path.write_text(transcript_html, encoding="utf-8")
        return SourceArtifact(
            artifact_id=f"artifact-{stable_hash(event_id + ':official-transcript')[:16]}",
            event_id=event_id,
            artifact_type="official_transcript",
            role="settlement_source",
            provider="whitehouse.gov",
            uri=transcript_url,
            local_path=str(transcript_path),
            captured_at=utc_now_iso(),
            published_at=published_at,
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

    def _extract_transcript_url(self, html: str, event_id: str) -> Optional[str]:
        title = self._extract_page_title(html)

        direct_candidates = self._extract_briefing_links(html, title or event_id)
        if direct_candidates:
            return direct_candidates[0]

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

    def _extract_youtube_video_id(self, html: str) -> Optional[str]:
        match = re.search(r"https://www\.youtube\.com/embed/([A-Za-z0-9_-]{11})", html)
        if match:
            return match.group(1)
        return None

    def _fetch_youtube_captions(self, youtube_id: str) -> Optional[str]:
        try:
            watch_html = self.client.get_text(
                f"https://www.youtube.com/watch?v={youtube_id}",
                headers={"User-Agent": YOUTUBE_BROWSER_USER_AGENT},
            )
            api_key = self._extract_youtube_innertube_api_key(watch_html)
            player = self.client.post_json(
                f"https://www.youtube.com/youtubei/v1/player?key={api_key}",
                payload={"context": YOUTUBE_ANDROID_CONTEXT, "videoId": youtube_id},
                headers={"User-Agent": YOUTUBE_ANDROID_USER_AGENT},
            )
            captions = player.get("captions", {}).get("playerCaptionsTracklistRenderer", {})
            track = self._select_youtube_caption_track(captions)
            if track is None or not track.get("baseUrl"):
                return None
            return (
                self.client.get_text(
                    track["baseUrl"],
                    headers={"User-Agent": YOUTUBE_ANDROID_USER_AGENT},
                ).strip()
                or None
            )
        except Exception:
            pass
        return None

    def _extract_youtube_innertube_api_key(self, html: str) -> str:
        match = re.search(r'"INNERTUBE_API_KEY":\s*"([A-Za-z0-9_-]+)"', html)
        if not match:
            raise ValueError("Could not extract YouTube INNERTUBE_API_KEY")
        return match.group(1)

    def _select_youtube_caption_track(self, captions: Dict) -> Optional[Dict]:
        tracks = captions.get("captionTracks", []) or []
        if not tracks:
            return None

        preferred_languages = ("en-US", "en")
        for language_code in preferred_languages:
            for track in tracks:
                if track.get("languageCode") == language_code and track.get("kind") != "asr":
                    return track
        for language_code in preferred_languages:
            for track in tracks:
                if track.get("languageCode") == language_code:
                    return track
        return tracks[0]
