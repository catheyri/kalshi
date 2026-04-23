#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"


def load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def sign_message(private_key_path: str, message: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as message_file:
        message_file.write(message.encode("utf-8"))
        message_file.flush()
        message_path = message_file.name

    try:
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                private_key_path,
                "-sigopt",
                "rsa_padding_mode:pss",
                "-sigopt",
                "rsa_pss_saltlen:digest",
                message_path,
            ],
            check=True,
            capture_output=True,
        )
    finally:
        Path(message_path).unlink(missing_ok=True)

    return base64.b64encode(result.stdout).decode("utf-8")


def build_headers(method: str, path: str) -> dict[str, str]:
    api_key_id = require_env("KALSHI_API_KEY_ID")
    private_key_path = require_env("KALSHI_PRIVATE_KEY_PATH")
    base_url = require_env("KALSHI_API_BASE_URL").rstrip("/")
    timestamp = str(int(time.time() * 1000))
    full_url = f"{base_url}{path}"
    parsed = urllib.parse.urlparse(full_url)
    path_without_query = parsed.path
    message = f"{timestamp}{method.upper()}{path_without_query}"
    signature = sign_message(private_key_path, message)

    return {
        "KALSHI-ACCESS-KEY": api_key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "Content-Type": "application/json",
        "User-Agent": "kalshi-local-client/0.1",
    }


def make_request(method: str, path: str) -> tuple[int, object]:
    base_url = require_env("KALSHI_API_BASE_URL").rstrip("/")
    full_url = f"{base_url}{path}"
    headers = build_headers(method, path)
    request = urllib.request.Request(full_url, method=method.upper(), headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        parsed = json.loads(body) if body else {"error": exc.reason}
        return exc.code, parsed


def resolve_endpoint(name: str) -> str:
    endpoints = {
        "balance": "/portfolio/balance",
        "api-keys": "/api_keys",
    }
    if name not in endpoints:
        raise SystemExit(f"Unknown endpoint alias: {name}")
    return endpoints[name]


def main() -> int:
    load_dotenv(ENV_PATH)

    parser = argparse.ArgumentParser(description="Minimal Kalshi API client")
    parser.add_argument(
        "endpoint",
        nargs="?",
        default="balance",
        help="Endpoint alias to call: balance or api-keys",
    )
    args = parser.parse_args()

    path = resolve_endpoint(args.endpoint)
    status, payload = make_request("GET", path)

    print(f"HTTP {status}")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
