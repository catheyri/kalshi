from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mentions_engine.utils import normalize_text, slugify


@dataclass(frozen=True)
class SpeakerProfile:
    canonical_name: str
    aliases: tuple[str, ...]
    key: Optional[str] = None
    transcript_labels: tuple[str, ...] = ()
    caption_speaker_markers: tuple[tuple[str, str], ...] = ()
    discovery_slug_terms: tuple[str, ...] = ()
    market_series_tickers: tuple[str, ...] = ()
    stopwords: tuple[str, ...] = ()
    target_phrase_patterns: tuple[str, ...] = ()

    @property
    def speaker_key(self) -> str:
        return self.key or slugify(self.canonical_name).replace("-", "_")

    @property
    def primary_transcript_label(self) -> Optional[str]:
        return self.transcript_labels[0] if self.transcript_labels else None

    def matches_text(self, text: str) -> bool:
        normalized = normalize_text(text)
        return any(normalize_text(alias) in normalized for alias in self.aliases)

    def matches_slug(self, value: str) -> bool:
        normalized = value.lower()
        return any(term.lower() in normalized for term in self.discovery_slug_terms)

    def normalized_transcript_labels(self) -> set[str]:
        return {label.strip().upper() for label in self.transcript_labels if label.strip()}


@dataclass(frozen=True)
class EventSourceProfile:
    key: str
    event_type: str
    category: str
    subcategory: str
    source_family: str
    event_family: str
    broadcast_network: str
    venue: Optional[str]
    source_priority: str
    broadcast_priority: Optional[str]
    transcript_url_patterns: tuple[str, ...]
    transcript_title_patterns: tuple[str, ...]
    video_url_patterns: tuple[str, ...]
    video_title_patterns: tuple[str, ...]
    mention_context_phrases: tuple[str, ...]
    utterance_context_phrases: tuple[str, ...]


KAROLINE_LEAVITT = SpeakerProfile(
    canonical_name="Karoline Leavitt",
    key="karoline_leavitt",
    aliases=(
        "karoline leavitt",
        "press secretary karoline leavitt",
        "white house press secretary karoline leavitt",
        "leavitt",
    ),
    transcript_labels=(
        "MS. LEAVITT",
        "KAROLINE LEAVITT",
        "PRESS SECRETARY LEAVITT",
    ),
    caption_speaker_markers=(
        ("karoline leavitt:", "MS. LEAVITT"),
        ("ms. leavitt:", "MS. LEAVITT"),
        ("press secretary leavitt:", "MS. LEAVITT"),
    ),
    discovery_slug_terms=("karoline-leavitt",),
    market_series_tickers=("KXSECPRESSMENTION",),
    stopwords=("karoline", "leavitt"),
)


WHITE_HOUSE_PRESS_BRIEFING = EventSourceProfile(
    key="white_house_press_briefing",
    event_type="white_house_press_briefing",
    category="government",
    subcategory="white_house_press_briefing",
    source_family="whitehouse",
    event_family="white_house_press_briefing",
    broadcast_network="White House",
    venue="White House Briefing Room",
    source_priority="official_transcript_then_official_video_then_third_party_transcript_then_asr",
    broadcast_priority="official_transcript_first",
    transcript_url_patterns=("press-briefing",),
    transcript_title_patterns=("press briefing",),
    video_url_patterns=(
        "briefs-members-of-the-media",
        "brief-members-of-the-media",
        "briefs-members-of-the-new-media",
        "press-briefing-by-press-secretary",
        "press-briefing-by-the-white-house-press-secretary",
        "holds-a-press-briefing",
    ),
    video_title_patterns=(
        "briefs members of the media",
        "brief members of the media",
        "briefs members of the new media",
        "press briefing by press secretary",
        "press briefing by the white house press secretary",
        "holds a press briefing",
    ),
    mention_context_phrases=(
        "briefing",
        "press briefing",
        "white house briefing",
        "members of the media",
    ),
    utterance_context_phrases=(
        "what will",
        "will ",
        "say ",
        "mention ",
        "utter ",
        "call ",
        "refer to ",
        "use the phrase",
    ),
)


SPEAKER_PROFILES = {
    KAROLINE_LEAVITT.speaker_key: KAROLINE_LEAVITT,
}

EVENT_SOURCE_PROFILES = {
    WHITE_HOUSE_PRESS_BRIEFING.key: WHITE_HOUSE_PRESS_BRIEFING,
}


def get_speaker_profile(speaker_key: str) -> SpeakerProfile:
    try:
        return SPEAKER_PROFILES[speaker_key]
    except KeyError as exc:
        raise KeyError(f"Unknown speaker profile: {speaker_key}") from exc


def get_event_source_profile(profile_key: str) -> EventSourceProfile:
    try:
        return EVENT_SOURCE_PROFILES[profile_key]
    except KeyError as exc:
        raise KeyError(f"Unknown event source profile: {profile_key}") from exc


def default_whitehouse_speaker_profiles() -> tuple[SpeakerProfile, ...]:
    return (KAROLINE_LEAVITT,)
