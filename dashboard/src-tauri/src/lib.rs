use base64::Engine;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Instant, SystemTime, UNIX_EPOCH};
use tokio::task::JoinSet;
use tokio::time::{sleep, Duration};

const API_BASE_URL: &str = "https://api.elections.kalshi.com/trade-api/v2";
const REFRESH_CONCURRENCY: usize = 6;
const EVENT_DETAILS_CONCURRENCY: usize = 6;
const PUBLIC_REQUEST_RETRIES: usize = 5;

struct PerfStats {
    command: &'static str,
    enabled: bool,
    request_count: usize,
    request_duration_ms: u128,
    signing_count: usize,
    signing_duration_ms: u128,
}

impl PerfStats {
    fn new(command: &'static str) -> Self {
        Self {
            command,
            enabled: matches!(
                env::var("KALSHI_PERF").as_deref(),
                Ok("1") | Ok("true") | Ok("TRUE")
            ),
            request_count: 0,
            request_duration_ms: 0,
            signing_count: 0,
            signing_duration_ms: 0,
        }
    }

    fn log_http(&mut self, target: &str, started_at: Instant, status: Option<u16>) {
        if !self.enabled {
            return;
        }

        let duration_ms = started_at.elapsed().as_millis();
        self.request_count += 1;
        self.request_duration_ms += duration_ms;

        let status = status
            .map(|value| value.to_string())
            .unwrap_or_else(|| "error".to_string());

        eprintln!(
            r#"{{"kind":"http","command":"{}","target":"{}","duration_ms":{},"status":"{}"}}"#,
            self.command, target, duration_ms, status
        );
    }

    fn log_signing(&mut self, started_at: Instant) {
        if !self.enabled {
            return;
        }

        let duration_ms = started_at.elapsed().as_millis();
        self.signing_count += 1;
        self.signing_duration_ms += duration_ms;

        eprintln!(
            r#"{{"kind":"sign","command":"{}","duration_ms":{}}}"#,
            self.command, duration_ms
        );
    }

    fn finish(&self, started_at: Instant, ok: bool) {
        if !self.enabled {
            return;
        }

        eprintln!(
            r#"{{"kind":"command","name":"{}","duration_ms":{},"request_count":{},"request_duration_ms":{},"signing_count":{},"signing_duration_ms":{},"ok":{}}}"#,
            self.command,
            started_at.elapsed().as_millis(),
            self.request_count,
            self.request_duration_ms,
            self.signing_count,
            self.signing_duration_ms,
            ok
        );
    }

    fn snapshot(&self) -> PerfSnapshot {
        PerfSnapshot {
            request_count: self.request_count,
            request_duration_ms: self.request_duration_ms,
            signing_count: self.signing_count,
            signing_duration_ms: self.signing_duration_ms,
        }
    }

    fn absorb(&mut self, snapshot: &PerfSnapshot) {
        self.request_count += snapshot.request_count;
        self.request_duration_ms += snapshot.request_duration_ms;
        self.signing_count += snapshot.signing_count;
        self.signing_duration_ms += snapshot.signing_duration_ms;
    }
}

