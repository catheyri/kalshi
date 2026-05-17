from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
import json
import re
from pathlib import Path
from typing import Iterable, Optional

from mentions_engine.profiles import (
    EventSourceProfile,
    SpeakerProfile,
    get_event_source_profile,
    get_speaker_profile,
)
from mentions_engine.storage import Database
from mentions_engine.utils import utc_now_iso


WORD_FREQUENCY_SCHEMA_VERSION = 1

TOKEN_PATTERN = re.compile(r"[a-z][a-z']*", re.IGNORECASE)
MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "can't",
    "cannot",
    "could",
    "couldn't",
    "did",
    "didn't",
    "do",
    "does",
    "doesn't",
    "doing",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "first",
    "for",
    "from",
    "further",
    "had",
    "hadn't",
    "has",
    "hasn't",
    "have",
    "haven't",
    "having",
    "he",
    "he'd",
    "he'll",
    "he's",
    "her",
    "here",
    "here's",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "house",
    "how",
    "how's",
    "get",
    "i",
    "i'd",
    "i'll",
    "i'm",
    "i've",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "itself",
    "just",
    "know",
    "let",
    "let's",
    "me",
    "more",
    "most",
    "mustn't",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "one",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "press",
    "same",
    "say",
    "said",
    "shall",
    "shan't",
    "she",
    "she'd",
    "she'll",
    "she's",
    "should",
    "shouldn't",
    "see",
    "secretary",
    "so",
    "some",
    "such",
    "than",
    "that",
    "that's",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "there's",
    "these",
    "they",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "this",
    "those",
    "thank",
    "think",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasn't",
    "we",
    "we'd",
    "we'll",
    "we're",
    "we've",
    "were",
    "weren't",
    "what",
    "what's",
    "when",
    "when's",
    "where",
    "where's",
    "which",
    "while",
    "white",
    "who",
    "who's",
    "whom",
    "why",
    "why's",
    "will",
    "with",
    "won't",
    "would",
    "wouldn't",
    "you",
    "you'd",
    "you'll",
    "you're",
    "you've",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "want",
    # Common transcript/caption noise.
    "applause",
    "going",
    "inaudible",
    "laughter",
    "look",
    "mr",
    "mrs",
    "ms",
    "music",
    "okay",
    "well",
    "um",
    "uh",
}

IRREGULAR_FORMS = {
    "children": "child",
    "feet": "foot",
    "men": "man",
    "people": "person",
    "teeth": "tooth",
    "women": "woman",
}

PROTECTED_FORMS = {
    "united",
}


@dataclass(frozen=True)
class WordFrequencyRow:
    event_id: str
    event_date: Optional[str]
    event_title: str
    transcript_id: str
    transcript_type: str
    term: str
    display_term: str
    count: int
    event_total_terms: int
    variants: dict[str, int]
    is_kalshi_market: bool
    kalshi_result: Optional[str]
    kalshi_market_id: Optional[str]
    kalshi_market_ids: list[str]
    kalshi_target_phrases: list[str]
    kalshi_results: list[str]

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_date": self.event_date,
            "event_title": self.event_title,
            "transcript_id": self.transcript_id,
            "transcript_type": self.transcript_type,
            "term": self.term,
            "display_term": self.display_term,
            "count": self.count,
            "event_total_terms": self.event_total_terms,
            "variants": self.variants,
            "is_kalshi_market": self.is_kalshi_market,
            "kalshi_result": self.kalshi_result,
            "kalshi_market_id": self.kalshi_market_id,
            "kalshi_market_ids": self.kalshi_market_ids,
            "kalshi_target_phrases": self.kalshi_target_phrases,
            "kalshi_results": self.kalshi_results,
        }


@dataclass(frozen=True)
class WordFrequencyBuildResult:
    rows: int
    events: int
    terms: int
    json_path: Optional[str]
    html_path: Optional[str]
    event_html_path: Optional[str]
    speaker_scope: str
    speaker_key: str
    speaker_name: str
    event_profile_key: str
    min_count: int


