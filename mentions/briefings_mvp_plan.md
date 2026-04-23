# White House Briefings MVP Plan

This document defines a concrete MVP plan for building the first working slice of the mentions engine using White House press briefings as the initial event family.

The immediate target is Karoline Leavitt press briefings because they are:

- frequent
- publicly visible
- often available as official video and sometimes official transcript
- likely to have enough historical material to validate the pipeline

This is intentionally a transcript-first first vertical, not a special-purpose one-off tool.

The implementation should follow the generalized architecture described in [mentionsengine.md](mentionsengine.md) and should be designed so that the same code can later support:

- other White House briefings
- other government briefings
- earnings calls
- podcasts
- YouTube videos
- sports broadcasts after feed capture is added

## MVP Goal

Build a working end-to-end system that can:

1. discover briefings
2. acquire transcript or video sources
3. produce normalized, timestamp-aware text
4. compile mention-market rules into structured criteria
5. detect candidate mentions
6. use those historical materials to build labels and predictive features
7. emit auditable evidence bundles
8. support probability estimates for upcoming briefing markets

The MVP does not need to place trades or produce a sophisticated forecasting model.

It should first prove that we can build the reusable research and prediction backbone cleanly on one narrow event family.

## Why This Event Type Is A Good Starting Point

Karoline Leavitt briefings are a good initial target because they sit in a favorable middle ground:

- easier than sports because public sources exist
- more dynamic and frequent than many earnings calls
- conversational enough to stress the mention matcher
- likely to include recurring topic and phrase patterns
- close enough to real Kalshi-style mention resolution to be useful

They are also useful because the event family supports multiple source paths:

- official White House transcript pages when available
- official White House video pages when transcript pages are missing
- third-party transcript pages such as Rev
- our own ASR as a fallback

That makes this a strong source family for building:

- source-priority logic
- transcript reconciliation logic
- evidence handling

## Product Framing

The MVP should be framed as a `prediction-oriented research and data-prep engine`, not yet as a full trading system.

The output we want at the end of the first milestone is:

- a structured event catalog
- structured source artifacts
- transcripts and transcript segments
- compiled rules
- historical mention labels and evidence bundles
- comparable-event features
- initial probability estimates for upcoming briefing markets

If that works well, we can later add:

- richer phrase frequency features
- stronger fair-value estimation
- opportunity scoring

## Scope

### In Scope

- official briefing discovery
- transcript and video source acquisition
- transcript fallback strategy
- text normalization
- rule compilation for mention markets
- phrase matching
- decision and evidence output
- historical backfill over a moderate archive
- a lightweight command-line workflow

### Out Of Scope For The First MVP

- trading automation
- order placement
- complex probabilistic pricing
- real-time low-latency alerting
- generalized live feed capture
- full web UI

## Source Strategy

The source strategy should explicitly separate:

- `research source`
- `settlement source`

Even if the White House transcript is eventually used as the main source, the system should preserve the distinction because later event families will depend on it.

### Source Priority Order

For this event family, the first-pass source priority should be:

1. official White House transcript page
2. official White House video page
3. third-party transcript page
4. locally generated transcript from official video

The MVP should record:

- what sources were discovered
- which source was selected
- why it was selected
- what fallback path was used

## Proposed Architecture Slice

This MVP should implement the following reusable modules.

### 1. Event Discovery

Responsibilities:

- find briefing events from White House listings
- extract event title, date, URL, and source metadata
- deduplicate and normalize event identities

Expected outputs:

- `Event`
- `SourceArtifact` stubs

### 2. Source Acquisition

Responsibilities:

- fetch official transcript pages when present
- fetch official video-page metadata when present
- fetch third-party transcript pages when configured
- download or reference replay media when needed

Expected outputs:

- stored source artifacts
- provenance metadata
- content hashes where practical

### 3. Transcript Ingestion

Responsibilities:

- parse official White House transcript HTML
- parse third-party transcript HTML
- unify multiple transcript shapes into one canonical schema
- attach timestamps when available
- keep untimestamped text usable when no timings exist

Expected outputs:

- `Transcript`
- `TranscriptSegment`

### 4. ASR Fallback

Responsibilities:

- download or extract audio from official video if no transcript is available
- transcribe with Whisper or equivalent
- produce timestamped transcript segments
- optionally produce word timings

Expected outputs:

- fallback `Transcript`
- segment and token timing data

### 5. Normalization

Responsibilities:

- normalize casing and punctuation
- tokenize consistently
- preserve original text
- preserve normalized text
- support multiple normalization profiles if needed later

Expected outputs:

- normalized transcript and segments

### 6. Rule Compilation

Responsibilities:

- represent a mention market in structured form
- support exact term matching
- support allowed variants
- support exclusions
- support speaker restrictions
- support source restrictions

Expected outputs:

- `CompiledRule`

### 7. Mention Matching

Responsibilities:

- scan transcript segments for candidate matches
- classify match type
- decide whether the candidate counts
- emit evidence

Expected outputs:

- `CandidateMention`
- `MentionDecision`
- `EvidenceBundle`

## Attack Plan

The engineering attack should be staged so that each step validates a reusable part of the engine.

### Phase 1: Skeleton And Schemas

Build:

- project layout
- core models
- storage layer
- CLI entry points

Deliverable:

- repository code structure with canonical models and serialization working

### Phase 2: White House Event Discovery

Build:

- event scraper for White House briefing pages and/or video listing pages
- event normalization logic
- incremental sync

Deliverable:

- a local catalog of briefing events with stable IDs

### Phase 3: Transcript Ingestion

Build:

- parser for official White House transcript pages
- parser for White House video pages
- parser for Rev transcripts as fallback or comparison
- canonical transcript serialization

Deliverable:

- a local corpus of transcripts and transcript segments

### Phase 4: Rule Engine MVP

Build:

- rule schema
- simple rule compiler
- exact and variant phrase matcher
- evidence generation

Deliverable:

- mention detection over historical briefings for a small set of phrases

### Phase 5: ASR Fallback

Build:

- audio extraction path from official videos
- Whisper transcription path
- transcript comparison tools

Deliverable:

- one path for recovering usable text even when transcripts are missing

### Phase 6: Evaluation And Hardening

Build:

- regression test cases
- phrase-level gold examples
- source-selection tests
- manual review outputs

Deliverable:

- confidence that the pipeline is stable enough to extend to other event types

## Data Model Usage For This MVP

This MVP should use the generalized canonical models from [mentionsengine.md](mentionsengine.md), with only minimal event-family-specific metadata.

At minimum, implement:

- `Event`
- `SourceArtifact`
- `Transcript`
- `TranscriptSegment`
- `CompiledRule`
- `CandidateMention`
- `MentionDecision`
- `EvidenceBundle`

Event-family-specific fields should live in `metadata`, not in bespoke top-level schemas unless they clearly generalize.

## Storage Plan

For the MVP, storage should be simple and robust.

Recommended first-pass approach:

- SQLite for structured entities
- local filesystem for raw source artifacts and downloaded media
- JSON exports for debugging and manual inspection

Why:

- easy local development
- easy reproducibility
- simple to inspect manually
- enough for moderate backfills

Suggested storage layout:

```text
data/
  raw/
    whitehouse/
    rev/
    media/
  derived/
    transcripts/
    evidence/
  app.db
```

## CLI Plan

The first interface should be a CLI rather than a UI.

Suggested commands:

```bash
python -m mentions_engine.sync_events
python -m mentions_engine.fetch_sources
python -m mentions_engine.build_transcripts
python -m mentions_engine.compile_rules
python -m mentions_engine.run_matcher
python -m mentions_engine.export_evidence
```

The exact names can change, but the workflow should stay modular.

## Evaluation Strategy

We need a small but high-quality labeled evaluation set early.

### Build A Phrase Test Set

Create a test corpus with:

- phrases that definitely appear
- phrases that definitely do not appear
- phrases that appear only in quoted questions
- phrases that appear in reporter questions but not in Leavitt’s answers
- phrases with pluralization or tense variations

This is important because the first real challenge is not finding words in text.

The first real challenge is determining what counts under market-like rules.

### Compare Source Variants

Where multiple source variants exist, compare:

- official White House transcript
- Rev transcript
- locally generated ASR transcript

We want to learn:

- what disagreements look like
- which sources are missing words
- how often timing differs
- whether fallback ASR is sufficient for mention detection

## Rule Engine Design For This MVP

The MVP should support a deliberately narrow but reusable rule language.

### Rule Features To Support First

- exact phrase
- allowed variants
- disallowed variants
- speaker scope
- source scope
- quotation policy
- case sensitivity
- stemming toggle

### Rule Example

