from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol

from mentions_engine.models import Event, SourceArtifact, Transcript, TranscriptSegment
from mentions_engine.profiles import SpeakerProfile, default_whitehouse_speaker_profiles, get_speaker_profile
from mentions_engine.transcripts.parsers import (
    parse_official_whitehouse_transcript,
    parse_youtube_captions,
)


@dataclass
class TranscriptBuildResult:
    transcript: Transcript
    segments: List[TranscriptSegment]


class TranscriptBuilder(Protocol):
    name: str

    def supports(self, event: Event, artifact: SourceArtifact) -> bool:
        ...

    def build(self, event: Event, artifact: SourceArtifact, raw_text: str) -> TranscriptBuildResult:
        ...


class WhiteHouseTranscriptBuilder:
    name = "whitehouse"

    def supports(self, event: Event, artifact: SourceArtifact) -> bool:
        if event.event_type != "white_house_press_briefing":
            return False
        return artifact.artifact_type in {"official_transcript", "closed_captions"}

    def build(self, event: Event, artifact: SourceArtifact, raw_text: str) -> TranscriptBuildResult:
        speaker_profiles = _speaker_profiles_for_event(event)
        if artifact.artifact_type == "official_transcript":
            transcript, segments = parse_official_whitehouse_transcript(
                artifact.artifact_id,
                raw_text,
                speaker_profiles=speaker_profiles,
            )
            return TranscriptBuildResult(transcript=transcript, segments=segments)
        if artifact.artifact_type == "closed_captions":
            transcript, segments = parse_youtube_captions(
                artifact.artifact_id,
                raw_text,
                speaker_profiles=speaker_profiles,
            )
            return TranscriptBuildResult(transcript=transcript, segments=segments)
        raise ValueError(f"Unsupported artifact_type for builder {self.name}: {artifact.artifact_type}")


def _speaker_profiles_for_event(event: Event) -> tuple[SpeakerProfile, ...]:
    speaker_key = event.metadata.get("speaker_key")
    if isinstance(speaker_key, str) and speaker_key:
        try:
            return (get_speaker_profile(speaker_key),)
        except KeyError:
            pass
    return default_whitehouse_speaker_profiles()


def read_artifact_text(artifact: SourceArtifact) -> str:
    if not artifact.local_path:
        raise ValueError(f"Artifact has no local_path: {artifact.artifact_id}")
    return Path(artifact.local_path).read_text(encoding="utf-8")
