from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .base import ModelBase


@dataclass
class PriceSnapshot(ModelBase):
    snapshot_id: str
    market_id: str
    captured_at: str
    yes_bid: Optional[int]
    yes_ask: Optional[int]
    no_bid: Optional[int]
    no_ask: Optional[int]
    last_price: Optional[int]
    volume: Optional[int]
    open_interest: Optional[int]
    orderbook_depth: Optional[int]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbabilityEstimate(ModelBase):
    estimate_id: str
    market_id: str
    event_id: Optional[str]
    generated_at: str
    probability_yes: float
    fair_yes_price: int
    fair_no_price: int
    model_name: str
    model_version: str
    input_summary: str
    uncertainty_score: Optional[float]
    confidence_band_low: Optional[float]
    confidence_band_high: Optional[float]
    notes: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Opportunity(ModelBase):
    opportunity_id: str
    market_id: str
    generated_at: str
    side: str
    market_price: Optional[int]
    fair_price: int
    edge_cents: Optional[int]
    liquidity_score: Optional[float]
    execution_risk_score: Optional[float]
    data_quality_score: Optional[float]
    rule_risk_score: Optional[float]
    priority_score: Optional[float]
    notes: str
    metadata: Dict[str, Any] = field(default_factory=dict)