```json
{
  "market_id": "demo-karoline-border-crisis",
  "target_terms": ["border crisis"],
  "allowed_variants": ["the border crisis"],
  "disallowed_variants": [],
  "speaker_scope": ["primary_speaker"],
  "source_scope": ["official_transcript", "official_video_asr"],
  "quotation_policy": "include",
  "case_sensitivity": false,
  "stemming_policy": "off",
  "requires_exact_phrase": true
}
```

This should not be overfit to White House briefings.

It should be general enough to extend to:

- earnings-call questions versus management remarks
- podcast host versus guest
- sports play-by-play versus sideline reporter

## Source Parsing Strategy

### Official White House Transcript Pages

Parser needs to:

- extract date and title
- extract transcript body
- preserve speaker labels
- preserve question/answer structure where possible
- convert transcript blocks into transcript segments

### White House Video Pages

Parser needs to:

- extract title, date, and page metadata
- find the embedded or linked media source when possible
- preserve the page as a source artifact even if media extraction is deferred

### Rev Transcript Pages

Parser needs to:

- extract transcript text
- preserve speaker labels and timestamps
- mark the transcript as third-party

## ASR Strategy

The ASR path should be treated as a reusable fallback module.

For this MVP:

- use Whisper or faster-whisper
- prefer segment timestamps at minimum
- add word timestamps if practical
- keep the raw transcript and the normalized transcript separate

The ASR module should not be White-House-specific.

It should accept any audio artifact and return canonical transcript objects.

## Review And Audit Strategy

Every final mention decision should be explainable.

Each evidence bundle should include:

- event ID
- source artifact ID
- transcript ID
- segment ID
- matched text
- normalized text
- speaker label
- timestamp if available
- rule ID
- decision reason

We should be able to inspect any decision by hand without reconstructing the entire pipeline mentally.

## Why Python Is A Good Choice

Python is a good choice for this phase.

Reasons:

- excellent HTML parsing ecosystem
- excellent HTTP and scraping tooling
- strong CLI ergonomics
- excellent ASR ecosystem, especially Whisper and faster-whisper
- excellent local-data tooling with SQLite, pandas, and text-processing libraries
- fast iteration for research-heavy workflows

Practical Python libraries likely useful here:

- `httpx` for HTTP
- `selectolax` or `BeautifulSoup` for HTML parsing
- `pydantic` for schemas
- `sqlalchemy` or `sqlite-utils` for persistence
- `typer` for CLI
- `faster-whisper` or `openai-whisper` for transcription
- `rapidfuzz` for fuzzy or variant matching
- `orjson` for fast serialization

## When Python Would Not Be Optimal

Python would be less optimal if:

- we were building a very high-throughput always-on low-latency capture system
- we needed ultra-efficient concurrent media ingestion at scale
- we were building a desktop-native media-processing app

In those cases, Rust or Go could be more attractive for some components.

### Why Not Rust First

Rust has real advantages:

- strong correctness guarantees
- good performance
- great for long-running ingestion daemons

But for this MVP, it is probably not the optimal first choice because:

- the main work is source acquisition, parsing, ASR integration, and research iteration
- Python’s library ecosystem is much stronger and faster to iterate in for this phase
- the bottlenecks are more likely to be network and transcription time than raw compute in our own code

### Recommended Language Strategy

Recommended plan:

- build the MVP in Python
- keep interfaces clean and data models explicit
- move specific hot paths or persistent capture services to Rust later if needed

This gives us:

- fastest iteration now
- minimal regret later

## Suggested Project Structure

```text
mentions_engine/
  __init__.py
  cli.py
  config.py
  models/
    events.py
    sources.py
    transcripts.py
    rules.py
    decisions.py
  storage/
    db.py
    repositories.py
  discovery/
    whitehouse.py
  acquisition/
    fetch.py
    whitehouse.py
    rev.py
  transcripts/
    parsers.py
    asr.py
    normalize.py
  rules/
    compiler.py
  matcher/
    candidates.py
    decisions.py
    evidence.py
  evaluation/
    fixtures.py
    tests.py
```

This structure is general enough to absorb future adapters without rewriting the core system.

## Concrete First Milestone

The first true milestone should be:

`Given one Karoline Leavitt briefing and one phrase rule, the system can fetch the source, build a transcript, detect whether the phrase appears, and export an evidence bundle.`

That is the smallest slice that proves the architecture is real.

## Concrete Second Milestone

The second milestone should be:

`Backfill a corpus of recent Karoline Leavitt briefings, run a small library of rules across all of them, and export a searchable table of mention decisions.`

That is the point where this stops being a toy and becomes a usable research tool.

