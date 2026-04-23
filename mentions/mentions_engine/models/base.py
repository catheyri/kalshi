from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict


@dataclass
class ModelBase:
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
