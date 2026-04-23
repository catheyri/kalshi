from __future__ import annotations

import json
import math
from typing import Dict, List

from mentions_engine.models import (
    Event,
    Market,
    Opportunity,
    PriceSnapshot,
    ProbabilityEstimate,
)
from mentions_engine.storage import Database
from mentions_engine.utils import stable_hash, utc_now_iso


class HistoricalOutcomeFeatureExtractor:
    name = "historical-outcomes"

    def __init__(self, db: Database):
        self.db = db

    def extract(self, market: Market, event: Event) -> Dict[str, object]:
        compiled_rule = self.db.get_compiled_rule_for_market(market.market_id)
        signature = self._rule_signature(None if compiled_rule is None else json.loads(compiled_rule["payload_json"]))
        outcome_rows = [
            row
            for row in self.db.list_market_outcome_training_rows(event.event_type)
            if self._rule_signature_from_row(row["rule_payload_json"]) == signature
            and row["market_event_id"] != market.event_id
        ]
        used_true_outcomes = len(outcome_rows) > 0
        positives = sum(1 for row in outcome_rows if row["resolved_yes"])

        if not used_true_outcomes and signature is not None:
            decision_rows = [
                row
                for row in self.db.list_accepted_decision_training_rows(event.event_type)
                if self._rule_signature_from_row(row["rule_payload_json"]) == signature
                and row["event_id"] != market.event_id
            ]
            total_events = len({row["event_id"] for row in decision_rows})
            positives = total_events
            sample_size = total_events
            source = "derived_mentions"
        else:
            sample_size = len(outcome_rows)
            source = "market_outcomes"

        return {
            "sample_size": sample_size,
            "positive_count": positives,
            "negative_count": max(sample_size - positives, 0),
            "source": source,
            "used_true_outcomes": used_true_outcomes,
        }

    def _rule_signature_from_row(self, payload_json: object) -> object:
        if not payload_json:
            return None
        return self._rule_signature(json.loads(payload_json))

    def _rule_signature(self, payload: object) -> object:
        if not isinstance(payload, dict):
            return None
        keep = {
            "target_terms": payload.get("target_terms", []),
            "allowed_variants": payload.get("allowed_variants", []),
            "disallowed_variants": payload.get("disallowed_variants", []),
            "speaker_scope": payload.get("speaker_scope", []),
            "time_scope": payload.get("time_scope", {}),
            "source_scope": payload.get("source_scope", []),
            "feed_scope": payload.get("feed_scope", []),
            "quotation_policy": payload.get("quotation_policy", "include"),
            "caption_policy": payload.get("caption_policy", "include"),
            "partial_word_policy": payload.get("partial_word_policy", "reject"),
            "case_sensitivity": payload.get("case_sensitivity", False),
            "stemming_policy": payload.get("stemming_policy", "off"),
            "counting_threshold": payload.get("counting_threshold", 1),
            "requires_exact_phrase": payload.get("requires_exact_phrase", True),
        }
        return json.dumps(keep, sort_keys=True)


class HistoricalFrequencyPricingModel:
    name = "historical-frequency"
    version = "1"

    def estimate(
        self,
        market: Market,
        event: Event,
        features: Dict[str, object],
    ) -> ProbabilityEstimate:
        sample_size = int(features.get("sample_size", 0))
        positive_count = int(features.get("positive_count", 0))
        probability_yes = (positive_count + 1.0) / (sample_size + 2.0)
        fair_yes_price = int(round(probability_yes * 100))
        fair_no_price = 100 - fair_yes_price
        uncertainty = 1.0 / math.sqrt(sample_size + 1.0)
        band = min(0.49, 1.96 * uncertainty * 0.15)
        summary = (
            f"Estimated from {sample_size} historical examples using {features.get('source', 'unknown')}."
        )
        return ProbabilityEstimate(
            estimate_id=f"estimate-{stable_hash(market.market_id + ':' + utc_now_iso())[:16]}",
            market_id=market.market_id,
            event_id=event.event_id,
            generated_at=utc_now_iso(),
            probability_yes=probability_yes,
            fair_yes_price=fair_yes_price,
            fair_no_price=fair_no_price,
            model_name=self.name,
            model_version=self.version,
            input_summary=summary,
            uncertainty_score=uncertainty,
            confidence_band_low=max(0.0, probability_yes - band),
            confidence_band_high=min(1.0, probability_yes + band),
            notes="Simple historical-frequency baseline. Prefer true resolved outcomes when available.",
            metadata={
                "sample_size": sample_size,
                "positive_count": positive_count,
                "feature_source": features.get("source"),
                "used_true_outcomes": bool(features.get("used_true_outcomes")),
            },
        )


class SimpleOpportunityScorer:
    name = "simple-edge"

    def score(
        self,
        market: Market,
        estimate: ProbabilityEstimate,
        snapshot: PriceSnapshot,
    ) -> Opportunity:
        market_yes = snapshot.yes_ask if snapshot.yes_ask is not None else snapshot.yes_bid
        if market_yes is None:
            side = "none"
            edge = None
            fair_price = estimate.fair_yes_price
        elif estimate.fair_yes_price > market_yes:
            side = "yes"
            edge = estimate.fair_yes_price - market_yes
            fair_price = estimate.fair_yes_price
        else:
            no_market = snapshot.no_ask if snapshot.no_ask is not None else snapshot.no_bid
            fair_price = estimate.fair_no_price
            if no_market is None:
                side = "none"
                edge = None
            elif estimate.fair_no_price > no_market:
                side = "no"
                edge = estimate.fair_no_price - no_market
            else:
                side = "none"
                edge = None

        sample_size = int(estimate.metadata.get("sample_size", 0))
        data_quality = min(sample_size / 10.0, 1.0)
        priority = None if edge is None else edge * max(data_quality, 0.1)
        return Opportunity(
            opportunity_id=f"opportunity-{stable_hash(market.market_id + ':' + estimate.estimate_id)[:16]}",
            market_id=market.market_id,
            generated_at=utc_now_iso(),
            side=side,
            market_price=None if side == "none" else (market_yes if side == "yes" else (snapshot.no_ask if snapshot.no_ask is not None else snapshot.no_bid)),
            fair_price=fair_price,
            edge_cents=edge,
            liquidity_score=None if snapshot.volume is None else min(snapshot.volume / 1000.0, 1.0),
            execution_risk_score=0.5 if edge is not None else 1.0,
            data_quality_score=data_quality,
            rule_risk_score=0.25 if estimate.metadata.get("used_true_outcomes") else 0.6,
            priority_score=priority,
            notes="Simple edge score from fair value versus current market.",
            metadata={},
        )


def snapshot_from_market(market: Market) -> PriceSnapshot:
    return PriceSnapshot(
        snapshot_id=f"snapshot-{stable_hash(market.market_id + ':' + utc_now_iso())[:16]}",
        market_id=market.market_id,
        captured_at=utc_now_iso(),
        yes_bid=market.yes_bid,
        yes_ask=market.yes_ask,
        no_bid=market.no_bid,
        no_ask=market.no_ask,
        last_price=None,
        volume=market.volume,
        open_interest=market.open_interest,
        orderbook_depth=None,
        metadata={},
    )
