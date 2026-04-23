from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import List, Optional, Tuple

from mentions_engine.models import Transcript, TranscriptSegment
from mentions_engine.transcripts.normalize import normalize_text_block
from mentions_engine.utils import stable_hash, utc_now_iso


def strip_tags(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&#8217;", "'")
    text = text.replace("&amp;", "&")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_official_whitehouse_transcript(
    artifact_id: str,
    html: str,
) -> Tuple[Transcript, List[TranscriptSegment]]:
    text = strip_tags(html)
    segments_raw = split_speaker_segments(text)
    normalized = normalize_text_block(text)

    transcript = Transcript(
        transcript_id=f"transcript-{stable_hash(artifact_id + ':official')[:16]}",
        artifact_id=artifact_id,
        transcript_type="official",
        version="1",
        created_at=utc_now_iso(),
        generator="parse_official_whitehouse_transcript",
        language="en",
        quality_score=1.0,
        is_machine_generated=False,
        is_human_supplied=True,
        raw_text=text,
        normalized_text=normalized,
        metadata={},
    )

    segments: List[TranscriptSegment] = []
    for index, (speaker_label, segment_text) in enumerate(segments_raw):
        norm = normalize_text_block(segment_text)
        segments.append(
            TranscriptSegment(
                segment_id=f"segment-{stable_hash(transcript.transcript_id + ':' + str(index))[:16]}",
                transcript_id=transcript.transcript_id,
                start_time_seconds=None,
                end_time_seconds=None,
                speaker_id=None,
                speaker_label=speaker_label,
                channel=None,
                text=segment_text,
                normalized_text=norm,
                confidence=None,
                word_count=len(segment_text.split()),
                metadata={"source": "official_transcript"},
            )
        )

    if not segments:
        segments.append(
            TranscriptSegment(
                segment_id=f"segment-{stable_hash(transcript.transcript_id + ':full')[:16]}",
                transcript_id=transcript.transcript_id,
                start_time_seconds=None,
                end_time_seconds=None,
                speaker_id=None,
                speaker_label=None,
                channel=None,
                text=text,
                normalized_text=normalized,
                confidence=None,
                word_count=len(text.split()),
                metadata={"source": "official_transcript", "fallback": True},
            )
        )

    return transcript, segments


def split_speaker_segments(text: str) -> List[Tuple[str, str]]:
    pattern = re.compile(r"\b(MS\. LEAVITT|Q|THE PRESS|MR\. [A-Z-]+|MS\. [A-Z-]+):", re.IGNORECASE)
    matches = list(pattern.finditer(text))
    if not matches:
        return []

    segments: List[Tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        speaker = match.group(1).upper()
        segment_text = text[start:end].strip()
        if segment_text:
            segments.append((speaker, segment_text))
    return segments


def parse_youtube_captions(
    artifact_id: str,
    raw_text: str,
) -> Tuple[Transcript, List[TranscriptSegment]]:
    raw_text_stripped = raw_text.strip()
    chunks = []
    if raw_text_stripped.startswith("["):
        payload = json.loads(raw_text_stripped)
        chunks = [
            (
                str(item.get("start", "")),
                str(item.get("duration", "")),
                item.get("text", ""),
            )
            for item in payload
        ]
    elif raw_text_stripped.startswith("<?xml") or raw_text_stripped.startswith("<timedtext"):
        chunks = _parse_youtube_timedtext(raw_text)
    else:
        chunks = re.findall(r'<text start="([^"]+)"(?: dur="([^"]+)")?[^>]*>(.*?)</text>', raw_text, re.DOTALL)
    raw_lines: List[str] = []
    segments: List[TranscriptSegment] = []

    transcript_id = f"transcript-{stable_hash(artifact_id + ':youtube-captions')[:16]}"

    for index, (start_value, duration_value, text_value) in enumerate(chunks):
        text = unescape(re.sub(r"<[^>]+>", " ", text_value))
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        raw_lines.append(text)
        start_seconds = float(start_value) if start_value else None
        duration_seconds = float(duration_value) if duration_value else None
        end_seconds = None
        if start_seconds is not None and duration_seconds is not None:
            end_seconds = start_seconds + duration_seconds
        normalized = normalize_text_block(text)
        speaker_label = infer_briefing_speaker_label(text)
        segments.append(
            TranscriptSegment(
                segment_id=f"segment-{stable_hash(transcript_id + ':' + str(index))[:16]}",
                transcript_id=transcript_id,
                start_time_seconds=start_seconds,
                end_time_seconds=end_seconds,
                speaker_id=None,
                speaker_label=speaker_label,
                channel=None,
                text=text,
                normalized_text=normalized,
                confidence=None,
                word_count=len(text.split()),
                metadata={
                    "source": "youtube_captions",
                    "speaker_inference": "heuristic" if speaker_label else "none",
                },
            )
        )

    raw_text = "\n".join(raw_lines)
    transcript = Transcript(
        transcript_id=transcript_id,
        artifact_id=artifact_id,
        transcript_type="captions",
        version="1",
        created_at=utc_now_iso(),
        generator="parse_youtube_captions",
        language="en",
        quality_score=0.75,
        is_machine_generated=True,
        is_human_supplied=False,
        raw_text=raw_text,
        normalized_text=normalize_text_block(raw_text),
        metadata={},
    )

    return transcript, segments


def _parse_youtube_timedtext(raw_text: str) -> List[Tuple[str, str, str]]:
    root = ET.fromstring(raw_text.strip())
    chunks: List[Tuple[str, str, str]] = []
    for node in root.findall(".//p"):
        start_ms = node.attrib.get("t")
        duration_ms = node.attrib.get("d")
        text = _timedtext_node_text(node)
        if not start_ms:
            continue
        start_seconds = str(float(start_ms) / 1000.0)
        duration_seconds = str(float(duration_ms) / 1000.0) if duration_ms else ""
        chunks.append((start_seconds, duration_seconds, text))
    return chunks


def _timedtext_node_text(node: ET.Element) -> str:
    parts: List[str] = []
    if node.text:
        parts.append(node.text)
    for child in node:
        if child.text:
            parts.append(child.text)
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def infer_briefing_speaker_label(text: str) -> Optional[str]:
    clean = text.strip()
    if not clean:
        return None

    # YouTube auto-captions often prefix speaker turns with >>.
    if clean.startswith(">>"):
        clean = clean[2:].strip()

    lower = clean.lower()

    # A lightweight reporter-question heuristic for transcript-free briefings.
    question_starters = (
        "can you",
        "could you",
        "will you",
        "would you",
        "do you",
        "does the president",
        "did the president",
        "is the president",
        "what",
        "why",
        "when",
        "where",
        "who",
        "how",
    )

    if "?" in clean and (
        lower.startswith(question_starters)
        or lower.startswith("and")
        or lower.startswith("on")
        or lower.startswith("just")
    ):
        return "Q"

    return "MS. LEAVITT"
