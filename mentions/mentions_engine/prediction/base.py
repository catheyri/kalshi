from __future__ import annotations

from typing import Dict, Protocol

from mentions_engine.models import Event, Market, Opportunity, PriceSnapshot, ProbabilityEstimate


class FeatureExtractor(Protocol):
    name: str

    def extract(self, market: Market, event: Event) -> Dict[str, object]:
        ...


class PricingModel(Protocol):
    name: str

    def estimate(
        self,
        market: Market,
        event: Event,
        features: Dict[str, object],
    ) -> ProbabilityEstimate:
        ...


class OpportunityScorer(Protocol):
    name: str

    def score(
        self,
        market: Market,
        estimate: ProbabilityEstimate,
        snapshot: PriceSnapshot,
    ) -> Opportunity:
        ...