@dataclass(frozen=True)
class _TranscriptRef:
    event_id: str
    event_title: str
    participants: str
    event_metadata: dict
    actual_start_time: Optional[str]
    artifact_id: str
    artifact_type: str
    transcript_id: str
    transcript_type: str
    quality_score: Optional[float]
    segment_count: int


@dataclass(frozen=True)
class _MarketHit:
    market_id: str
    target_phrase: str
    result: str
    status: Optional[str]


def build_word_frequency_dataset(
    db: Database,
    *,
    json_path: Optional[Path] = None,
    html_path: Optional[Path] = None,
    event_html_path: Optional[Path] = None,
    speaker_scope: str = "primary",
    speaker_key: str = "karoline_leavitt",
    speaker_profile: Optional[SpeakerProfile] = None,
    event_profile_key: str = "white_house_press_briefing",
    event_profile: Optional[EventSourceProfile] = None,
    min_count: int = 1,
) -> WordFrequencyBuildResult:
    if speaker_scope not in {"primary", "all"}:
        raise ValueError("speaker_scope must be 'primary' or 'all'")
    if min_count < 1:
        raise ValueError("min_count must be >= 1")

    speaker_profile = speaker_profile or get_speaker_profile(speaker_key)
    event_profile = event_profile or get_event_source_profile(event_profile_key)
    market_records = _build_market_records(
        db,
        speaker_profile=speaker_profile,
        event_profile=event_profile,
    )
    rows = build_event_word_frequency_rows(
        db,
        speaker_scope=speaker_scope,
        speaker_profile=speaker_profile,
        event_profile=event_profile,
        min_count=min_count,
        market_records=market_records,
    )
    replace_event_word_frequencies(db, rows)

    payload = build_word_frequency_payload(
        rows,
        market_records=market_records,
        speaker_scope=speaker_scope,
        speaker_profile=speaker_profile,
        event_profile=event_profile,
        min_count=min_count,
    )
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(payload, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    if html_path is not None:
        from mentions_engine.visualization.word_frequency_explorer import render_word_frequency_explorer

        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_word_frequency_explorer(payload), encoding="utf-8")
    if event_html_path is not None:
        from mentions_engine.visualization.event_word_frequency_explorer import (
            render_event_word_frequency_explorer,
        )

        event_html_path.parent.mkdir(parents=True, exist_ok=True)
        event_html_path.write_text(
            render_event_word_frequency_explorer(payload),
            encoding="utf-8",
        )

    return WordFrequencyBuildResult(
        rows=len(rows),
        events=len({row.event_id for row in rows}),
        terms=len({row.term for row in rows}),
        json_path=None if json_path is None else str(json_path),
        html_path=None if html_path is None else str(html_path),
        event_html_path=None if event_html_path is None else str(event_html_path),
        speaker_scope=speaker_scope,
        speaker_key=speaker_profile.speaker_key,
        speaker_name=speaker_profile.canonical_name,
        event_profile_key=event_profile.key,
        min_count=min_count,
    )


def build_event_word_frequency_rows(
    db: Database,
    *,
    speaker_scope: str = "primary",
    speaker_key: str = "karoline_leavitt",
    speaker_profile: Optional[SpeakerProfile] = None,
    event_profile_key: str = "white_house_press_briefing",
    event_profile: Optional[EventSourceProfile] = None,
    min_count: int = 1,
    market_records: Optional[list[dict]] = None,
) -> list[WordFrequencyRow]:
    speaker_profile = speaker_profile or get_speaker_profile(speaker_key)
    event_profile = event_profile or get_event_source_profile(event_profile_key)
    market_records = (
        _build_market_records(db, speaker_profile=speaker_profile, event_profile=event_profile)
        if market_records is None
        else market_records
    )
    transcript_refs = _select_best_transcripts(
        _load_transcript_refs(
            db,
            speaker_profile=speaker_profile,
            event_profile=event_profile,
        )
    )
    market_index = _build_market_index(market_records)
    market_phrase_terms = {record["term"] for record in market_records if " " in record.get("term", "")}
    rows: list[WordFrequencyRow] = []

    for ref in transcript_refs:
        event_date = infer_event_date(
            event_id=ref.event_id,
            title=ref.event_title,
            actual_start_time=ref.actual_start_time,
            metadata=ref.event_metadata,
        )
        term_counts, variants, total_terms = _count_transcript_terms(
            db,
            ref.transcript_id,
            speaker_scope=speaker_scope,
            speaker_profile=speaker_profile,
            phrase_terms=market_phrase_terms,
        )
        for term, count in sorted(term_counts.items()):
            if count < min_count:
                continue
            hits = market_index.get((event_date, term), []) if event_date else []
            row = _build_row(
                ref=ref,
                event_date=event_date,
                term=term,
                count=count,
                total_terms=total_terms,
                variants=dict(sorted(variants[term].items())),
                hits=hits,
            )
            rows.append(row)
    return rows


