# Mentions Engine Spec

This document defines the core architecture and product direction for a reusable mentions-market engine.

The goal is to support Kalshi mention markets across multiple event types using one common processing backbone, while allowing different data-acquisition strategies depending on how hard the underlying source data is to obtain.

## Product Thesis

Mention markets are not all equally competitive.

Markets with easy, widely available official transcripts tend to be more efficient because many participants can access the same data quickly. Markets with harder-to-obtain data, especially sports broadcasts and other live-feed events, are more attractive because the operational burden is higher and fewer participants can build robust tooling around them.

This creates a useful strategic framing:

- Easy-transcript markets are useful for early validation.
- Hard-to-source markets are more likely to offer durable edge.
- The long-term moat is likely to come more from data acquisition and rules-grade resolution logic than from generic forecasting alone.

## Core View

The same backbone should apply across most mention markets.

Once we have the underlying text or audio, the main engine is broadly the same:

1. Acquire source data.
2. Produce or ingest timestamped text.
3. Normalize text into a search- and rules-friendly representation.
4. Attribute words to the correct speaker or feed when required.
5. Compile Kalshi market rules into machine-checkable criteria.
6. Detect mentions that satisfy those criteria.
7. Estimate the probability of future mentions and convert that into fair value.
8. Compare fair value to the market and support execution.

The event-specific differences mostly live in the ingestion layer. The rest should be designed as a shared engine.

## Strategic Implications

### Why Easy Markets Matter

Transcript-rich markets such as FOMC or some podcast/video markets are useful because they:

- are easier to prototype against
- make backtesting easier
- let us validate mention-detection and rules logic quickly
- reduce early engineering uncertainty

They are not necessarily the best long-term opportunity because they are likely more competitive.

### Why Hard Markets Matter

Sports mention markets are attractive because they:

- occur frequently
- offer many repeated opportunities
- involve data that is harder to acquire and standardize
- may allow a larger operational edge

Their downsides are also clear:

- lower liquidity in some contracts
- more fragmented and feed-specific source data
- harder backtesting
- greater ambiguity around what exactly counts

The likely conclusion is that the engine should be general, but sports should be treated as a high-value long-term target rather than avoided.

## Market-Type Data Availability

There are three broad source buckets.

### 1. Transcript-First Markets

These markets often have an official or near-official transcript available.

Examples:

- FOMC / Fed press conferences
- some government speeches and hearings
- many podcasts
- many YouTube videos or keynotes

These are easiest to build against first.

### 2. Replay-Plus-Transcription Markets

These markets may not have reliable official transcripts, but replay audio or video is usually available and can be transcribed with Whisper or a similar system.

Examples:

- corporate earnings calls
- investor presentations
- conference appearances
- some interviews and long-form creator content

These are strong early targets because acquisition is practical and the downstream engine remains mostly the same.

### 3. Feed-Capture Markets

These markets usually do not have reliable public transcripts and may require capturing the exact broadcast or event feed directly.

Examples:

- sports announcer mention markets
- some live TV or entertainment broadcasts
- niche live events with no durable replay source

These are hardest operationally, but likely among the most interesting from an edge perspective.

## Data Source Map

This section catalogs practical data sources for different mention-market event types.

The goal is not just to note that a source exists, but to classify:

- whether it exposes an API
- whether it is directly fetchable with plain HTTP `GET`
- whether it is only realistically available through browser automation or manual export
- whether it is best suited as a research source, a settlement source, or both

### Source Quality Labels

- `API`: documented programmatic access exists
- `GET`: directly fetchable with ordinary HTTP requests or predictable URLs
- `App/UI`: visible in a product UI but not exposed through a stable public API
- `Capture`: requires us to record or ingest the media feed ourselves

### FOMC / Fed Press Conferences

| Source | Type | Access | Notes | Role |
|---|---|---|---|---|
| Federal Reserve meeting pages | transcript + video | `GET` | official press conference pages publish transcript PDFs and video links | `settlement_candidate`, `research_source` |
| Federal Reserve YouTube / video pages | video replay | `GET` | useful for fallback verification and timing | `research_source` |

Practical view:

- This is one of the cleanest mention-market categories.
- Official transcripts are usually available.
- Acquisition is easy and low-friction.
- Edge is likely lower because the data is easy.

### Government Hearings / Public Proceedings

| Source | Type | Access | Notes | Role |
|---|---|---|---|---|
| Congress.gov hearing transcript pages | transcript listings | `GET` | hearing transcript pages are publicly visible and can be crawled | `research_source` |
| GovInfo API | metadata + documents | `API` | official API with package metadata and document access; requires `api.data.gov` key | `research_source`, sometimes `settlement_candidate` |
| GovInfo bulk data | bulk documents | `GET` + key for API routes | useful for historical collection building | `research_source` |
| C-SPAN Video Library | transcript + video archive | `App/UI` | strong archive for public affairs content, but not a general open transcript API | `research_source` |

Practical view:

- Coverage can be very good for federal proceedings.
- Transcript formats and timing are less standardized than FOMC.
- Good source family for research and backfill.

### Earnings Calls

| Source | Type | Access | Notes | Role |
|---|---|---|---|---|
| Company investor relations pages | webcast + replay + deck | `GET` or simple page scrape | best official source for live/replay audio; transcript availability varies by issuer | `research_source`, sometimes `settlement_candidate` |
| SEC EDGAR / `data.sec.gov` | filings metadata + 8-K earnings release context | `API` + `GET` | official SEC JSON APIs help identify event timing, earnings releases, and related filings, but not call transcripts | `research_source` |
| Alpha Vantage earnings call transcript API | transcript | `API` | direct transcript endpoint by symbol and quarter | `research_source` |
| Financial Modeling Prep transcript endpoints | transcript | `API` | multiple transcript list/search endpoints | `research_source` |
| API Ninjas earnings call transcript API | transcript | `API` | GET endpoint by ticker/CIK/year/quarter | `research_source` |
| Third-party transcript vendors | transcript | varies | broad coverage but may be paid and quality varies | `research_source` |

