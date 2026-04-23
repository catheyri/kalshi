# kalshi

Minimal local tooling for authenticated Kalshi API calls.

## Setup

Store your credentials in the repo-root `.env` file:

```env
KALSHI_ENV=prod
KALSHI_API_KEY_ID=your-key-id
KALSHI_PRIVATE_KEY_PATH=/absolute/path/to/private-key.pem
KALSHI_API_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
```

## Run

Call the authenticated balance endpoint:

```bash
cd dashboard
python3 kalshi_client.py
```

List your API keys instead:

```bash
cd dashboard
python3 kalshi_client.py api-keys
```

This script uses OpenSSL locally to generate the RSA-PSS signature Kalshi expects for
the `KALSHI-ACCESS-SIGNATURE` header.