def replace_event_word_frequencies(db: Database, rows: Iterable[WordFrequencyRow]) -> None:
    row_list = list(rows)
    with db.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS event_word_frequencies (
                event_id TEXT NOT NULL,
                event_date TEXT,
                event_title TEXT NOT NULL,
                transcript_id TEXT NOT NULL,
                transcript_type TEXT NOT NULL,
                term TEXT NOT NULL,
                display_term TEXT NOT NULL,
                count INTEGER NOT NULL,
                event_total_terms INTEGER NOT NULL,
                variants_json TEXT NOT NULL,
                is_kalshi_market INTEGER NOT NULL,
                kalshi_result TEXT,
                kalshi_market_id TEXT,
                kalshi_market_ids_json TEXT NOT NULL,
                kalshi_target_phrases_json TEXT NOT NULL,
                kalshi_results_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                PRIMARY KEY (event_id, transcript_id, term)
            );
            CREATE INDEX IF NOT EXISTS idx_event_word_frequencies_term
                ON event_word_frequencies(term);
            CREATE INDEX IF NOT EXISTS idx_event_word_frequencies_event_date
                ON event_word_frequencies(event_date);
            CREATE INDEX IF NOT EXISTS idx_event_word_frequencies_kalshi
                ON event_word_frequencies(is_kalshi_market, kalshi_result);
            """
        )
        conn.execute("DELETE FROM event_word_frequencies")
        conn.executemany(
            """
            INSERT INTO event_word_frequencies (
                event_id, event_date, event_title, transcript_id, transcript_type,
                term, display_term, count, event_total_terms, variants_json,
                is_kalshi_market, kalshi_result, kalshi_market_id, kalshi_market_ids_json,
                kalshi_target_phrases_json, kalshi_results_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.event_id,
                    row.event_date,
                    row.event_title,
                    row.transcript_id,
                    row.transcript_type,
                    row.term,
                    row.display_term,
                    row.count,
                    row.event_total_terms,
                    json.dumps(row.variants, sort_keys=True),
                    int(row.is_kalshi_market),
                    row.kalshi_result,
                    row.kalshi_market_id,
                    json.dumps(row.kalshi_market_ids, sort_keys=True),
                    json.dumps(row.kalshi_target_phrases, sort_keys=True),
                    json.dumps(row.kalshi_results, sort_keys=True),
                    json.dumps({"schema_version": WORD_FREQUENCY_SCHEMA_VERSION}, sort_keys=True),
                )
                for row in row_list
            ],
        )