Practical view:

- Official transcript coverage is inconsistent.
- Official audio replay coverage is usually very strong.
- This is an excellent replay-plus-transcription category.

### Podcasts

| Source | Type | Access | Notes | Role |
|---|---|---|---|---|
| Raw podcast RSS feed | metadata + audio enclosure | `GET` | core acquisition path for episode MP3/M4A and metadata | `research_source` |
| Podcasting 2.0 `podcast:transcript` tag | transcript link | `GET` when present | strongest open-web transcript path; links can point to TXT, VTT, SRT, JSON, HTML | `research_source`, sometimes `settlement_candidate` |
| Apple Podcasts transcripts | transcript | `App/UI` | Apple generates transcripts automatically, but public API access is not documented | `research_source` |
| Spotify transcripts | transcript | `App/UI` | creator-facing tooling supports transcript download/upload and RSS distribution, but not a public general-purpose transcript API | `research_source` |
| Podcast host pages | transcript + embedded player | `GET` or scrape | some creators publish transcripts openly on their own sites | `research_source` |

Practical view:

- Podcasts are often more open than they first appear.
- The best acquisition path is usually the RSS feed plus any linked transcript files.
- Apple and Spotify transcripts are strategically useful signals, but not ideal to depend on as a primary automated source.

### YouTube Videos / Livestreams / Creator Content

| Source | Type | Access | Notes | Role |
|---|---|---|---|---|
| YouTube Data API captions endpoints | caption metadata and downloads | `API` | official caption API exists, but caption download requires authorization tied to the video owner/editor | `research_source` in owned/cooperative cases |
| Public YouTube transcript extraction libraries | transcript | undocumented `GET` workflow | tools exist to fetch public/manual/auto captions without an API key, but they rely on undocumented web endpoints | `research_source` |
| Video replay via YouTube page | video replay | `GET` via normal page access and tooling | useful fallback when transcript extraction is brittle | `research_source` |

Practical view:

- Public transcript extraction is very workable in practice.
- Official API access is not sufficient for arbitrary third-party videos.
- For non-owned content, the practical route is replay plus public-caption extraction plus fallback ASR.

### TV News / Interviews / Public Affairs Broadcasts

| Source | Type | Access | Notes | Role |
|---|---|---|---|---|
| Internet Archive TV News Archive | captions + clips | `App/UI` + fetchable assets | rich archive for many TV news broadcasts | `research_source` |
| GDELT TV API | search over TV captions and context | `API` | useful for monitoring and search, especially for news mentions | `research_source` |
| Network clip pages | video clips | `GET` or scrape | often partial and not necessarily the full resolving source | `research_source` |
| C-SPAN Video Library | transcript + video | `App/UI` | strong archive for political/public-affairs TV | `research_source` |

Practical view:

- News and interview markets may be much easier than sports because caption archives exist.
- The main issue is whether the archive matches the exact airing/feed named in the rules.

### Sports Broadcasts

| Source | Type | Access | Notes | Role |
|---|---|---|---|---|
| League schedule / metadata APIs | game metadata | `API` | useful for game IDs, teams, start times, and broadcaster metadata | `research_source` |
| Broadcast metadata feeds | network/feed labels | `API` or `GET` | essential for identifying home/away/national broadcasts | `research_source` |
| Live broadcast audio/video | source media | `Capture` | usually the only robust route for announcer mention markets | `research_source`, sometimes `settlement_candidate` |
| Closed captions from the live feed | timed text | `Capture` or provider-specific | may exist, but availability and fidelity vary significantly | `research_source` |
| Replay streams | video/audio replay | `GET`, `App/UI`, or `Capture` | useful when available, but may differ from the original feed | `research_source` |

Practical view:

- This is where the edge is likely largest.
- It is also where the system will depend most on our own capture infrastructure.

## Baseball-Focused Source Inventory

Because MLB season is active and immediately useful, baseball should be treated as the first sports implementation target.

### MLB Metadata And Context Sources

| Source | What it provides | Access | Practical use |
|---|---|---|---|
| MLB Stats API `game/{gamePk}/feed/live` | live game state, play-by-play, teams, players, timing, game context | `GET` | anchor timeline for aligning commentary with events |
| MLB Stats API schedule endpoints | schedule, game IDs, timing | `GET` | event discovery and planning |
| MLB Stats API metadata endpoints | players, teams, venues, event types | `GET` | contextual features and normalization |
| Baseball Savant / Statcast | pitch-by-pitch and advanced context | `GET` via public search endpoints and tools built on them | richer context for mention modeling |
| Sportradar MLB API | schedules, play-by-play, coverage, broadcast metadata | `API` | strong commercial source for structured context |
| SportsDataIO MLB API | scores, play-by-play, news, betting data | `API` | useful commercial augmentation |
| BallDontLie MLB API | MLB stats and game data | `API` | lighter-weight commercial/freemium context source |

Important note:

- None of these appear to solve announcer-language capture directly.
- They are context feeds, not transcript feeds.

### MLB Audio / Broadcast Availability

