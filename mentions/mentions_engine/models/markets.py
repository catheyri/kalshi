from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import ModelBase


@dataclass
class Market(ModelBase):
    market_id: str
    event_id: Optional[str]
    series_id: Optional[str]
    title: str
    subtitle: Optional[str]
    status: Optional[str]
    close_time: Optional[str]
    settlement_time: Optional[str]
    yes_bid: Optional[int]
    yes_ask: Optional[int]
    no_bid: Optional[int]
    no_ask: Optional[int]
    volume: Optional[int]
    open_interest: Optional[int]
    rules_text: Optional[str]
    rules_summary_text: Optional[str]
    source_text: Optional[str]
    url: Optional[str]
    last_updated_at: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