def build_word_frequency_payload(
    rows: list[WordFrequencyRow],
    *,
    market_records: Optional[list[dict]] = None,
    speaker_scope: str,
    speaker_profile: SpeakerProfile,
    event_profile: EventSourceProfile,
    min_count: int,
) -> dict:
    events: dict[tuple[str, str], dict] = {}
    term_summary: dict[str, dict] = {}
    for row in rows:
        events[(row.event_id, row.transcript_id)] = {
            "event_id": row.event_id,
            "event_date": row.event_date,
            "event_title": row.event_title,
            "transcript_id": row.transcript_id,
            "transcript_type": row.transcript_type,
            "event_total_terms": row.event_total_terms,
        }
        summary = term_summary.setdefault(
            row.term,
            {
                "term": row.term,
                "display_term": row.display_term,
                "total_count": 0,
                "event_count": 0,
                "kalshi_market_event_count": 0,
                "kalshi_yes_event_count": 0,
                "kalshi_no_event_count": 0,
            },
        )
        summary["total_count"] += row.count
        summary["event_count"] += 1
        if row.is_kalshi_market:
            summary["kalshi_market_event_count"] += 1
            if row.kalshi_result == "yes":
                summary["kalshi_yes_event_count"] += 1
            elif row.kalshi_result == "no":
                summary["kalshi_no_event_count"] += 1

    return {
        "schema_version": WORD_FREQUENCY_SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "speaker_scope": speaker_scope,
        "speaker_key": speaker_profile.speaker_key,
        "speaker_name": speaker_profile.canonical_name,
        "event_profile_key": event_profile.key,
        "event_type": event_profile.event_type,
        "min_count": min_count,
        "event_count": len(events),
        "term_count": len(term_summary),
        "row_count": len(rows),
        "market_count": len(market_records or []),
        "events": sorted(
            events.values(),
            key=lambda event: (event.get("event_date") or "", event["event_id"]),
        ),
        "terms": sorted(
            term_summary.values(),
            key=lambda term: (term["total_count"], term["event_count"], term["term"]),
            reverse=True,
        ),
        "rows": [
            row.to_dict()
            for row in sorted(
                rows,
                key=lambda item: (item.event_date or "", item.event_id, item.term),
            )
        ],
        "markets": sorted(
            market_records or [],
            key=lambda item: (
                item.get("event_date") or "",
                item.get("term") or "",
                item.get("market_id") or "",
            ),
        ),
    }


def tokenize_text(text: str) -> list[str]:
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    return [match.group(0).lower().strip("'") for match in TOKEN_PATTERN.finditer(text)]


def canonicalize_word(word: str) -> str:
    word = word.lower().strip("'")
    if word.endswith("'s"):
        word = word[:-2]
    if word in PROTECTED_FORMS:
        return word
    if word in IRREGULAR_FORMS:
        return IRREGULAR_FORMS[word]
    if len(word) <= 3:
        return word

    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("ing") and len(word) > 5:
        return _normalize_base_after_suffix(word[:-3])
    if word.endswith("ed") and len(word) > 4:
        return _normalize_base_after_suffix(word[:-2])
    if word.endswith("es") and len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes", "zes", "oes")):
        return word[:-2]
    if word.endswith("s") and len(word) > 3 and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def infer_event_date(
    *,
    event_id: str,
    title: str,
    actual_start_time: Optional[str],
    metadata: dict,
) -> Optional[str]:
    for value in [title, event_id]:
        parsed = _extract_date_from_text(value)
        if parsed is not None:
            return parsed.isoformat()
    for key in ["event_date", "published_at", "published_label", "source_url"]:
        parsed = _coerce_date(metadata.get(key))
        if parsed is not None:
            return parsed.isoformat()
    parsed = _coerce_date(actual_start_time)
    return None if parsed is None else parsed.isoformat()


def market_terms_from_phrase(phrase: str) -> set[str]:
    terms: set[str] = set()
    for variant in re.split(r"\s*/\s*|\bor\b", phrase):
        variant = re.sub(r"\([^)]*\)", " ", variant)
        variant = variant.replace("&", " and ")
        variant_terms = []
        for token in tokenize_text(variant):
            term = canonicalize_word(token)
            if term and len(term) > 1:
                variant_terms.append(term)
        if len(variant_terms) == 1:
            if variant_terms[0] not in STOPWORDS:
                terms.add(variant_terms[0])
        elif len(variant_terms) > 1:
            terms.add(" ".join(variant_terms))
    return terms


def _normalize_base_after_suffix(base: str) -> str:
    if len(base) > 3 and base[-1] == base[-2] and base[-1] not in "aeiou" and not base.endswith("ff"):
        base = base[:-1]
    if len(base) > 3 and base.endswith("i"):
        base = base[:-1] + "y"
    if len(base) > 3 and base.endswith(("at", "iv", "iz")):
        return base + "e"
    return base