| Source | What it provides | Access | Practical use |
|---|---|---|---|
| MLB Audio / MLB+ / MLB.TV | live and archived audio or game streams, subject to subscription and rights | `App/UI` | lawful access path to game audio where authorized |
| Broadcast metadata from MLB or commercial APIs | network/home-away feed info | `GET` or `API` | identify which announcer crew and feed matter |
| Provider/local cable or streaming replay | replay stream | `App/UI` | possible post-event review path |

The likely MLB conclusion:

- game context is easy
- exact announcer speech is hard
- building an edge requires pairing official game context with our own audio capture or legally accessible replay ingestion

### MLB Mention-Market Source Rule

Current working assumption from observed Kalshi MLB mention markets:

- the resolving source is explicitly `video`
- if a national broadcast exists, the national TV broadcast is the relevant source
- if no national broadcast exists, the home team TV broadcast is the relevant source

Practical implications:

- `MLB+` is not sufficient because it provides radio audio rather than the resolving TV booth feed
- `MLB.TV` is the relevant baseline product for broad MLB mention-market coverage
- the engine must determine the correct resolving feed before capture begins
- feed selection logic is a first-class requirement, not a secondary detail

This means the MLB ingestion workflow should begin with:

1. determine whether a national broadcast exists
2. if yes, capture the national TV feed
3. if no, capture the home team TV feed
4. preserve exact feed metadata for later audit and mention review

### NBA Playoff Mention-Market Source Options

Current working assumption for NBA playoff mention markets:

- playoff games are typically carried by national broadcast partners rather than local team feeds
- the relevant source is therefore usually easier to identify than in MLB
- the main acquisition problem is platform coverage, not home-vs-away feed selection

As of the current 2025-26 media cycle, national NBA games and playoff coverage are distributed across:

- `ABC / ESPN`
- `NBC / Peacock`
- `Prime Video`

Practical implications:

- NBA playoff sourcing is simpler than MLB because the market is usually tied to a national broadcast
- `YouTube TV` is useful for `ABC`, `ESPN`, and local `NBC` carriage where available
- `Prime Video` is required for Prime-exclusive playoff games
- `Peacock` may be useful for direct NBCUniversal streaming access

This means the NBA playoff ingestion workflow should begin with:

1. identify the official national broadcast partner for the game
2. map that game to the correct platform: `ABC/ESPN`, `NBC/Peacock`, or `Prime Video`
3. acquire or record the correct video replay or live stream
4. preserve platform and broadcast metadata for later audit and mention review

### YouTube TV As A Source

YouTube TV is attractive because it provides:

- broad carriage of major national sports channels
- unlimited DVR storage
- TV Everywhere login support for some network sites

Practical implications:

- for games on supported linear channels, YouTube TV DVR may be the cleanest lawful replay source
- TV Everywhere access may allow capture or review from network-native sites after authenticating with YouTube TV
- this may reduce reliance on direct capture from the YouTube TV web player itself

Important limitations:

- YouTube TV does not solve `Prime Video` games
- rights restrictions can still make some sporting events unavailable
- a stable public API for extracting recordings or direct media URLs was not identified

### Existing YouTube TV Capture Approaches

No clean public extractor or stable documented API for YouTube TV recording was identified.

The practical approaches appear to be:

1. use YouTube TV DVR as the replay source
2. where useful, authenticate into supported network sites using TV Everywhere
3. if direct automated extraction is unavailable, use lawful local capture from an authorized playback session

Open-source and community-visible patterns suggest:

- `OBS Studio` is the main fallback for capture from an authorized playback session
- `FFmpeg` remains useful for post-processing, remuxing, and audio extraction after capture
- some applications and playback contexts produce black-screen behavior, in which case `display capture` is often used instead of more direct capture modes

Current practical conclusion:

- YouTube TV is best treated as a `lawful playback and DVR source`, not as a clean programmable media API
- if this path is used, the first realistic workflow is likely `record in DVR -> replay in authorized browser/app session -> capture/extract audio locally`
- truly headless capture from YouTube TV should be treated as unproven

## Sports Capture Workflows

For sports mention markets, the core engineering problem is often not data modeling but lawful feed acquisition.

The broad workflow described in open-source communities is:

1. acquire a stream URL or authorized playback source
2. record the stream or screen/audio in real time
3. preserve exact timestamps and feed identifiers
4. extract audio
5. transcribe and review candidate mentions

### Common Tooling Mentioned In Open Source Communities

| Tool | What it does | Access pattern | Relevance |
|---|---|---|---|
| Streamlink | CLI/library that extracts supported live streams and can write output to a player or filesystem | local tool | strong base tool for lawful stream recording workflows |
| FFmpeg | records, remuxes, segments, transcodes, and extracts audio from live media streams | local tool | core building block for any ingestion pipeline |
| OBS Studio | screen/audio capture and recording | local tool | fallback when direct stream access is unavailable but lawful playback exists |
| `youtube-transcript-api` | fetches public YouTube transcripts using undocumented endpoints | library | useful for non-sports livestreams and replay archives |
| `livestream_saver` | monitors channels and records YouTube livestreams from the first segment | open-source repo | useful for livestream categories outside sports |
| `StreamCap` / `stream-rec` and similar projects | automated stream recording across many platforms | open-source repos | useful for studying monitor-record-transcode patterns |

### Publicly Visible Workflow Patterns

Patterns repeatedly visible in GitHub projects and community discussions:

- `streamlink + ffmpeg` for direct stream recording
- scheduled or monitored recording jobs for repeated events
- automatic remuxing to MP4 or MKV after capture
- audio extraction after recording
- retention of original segments for debugging and re-processing
- use of cookies or account-authenticated sessions where the user is authorized to access the stream
- fall back to screen/audio capture with OBS when a direct stream pipeline is not viable

