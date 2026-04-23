from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import ModelBase


@dataclass
class MarketOutcome(ModelBase):
    outcome_id: str
    market_id: str
    event_id: Optional[str]
    observed_at: str
    resolved_yes: bool
    outcome_source: str
    label_kind: str
    notes: str
    metadata: Dict[str, Any] = field(default_factory=dict)