def _select_best_transcripts(refs: list[_TranscriptRef]) -> list[_TranscriptRef]:
    by_event: dict[str, list[_TranscriptRef]] = defaultdict(list)
    for ref in refs:
        by_event[ref.event_id].append(ref)
    selected = []
    for event_refs in by_event.values():
        selected.append(
            sorted(
                event_refs,
                key=lambda ref: (
                    _transcript_type_priority(ref.transcript_type),
                    -(ref.quality_score or 0.0),
                    -ref.segment_count,
                    ref.transcript_id,
                ),
            )[0]
        )
    return sorted(selected, key=lambda ref: ref.event_id)


def _transcript_type_priority(transcript_type: str) -> int:
    if transcript_type == "official":
        return 0
    if transcript_type == "captions":
        return 1
    return 2


def _load_transcript_refs(
    db: Database,
    *,
    speaker_profile: SpeakerProfile,
    event_profile: EventSourceProfile,
) -> list[_TranscriptRef]:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT
                e.event_id,
                e.title AS event_title,
                e.participants,
                e.actual_start_time,
                e.metadata_json AS event_metadata_json,
                sa.artifact_id,
                sa.artifact_type,
                t.transcript_id,
                t.transcript_type,
                t.quality_score,
                COUNT(ts.segment_id) AS segment_count
            FROM transcripts t
            JOIN source_artifacts sa ON sa.artifact_id = t.artifact_id
            JOIN events e ON e.event_id = sa.event_id
            LEFT JOIN transcript_segments ts ON ts.transcript_id = t.transcript_id
            WHERE e.event_type = ?
            GROUP BY
                e.event_id,
                e.title,
                e.participants,
                e.actual_start_time,
                e.metadata_json,
                sa.artifact_id,
                sa.artifact_type,
                t.transcript_id,
                t.transcript_type,
                t.quality_score
            """,
            (event_profile.event_type,),
        ).fetchall()
    refs: list[_TranscriptRef] = []
    for row in rows:
        event_metadata = json.loads(row["event_metadata_json"])
        if not _event_matches_speaker_profile(
            event_metadata,
            event_title=row["event_title"],
            participants=row["participants"],
            speaker_profile=speaker_profile,
        ):
            continue
        refs.append(
            _TranscriptRef(
                event_id=row["event_id"],
                event_title=row["event_title"],
                participants=row["participants"],
                event_metadata=event_metadata,
                actual_start_time=row["actual_start_time"],
                artifact_id=row["artifact_id"],
                artifact_type=row["artifact_type"],
                transcript_id=row["transcript_id"],
                transcript_type=row["transcript_type"],
                quality_score=row["quality_score"],
                segment_count=int(row["segment_count"]),
            )
        )
    return refs


def _event_matches_speaker_profile(
    metadata: dict,
    *,
    event_title: str,
    participants: str,
    speaker_profile: SpeakerProfile,
) -> bool:
    speaker_key = metadata.get("speaker_key")
    if isinstance(speaker_key, str) and speaker_key:
        return speaker_key == speaker_profile.speaker_key

    text_candidates = [
        metadata.get("speaker_name"),
        metadata.get("participants"),
        participants,
        event_title,
    ]
    return any(
        isinstance(value, str) and value and speaker_profile.matches_text(value)
        for value in text_candidates
    )


def _count_transcript_terms(
    db: Database,
    transcript_id: str,
    *,
    speaker_scope: str,
    speaker_profile: SpeakerProfile,
    phrase_terms: Iterable[str] = (),
) -> tuple[Counter[str], dict[str, Counter[str]], int]:
    counts: Counter[str] = Counter()
    variants: dict[str, Counter[str]] = defaultdict(Counter)
    phrase_patterns = _phrase_patterns_by_length(phrase_terms)
    stopwords = STOPWORDS | set(speaker_profile.stopwords)
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT speaker_label, text
            FROM transcript_segments
            WHERE transcript_id = ?
            ORDER BY COALESCE(start_time_seconds, 0), segment_id
            """,
            (transcript_id,),
        ).fetchall()
    for row in rows:
        if speaker_scope == "primary" and not _is_primary_speaker(row["speaker_label"], speaker_profile):
            continue
        tokens = tokenize_text(row["text"])
        _count_phrase_terms(tokens, phrase_patterns, counts, variants)
        for token in tokens:
            if len(token) <= 1 or token in stopwords:
                continue
            term = canonicalize_word(token)
            if len(term) <= 1 or term in stopwords:
                continue
            counts[term] += 1
            variants[term][token] += 1
    return counts, variants, sum(counts.values())


