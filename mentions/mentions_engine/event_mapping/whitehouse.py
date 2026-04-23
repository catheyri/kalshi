from __future__ import annotations

from datetime import datetime
from typing import Optional

from mentions_engine.models import Event, Market
from mentions_engine.utils import slugify


class WhiteHouseEventMapper:
    name = "whitehouse"

    def supports(self, market: Market) -> bool:
        event_type = market.metadata.get("event_type")
        if event_type == "white_house_press_briefing":
            return True
        source_family = market.metadata.get("source_family")
        return source_family == "whitehouse"

    def map(self, market: Market) -> Optional[Event]:
        if not self.supports(market):
            return None
        speaker_name = market.metadata.get("speaker_name", "White House briefing speaker")
        event_date = market.metadata.get("event_date") or self._infer_event_date(market)
        speaker_key = market.metadata.get("speaker_key") or slugify(speaker_name).replace("-", "_")
        event_id = market.event_id or market.metadata.get("event_id")
        if not event_id:
            if event_date:
                event_id = f"whitehouse-{speaker_key}-{event_date}"
            else:
                title_seed = market.metadata.get("event_title") or market.title
                event_id = f"whitehouse-{slugify(title_seed)}"
        title = market.metadata.get("event_title") or f"{speaker_name} White House press briefing"
        participants = market.metadata.get("participants", speaker_name)
        return Event(
            event_id=event_id,
            event_type="white_house_press_briefing",
            title=title,
            category="government",
            subcategory="white_house_press_briefing",
            scheduled_start_time=market.metadata.get("scheduled_start_time") or market.close_time,
            scheduled_end_time=market.metadata.get("scheduled_end_time"),
            actual_start_time=None,
            actual_end_time=None,
            participants=participants,
            broadcast_network=market.metadata.get("broadcast_network", "White House"),
            league=None,
            season=None,
            venue=market.metadata.get("venue", "White House Briefing Room"),
            source_priority="official_transcript_then_official_video_then_third_party_transcript_then_asr",
            broadcast_priority="official_transcript_first",
            metadata={
                "mapped_from_market_id": market.market_id,
                "mapping_strategy": "market_metadata",
                "speaker_name": speaker_name,
                "speaker_key": speaker_key,
                "event_date": event_date,
                "target_phrase": market.metadata.get("target_phrase"),
            },
        )

    def _infer_event_date(self, market: Market) -> Optional[str]:
        for value in [market.metadata.get("scheduled_start_time"), market.close_time, market.settlement_time]:
            if not value:
                continue
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                continue
        return None
