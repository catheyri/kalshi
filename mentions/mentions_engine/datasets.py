from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from mentions_engine.config import AppPaths
from mentions_engine.storage import Database


def write_jsonl(path: Path, rows: List[dict]) -> None:
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    path.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


class DatasetExporter:
    def __init__(self, db: Database, paths: AppPaths):
        self.db = db
        self.paths = paths

    def export_market_dataset(
        self,
        output_path: Path,
        *,
        status: Optional[str] = None,
    ) -> Dict[str, object]:
        rows = []
        for market_row in self.db.list_markets(status=status):
            rows.append(self._build_market_row(market_row["market_id"]))
        write_jsonl(output_path, rows)
        return {
            "rows": len(rows),
            "output_path": str(output_path),
            "status_filter": status,
        }

    def _build_market_row(self, market_id: str) -> dict:
        market = self.db.get_market(market_id)
        if market is None:
            raise ValueError(f"Market not found: {market_id}")
        event = None if not market["event_id"] else self.db.get_event(market["event_id"])
        rule = self.db.get_compiled_rule_for_market(market_id)
        outcomes = self.db.list_market_outcomes(market_id)
        estimate = self.db.latest_probability_estimate(market_id)
        opportunity = self.db.latest_opportunity(market_id)
        transcripts = []
        if event is not None:
            for transcript in self.db.list_transcripts_for_event(event["event_id"]):
                transcripts.append(
                    {
                        "transcript_id": transcript["transcript_id"],
                        "artifact_id": transcript["artifact_id"],
                        "transcript_type": transcript["transcript_type"],
                        "generator": transcript["generator"],
                        "quality_score": transcript["quality_score"],
                        "canonical_path": str(
                            self.paths.canonical_dir / "transcripts" / f"{transcript['transcript_id']}.json"
                        ),
                        "segment_count": self.db.count_segments(transcript["transcript_id"]),
                    }
                )
        return {
            "market": _row_to_dict(market),
            "event": None if event is None else _row_to_dict(event),
            "compiled_rule": None if rule is None else json.loads(rule["payload_json"]),
            "outcomes": [_row_to_dict(row) for row in outcomes],
            "latest_estimate": None if estimate is None else _row_to_dict(estimate),
            "latest_opportunity": None if opportunity is None else _row_to_dict(opportunity),
            "transcripts": transcripts,
        }


def _row_to_dict(row) -> dict:
    return {key: row[key] for key in row.keys()}