#[derive(Clone, Debug, Default, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PerfSnapshot {
    pub request_count: usize,
    pub request_duration_ms: u128,
    pub signing_count: usize,
    pub signing_duration_ms: u128,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PositionsBenchmarkSummary {
    pub duration_ms: u128,
    pub row_count: usize,
    pub perf: PerfSnapshot,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WatchingBenchmarkSummary {
    pub duration_ms: u128,
    pub row_count: usize,
    pub perf: PerfSnapshot,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CategoryBenchmarkSummary {
    pub duration_ms: u128,
    pub category: String,
    pub event_count: usize,
    pub pages_per_source: usize,
    pub perf: PerfSnapshot,
}

impl PerfSnapshot {
    fn absorb(&mut self, other: &PerfSnapshot) {
        self.request_count += other.request_count;
        self.request_duration_ms += other.request_duration_ms;
        self.signing_count += other.signing_count;
        self.signing_duration_ms += other.signing_duration_ms;
    }
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EventSummary {
    id: String,
    category: String,
    subcategory: String,
    title: String,
    start_time: String,
    is_live: bool,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EventDetails {
    id: String,
    markets: Vec<MarketRecord>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct EventPage {
    category: String,
    events: Vec<EventSummary>,
    cursor: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct MarketRecord {
    id: String,
    event_id: String,
    label: String,
    title: String,
    yes_bid: i32,
    yes_ask: i32,
    no_bid: i32,
    no_ask: i32,
    volume: i64,
    rules_primary: String,
    status: String,
    close_time: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct PositionRecord {
    ticker: String,
    event_ticker: String,
    category: String,
    event_title: String,
    market_label: String,
    start_time: String,
    is_live: bool,
    yes_bid: i32,
    yes_ask: i32,
    no_bid: i32,
    no_ask: i32,
    volume: i64,
    position: f64,
    exposure_dollars: f64,
    total_traded_dollars: f64,
    realized_pnl_dollars: f64,
    fees_paid_dollars: f64,
    rules_primary: String,
}

#[derive(Debug, Deserialize)]
struct ApiEventsResponse {
    events: Option<Vec<ApiEvent>>,
    cursor: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ApiSeriesResponse {
    series: Vec<ApiSeries>,
}

#[derive(Debug, Deserialize)]
struct ApiSeries {
    category: Option<String>,
}

#[derive(Debug, Deserialize)]
struct ApiEventResponse {
    event: ApiEvent,
}

#[derive(Debug, Deserialize)]
struct ApiMarketResponse {
    market: ApiMarket,
}

#[derive(Debug, Deserialize)]
struct ApiPositionsResponse {
    cursor: Option<String>,
    #[serde(default)]
    event_positions: Vec<ApiEventPosition>,
    market_positions: Vec<ApiMarketPosition>,
}

#[derive(Debug, Deserialize)]
struct ApiMarketPosition {
    ticker: String,
    total_traded_dollars: String,
    position_fp: String,
    market_exposure_dollars: String,
    realized_pnl_dollars: String,
    fees_paid_dollars: String,
}

#[derive(Debug, Deserialize)]
struct ApiEventPosition {
    event_ticker: String,
}

#[derive(Clone, Debug, Deserialize)]
struct ApiEvent {
    event_ticker: String,
    series_ticker: String,
    title: String,
    sub_title: Option<String>,
    category: Option<String>,
    strike_date: Option<String>,
    markets: Option<Vec<ApiMarket>>,
}

#[derive(Clone, Debug, Deserialize)]
struct ApiMarket {
    ticker: String,
    event_ticker: String,
    title: Option<String>,
    subtitle: Option<String>,
    status: Option<String>,
    yes_sub_title: Option<String>,
    yes_bid_dollars: Option<String>,
    yes_ask_dollars: Option<String>,
    no_bid_dollars: Option<String>,
    no_ask_dollars: Option<String>,
    volume_fp: Option<String>,
    rules_primary: Option<String>,
    close_time: Option<String>,
}

#[derive(Clone, Debug)]
struct AuthConfig {
    api_key_id: String,
    private_key_path: String,
    base_url: String,
}

fn parse_price_to_cents(value: Option<&str>) -> i32 {
    value
        .and_then(|raw| raw.parse::<f64>().ok())
        .map(|parsed| (parsed * 100.0).round() as i32)
        .unwrap_or(0)
}

fn parse_volume(value: Option<&str>) -> i64 {
    value
        .and_then(|raw| raw.parse::<f64>().ok())
        .map(|parsed| parsed.round() as i64)
        .unwrap_or(0)
}

fn parse_f64(value: &str) -> f64 {
    value.parse::<f64>().unwrap_or(0.0)
}

fn get_market_label(market: &ApiMarket) -> String {
    market
        .subtitle
        .clone()
        .or_else(|| market.yes_sub_title.clone())
        .or_else(|| market.title.clone())
        .unwrap_or_else(|| market.ticker.clone())
}

fn is_open_like_market(status: Option<&str>) -> bool {
    match status {
        Some("closed") | Some("settled") | Some("finalized") => false,
        Some(_) => true,
        None => true,
    }
}

fn is_live_from_timestamp(start_time: &str) -> bool {
    chrono::DateTime::parse_from_rfc3339(start_time)
        .map(|timestamp| timestamp <= chrono::Utc::now())
        .unwrap_or(false)
}

fn normalize_event_summary(event: ApiEvent) -> EventSummary {
    let start_time = event
        .strike_date
        .unwrap_or_else(|| "1970-01-01T00:00:00Z".to_string());

    EventSummary {
        id: event.event_ticker,
        category: event.category.unwrap_or_else(|| "Other".to_string()),
        subcategory: event
            .sub_title
            .or(Some(event.series_ticker))
            .unwrap_or_else(|| "General".to_string()),
        title: event.title,
        start_time: start_time.clone(),
        is_live: is_live_from_timestamp(&start_time),
    }
}

fn normalize_market_record(market: ApiMarket) -> MarketRecord {
    MarketRecord {
        id: market.ticker.clone(),
        event_id: market.event_ticker.clone(),
        label: get_market_label(&market),
        title: market.title.unwrap_or_else(|| market.ticker.clone()),
        yes_bid: parse_price_to_cents(market.yes_bid_dollars.as_deref()),
        yes_ask: parse_price_to_cents(market.yes_ask_dollars.as_deref()),
        no_bid: parse_price_to_cents(market.no_bid_dollars.as_deref()),
        no_ask: parse_price_to_cents(market.no_ask_dollars.as_deref()),
        volume: parse_volume(market.volume_fp.as_deref()),
        rules_primary: market.rules_primary.unwrap_or_default(),
        status: market.status.unwrap_or_else(|| "unknown".to_string()),
        close_time: market.close_time,
    }
}

fn normalize_event_details(event: ApiEvent) -> EventDetails {
    let markets = event
        .markets
        .unwrap_or_default()
        .into_iter()
        .filter(|market| is_open_like_market(market.status.as_deref()))
        .map(normalize_market_record)
        .collect();

    EventDetails {
        id: event.event_ticker,
        markets,
    }
}

fn build_watch_record(market: &MarketRecord, event: &EventSummary) -> PositionRecord {
    PositionRecord {
        ticker: market.id.clone(),
        event_ticker: market.event_id.clone(),
        category: event.category.clone(),
        event_title: event.title.clone(),
        market_label: market.label.clone(),
        start_time: event.start_time.clone(),
        is_live: event.is_live,
        yes_bid: market.yes_bid,
        yes_ask: market.yes_ask,
        no_bid: market.no_bid,
        no_ask: market.no_ask,
        volume: market.volume,
        position: 0.0,
        exposure_dollars: 0.0,
        total_traded_dollars: 0.0,
        realized_pnl_dollars: 0.0,
        fees_paid_dollars: 0.0,
        rules_primary: market.rules_primary.clone(),
    }
}

fn merge_event_summaries(
    current: Vec<EventSummary>,
    incoming: Vec<EventSummary>,
) -> Vec<EventSummary> {
    let mut deduped = BTreeMap::new();

    for event in current {
        deduped.insert(event.id.clone(), event);
    }

    for event in incoming {
        deduped.insert(event.id.clone(), event);
    }

    deduped.into_values().collect()
}

fn retry_delay_for_attempt(attempt: usize) -> Duration {
    let multiplier = 1u64 << attempt.min(5);
    Duration::from_millis(250 * multiplier)
}

fn discover_env_file() -> Option<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(current_dir) = std::env::current_dir() {
        candidates.push(current_dir);
    }

    if let Some(repo_root) = PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent() {
        candidates.push(repo_root.to_path_buf());
    }

    if let Ok(current_exe) = std::env::current_exe() {
        let mut dir = current_exe.parent().map(Path::to_path_buf);
        while let Some(current) = dir {
            candidates.push(current.clone());
            dir = current.parent().map(Path::to_path_buf);
        }
    }

    for candidate in candidates {
        let path = candidate.join(".env");
        if path.exists() {
            return Some(path);
        }
    }

    None
}

fn load_auth_config() -> Result<AuthConfig, String> {
    let mut values = BTreeMap::new();

    if let Some(env_path) = discover_env_file() {
        let contents = fs::read_to_string(env_path)
            .map_err(|error| format!("Unable to read .env file: {error}"))?;

        for raw in contents.lines() {
            let line = raw.trim();
            if line.is_empty() || line.starts_with('#') || !line.contains('=') {
                continue;
            }
            let (key, value) = line.split_once('=').unwrap_or(("", ""));
            values.insert(
                key.trim().to_string(),
                value
                    .trim()
                    .trim_matches('"')
                    .trim_matches('\'')
                    .to_string(),
            );
        }
    }

    for key in [
        "KALSHI_API_KEY_ID",
        "KALSHI_PRIVATE_KEY_PATH",
        "KALSHI_API_BASE_URL",
    ] {
        if let Ok(value) = std::env::var(key) {
            values.insert(key.to_string(), value);
        }
    }

    Ok(AuthConfig {
        api_key_id: values
            .get("KALSHI_API_KEY_ID")
            .cloned()
            .ok_or("Missing KALSHI_API_KEY_ID.")?,
        private_key_path: values
            .get("KALSHI_PRIVATE_KEY_PATH")
            .cloned()
            .ok_or("Missing KALSHI_PRIVATE_KEY_PATH.")?,
        base_url: values
            .get("KALSHI_API_BASE_URL")
            .cloned()
            .unwrap_or_else(|| API_BASE_URL.to_string()),
    })
}

fn sign_message(
    private_key_path: &str,
    message: &str,
    perf: &mut PerfStats,
) -> Result<String, String> {
    let signing_started_at = Instant::now();
    let temp_path = std::env::temp_dir().join(format!(
        "kalshi-signature-{}-{}.txt",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or_default()
    ));

    fs::write(&temp_path, message)
        .map_err(|error| format!("Unable to write temp file: {error}"))?;

    let output = Command::new("openssl")
        .args([
            "dgst",
            "-sha256",
            "-sign",
            private_key_path,
            "-sigopt",
            "rsa_padding_mode:pss",
            "-sigopt",
            "rsa_pss_saltlen:digest",
            temp_path.to_string_lossy().as_ref(),
        ])
        .output()
        .map_err(|error| format!("Unable to execute openssl: {error}"))?;

    let _ = fs::remove_file(temp_path);

    if !output.status.success() {
        return Err(format!(
            "OpenSSL signing failed: {}",
            String::from_utf8_lossy(&output.stderr)
        ));
    }

    perf.log_signing(signing_started_at);

    Ok(base64::engine::general_purpose::STANDARD.encode(output.stdout))
}

async fn build_public_client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .build()
        .map_err(|error| format!("Unable to build HTTP client: {error}"))
}

async fn authenticated_get(
    client: &reqwest::Client,
    config: &AuthConfig,
    path_and_query: &str,
    perf: &mut PerfStats,
) -> Result<reqwest::Response, String> {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().to_string())
        .map_err(|error| format!("Unable to build timestamp: {error}"))?;

    let full_url = format!(
        "{}{}",
        config.base_url.trim_end_matches('/'),
        path_and_query
    );
    let parsed =
        reqwest::Url::parse(&full_url).map_err(|error| format!("Invalid request URL: {error}"))?;
    let path_only = parsed.path();
    let message = format!("{timestamp}GET{path_only}");
    let signature = sign_message(&config.private_key_path, &message, perf)?;

    let request_started_at = Instant::now();
    let response = client
        .get(full_url)
        .header("KALSHI-ACCESS-KEY", &config.api_key_id)
        .header("KALSHI-ACCESS-TIMESTAMP", timestamp)
        .header("KALSHI-ACCESS-SIGNATURE", signature)
        .header("Accept", "application/json")
        .header("Content-Type", "application/json")
        .header("User-Agent", "kalshi-local-client/0.1")
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"));

    perf.log_http(
        "authenticated_get",
        request_started_at,
        response.as_ref().ok().map(|value| value.status().as_u16()),
    );

    response
}

async fn fetch_event_page(
    client: &reqwest::Client,
    path: &str,
    category: &str,
    include_status: bool,
    cursor: Option<String>,
    perf: &mut PerfStats,
) -> Result<EventPage, String> {
    let target = if path.contains("multivariate") {
        "event_page_multivariate"
    } else {
        "event_page_standard"
    };

    for attempt in 0..=PUBLIC_REQUEST_RETRIES {
        let mut request = client
            .get(format!("{API_BASE_URL}{path}"))
            .query(&[("limit", "200"), ("category", category)]);

        if include_status {
            request = request.query(&[("status", "open")]);
        }

        if let Some(ref current_cursor) = cursor {
            request = request.query(&[("cursor", current_cursor)]);
        }

        let request_started_at = Instant::now();
        let response = request
            .send()
            .await
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let status = response.status();
        perf.log_http(target, request_started_at, Some(status.as_u16()));

        if status == reqwest::StatusCode::TOO_MANY_REQUESTS && attempt < PUBLIC_REQUEST_RETRIES {
            sleep(retry_delay_for_attempt(attempt)).await;
            continue;
        }

        let response = response
            .error_for_status()
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let payload: ApiEventsResponse = response
            .json()
            .await
            .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

        return Ok(EventPage {
            category: category.to_string(),
            events: payload
                .events
                .unwrap_or_default()
                .into_iter()
                .map(normalize_event_summary)
                .filter(|event| event.category == category)
                .collect(),
            cursor: payload.cursor.filter(|value| !value.is_empty()),
        });
    }

    Err(format!(
        "Kalshi request exceeded retry budget for category page: {category}"
    ))
}

async fn fetch_market_details(
    client: &reqwest::Client,
    ticker: &str,
    perf: &mut PerfStats,
) -> Result<MarketRecord, String> {
    for attempt in 0..=PUBLIC_REQUEST_RETRIES {
        let request_started_at = Instant::now();
        let response = client
            .get(format!("{API_BASE_URL}/markets/{ticker}"))
            .send()
            .await
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let status = response.status();
        perf.log_http("market_details", request_started_at, Some(status.as_u16()));

        if status == reqwest::StatusCode::TOO_MANY_REQUESTS && attempt < PUBLIC_REQUEST_RETRIES {
            sleep(retry_delay_for_attempt(attempt)).await;
            continue;
        }

        let response = response
            .error_for_status()
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let payload: ApiMarketResponse = response
            .json()
            .await
            .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

        return Ok(normalize_market_record(payload.market));
    }

    Err(format!(
        "Kalshi request exceeded retry budget for market details: {ticker}"
    ))
}

async fn fetch_event_metadata(
    client: &reqwest::Client,
    event_ticker: &str,
    perf: &mut PerfStats,
) -> Result<EventSummary, String> {
    for attempt in 0..=PUBLIC_REQUEST_RETRIES {
        let request_started_at = Instant::now();
        let response = client
            .get(format!("{API_BASE_URL}/events/{event_ticker}"))
            .send()
            .await
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let status = response.status();
        perf.log_http("event_metadata", request_started_at, Some(status.as_u16()));

        if status == reqwest::StatusCode::TOO_MANY_REQUESTS && attempt < PUBLIC_REQUEST_RETRIES {
            sleep(retry_delay_for_attempt(attempt)).await;
            continue;
        }

        let response = response
            .error_for_status()
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let payload: ApiEventResponse = response
            .json()
            .await
            .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

        return Ok(normalize_event_summary(payload.event));
    }

    Err(format!(
        "Kalshi request exceeded retry budget for event metadata: {event_ticker}"
    ))
}

async fn fetch_event_details_data(
    client: &reqwest::Client,
    event_ticker: &str,
    perf: &mut PerfStats,
) -> Result<(EventSummary, EventDetails), String> {
    fetch_event_details_data_maybe(client, event_ticker, perf, false)
        .await?
        .ok_or_else(|| format!("Missing event details for {event_ticker}"))
}

async fn fetch_event_details_data_maybe(
    client: &reqwest::Client,
    event_ticker: &str,
    perf: &mut PerfStats,
    allow_not_found: bool,
) -> Result<Option<(EventSummary, EventDetails)>, String> {
    for attempt in 0..=PUBLIC_REQUEST_RETRIES {
        let request_started_at = Instant::now();
        let response = client
            .get(format!("{API_BASE_URL}/events/{event_ticker}"))
            .query(&[("with_nested_markets", "true")])
            .send()
            .await
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let status = response.status();
        perf.log_http("event_details", request_started_at, Some(status.as_u16()));

        if status == reqwest::StatusCode::NOT_FOUND && allow_not_found {
            return Ok(None);
        }

        if status == reqwest::StatusCode::TOO_MANY_REQUESTS && attempt < PUBLIC_REQUEST_RETRIES {
            sleep(retry_delay_for_attempt(attempt)).await;
            continue;
        }

        let response = response
            .error_for_status()
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let payload: ApiEventResponse = response
            .json()
            .await
            .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

        let event = payload.event;
        return Ok(Some((
            normalize_event_summary(event.clone()),
            normalize_event_details(event),
        )));
    }

    Err(format!(
        "Kalshi request exceeded retry budget for event details: {event_ticker}"
    ))
}

async fn fetch_event_details_parallel(
    client: &reqwest::Client,
    event_ids: Vec<String>,
    command: &'static str,
) -> Result<(BTreeMap<String, (EventSummary, EventDetails)>, PerfSnapshot), String> {
    let mut pending = event_ids.into_iter();
    let mut join_set = JoinSet::new();
    let mut events = BTreeMap::new();
    let mut perf = PerfSnapshot::default();

    for _ in 0..EVENT_DETAILS_CONCURRENCY {
        let Some(event_id) = pending.next() else {
            break;
        };
        let client = client.clone();
        join_set.spawn(async move {
            let mut local_perf = PerfStats::new(command);
            let result = fetch_event_details_data(&client, &event_id, &mut local_perf).await;
            (event_id, result, local_perf.snapshot())
        });
    }

    while let Some(joined) = join_set.join_next().await {
        let (event_id, result, snapshot) =
            joined.map_err(|error| format!("Event detail task failed: {error}"))?;
        perf.absorb(&snapshot);
        events.insert(event_id, result?);

        if let Some(next_event_id) = pending.next() {
            let client = client.clone();
            join_set.spawn(async move {
                let mut local_perf = PerfStats::new(command);
                let result =
                    fetch_event_details_data(&client, &next_event_id, &mut local_perf).await;
                (next_event_id, result, local_perf.snapshot())
            });
        }
    }

    Ok((events, perf))
}

async fn fetch_market_details_parallel(
    client: &reqwest::Client,
    tickers: Vec<String>,
    command: &'static str,
) -> Result<(BTreeMap<String, MarketRecord>, PerfSnapshot), String> {
    let mut pending = tickers.into_iter();
    let mut join_set = JoinSet::new();
    let mut markets = BTreeMap::new();
    let mut perf = PerfSnapshot::default();

    for _ in 0..REFRESH_CONCURRENCY {
        let Some(ticker) = pending.next() else {
            break;
        };
        let client = client.clone();
        join_set.spawn(async move {
            let mut local_perf = PerfStats::new(command);
            let result = fetch_market_details(&client, &ticker, &mut local_perf).await;
            (ticker, result, local_perf.snapshot())
        });
    }

    while let Some(joined) = join_set.join_next().await {
        let (ticker, result, snapshot) =
            joined.map_err(|error| format!("Market detail task failed: {error}"))?;
        perf.absorb(&snapshot);
        markets.insert(ticker, result?);

        if let Some(next_ticker) = pending.next() {
            let client = client.clone();
            join_set.spawn(async move {
                let mut local_perf = PerfStats::new(command);
                let result = fetch_market_details(&client, &next_ticker, &mut local_perf).await;
                (next_ticker, result, local_perf.snapshot())
            });
        }
    }

    Ok((markets, perf))
}

async fn fetch_event_metadata_parallel(
    client: &reqwest::Client,
    event_ids: Vec<String>,
    command: &'static str,
) -> Result<(BTreeMap<String, EventSummary>, PerfSnapshot), String> {
    let mut pending = event_ids.into_iter();
    let mut join_set = JoinSet::new();
    let mut events = BTreeMap::new();
    let mut perf = PerfSnapshot::default();

    for _ in 0..REFRESH_CONCURRENCY {
        let Some(event_id) = pending.next() else {
            break;
        };
        let client = client.clone();
        join_set.spawn(async move {
            let mut local_perf = PerfStats::new(command);
            let result = fetch_event_metadata(&client, &event_id, &mut local_perf).await;
            (event_id, result, local_perf.snapshot())
        });
    }

    while let Some(joined) = join_set.join_next().await {
        let (event_id, result, snapshot) =
            joined.map_err(|error| format!("Event metadata task failed: {error}"))?;
        perf.absorb(&snapshot);
        events.insert(event_id, result?);

        if let Some(next_event_id) = pending.next() {
            let client = client.clone();
            join_set.spawn(async move {
                let mut local_perf = PerfStats::new(command);
                let result = fetch_event_metadata(&client, &next_event_id, &mut local_perf).await;
                (next_event_id, result, local_perf.snapshot())
            });
        }
    }

    Ok((events, perf))
}

async fn fetch_categories_list(perf: &mut PerfStats) -> Result<Vec<String>, String> {
    let client = build_public_client().await?;

    let request_started_at = Instant::now();
    let response = client
        .get(format!("{API_BASE_URL}/series"))
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    perf.log_http(
        "series",
        request_started_at,
        Some(response.status().as_u16()),
    );

    let response = response
        .error_for_status()
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let payload: ApiSeriesResponse = response
        .json()
        .await
        .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

    let mut categories: Vec<String> = payload
        .series
        .into_iter()
        .filter_map(|series| series.category)
        .collect();

    categories.sort();
    categories.dedup();
    Ok(categories)
}

#[allow(dead_code)]
async fn fetch_complete_category_events(
    category: &str,
    perf: &mut PerfStats,
) -> Result<Vec<EventSummary>, String> {
    fetch_complete_category_events_with_limit(category, None, perf).await
}

async fn fetch_complete_category_events_with_limit(
    category: &str,
    max_pages_per_source: Option<usize>,
    perf: &mut PerfStats,
) -> Result<Vec<EventSummary>, String> {
    let client = build_public_client().await?;
    let command = perf.command;

    let mut join_set = JoinSet::new();
    for source in ["standard", "multivariate"] {
        let client = client.clone();
        let category_name = category.to_string();
        join_set.spawn(async move {
            let mut local_perf = PerfStats::new(command);
            let result = match source {
                "standard" => {
                    fetch_event_page(
                        &client,
                        "/events",
                        &category_name,
                        true,
                        None,
                        &mut local_perf,
                    )
                    .await
                }
                "multivariate" => {
                    fetch_event_page(
                        &client,
                        "/events/multivariate",
                        &category_name,
                        false,
                        None,
                        &mut local_perf,
                    )
                    .await
                }
                _ => Err("Unknown event source requested.".to_string()),
            };
            (source.to_string(), result, local_perf.snapshot())
        });
    }

    let mut standard_first: Option<EventPage> = None;
    let mut multivariate_first: Option<EventPage> = None;
    while let Some(joined) = join_set.join_next().await {
        let (source, result, snapshot) =
            joined.map_err(|error| format!("Category page task failed: {error}"))?;
        perf.absorb(&snapshot);
        match source.as_str() {
            "standard" => standard_first = Some(result?),
            "multivariate" => multivariate_first = Some(result?),
            _ => return Err("Unknown event source requested.".to_string()),
        }
    }

    let standard_first = standard_first.ok_or("Missing standard page.")?;
    let multivariate_first = multivariate_first.ok_or("Missing multivariate page.")?;

    let mut accumulated = merge_event_summaries(standard_first.events, multivariate_first.events);
    let mut standard_cursor = standard_first.cursor;
    let mut multivariate_cursor = multivariate_first.cursor;
    let mut standard_pages = 1usize;
    let mut multivariate_pages = 1usize;

    while standard_cursor.is_some() || multivariate_cursor.is_some() {
        if let Some(cursor) = standard_cursor.take() {
            if max_pages_per_source.is_none_or(|limit| standard_pages < limit) {
                let page = fetch_event_page(&client, "/events", category, true, Some(cursor), perf)
                    .await?;
                accumulated = merge_event_summaries(accumulated, page.events);
                standard_cursor = page.cursor;
                standard_pages += 1;
            }
        }

        if let Some(cursor) = multivariate_cursor.take() {
            if max_pages_per_source.is_none_or(|limit| multivariate_pages < limit) {
                let page = fetch_event_page(
                    &client,
                    "/events/multivariate",
                    category,
                    false,
                    Some(cursor),
                    perf,
                )
                .await?;
                accumulated = merge_event_summaries(accumulated, page.events);
                multivariate_cursor = page.cursor;
                multivariate_pages += 1;
            }
        }
    }

    Ok(accumulated)
}

#[tauri::command]
async fn fetch_categories_command() -> Result<Vec<String>, String> {
    let mut perf = PerfStats::new("fetch_categories_command");
    let command_started_at = Instant::now();

    let result = fetch_categories_list(&mut perf).await;

    perf.finish(command_started_at, result.is_ok());
    result
}

#[tauri::command]
async fn fetch_event_page_command(
    source: String,
    category: String,
    cursor: Option<String>,
) -> Result<EventPage, String> {
    let mut perf = PerfStats::new("fetch_event_page_command");
    let command_started_at = Instant::now();

    let result = async {
        let client = build_public_client().await?;

        match source.as_str() {
            "standard" => {
                fetch_event_page(&client, "/events", &category, true, cursor, &mut perf).await
            }
            "multivariate" => {
                fetch_event_page(
                    &client,
                    "/events/multivariate",
                    &category,
                    false,
                    cursor,
                    &mut perf,
                )
                .await
            }
            _ => Err("Unknown event source requested.".to_string()),
        }
    }
    .await;

    perf.finish(command_started_at, result.is_ok());
    result
}

#[tauri::command]
async fn fetch_event_details_command(event_ticker: String) -> Result<EventDetails, String> {
    let mut perf = PerfStats::new("fetch_event_details_command");
    let command_started_at = Instant::now();

    let result = async {
        let client = build_public_client().await?;
        let (_, details) = fetch_event_details_data(&client, &event_ticker, &mut perf).await?;
        Ok(details)
    }
    .await;

    perf.finish(command_started_at, result.is_ok());
    result
}

#[tauri::command]
async fn fetch_positions_command() -> Result<Vec<PositionRecord>, String> {
    let mut perf = PerfStats::new("fetch_positions_command");
    let command_started_at = Instant::now();

    let result = fetch_positions_records(&mut perf).await;

    perf.finish(command_started_at, result.is_ok());
    result
}

#[tauri::command]
async fn fetch_watch_markets_command(tickers: Vec<String>) -> Result<Vec<PositionRecord>, String> {
    let mut perf = PerfStats::new("fetch_watch_markets_command");
    let command_started_at = Instant::now();

    let result = fetch_watch_records(tickers, &mut perf).await;

    perf.finish(command_started_at, result.is_ok());
    result
}

async fn fetch_watch_records(
    tickers: Vec<String>,
    perf: &mut PerfStats,
) -> Result<Vec<PositionRecord>, String> {
    let public_client = build_public_client().await?;
    let deduped_tickers = tickers
        .into_iter()
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();

    let command = perf.command;
    let (markets_by_ticker, market_perf) =
        fetch_market_details_parallel(&public_client, deduped_tickers.clone(), command).await?;
    perf.absorb(&market_perf);

    let event_ids = markets_by_ticker
        .values()
        .map(|market| market.event_id.clone())
        .collect::<BTreeSet<_>>()
        .into_iter()
        .collect::<Vec<_>>();

    let (events_by_id, event_perf) =
        fetch_event_metadata_parallel(&public_client, event_ids, command).await?;
    perf.absorb(&event_perf);

    let mut records = Vec::new();

    for ticker in deduped_tickers {
        let Some(market) = markets_by_ticker.get(&ticker) else {
            continue;
        };
        let Some(event) = events_by_id.get(&market.event_id) else {
            return Err(format!(
                "Missing event metadata for watched market {}.",
                ticker
            ));
        };
        records.push(build_watch_record(market, event));
    }

    Ok(records)
}

async fn fetch_positions_records(perf: &mut PerfStats) -> Result<Vec<PositionRecord>, String> {
    let public_client = build_public_client().await?;
    let auth_client = build_public_client().await?;
    let auth = load_auth_config()?;

    let mut positions = Vec::new();
    let mut event_tickers = BTreeSet::new();
    let mut cursor: Option<String> = None;

    loop {
        let mut path =
            "/portfolio/positions?limit=200&count_filter=position,total_traded".to_string();
        if let Some(current_cursor) = &cursor {
            path.push_str("&cursor=");
            path.push_str(current_cursor);
        }

        let response = authenticated_get(&auth_client, &auth, &path, perf).await?;
        let response = response
            .error_for_status()
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let payload: ApiPositionsResponse = response
            .json()
            .await
            .map_err(|error| format!("Unable to parse positions response: {error}"))?;

        event_tickers.extend(
            payload
                .event_positions
                .into_iter()
                .map(|event| event.event_ticker),
        );
        positions.extend(payload.market_positions);
        cursor = payload.cursor.filter(|value| !value.is_empty());
        if cursor.is_none() {
            break;
        }
    }

    let command = perf.command;
    let position_by_ticker: BTreeMap<String, ApiMarketPosition> = positions
        .into_iter()
        .map(|position| (position.ticker.clone(), position))
        .collect();
    let (event_bundles, event_perf) =
        fetch_event_details_parallel(&public_client, event_tickers.into_iter().collect(), command)
            .await?;
    perf.absorb(&event_perf);

    let mut markets_by_ticker = BTreeMap::new();
    let mut events_by_market_ticker = BTreeMap::new();

    for (_, (event_summary, event_details)) in event_bundles {
        for market in event_details.markets {
            let ticker = market.id.clone();
            markets_by_ticker.insert(ticker.clone(), market);
            events_by_market_ticker.insert(ticker, event_summary.clone());
        }
    }

    let mut records = Vec::new();

    for (ticker, position) in position_by_ticker {
        let Some(market) = markets_by_ticker.get(&ticker) else {
            continue;
        };
        if !is_open_like_market(Some(&market.status)) {
            continue;
        }

        let Some(event) = events_by_market_ticker.get(&ticker) else {
            return Err(format!(
                "Missing event metadata for market {} while building positions.",
                ticker
            ));
        };

        records.push(PositionRecord {
            ticker: market.id.clone(),
            event_ticker: event.id.clone(),
            category: event.category.clone(),
            event_title: event.title.clone(),
            market_label: market.label.clone(),
            start_time: event.start_time.clone(),
            is_live: event.is_live,
            yes_bid: market.yes_bid,
            yes_ask: market.yes_ask,
            no_bid: market.no_bid,
            no_ask: market.no_ask,
            volume: market.volume,
            position: parse_f64(&position.position_fp),
            exposure_dollars: parse_f64(&position.market_exposure_dollars),
            total_traded_dollars: parse_f64(&position.total_traded_dollars),
            realized_pnl_dollars: parse_f64(&position.realized_pnl_dollars),
            fees_paid_dollars: parse_f64(&position.fees_paid_dollars),
            rules_primary: market.rules_primary.clone(),
        });
    }

    Ok(records)
}

pub async fn benchmark_positions_once() -> Result<PositionsBenchmarkSummary, String> {
    let started_at = Instant::now();
    let mut perf = PerfStats::new("benchmark_positions_once");
    let records = fetch_positions_records(&mut perf).await?;

    Ok(PositionsBenchmarkSummary {
        duration_ms: started_at.elapsed().as_millis(),
        row_count: records.len(),
        perf: perf.snapshot(),
    })
}

pub async fn benchmark_watching_once(
    tickers: Vec<String>,
) -> Result<WatchingBenchmarkSummary, String> {
    let started_at = Instant::now();
    let mut perf = PerfStats::new("benchmark_watching_once");
    let records = fetch_watch_records(tickers, &mut perf).await?;

    Ok(WatchingBenchmarkSummary {
        duration_ms: started_at.elapsed().as_millis(),
        row_count: records.len(),
        perf: perf.snapshot(),
    })
}

pub async fn benchmark_category_once(category: String) -> Result<CategoryBenchmarkSummary, String> {
    benchmark_category_limited_once(category, None).await
}

pub async fn benchmark_category_limited_once(
    category: String,
    max_pages_per_source: Option<usize>,
) -> Result<CategoryBenchmarkSummary, String> {
    let started_at = Instant::now();
    let mut perf = PerfStats::new("benchmark_category_once");
    let events =
        fetch_complete_category_events_with_limit(&category, max_pages_per_source, &mut perf)
            .await?;

    Ok(CategoryBenchmarkSummary {
        duration_ms: started_at.elapsed().as_millis(),
        category,
        event_count: events.len(),
        pages_per_source: max_pages_per_source.unwrap_or(usize::MAX),
        perf: perf.snapshot(),
    })
}

pub async fn benchmark_list_categories() -> Result<Vec<String>, String> {
    let mut perf = PerfStats::new("benchmark_list_categories");
    fetch_categories_list(&mut perf).await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            fetch_categories_command,
            fetch_event_page_command,
            fetch_event_details_command,
            fetch_positions_command,
            fetch_watch_markets_command
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