### Lawful-Capture Constraint

This project should be built around sources we are authorized to access and record.

That means:

- do not assume DRM-protected streams can or should be bypassed
- prefer official subscriptions, replay rights, or openly accessible feeds
- keep the ingestion design modular so capture methods can vary by source

## Recommended Data-Source Priorities

The engine should prioritize source families in this order:

1. official transcript
2. open transcript link in RSS or page markup
3. official replay audio/video
4. platform transcript visible in UI
5. commercial transcript API
6. our own lawful feed capture

The best early build sequence remains:

1. FOMC and official transcript markets
2. earnings calls
3. podcasts and YouTube
4. TV/public-affairs archives
5. MLB and broader sports broadcasts

## Identified Sources

This is the current source inventory referenced above.

### Official / primary sources

- Federal Reserve FOMC press conference pages: https://www.federalreserve.gov/monetarypolicy/fomcpressconf20260128.htm
- Federal Reserve March 18, 2026 press conference page: https://www.federalreserve.gov/monetarypolicy/fomcpresconf20260318.htm
- SEC Developer Resources: https://www.sec.gov/about/developer-resources
- SEC API documentation: https://www.sec.gov/edgar/sec-api-documentation
- SEC data portal: https://data.sec.gov/
- GovInfo Developer Hub: https://www.govinfo.gov/developers
- GovInfo API overview: https://www.govinfo.gov/features/api
- Congress.gov House hearing transcripts: https://www.congress.gov/house-hearing-transcripts
- Apple Podcasts transcripts announcement: https://www.apple.com/newsroom/2024/03/apple-introduces-transcripts-for-apple-podcasts/
- Apple Podcasts creator transcript docs: https://podcasters.apple.com/support/5316-transcripts-on-apple-podcasts
- Spotify creator transcript docs: https://support.spotify.com/ws/creators/article/managing-episode-transcripts-on-spotify/
- Podcasting 2.0 transcript tag spec: https://podcasting2.org/podcast-namespace/tags/transcript
- YouTube Data API captions guide: https://developers.google.com/youtube/v3/guides/implementation/captions
- YouTube captions reference: https://developers.google.com/youtube/v3/docs/captions
- YouTube captions download reference: https://developers.google.com/youtube/v3/docs/captions/download
- MLB Audio / subscription page: https://www.mlb.com/live-stream-games/subscribe/mlb-audio
- MLB help for archived/on-demand audio access: https://www.mlb.com/live-stream-games/help-center/accessibility-how-do-i-access-on-demand-games-with-mlb-audio
- Baseball Savant / Statcast: https://baseballsavant.mlb.com/en/

### Practical public APIs and tools

- Alpha Vantage documentation: https://www.alphavantage.co/documentation/
- API Ninjas earnings call transcript API: https://api-ninjas.com/api/earningscalltranscript
- Financial Modeling Prep transcript docs: https://site.financialmodelingprep.com/developer/docs/stable/search-transcripts
- FMP transcript list docs: https://site.financialmodelingprep.com/developer/docs/earning-call-transcript-api
- GDELT TV API introduction: https://blog.gdeltproject.org/gdelt-2-0-television-api-debuts/amp/
- Internet Archive API overview: https://openpublicapis.com/api/archive-org

### MLB / baseball-oriented APIs and wrappers

- MLB StatsAPI wrapper and endpoint docs: https://github.com/toddrob99/MLB-StatsAPI
- MLB StatsAPI endpoints wiki: https://github.com/toddrob99/MLB-StatsAPI/wiki/Endpoints
- pybaseball data-source notes: https://deepwiki.com/jldbc/pybaseball/3-data-sources
- pybaseball statcast docs: https://github.com/jldbc/pybaseball/blob/master/docs/statcast.md
- Sportradar MLB API basics: https://developer.sportradar.com/baseball/docs/mlb-ig-api-basics
- Sportradar MLB broadcasts metadata update: https://developer.sportradar.com/sportradar-updates/changelog/mlb-api-multiple-broadcasts-per-game
- SportsDataIO MLB API: https://sportsdata.io/mlb-api
- BallDontLie MLB API: https://mlb.balldontlie.io/

### Open-source capture and transcript tooling

- Streamlink: https://github.com/streamlink/streamlink
- OBS Studio: https://github.com/obsproject/obs-studio
- `youtube-transcript-api`: https://github.com/jdepoix/youtube-transcript-api
- `livestream_saver`: https://github.com/glubsy/livestream_saver
- `StreamCap`: https://github.com/ihmily/StreamCap
- `stream-rec`: https://github.com/stream-rec/stream-rec

## System Goals

The engine should:

- support multiple market types through one common pipeline
- separate acquisition from downstream text and pricing logic
- retain enough metadata to reproduce why a mention was or was not counted
- preserve links between detection output and the original source evidence
- be designed around Kalshi rules, not just generic phrase search
- support both historical research and live decision-making

## Architecture

### Layer 1: Source Ingestion

This layer acquires raw event data.

Its job is to hide source-specific complexity behind a common interface.

Planned adapter types:

- `official_transcript_adapter`
- `platform_transcript_adapter`
- `replay_audio_adapter`
- `live_broadcast_capture_adapter`

Responsibilities:

- fetch or record source material
- preserve source metadata
- preserve timestamps where available
- identify event, feed, and speaker context where possible
- store original artifacts for later audit

Important rule:

The engine must distinguish between:

- `research source`
- `settlement source`

These may be the same, but they cannot be assumed to be the same.

### Layer 2: Transcription

This layer converts audio into timestamped text when no transcript is directly available or when independent verification is preferred.

Responsibilities:

- run transcription on replay or live-captured audio
- preserve timestamps at word or phrase level if possible
- preserve confidence metrics
- optionally support multiple transcript versions for comparison

For sports and other hard-feed markets, this layer is central.

### Layer 3: Normalization

This layer converts raw transcript text into a rules-friendly format.

Responsibilities:

- normalize punctuation and casing
- tokenize text consistently
- preserve the original text alongside normalized forms
- handle pluralization, tense changes, and basic morphological variants
- support configurable phrase families and pattern sets
- support rule-aware treatment of partial words, quoted language, captions, and subtitles

This layer is reusable across nearly all mention markets.

### Layer 4: Speaker Attribution

This layer determines who said the relevant words.

Responsibilities:

- map utterances to speakers when transcripts provide labels
- infer speaker segments when only audio exists
- distinguish between primary speaker, secondary speaker, announcer, sideline reporter, guest, analyst, or crowd where needed
- track uncertainty when attribution is imperfect

This is much more important and much harder in sports and broadcast markets than in single-speaker official transcript markets.

### Layer 5: Rule Compiler

This layer translates Kalshi market rules into structured logic.

Responsibilities:

- represent target phrase or phrase set
- represent accepted variants
- represent speaker restrictions
- represent event-window restrictions
- represent source restrictions
- represent feed restrictions
- represent exclusions and edge cases

The output should be machine-checkable criteria, not just free text.

Example rule fields:

- `market_id`
- `target_terms`
- `allowed_variants`
- `speaker_scope`
- `time_scope`
- `source_scope`
- `feed_scope`
- `counting_exclusions`

### Layer 6: Mention Matcher

This layer decides whether an observed utterance qualifies under compiled rules.

Responsibilities:

- scan normalized text for candidate mentions
- score and classify candidate matches
- apply speaker and timing filters
- apply source and feed filters
- emit evidence objects that explain the decision

Output should include:

- whether the candidate counts
- matched text
- normalized form
- timestamp
- speaker
- source artifact reference
- explanation of rule satisfaction or failure

### Layer 7: Pricing Model

This layer estimates the probability of future mentions.

Responsibilities:

- use historical phrase frequencies
- condition on speaker, event type, and context
- incorporate time remaining in the event
- incorporate pre-event topic context
- convert probability estimates into fair value

The exact model can evolve, but it should plug into the same downstream interface regardless of event type.

### Layer 8: Execution Layer

This layer compares fair value to market price and supports trading workflows.

Responsibilities:

- compare model value to Kalshi price
- account for spread and liquidity
- account for uncertainty in source coverage and rule interpretation
- surface opportunity quality rather than just raw mispricing

In thin markets, execution logic may matter almost as much as the model itself.

## Sports-Specific Requirements

Sports are likely the hardest and most valuable category to support well.

Additional requirements:

- exact-feed tracking
- timestamped audio archive
- support for local vs national broadcast distinctions
- support for multiple announcers and sideline reporters
- optional diarization or speaker labeling
- review workflow for ambiguous detections
- support for feed-priority resolution logic before capture starts

Important risks:

- alternate feeds may differ materially
- clipped replays may not match the live resolving source
- closed captions may omit, simplify, or rewrite language
- crowd noise and overlap can degrade transcription quality

The sports system should therefore be designed for evidence preservation and human review, not just automated binary classification.

## Design Principles

- Build one reusable engine, not separate tools for each market type.
- Keep ingestion adapters market-specific and everything downstream as shared as possible.
- Preserve source evidence at every stage.
- Treat Kalshi rules as first-class structured inputs.
- Favor auditability over black-box outputs.
- Separate research quality from settlement quality.

## Phased Build Plan

### Phase 1: Core Backbone

Build the common pipeline:

- source abstraction
- transcript ingestion
- normalization
- rules compiler
- mention matcher
- evidence model

This phase should be validated on easy transcript-rich events.

### Phase 2: Replay Audio Workflow

Add replay-based transcription:

- audio fetch
- Whisper transcription
- timestamped search
- phrase detection against compiled rules

This phase should be validated on earnings calls and similar events.

### Phase 3: Historical Pricing Layer

Add research and pricing:

- phrase frequency database
- event-type priors
- speaker-specific priors
- fair-value estimation

This turns the engine from a resolver into a trading tool.

### Phase 4: Feed-Capture Module

Add live-feed acquisition for hard markets:

- broadcast capture
- live transcription
- speaker segmentation
- alerting and review

This phase is especially relevant for sports announcer markets.

## Open Questions

- How often do Kalshi sports mention markets resolve off a source that can realistically be reproduced from public data?
- How often do closed captions align closely enough with the resolving source to be useful?
- What is the minimum evidence package needed to feel confident in a sports mention before trading?
- Which sports and broadcasters are easiest to capture reliably?
- Which event classes offer the best combination of repeated opportunity and workable liquidity?

## Initial Conclusion

The right approach is not to build a separate tool for each mention-market category.

The right approach is to build a universal mentions engine with:

- interchangeable ingestion modules
- one shared normalization and rules pipeline
- one shared mention-detection core
- one shared pricing interface

Easy-transcript markets should be used to validate the engine quickly.

Hard-feed markets, especially sports, are likely where the strongest long-term edge may exist if the acquisition and rules-resolution problems can be solved reliably.

## MVP Acquisition Plans

This section defines concrete first-pass acquisition plans for the most relevant early source families.

The goal is not to design the final perfect ingestion stack immediately.

The goal is to define the first workable, lawful, testable path for:

- one sports workflow with complex feed selection
- one sports workflow with cleaner national broadcast sourcing
- one non-sports workflow with replay audio and strong transcript potential