def _phrase_patterns_by_length(phrase_terms: Iterable[str]) -> dict[int, dict[tuple[str, ...], str]]:
    patterns: dict[int, dict[tuple[str, ...], str]] = defaultdict(dict)
    for term in phrase_terms:
        parts = tuple(part for part in term.split() if part)
        if len(parts) > 1:
            patterns[len(parts)][parts] = term
    return patterns


def _count_phrase_terms(
    tokens: list[str],
    phrase_patterns: dict[int, dict[tuple[str, ...], str]],
    counts: Counter[str],
    variants: dict[str, Counter[str]],
) -> None:
    if not tokens or not phrase_patterns:
        return
    canonical_tokens = [canonicalize_word(token) for token in tokens]
    for length, patterns in phrase_patterns.items():
        if len(canonical_tokens) < length:
            continue
        for index in range(0, len(canonical_tokens) - length + 1):
            term = patterns.get(tuple(canonical_tokens[index : index + length]))
            if term is None:
                continue
            counts[term] += 1
            variants[term][" ".join(tokens[index : index + length])] += 1


def _is_primary_speaker(speaker_label: Optional[str], speaker_profile: SpeakerProfile) -> bool:
    if speaker_label is None:
        return False
    normalized = speaker_label.strip().upper()
    if not normalized:
        return False
    return normalized in speaker_profile.normalized_transcript_labels()


def _build_market_index(market_records: Iterable[dict]) -> dict[tuple[str, str], list[_MarketHit]]:
    index: dict[tuple[str, str], list[_MarketHit]] = defaultdict(list)
    for record in market_records:
        event_date = record.get("event_date")
        term = record.get("term")
        if not event_date or not term:
            continue
        index[(event_date, term)].append(
            _MarketHit(
                market_id=record["market_id"],
                target_phrase=record["target_phrase"],
                result=record["result"],
                status=record.get("status"),
            )
        )
    return index


