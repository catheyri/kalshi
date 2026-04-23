from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from mentions_engine.models import CompiledRule, Market
from mentions_engine.utils import stable_hash, utc_now_iso


def compile_rule_from_json(payload: Dict[str, Any]) -> CompiledRule:
    market_id = payload["market_id"]
    compiled_rule_id = f"rule-{stable_hash(market_id + ':' + str(payload.get('target_terms', [])))[:16]}"
    return CompiledRule(
        compiled_rule_id=compiled_rule_id,
        market_id=market_id,
        target_terms=list(payload.get("target_terms", [])),
        allowed_variants=list(payload.get("allowed_variants", [])),
        disallowed_variants=list(payload.get("disallowed_variants", [])),
        speaker_scope=list(payload.get("speaker_scope", [])),
        time_scope=dict(payload.get("time_scope", {})),
        source_scope=list(payload.get("source_scope", [])),
        feed_scope=list(payload.get("feed_scope", [])),
        quotation_policy=payload.get("quotation_policy", "include"),
        caption_policy=payload.get("caption_policy", "include"),
        partial_word_policy=payload.get("partial_word_policy", "reject"),
        case_sensitivity=bool(payload.get("case_sensitivity", False)),
        stemming_policy=payload.get("stemming_policy", "off"),
        counting_threshold=int(payload.get("counting_threshold", 1)),
        requires_exact_phrase=bool(payload.get("requires_exact_phrase", True)),
        notes=payload.get("notes", ""),
        compiled_at=utc_now_iso(),
    )


def parse_market_from_json(payload: Dict[str, Any]) -> Optional[Market]:
    market_payload = payload.get("market")
    if not isinstance(market_payload, dict):
        return None
    return Market(
        market_id=market_payload["market_id"],
        event_id=market_payload.get("event_id"),
        series_id=market_payload.get("series_id"),
        title=market_payload.get("title", market_payload["market_id"]),
        subtitle=market_payload.get("subtitle"),
        status=market_payload.get("status"),
        close_time=market_payload.get("close_time"),
        settlement_time=market_payload.get("settlement_time"),
        yes_bid=market_payload.get("yes_bid"),
        yes_ask=market_payload.get("yes_ask"),
        no_bid=market_payload.get("no_bid"),
        no_ask=market_payload.get("no_ask"),
        volume=market_payload.get("volume"),
        open_interest=market_payload.get("open_interest"),
        rules_text=market_payload.get("rules_text"),
        rules_summary_text=market_payload.get("rules_summary_text"),
        source_text=market_payload.get("source_text"),
        url=market_payload.get("url"),
        last_updated_at=market_payload.get("last_updated_at"),
        metadata=dict(market_payload.get("metadata", {})),
    )


def compile_bundle_from_json(payload: Dict[str, Any]) -> Tuple[CompiledRule, Optional[Market]]:
    return compile_rule_from_json(payload), parse_market_from_json(payload)
