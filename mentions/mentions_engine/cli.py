from __future__ import annotations

import json
import sys
from pathlib import Path

from mentions_engine.acquisition import WhiteHouseAcquisition
from mentions_engine.config import default_paths
from mentions_engine.discovery import WhiteHouseDiscovery
from mentions_engine.matcher import build_evidence, find_candidates, make_decisions
from mentions_engine.rules import compile_rule_from_json
from mentions_engine.storage import Database
from mentions_engine.transcripts import parse_official_whitehouse_transcript, parse_youtube_captions
from mentions_engine.utils import dump_json


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "Usage: python3 -m mentions_engine.cli <command> [args]\n"
            "Commands: init-db, sync-whitehouse, fetch-whitehouse-sources, build-transcript, compile-rule, run-rule",
            file=sys.stderr,
        )
        return 1

    command = argv.pop(0)
    paths = default_paths()
    paths.ensure()
    db = Database(paths.db_path)

    if command == "init-db":
        db.initialize()
        print(paths.db_path)
        return 0

    if command == "sync-whitehouse":
        db.initialize()
        discovery = WhiteHouseDiscovery()
        result = discovery.discover_press_briefings()
        for event in result.events:
            db.upsert_event(event)
        for artifact in result.artifacts:
            db.upsert_source_artifact(artifact)
        print(json.dumps({"events": len(result.events), "artifacts": len(result.artifacts)}, indent=2))
        return 0

    if command == "fetch-whitehouse-sources":
        db.initialize()
        if not argv:
            print("fetch-whitehouse-sources requires <event_id>", file=sys.stderr)
            return 1
        event_id = argv.pop(0)
        artifacts = db.list_artifacts_for_event(event_id)
        video_artifact = next((row for row in artifacts if row["provider"] == "whitehouse.gov"), None)
        if video_artifact is None or not video_artifact["uri"]:
            print(f"No White House video artifact found for {event_id}", file=sys.stderr)
            return 1
        acquisition = WhiteHouseAcquisition(paths)
        result = acquisition.fetch_event_sources(event_id, video_artifact["uri"])
        for artifact in result.artifacts:
            db.upsert_source_artifact(artifact)
        print(json.dumps({"event_id": event_id, "artifacts": len(result.artifacts)}, indent=2))
        return 0

    if command == "build-transcript":
        db.initialize()
        if not argv:
            print("build-transcript requires <artifact_id>", file=sys.stderr)
            return 1
        artifact_id = argv.pop(0)
        artifact = db.get_artifact(artifact_id)
        if artifact is None:
            print(f"Artifact not found: {artifact_id}", file=sys.stderr)
            return 1
        local_path = artifact["local_path"]
        if not local_path:
            print(f"Artifact has no local_path: {artifact_id}", file=sys.stderr)
            return 1
        html = Path(local_path).read_text(encoding="utf-8")
        if artifact["artifact_type"] == "official_transcript":
            transcript, segments = parse_official_whitehouse_transcript(artifact_id, html)
        elif artifact["artifact_type"] == "closed_captions":
            transcript, segments = parse_youtube_captions(artifact_id, html)
        else:
            print(f"Unsupported artifact_type for transcript building: {artifact['artifact_type']}", file=sys.stderr)
            return 1
        db.upsert_transcript(transcript)
        db.replace_segments(transcript.transcript_id, segments)
        print(
            json.dumps(
                {
                    "transcript_id": transcript.transcript_id,
                    "segments": len(segments),
                },
                indent=2,
            )
        )
        return 0

    if command == "compile-rule":
        db.initialize()
        if len(argv) < 2:
            print("compile-rule requires <rule_json_path> <output_path>", file=sys.stderr)
            return 1
        rule_path = Path(argv[0])
        output_path = Path(argv[1])
        payload = json.loads(rule_path.read_text(encoding="utf-8"))
        rule = compile_rule_from_json(payload)
        db.upsert_compiled_rule(rule)
        dump_json(output_path, rule.to_dict())
        print(output_path)
        return 0

    if command == "run-rule":
        db.initialize()
        if len(argv) < 4:
            print("run-rule requires <event_id> <artifact_id> <transcript_id> <rule_json_path>", file=sys.stderr)
            return 1
        event_id, artifact_id, transcript_id, rule_path = argv[:4]
        transcript = db.get_transcript(transcript_id)
        artifact = db.get_artifact(artifact_id)
        if transcript is None or artifact is None:
            print("Artifact or transcript not found", file=sys.stderr)
            return 1
        segments = db.list_segments(transcript_id)
        rule_payload = json.loads(Path(rule_path).read_text(encoding="utf-8"))
        rule = compile_rule_from_json(rule_payload)
        candidates = find_candidates(
            market_id=rule.market_id,
            rule=rule,
            event_id=event_id,
            transcript_id=transcript_id,
            segments=[
                _segment_from_row(row)
                for row in segments
            ],
        )
        decisions = make_decisions(candidates)
        evidence = [
            build_evidence(
                artifact_id=artifact_id,
                transcript_id=transcript_id,
                segments=[_segment_from_row(row) for row in segments],
                candidate=candidate,
                decision=decision,
            ).to_dict()
            for candidate, decision in zip(candidates, decisions)
        ]
        print(
            json.dumps(
                {
                    "candidates": [candidate.to_dict() for candidate in candidates],
                    "decisions": [decision.to_dict() for decision in decisions],
                    "evidence": evidence,
                },
                indent=2,
            )
        )
        return 0

    print(f"Unknown command: {command}", file=sys.stderr)
    return 1


def _segment_from_row(row):
    from mentions_engine.models import TranscriptSegment

    return TranscriptSegment(
        segment_id=row["segment_id"],
        transcript_id=row["transcript_id"],
        start_time_seconds=row["start_time_seconds"],
        end_time_seconds=row["end_time_seconds"],
        speaker_id=row["speaker_id"],
        speaker_label=row["speaker_label"],
        channel=row["channel"],
        text=row["text"],
        normalized_text=row["normalized_text"],
        confidence=row["confidence"],
        word_count=row["word_count"],
        metadata=json.loads(row["metadata_json"]),
    )


if __name__ == "__main__":
    raise SystemExit(main())
