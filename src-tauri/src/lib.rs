use base64::Engine;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

const API_BASE_URL: &str = "https://api.elections.kalshi.com/trade-api/v2";

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
                value.trim().trim_matches('"').trim_matches('\'').to_string(),
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

fn sign_message(private_key_path: &str, message: &str) -> Result<String, String> {
    let temp_path = std::env::temp_dir().join(format!(
        "kalshi-signature-{}-{}.txt",
        std::process::id(),
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_millis())
            .unwrap_or_default()
    ));

    fs::write(&temp_path, message).map_err(|error| format!("Unable to write temp file: {error}"))?;

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
) -> Result<reqwest::Response, String> {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().to_string())
        .map_err(|error| format!("Unable to build timestamp: {error}"))?;

    let path_only = path_and_query
        .split('?')
        .next()
        .ok_or("Invalid request path.")?;
    let message = format!("{timestamp}GET{path_only}");
    let signature = sign_message(&config.private_key_path, &message)?;

    client
        .get(format!("{}{}", config.base_url.trim_end_matches('/'), path_and_query))
        .header("KALSHI-ACCESS-KEY", &config.api_key_id)
        .header("KALSHI-ACCESS-TIMESTAMP", timestamp)
        .header("KALSHI-ACCESS-SIGNATURE", signature)
        .header("Content-Type", "application/json")
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"))
}

async fn fetch_event_page(
    client: &reqwest::Client,
    path: &str,
    category: &str,
    include_status: bool,
    cursor: Option<String>,
) -> Result<EventPage, String> {
    let mut request = client
        .get(format!("{API_BASE_URL}{path}"))
        .query(&[("limit", "200"), ("category", category)]);

    if include_status {
        request = request.query(&[("status", "open")]);
    }

    if let Some(ref current_cursor) = cursor {
        request = request.query(&[("cursor", current_cursor)]);
    }

    let response = request
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let response = response
        .error_for_status()
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let payload: ApiEventsResponse = response
        .json()
        .await
        .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

    Ok(EventPage {
        category: category.to_string(),
        events: payload
            .events
            .unwrap_or_default()
            .into_iter()
            .map(normalize_event_summary)
            .filter(|event| event.category == category)
            .collect(),
        cursor: payload.cursor.filter(|value| !value.is_empty()),
    })
}

async fn fetch_market_details(client: &reqwest::Client, ticker: &str) -> Result<MarketRecord, String> {
    let response = client
        .get(format!("{API_BASE_URL}/markets/{ticker}"))
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let response = response
        .error_for_status()
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let payload: ApiMarketResponse = response
        .json()
        .await
        .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

    Ok(normalize_market_record(payload.market))
}

async fn fetch_event_metadata(client: &reqwest::Client, event_ticker: &str) -> Result<EventSummary, String> {
    let response = client
        .get(format!("{API_BASE_URL}/events/{event_ticker}"))
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let response = response
        .error_for_status()
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let payload: ApiEventResponse = response
        .json()
        .await
        .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

    Ok(normalize_event_summary(payload.event))
}

#[tauri::command]
async fn fetch_categories_command() -> Result<Vec<String>, String> {
    let client = build_public_client().await?;

    let response = client
        .get(format!("{API_BASE_URL}/series"))
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

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

#[tauri::command]
async fn fetch_event_page_command(
    source: String,
    category: String,
    cursor: Option<String>,
) -> Result<EventPage, String> {
    let client = build_public_client().await?;

    match source.as_str() {
        "standard" => fetch_event_page(&client, "/events", &category, true, cursor).await,
        "multivariate" => {
            fetch_event_page(&client, "/events/multivariate", &category, false, cursor).await
        }
        _ => Err("Unknown event source requested.".to_string()),
    }
}

#[tauri::command]
async fn fetch_event_details_command(event_ticker: String) -> Result<EventDetails, String> {
    let client = build_public_client().await?;

    let response = client
        .get(format!("{API_BASE_URL}/events/{event_ticker}"))
        .query(&[("with_nested_markets", "true")])
        .send()
        .await
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let response = response
        .error_for_status()
        .map_err(|error| format!("Kalshi request failed: {error}"))?;

    let payload: ApiEventResponse = response
        .json()
        .await
        .map_err(|error| format!("Unable to parse Kalshi response: {error}"))?;

    Ok(normalize_event_details(payload.event))
}

#[tauri::command]
async fn fetch_positions_command() -> Result<Vec<PositionRecord>, String> {
    let public_client = build_public_client().await?;
    let auth_client = build_public_client().await?;
    let auth = load_auth_config()?;

    let mut positions = Vec::new();
    let mut cursor: Option<String> = None;

    loop {
        let mut path = "/portfolio/positions?limit=200&count_filter=position,total_traded".to_string();
        if let Some(current_cursor) = &cursor {
            path.push_str("&cursor=");
            path.push_str(current_cursor);
        }

        let response = authenticated_get(&auth_client, &auth, &path).await?;
        let response = response
            .error_for_status()
            .map_err(|error| format!("Kalshi request failed: {error}"))?;

        let payload: ApiPositionsResponse = response
            .json()
            .await
            .map_err(|error| format!("Unable to parse positions response: {error}"))?;

        positions.extend(payload.market_positions);
        cursor = payload.cursor.filter(|value| !value.is_empty());
        if cursor.is_none() {
            break;
        }
    }

    let mut event_cache: BTreeMap<String, EventSummary> = BTreeMap::new();
    let mut records = Vec::new();

    for position in positions {
        let market = fetch_market_details(&public_client, &position.ticker).await?;

        if !is_open_like_market(Some(&market.status)) {
          continue;
        }

        let event = if let Some(existing) = event_cache.get(&market.event_id) {
            existing.clone()
        } else {
            let fetched = fetch_event_metadata(&public_client, &market.event_id).await?;
            event_cache.insert(market.event_id.clone(), fetched.clone());
            fetched
        };

        records.push(PositionRecord {
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

#[tauri::command]
async fn fetch_watch_markets_command(tickers: Vec<String>) -> Result<Vec<PositionRecord>, String> {
    let public_client = build_public_client().await?;
    let mut event_cache: BTreeMap<String, EventSummary> = BTreeMap::new();
    let mut deduped: BTreeSet<String> = BTreeSet::new();
    let mut records = Vec::new();

    for ticker in tickers {
        if !deduped.insert(ticker.clone()) {
            continue;
        }

        let market = fetch_market_details(&public_client, &ticker).await?;
        let event = if let Some(existing) = event_cache.get(&market.event_id) {
            existing.clone()
        } else {
            let fetched = fetch_event_metadata(&public_client, &market.event_id).await?;
            event_cache.insert(market.event_id.clone(), fetched.clone());
            fetched
        };

        records.push(PositionRecord {
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
        });
    }

    Ok(records)
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