## Open Questions

- How complete is the official transcript coverage relative to the video archive?
- How often do White House transcript pages differ materially from Rev or ASR?
- How should reporter questions versus Leavitt responses be represented in speaker scope?
- What minimum rule language is enough to cover real mention markets cleanly without premature complexity?
- At what point do we introduce probability estimation rather than pure resolution logic?

## Recommended Next Steps

1. Create the Python package skeleton and canonical model definitions.
2. Implement White House event discovery and source acquisition.
3. Build transcript parsers for official pages and Rev.
4. Add the first rule compiler and matcher.
5. Evaluate on a small labeled phrase set.
6. Add ASR fallback only after the transcript-first path works cleanly.

## Implementation Status

This section records the current implementation state of the MVP in the repository.

### What Has Been Built

The first reusable Python slice now exists under [mentions_engine](mentions_engine).

Implemented components:

- package scaffolding and project config
- canonical models aligned with [mentionsengine.md](mentionsengine.md)
- SQLite storage for events, source artifacts, transcripts, transcript segments, and compiled rules
- CLI entry points for initialization, syncing, source fetching, transcript building, rule compilation, and rule execution
- White House video-library discovery for Karoline Leavitt briefings
- White House source acquisition for video pages
- YouTube caption fallback extraction from embedded White House video pages
- official transcript parsing
- YouTube caption parsing into canonical transcript segments
- simple speaker-aware heuristics for briefing captions
- first rule compiler
- first mention matcher
- decision and evidence bundle generation
- unit tests for discovery, parsing, and matching

### Files Added Or Updated

Core implementation:

- [pyproject.toml](pyproject.toml)
- [mentions_engine/cli.py](mentions_engine/cli.py)
- [mentions_engine/config.py](mentions_engine/config.py)
- [mentions_engine/http.py](mentions_engine/http.py)
- [mentions_engine/utils.py](mentions_engine/utils.py)
- [mentions_engine/discovery/whitehouse.py](mentions_engine/discovery/whitehouse.py)
- [mentions_engine/acquisition/whitehouse.py](mentions_engine/acquisition/whitehouse.py)
- [mentions_engine/transcripts/parsers.py](mentions_engine/transcripts/parsers.py)
- [mentions_engine/rules/compiler.py](mentions_engine/rules/compiler.py)
- [mentions_engine/matcher/simple.py](mentions_engine/matcher/simple.py)
- [mentions_engine/storage/db.py](mentions_engine/storage/db.py)

Test and example artifacts:

- [tests/test_whitehouse_discovery.py](tests/test_whitehouse_discovery.py)
- [tests/test_transcript_parser.py](tests/test_transcript_parser.py)
- [tests/test_matcher.py](tests/test_matcher.py)
- [examples/karoline_border_crisis_rule.json](examples/karoline_border_crisis_rule.json)

### Live Workflow That Now Works

The following live workflow has been validated:

1. initialize the SQLite database
2. sync White House briefing events from the live White House video library
3. fetch source artifacts for a specific briefing
4. extract YouTube auto-captions from the White House embedded video when no clean official transcript page is resolved
5. build a timed transcript from those captions
6. run a mention rule against the transcript
7. emit candidates, decisions, and evidence with timestamps

The prediction-oriented workflow that the project is moving toward is:

1. ingest open or upcoming briefing markets
2. map each market to the future briefing event
3. backfill comparable historical briefings
4. record real market outcomes when available
5. estimate `YES` probability and fair value for open markets

Storage principle:

- keep fetched source files in `data/raw/`
- keep normalized speaker-attributed transcripts in `data/canonical/`
- keep feature tables and model-ready exports in `data/derived/`
- never discard canonical transcript text after feature extraction

Validated on:

- `whitehouse-press-secretary-karoline-leavitt-briefs-members-of-the-media-mar-30-2026`

Relevant artifact and transcript objects observed during validation:

- caption artifact: `artifact-231351f4fce2f4bb`
- timed transcript: `transcript-45f40fce472c3225`

### Command Paths Verified

These commands are working:

