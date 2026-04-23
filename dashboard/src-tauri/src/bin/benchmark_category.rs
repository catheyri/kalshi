use kalshi_dashboard_lib::{benchmark_category_limited_once, benchmark_list_categories};
use serde::Serialize;
use std::env;
use std::fs;
use std::path::PathBuf;

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct BenchmarkRun {
    iteration: usize,
    category: String,
    duration_ms: u128,
    event_count: usize,
    pages_per_source: usize,
    request_count: usize,
    request_duration_ms: u128,
    signing_count: usize,
    signing_duration_ms: u128,
}

#[derive(Serialize)]
#[serde(rename_all = "camelCase")]
struct BenchmarkReport {
    runs: Vec<BenchmarkRun>,
    average_duration_ms: u128,
    average_request_count: usize,
    average_request_duration_ms: u128,
    average_signing_duration_ms: u128,
}

fn apply_env_file(path: &PathBuf) -> Result<(), String> {
    let contents = fs::read_to_string(path)
        .map_err(|error| format!("Unable to read env file {}: {error}", path.display()))?;

    for raw in contents.lines() {
        let line = raw.trim();
        if line.is_empty() || line.starts_with('#') || !line.contains('=') {
            continue;
        }

        let (key, value) = line
            .split_once('=')
            .ok_or_else(|| format!("Invalid env entry in {}", path.display()))?;

        unsafe {
            env::set_var(
                key.trim(),
                value.trim().trim_matches('"').trim_matches('\''),
            );
        }
    }

    Ok(())
}

#[tokio::main]
async fn main() {
    let mut repeat_count = 1usize;
    let mut env_file: Option<PathBuf> = None;
    let mut list_categories = false;
    let mut max_pages_per_source: Option<usize> = None;
    let mut category: Option<String> = None;
    let mut args = env::args().skip(1);

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--env-file" => {
                let Some(path) = args.next() else {
                    eprintln!("--env-file requires a path");
                    std::process::exit(1);
                };
                env_file = Some(PathBuf::from(path));
            }
            "--list-categories" => {
                list_categories = true;
            }
            "--max-pages-per-source" => {
                let Some(value) = args.next() else {
                    eprintln!("--max-pages-per-source requires a number");
                    std::process::exit(1);
                };
                max_pages_per_source = value.parse::<usize>().ok().filter(|count| *count > 0);
                if max_pages_per_source.is_none() {
                    eprintln!("--max-pages-per-source requires a positive number");
                    std::process::exit(1);
                }
            }
            value => {
                if category.is_none() {
                    if let Some(parsed) = value.parse::<usize>().ok().filter(|count| *count > 0) {
                        repeat_count = parsed;
                        continue;
                    }
                }

                if category.is_none() {
                    category = Some(value.to_string());
                } else {
                    eprintln!("Unexpected extra argument: {value}");
                    std::process::exit(1);
                }
            }
        }
    }

    if let Some(path) = env_file {
        if let Err(error) = apply_env_file(&path) {
            eprintln!(
                "{}",
                serde_json::json!({
                    "kind": "benchmark_error",
                    "error": error,
                })
            );
            std::process::exit(1);
        }
    }

    if list_categories {
        match benchmark_list_categories().await {
            Ok(categories) => {
                for category in categories {
                    println!("{category}");
                }
            }
            Err(error) => {
                eprintln!(
                    "{}",
                    serde_json::json!({
                        "kind": "benchmark_error",
                        "error": error,
                    })
                );
                std::process::exit(1);
            }
        }
        return;
    }

    let Some(category) = category else {
        eprintln!("Provide a category name or use --list-categories.");
        std::process::exit(1);
    };

    let mut runs = Vec::with_capacity(repeat_count);

    for iteration in 1..=repeat_count {
        match benchmark_category_limited_once(category.clone(), max_pages_per_source).await {
            Ok(summary) => runs.push(BenchmarkRun {
                iteration,
                category: summary.category,
                duration_ms: summary.duration_ms,
                event_count: summary.event_count,
                pages_per_source: summary.pages_per_source,
                request_count: summary.perf.request_count,
                request_duration_ms: summary.perf.request_duration_ms,
                signing_count: summary.perf.signing_count,
                signing_duration_ms: summary.perf.signing_duration_ms,
            }),
            Err(error) => {
                eprintln!(
                    "{}",
                    serde_json::json!({
                        "kind": "benchmark_error",
                        "iteration": iteration,
                        "error": error,
                    })
                );
                std::process::exit(1);
            }
        }
    }

    let run_count = runs.len() as u128;
    let average_duration_ms = runs.iter().map(|run| run.duration_ms).sum::<u128>() / run_count;
    let average_request_count =
        runs.iter().map(|run| run.request_count).sum::<usize>() / runs.len();
    let average_request_duration_ms =
        runs.iter().map(|run| run.request_duration_ms).sum::<u128>() / run_count;
    let average_signing_duration_ms =
        runs.iter().map(|run| run.signing_duration_ms).sum::<u128>() / run_count;

    let report = BenchmarkReport {
        runs,
        average_duration_ms,
        average_request_count,
        average_request_duration_ms,
        average_signing_duration_ms,
    };

    println!(
        "{}",
        serde_json::to_string_pretty(&report).expect("benchmark report should serialize")
    );
}
