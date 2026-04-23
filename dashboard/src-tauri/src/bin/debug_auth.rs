use reqwest::Client;
use serde::Deserialize;
use serde_json::Value;
use std::env;
use std::fs;
use std::process::Command;
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Deserialize)]
struct EnvConfig {
    key: String,
    private_key_path: String,
    base_url: String,
}

fn load_config() -> EnvConfig {
    EnvConfig {
        key: env::var("KALSHI_API_KEY_ID").expect("missing KALSHI_API_KEY_ID"),
        private_key_path: env::var("KALSHI_PRIVATE_KEY_PATH")
            .expect("missing KALSHI_PRIVATE_KEY_PATH"),
        base_url: env::var("KALSHI_API_BASE_URL").expect("missing KALSHI_API_BASE_URL"),
    }
}

fn sign_message(private_key_path: &str, message: &str) -> String {
    let temp_path = std::env::temp_dir().join("kalshi-debug-signature.txt");
    fs::write(&temp_path, message).expect("write temp message");
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
        .expect("run openssl");
    let _ = fs::remove_file(temp_path);
    if !output.status.success() {
        panic!("{}", String::from_utf8_lossy(&output.stderr));
    }
    use base64::Engine;
    base64::engine::general_purpose::STANDARD.encode(output.stdout)
}

async fn call(client: &Client, config: &EnvConfig, path: &str) {
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis()
        .to_string();
    let url = format!("{}{}", config.base_url.trim_end_matches('/'), path);
    let parsed = reqwest::Url::parse(&url).expect("parse url");
    let path_only = parsed.path();
    let signature = sign_message(
        &config.private_key_path,
        &format!("{timestamp}GET{path_only}"),
    );

    let response = client
        .get(&url)
        .header("KALSHI-ACCESS-KEY", &config.key)
        .header("KALSHI-ACCESS-TIMESTAMP", &timestamp)
        .header("KALSHI-ACCESS-SIGNATURE", signature)
        .header("Accept", "application/json")
        .header("Content-Type", "application/json")
        .header("User-Agent", "kalshi-local-client/0.1")
        .send()
        .await
        .expect("request failed");

    let status = response.status();
    let body = response.text().await.expect("read body");
    println!("PATH {path}");
    println!("HTTP {status}");

    if path.starts_with("/portfolio/positions") && status.is_success() {
        let parsed: Value = serde_json::from_str(&body).expect("parse positions body");
        println!(
            "{}",
            serde_json::to_string_pretty(&parsed).expect("serialize positions body")
        );
    } else {
        println!("{}", &body[..body.len().min(800)]);
    }
}

#[tokio::main]
async fn main() {
    let config = load_config();
    let client = Client::builder().build().expect("client");
    call(&client, &config, "/api_keys").await;
    call(&client, &config, "/portfolio/balance").await;
    call(&client, &config, "/portfolio/positions?limit=5").await;
}