### MVP Plan: MLB.TV

Target use case:

- MLB announcer mention markets where the resolving source is national TV if available, otherwise home team TV

Objective:

- prove that we can reliably identify, access, record, and transcribe the exact resolving TV feed for one game

Baseline subscription assumption:

- `MLB.TV`

Acquisition steps:

1. ingest game schedule and metadata from MLB Stats API
2. ingest broadcast metadata from MLB or commercial broadcast-metadata sources
3. map each Kalshi market to a specific game and a resolving feed priority
4. determine whether a national feed exists
5. if yes, select the national TV feed
6. if no, select the home team TV feed
7. access the feed through an authorized MLB.TV session
8. record the session or replay while preserving timestamps
9. extract the audio track
10. transcribe and store segments, word timings, and evidence artifacts

First milestone:

- one complete end-to-end captured and transcribed game with feed metadata preserved

Key risks:

- identifying national-feed availability reliably
- determining whether the desired feed is accessible through the account and region
- capturing the exact resolving source without ambiguity
- validating whether multi-game concurrent capture is possible under the subscription and platform behavior

Fallbacks:

- post-game replay capture rather than live capture
- local capture from authorized playback if direct ingest is not viable

### MVP Plan: NBA Playoffs via YouTube TV + Prime Video

Target use case:

- NBA playoff announcer mention markets tied to national broadcasts

Objective:

- prove that we can map an NBA mention market to the correct national platform and recover a replay source suitable for transcription

Baseline subscription assumption:

- `YouTube TV`
- `Prime Video`
- optionally `Peacock`

Acquisition steps:

1. ingest the NBA playoff schedule and identify the national broadcaster for each game
2. map each Kalshi market to the correct platform:
   - `ABC / ESPN` via `YouTube TV`
   - `NBC / Peacock` via `YouTube TV` or `Peacock`
   - `Prime Video` directly
3. record or replay the authorized source
4. preserve network/platform metadata for each captured artifact
5. extract audio and transcribe
6. align transcript timing with game context and market timestamps

First milestone:

- one end-to-end national playoff game processed from replay to transcript and candidate mentions

Key risks:

- determining whether replay capture is easier from YouTube TV itself or from TV Everywhere/network-native sites
- handling Prime-exclusive games separately
- validating whether browser or app playback produces capture restrictions

Fallbacks:

- prioritize replay over live capture
- use display capture from authorized playback if no cleaner path exists

### MVP Plan: Earnings Calls

Target use case:

- company earnings-call mention markets

Objective:

- prove that replay-plus-transcription can power the engine cleanly without sports-feed complexity

Baseline acquisition assumption:

- public or investor-relations-hosted webcast replay
- optional transcript APIs for backfill and cross-checking

Acquisition steps:

1. detect the relevant company event and scheduled earnings-call time
2. collect context from SEC filings and earnings release metadata
3. locate the official investor-relations webcast or replay page
4. fetch the replay asset or replay page
5. ingest any available transcript from the company or a transcript API
6. if no transcript exists, transcribe the replay audio
7. normalize, segment, and speaker-label the transcript
8. run the compiled mention rules and store evidence

First milestone:

- one end-to-end earnings call processed from replay audio to mention decisions

Key risks:

- replay URLs may be inconsistent across issuers
- official transcript availability is uneven
- analyst Q&A and management prepared remarks may need different speaker handling

Fallbacks:

- use transcript APIs for backfill even if the main production source is replay audio
- use manual event-specific source mapping early rather than over-automating issuer discovery

## MVP Comparison

| Workflow | Difficulty | Source clarity | Feed complexity | Data edge potential | Best use |
|---|---|---|---|---|---|
| `Earnings calls` | `Low-Medium` | `High` | `Low` | `Medium` | validate the core engine |
| `NBA playoffs` | `Medium` | `High` | `Medium` | `Medium-High` | first national-broadcast sports workflow |
| `MLB.TV` | `High` | `Medium` | `High` | `High` | first high-edge sports workflow |

## Recommended MVP Order

1. `Earnings calls`
2. `NBA playoffs`
3. `MLB.TV`

Rationale:

- earnings calls are the cleanest way to validate ingestion, transcription, rule compilation, and mention matching
- NBA playoffs are the cleanest sports proving ground because the broadcasts are mostly national and feed selection is simpler
- MLB is likely the most strategically valuable early sports category, but only after the acquisition stack is proven on something less operationally messy

## Data Models

The engine should use a small set of canonical data models that are shared across all market types.

These models should be designed to:

- preserve raw evidence
- preserve provenance
- support auditability
- support both historical and live workflows
- keep sports and non-sports under one schema

### Market

Represents a Kalshi mention market as traded.

Suggested fields:

- `market_id`
- `event_id`
- `series_id`
- `title`
- `subtitle`
- `status`
- `close_time`
- `settlement_time`
- `yes_bid`
- `yes_ask`
- `no_bid`
- `no_ask`
- `volume`
- `open_interest`
- `rules_text`
- `rules_summary_text`
- `source_text`
- `url`
- `last_updated_at`

### Event

Represents the real-world event the market depends on.

Suggested fields:

- `event_id`
- `event_type`
- `title`
- `category`
- `subcategory`
- `scheduled_start_time`
- `scheduled_end_time`
- `actual_start_time`
- `actual_end_time`
- `participants`
- `broadcast_network`
- `league`
- `season`
- `venue`
- `source_priority`
- `broadcast_priority`
- `metadata`

Examples of `event_type`:

- `fomc_press_conference`
- `earnings_call`
- `podcast_episode`
- `youtube_video`
- `tv_broadcast`
- `sports_broadcast`
- `government_hearing`