def _build_market_records(
    db: Database,
    *,
    speaker_profile: SpeakerProfile,
    event_profile: EventSourceProfile,
) -> list[dict]:
    records: list[dict] = []
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT market_id, event_id, status, close_time, settlement_time, subtitle, title, metadata_json
            FROM markets
            WHERE json_extract(metadata_json, '$.market_family') = 'mention'
               OR json_extract(metadata_json, '$.source_family') = ?
               OR json_extract(metadata_json, '$.event_family') = ?
               OR market_id LIKE 'KXSECPRESSMENTION%'
            """,
            (event_profile.source_family, event_profile.event_family),
        ).fetchall()

    for row in rows:
        metadata = json.loads(row["metadata_json"])
        if not _market_matches_profiles(metadata, speaker_profile=speaker_profile, event_profile=event_profile):
            continue
        event_date = _coerce_date(row["close_time"]) or _coerce_date(metadata.get("event_date"))
        if event_date is None:
            continue
        phrase = _market_target_phrase(metadata, row["subtitle"])
        if not phrase:
            continue
        result = _market_result(metadata, row["status"])
        market_terms = sorted(market_terms_from_phrase(phrase))
        market_term_key = "|".join(market_terms)
        for term in market_terms:
            records.append(
                {
                    "event_date": event_date.isoformat(),
                    "event_ticker": row["event_id"],
                    "market_id": row["market_id"],
                    "term": term,
                    "market_terms": market_terms,
                    "market_term_key": market_term_key,
                    "display_term": _market_display_term(phrase, term),
                    "target_phrase": phrase,
                    "result": result,
                    "status": row["status"],
                    "close_time": row["close_time"],
                    "settlement_time": row["settlement_time"],
                    "title": row["title"],
                }
            )
    return records


def _market_matches_profiles(
    metadata: dict,
    *,
    speaker_profile: SpeakerProfile,
    event_profile: EventSourceProfile,
) -> bool:
    speaker_key = metadata.get("speaker_key")
    if isinstance(speaker_key, str) and speaker_key and speaker_key != speaker_profile.speaker_key:
        return False
    event_family = metadata.get("event_family")
    if isinstance(event_family, str) and event_family and event_family != event_profile.event_family:
        return False
    event_type = metadata.get("event_type")
    if isinstance(event_type, str) and event_type and event_type != event_profile.event_type:
        return False
    return True


def _build_row(
    *,
    ref: _TranscriptRef,
    event_date: Optional[str],
    term: str,
    count: int,
    total_terms: int,
    variants: dict[str, int],
    hits: list[_MarketHit],
) -> WordFrequencyRow:
    # This table only contains positive transcript counts. A same-date market that resolved
    # No is therefore more likely a loose alignment, phrase, or eligibility mismatch than a
    # useful positive market label for the observed word.
    hits = [hit for hit in hits if hit.result != "no"]
    hits = sorted(hits, key=lambda hit: hit.market_id)
    market_ids = [hit.market_id for hit in hits]
    phrases = sorted({hit.target_phrase for hit in hits})
    results = sorted({hit.result for hit in hits if hit.result})
    kalshi_result = _summarize_results(results)
    display_term = _display_term(variants, term)
    return WordFrequencyRow(
        event_id=ref.event_id,
        event_date=event_date,
        event_title=ref.event_title,
        transcript_id=ref.transcript_id,
        transcript_type=ref.transcript_type,
        term=term,
        display_term=display_term,
        count=count,
        event_total_terms=total_terms,
        variants=variants,
        is_kalshi_market=bool(hits),
        kalshi_result=kalshi_result,
        kalshi_market_id=market_ids[0] if len(market_ids) == 1 else None,
        kalshi_market_ids=market_ids,
        kalshi_target_phrases=phrases,
        kalshi_results=results,
    )


def _display_term(variants: dict[str, int], fallback: str) -> str:
    if not variants:
        return fallback
    return sorted(variants.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _market_display_term(phrase: str, term: str) -> str:
    phrase = phrase.strip()
    if not phrase:
        return term
    if len(phrase) <= 32:
        return phrase
    return term


def _summarize_results(results: list[str]) -> Optional[str]:
    if not results:
        return None
    if len(results) == 1:
        return results[0]
    settled = {result for result in results if result in {"yes", "no"}}
    if len(settled) == 1 and all(result in settled or result in {"open", "unknown"} for result in results):
        return next(iter(settled))
    return "mixed"


def _market_target_phrase(metadata: dict, subtitle: Optional[str]) -> Optional[str]:
    payload = metadata.get("response_payload")
    if not isinstance(payload, dict):
        payload = {}
    custom_strike = payload.get("custom_strike")
    if not isinstance(custom_strike, dict):
        custom_strike = {}
    candidates = [
        metadata.get("target_phrase"),
        custom_strike.get("Word"),
        payload.get("yes_sub_title"),
        payload.get("no_sub_title"),
        subtitle,
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _market_result(metadata: dict, status: Optional[str]) -> str:
    payload = metadata.get("response_payload")
    if not isinstance(payload, dict):
        payload = {}
    for candidate in [metadata.get("result"), payload.get("result"), payload.get("winning_outcome")]:
        if isinstance(candidate, str) and candidate.lower() in {"yes", "no"}:
            return candidate.lower()
    status_normalized = (status or "").lower()
    if status_normalized in {"active", "open"}:
        return "open"
    return "unknown"


def _extract_date_from_text(value: str) -> Optional[date]:
    for match in re.finditer(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?[-\s]+(\d{1,2})(?:st|nd|rd|th)?[-,\s]+(\d{4})\b",
        value,
        flags=re.IGNORECASE,
    ):
        month = MONTHS[match.group(1).lower().rstrip(".")]
        return date(int(match.group(3)), month, int(match.group(2)))
    return None


def _coerce_date(value: object) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    parsed_from_text = _extract_date_from_text(text)
    if parsed_from_text is not None:
        return parsed_from_text
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None
