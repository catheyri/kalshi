from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .base import ModelBase


@dataclass
class CompiledRule(ModelBase):
    compiled_rule_id: str
    market_id: str
    target_terms: List[str]
    allowed_variants: List[str]
    disallowed_variants: List[str]
    speaker_scope: List[str]
    time_scope: Dict[str, Any]
    source_scope: List[str]
    feed_scope: List[str]
    quotation_policy: str
    caption_policy: str
    partial_word_policy: str
    case_sensitivity: bool
    stemming_policy: str
    counting_threshold: int
    requires_exact_phrase: bool
    notes: str
    compiled_at: str