Examples of `broadcast_priority`:

- `national_then_home_tv`
- `home_tv_only`
- `official_transcript_first`
- `research_best_available`

### Source Artifact

Represents an acquired source object.

This is the core provenance object.

Suggested fields:

- `artifact_id`
- `event_id`
- `artifact_type`
- `role`
- `provider`
- `uri`
- `local_path`
- `captured_at`
- `published_at`
- `start_time`
- `end_time`
- `duration_seconds`
- `checksum`
- `mime_type`
- `is_official`
- `is_settlement_candidate`
- `feed_label`
- `feed_priority`
- `broadcast_scope`
- `language`
- `metadata`

Examples of `artifact_type`:

- `official_transcript`
- `platform_transcript`
- `audio_replay`
- `video_replay`
- `live_audio_capture`
- `live_video_capture`
- `closed_captions`

Examples of `feed_priority`:

- `national`
- `home_tv`
- `away_tv`
- `local_radio`

Examples of `broadcast_scope`:

- `national`
- `regional`
- `local`

Examples of `role`:

- `research_source`
- `settlement_source`
- `fallback_source`
- `derived_source`

### Transcript

Represents a transcript linked to one source artifact.

Suggested fields:

- `transcript_id`
- `artifact_id`
- `transcript_type`
- `version`
- `created_at`
- `generator`
- `language`
- `quality_score`
- `is_machine_generated`
- `is_human_supplied`
- `raw_text`
- `normalized_text`
- `metadata`

Examples of `transcript_type`:

- `official`
- `platform`
- `asr_whisper`
- `asr_other`
- `captions`

### Transcript Segment

Represents a time-bounded chunk of transcript.

Suggested fields:

- `segment_id`
- `transcript_id`
- `start_time_seconds`
- `end_time_seconds`
- `speaker_id`
- `speaker_label`
- `channel`
- `text`
- `normalized_text`
- `confidence`
- `word_count`
- `metadata`

This object should be present even when no explicit speaker is known.

### Token or Word Timing

Optional finer-grained representation for precise rule handling.

Suggested fields:

- `token_id`
- `segment_id`
- `text`
- `normalized_text`
- `start_time_seconds`
- `end_time_seconds`
- `confidence`

This is especially useful for:

- exact phrase matching
- partial-word exclusions
- ambiguous overlaps
- high-speed live review

### Speaker

Represents a person or role appearing in the event.

Suggested fields:

- `speaker_id`
- `event_id`
- `name`
- `role`
- `team`
- `organization`
- `channel`
- `is_primary`
- `metadata`

Examples of `role`:

- `chair`
- `ceo`
- `cfo`
- `host`
- `guest`
- `analyst`
- `play_by_play`
- `color_commentator`
- `sideline_reporter`
- `crowd`

### Compiled Rule

Represents a structured form of the market’s mention-counting logic.

Suggested fields:

- `compiled_rule_id`
- `market_id`
- `target_terms`
- `allowed_variants`
- `disallowed_variants`
- `speaker_scope`
- `time_scope`
- `source_scope`
- `feed_scope`
- `quotation_policy`
- `caption_policy`
- `partial_word_policy`
- `case_sensitivity`
- `stemming_policy`
- `counting_threshold`
- `requires_exact_phrase`
- `notes`
- `compiled_at`

This model should be versioned because rule interpretations may improve over time.

### Candidate Mention

Represents a possible mention before final adjudication.

Suggested fields:

- `candidate_id`
- `market_id`
- `compiled_rule_id`
- `event_id`
- `transcript_id`
- `segment_id`
- `speaker_id`
- `matched_text`
- `normalized_match`
- `start_time_seconds`
- `end_time_seconds`
- `match_type`
- `confidence`
- `metadata`

Examples of `match_type`:

- `exact`
- `variant`
- `stemmed`
- `fuzzy`
- `caption_only`

### Mention Decision

Represents the engine’s adjudication of whether a candidate counts.

Suggested fields:

- `decision_id`
- `candidate_id`
- `market_id`
- `counts`
- `decision_status`
- `reason_code`
- `explanation`
- `review_status`
- `reviewed_by`
- `reviewed_at`
- `created_at`

Examples of `decision_status`:

- `accepted`
- `rejected`
- `uncertain`

Examples of `review_status`:

- `auto`
- `needs_review`
- `human_confirmed`
- `human_rejected`

### Evidence Bundle

Represents the complete evidence needed to explain a decision.

Suggested fields:

- `evidence_bundle_id`
- `market_id`
- `decision_id`
- `artifact_ids`
- `transcript_ids`
- `segment_ids`
- `speaker_ids`
- `source_excerpt`
- `normalized_excerpt`
- `timestamp_reference`
- `feed_reference`
- `export_payload`
- `created_at`

This object is important for debugging, backtesting, and trading review.

### Price Snapshot

Represents a point-in-time market observation.

Suggested fields:

- `snapshot_id`
- `market_id`
- `captured_at`
- `yes_bid`
- `yes_ask`
- `no_bid`
- `no_ask`
- `last_price`
- `volume`
- `open_interest`
- `orderbook_depth`
- `metadata`

### Probability Estimate

Represents the model’s fair-value output.

Suggested fields:

- `estimate_id`
- `market_id`
- `event_id`
- `generated_at`
- `probability_yes`
- `fair_yes_price`
- `fair_no_price`
- `model_name`
- `model_version`
- `input_summary`
- `uncertainty_score`
- `confidence_band_low`
- `confidence_band_high`
- `notes`

### Opportunity

Represents a tradable discrepancy between model value and market price.