```bash
cd mentions
python3 -m mentions_engine.cli init-db
python3 -m mentions_engine.cli ingest-markets <markets_json_path>
python3 -m mentions_engine.cli ingest-kalshi-market-tickers <ticker> [ticker...]
python3 -m mentions_engine.cli ingest-kalshi-event-tickers <event_ticker> [event_ticker...]
python3 -m mentions_engine.cli ingest-kalshi-category <category> [max_pages]
python3 -m mentions_engine.cli ingest-whitehouse-mention-market-tickers <ticker> [ticker...]
python3 -m mentions_engine.cli ingest-whitehouse-mention-event-tickers <event_ticker> [event_ticker...]
python3 -m mentions_engine.cli ingest-whitehouse-mention-category <category> [max_pages]
python3 -m mentions_engine.cli import-outcomes <outcomes_json_path>
python3 -m mentions_engine.cli import-kalshi-outcomes <ticker> [ticker...]
python3 -m mentions_engine.cli map-market <market_id>
python3 -m mentions_engine.cli estimate-market <market_id>
python3 -m mentions_engine.cli list-markets open
python3 -m mentions_engine.cli export-dataset <output_path> [status]
python3 -m mentions_engine.cli sync-events whitehouse
python3 -m mentions_engine.cli fetch-sources <event_id>
python3 -m mentions_engine.cli build-transcript <artifact_id>
python3 -m mentions_engine.cli compile-rule <rule_json_path> <output_path>
python3 -m mentions_engine.cli run-rule <event_id> <artifact_id> <transcript_id> <rule_json_path>
```

### Testing Status

The local unit test suite currently covers:

- White House discovery parsing
- official transcript parsing
- YouTube caption parsing
- simple speaker inference
- matcher behavior for `primary_speaker`

Current verification command:

```bash
PYTHONPYCACHEPREFIX=/tmp/mentions_pycache python3 -m unittest discover -s tests -p 'test_*.py'
```

## Current Limitations

### Official Transcript Discovery Is Improved But Still Not Fully Solved

The acquisition layer no longer grabs the generic `Briefings & Statements` archive root as though it were a transcript page.

Current behavior:

- try to find a matching `briefings-statements` link on the video page
- if none is present, query White House search and look for matching `briefings-statements` links
- if still none is found, fall back to the embedded YouTube captions

This is a real improvement, but it does not yet guarantee discovery of all official transcript pages if the White House site structure is inconsistent.

### Caption-Side Speaker Attribution Is Heuristic

For YouTube-caption-derived briefings, speaker labeling is still approximate.

Current behavior:

- reporter-like question segments are heuristically labeled `Q`
- most other segments are labeled `MS. LEAVITT`

This is enough to support early `primary_speaker` filtering, but it is not yet a robust diarization or turn-segmentation system.

### No Rev Ingestion Yet

The MVP plan called for optional Rev fallback or comparison.

That has not yet been implemented.

### No ASR Fallback Yet

The current fallback is:

- White House video page
- embedded YouTube captions

We have not yet added:

- media download
- audio extraction
- Whisper or faster-whisper transcription

### No Probability Model Yet

The current system resolves mentions and emits evidence.

It does not yet estimate:

- mention probability
- fair value
- trade opportunity ranking

## Updated Next Steps

The most important next steps are now:

1. strengthen official transcript discovery
2. add Rev ingestion and transcript comparison
3. add ASR fallback from official video sources
4. improve question/answer turn inference for caption-derived briefings
5. backfill a larger corpus of briefings into the local database
6. build a labeled evaluation set of target phrases and rule outcomes
7. introduce a lightweight research layer for phrase frequencies across the corpus

## Recommended Immediate Development Order

### 1. Backfill Corpus

Use the current working pipeline to ingest all discovered Karoline Leavitt briefings and persist:

- events
- artifacts
- transcripts
- segments

This gives us a usable research dataset quickly.

### 2. Add Rev Adapter

Implement a third-party transcript adapter so we can compare:

- official White House transcript pages
- YouTube captions
- Rev transcripts

This is important for understanding transcription drift and evidence reliability.

### 3. Add ASR Module

Implement a reusable audio-to-transcript path that takes any media artifact and returns canonical transcript objects.

That will preserve the generality of the engine and prepare it for:

- other briefings
- earnings calls
- podcasts
- sports later

### 4. Improve Rule Evaluation

Expand the rule engine beyond exact matching to support:

- better speaker restrictions
- quotation handling
- variant and exclusion logic
- segment-window reasoning

## Practical Conclusion

The MVP is now past the “architecture only” stage.

We have a live transcript-first pipeline that works on real White House briefing data and already matches the generalized mentions-engine design:

- shared models
- shared storage
- shared rules
- shared evidence output
- source-specific acquisition adapters

The next phase should focus on making the source stack more reliable and turning the current single-event proof into a corpus-level research tool.
