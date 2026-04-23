from __future__ import annotations

from typing import Any, Dict

from mentions_engine.models import CompiledRule
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