Suggested fields:

- `opportunity_id`
- `market_id`
- `generated_at`
- `side`
- `market_price`
- `fair_price`
- `edge_cents`
- `liquidity_score`
- `execution_risk_score`
- `data_quality_score`
- `rule_risk_score`
- `priority_score`
- `notes`

## Interfaces

The engine should be built around clear interfaces between layers.

These interfaces should allow the same downstream machinery to work regardless of whether the source is an official transcript, a replay file, or a captured sports broadcast.

### Source Adapter Interface

Purpose:

- acquire source artifacts for an event

Suggested contract:

```ts
interface SourceAdapter {
  name: string;
  supports(eventType: string): boolean;
  fetch(event: Event): Promise<SourceArtifact[]>;
}
```

Expected implementations:

- `OfficialTranscriptAdapter`
- `PlatformTranscriptAdapter`
- `ReplayAudioAdapter`
- `LiveBroadcastCaptureAdapter`

### Transcription Interface

Purpose:

- produce a transcript from a source artifact when needed

Suggested contract:

```ts
interface Transcriber {
  name: string;
  supports(artifact: SourceArtifact): boolean;
  transcribe(artifact: SourceArtifact): Promise<Transcript>;
}
```

This should support both:

- batch replay transcription
- live incremental transcription

### Normalization Interface

Purpose:

- convert raw transcript text into structured normalized text

Suggested contract:

```ts
interface Normalizer {
  normalizeTranscript(transcript: Transcript): Promise<Transcript>;
  normalizeSegment(segment: TranscriptSegment): TranscriptSegment;
  normalizePhrase(text: string): string;
}
```

### Speaker Attribution Interface

Purpose:

- assign or infer speaker identity for transcript segments

Suggested contract:

```ts
interface SpeakerResolver {
  resolve(
    event: Event,
    transcript: Transcript,
    segments: TranscriptSegment[],
  ): Promise<TranscriptSegment[]>;
}
```

This may be:

- label-preserving for transcript-rich events
- inference-heavy for sports audio

### Rule Compiler Interface

Purpose:

- convert market rules text into a structured compiled rule

Suggested contract:

```ts
interface RuleCompiler {
  compile(market: Market): Promise<CompiledRule>;
}
```

This compiler may include:

- deterministic parsing
- manual overrides
- curated rule templates by market family

### Mention Matcher Interface

Purpose:

- find candidate mentions and adjudicate whether they count

Suggested contract:

```ts
interface MentionMatcher {
  findCandidates(
    rule: CompiledRule,
    transcript: Transcript,
    segments: TranscriptSegment[],
  ): Promise<CandidateMention[]>;

  decide(
    rule: CompiledRule,
    candidate: CandidateMention,
  ): Promise<MentionDecision>;
}
```

### Evidence Builder Interface

Purpose:

- package source data and reasoning into an auditable record

Suggested contract:

```ts
interface EvidenceBuilder {
  build(
    market: Market,
    decision: MentionDecision,
  ): Promise<EvidenceBundle>;
}
```

### Feature Extraction Interface

Purpose:

- derive model features from event context, transcript history, and source metadata

Suggested contract:

```ts
interface FeatureExtractor {
  extract(market: Market, event: Event): Promise<Record<string, unknown>>;
}
```

### Pricing Interface

Purpose:

- estimate fair value

Suggested contract:

```ts
interface PricingModel {
  estimate(
    market: Market,
    event: Event,
    features: Record<string, unknown>,
  ): Promise<ProbabilityEstimate>;
}
```

### Opportunity Scoring Interface

Purpose:

- rank tradable setups after accounting for data quality and execution constraints

Suggested contract:

```ts
interface OpportunityScorer {
  score(
    market: Market,
    estimate: ProbabilityEstimate,
    snapshot: PriceSnapshot,
  ): Promise<Opportunity>;
}
```

## Storage Model

The storage layer should separate durable entities from derived outputs.

### Durable Entities

These should usually be stored permanently:

- markets
- events
- source artifacts
- transcripts
- transcript segments
- speakers
- compiled rules
- price snapshots

### Derived Entities

These may be recomputed but should still be stored for audit and backtesting:

- candidate mentions
- mention decisions
- evidence bundles
- probability estimates
- opportunities

## Live vs Historical Modes

The same engine should support both historical research and live operation.

### Historical Mode

Use cases:

- build datasets
- backtest mention detection
- backtest pricing
- improve rule templates

Historical mode emphasizes completeness and reproducibility.

### Live Mode

Use cases:

- ingest active event data
- surface potential mentions during the event
- update mention probabilities as the event evolves
- rank opportunities for action

Live mode emphasizes latency, confidence scoring, and review workflows.

## Review Workflow

The system should assume that some mention decisions will remain ambiguous.

This is especially true for:

- sports announcer overlap
- noisy broadcasts
- clipped words
- homophones
- disputed speaker attribution
- rule ambiguity

Therefore the engine should support:

- `auto accept`
- `auto reject`
- `flag for review`

The review UI or downstream review system should show:

- source excerpt
- timestamp
- speaker
- feed
- matched phrase
- compiled rule summary
- explanation of why the engine was uncertain

## Notes On Sports And Non-Sports Scope

The engine should not be designed as a sports-only system.

Sports are strategically attractive because the data is harder and the opportunity set is frequent, but non-sports markets remain important because they:

- are easier to validate against
- broaden the opportunity set
- provide cleaner datasets for improving the core engine
- let the same pricing and rules logic compound across event types

The right design is therefore:

- one universal mentions engine
- one common schema
- one common downstream pipeline
- multiple acquisition adapters for different source environments
