from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, Optional, Sequence

from mentions_engine.models import Market
from mentions_engine.profiles import (
    EventSourceProfile,
    SpeakerProfile,
    WHITE_HOUSE_PRESS_BRIEFING,
    default_whitehouse_speaker_profiles,
)
from mentions_engine.utils import normalize_text


WhiteHouseSpeakerRule = SpeakerProfile


class WhiteHouseMentionMarketParser:
    name = "whitehouse-mention"

    _DEFAULT_TARGET_PHRASE_PATTERNS = (
        r"\b(?:say|mention|call|refer to|use)\s+(?:the phrase\s+)?(.+?)\s+(?:during|in|at)\s+the\b",
        r"\b(?:says|mentions|calls|refers to|uses)\s+(?:the phrase\s+)?(.+?)\s+(?:during|in|at)\b",
        r"\bwhat will [^?]+?\s+(?:say|mention|call|refer to)\s+(?:about\s+)?(.+?)\??$",
    )
    def __init__(
        self,
        speaker_rules: Optional[Sequence[WhiteHouseSpeakerRule]] = None,
        target_phrase_patterns: Optional[Sequence[str]] = None,
        event_profile: EventSourceProfile = WHITE_HOUSE_PRESS_BRIEFING,
    ):
        self.speaker_rules = tuple(speaker_rules or default_whitehouse_speaker_profiles())
        self.target_phrase_patterns = tuple(target_phrase_patterns or self._DEFAULT_TARGET_PHRASE_PATTERNS)
        self.event_profile = event_profile

    def parse(self, market: Market) -> Optional[Market]:
        haystack = " ".join(
            value
            for value in [
                market.title,
                market.subtitle,
                market.rules_text,
                market.source_text,
                market.metadata.get("event_title"),
                market.metadata.get("event_subtitle"),
            ]
            if value
        )
        normalized = normalize_text(haystack)
        if not normalized:
            return None

        speaker_rule = self._detect_speaker(normalized)
        if speaker_rule is None:
            return None
        if not self._looks_like_mention_market(normalized):
            return None

        target_phrase = self._extract_target_phrase(market, speaker_rule)
        if target_phrase is None:
            return None

        event_date = self._infer_event_date(market)
        metadata = dict(market.metadata)
        metadata.update(
            {
                "market_family": "mention",
                "mention_parser": self.name,
                "source_family": self.event_profile.source_family,
                "event_family": self.event_profile.event_family,
                "event_type": self.event_profile.event_type,
                "speaker_name": speaker_rule.canonical_name,
                "speaker_key": speaker_rule.speaker_key,
                "participants": speaker_rule.canonical_name,
                "target_phrase": target_phrase,
                "target_terms": [target_phrase],
                "target_phrase_normalized": normalize_text(target_phrase),
                "briefing_scope": self._infer_briefing_scope(normalized),
                "event_title": metadata.get("event_title")
                or self._build_event_title(speaker_rule.canonical_name, event_date),
                "event_date": event_date,
                "mapping_strategy": "speaker_first_market_parse",
            }
        )
        market.metadata = metadata
        return market

    def _detect_speaker(self, normalized_text: str) -> Optional[WhiteHouseSpeakerRule]:
        for rule in self.speaker_rules:
            for alias in rule.aliases:
                if normalize_text(alias) in normalized_text:
                    return rule
        return None

    def _looks_like_mention_market(self, normalized_text: str) -> bool:
        has_briefing_context = any(
            phrase in normalized_text
            for phrase in self.event_profile.mention_context_phrases
        )
        has_utterance_context = any(
            phrase in normalized_text
            for phrase in self.event_profile.utterance_context_phrases
        )
        return has_briefing_context and has_utterance_context

    def _extract_target_phrase(self, market: Market, speaker_rule: WhiteHouseSpeakerRule) -> Optional[str]:
        candidates = [value for value in [market.title, market.subtitle, market.rules_text, market.source_text] if value]
        for candidate in candidates:
            quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', candidate)
            flattened = [value for pair in quoted for value in pair if value]
            if flattened:
                return self._clean_target_phrase(flattened[0])

        if market.subtitle:
            subtitle_value = self._clean_target_phrase(market.subtitle)
            if subtitle_value:
                return subtitle_value

        patterns = tuple(speaker_rule.target_phrase_patterns) or self.target_phrase_patterns
        for candidate in candidates:
            extracted = self._extract_with_patterns(candidate, patterns)
            if extracted:
                return extracted
        return None

    def _extract_with_patterns(self, candidate: str, patterns: Iterable[str]) -> Optional[str]:
        for pattern in patterns:
            match = re.search(pattern, candidate, flags=re.IGNORECASE)
            if match:
                value = self._clean_target_phrase(match.group(1))
                if value:
                    return value
        return None

    def _clean_target_phrase(self, value: str) -> str:
        value = re.sub(r"\s+", " ", value).strip(" ?.,:;\"'")
        value = re.sub(r"^(?:the phrase|phrase)\s+", "", value, flags=re.IGNORECASE)
        return value.strip()

    def _infer_briefing_scope(self, normalized_text: str) -> str:
        scope_patterns = (
            ("today", "today"),
            ("tomorrow", "tomorrow"),
            ("this week", "this_week"),
            ("next press briefing", "next_briefing"),
            ("next briefing", "next_briefing"),
        )
        for needle, label in scope_patterns:
            if needle in normalized_text:
                return label
        return "unspecified"

    def _infer_event_date(self, market: Market) -> Optional[str]:
        values = [
            market.metadata.get("scheduled_start_time"),
            market.metadata.get("event_date"),
            market.close_time,
            market.settlement_time,
        ]
        for value in values:
            if not value:
                continue
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed.date().isoformat()
            except ValueError:
                continue
        return None

    def _build_event_title(self, speaker_name: str, event_date: Optional[str]) -> str:
        if event_date:
            return f"{speaker_name} White House press briefing {event_date}"
        return f"{speaker_name} White House press briefing"
