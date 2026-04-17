# kalshi

Minimal local tooling for authenticated Kalshi API calls.

## Setup

Store your credentials in [`.env`](/Users/icathey/Documents/Projects/Kalshi/.env:1):

```env
KALSHI_ENV=prod
KALSHI_API_KEY_ID=your-key-id
KALSHI_PRIVATE_KEY_PATH=/absolute/path/to/private-key.pem
KALSHI_API_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
```

## Run

Call the authenticated balance endpoint:

```bash
python3 kalshi_client.py
```

List your API keys instead:

```bash
python3 kalshi_client.py api-keys
```

This script uses OpenSSL locally to generate the RSA-PSS signature Kalshi expects for
the `KALSHI-ACCESS-SIGNATURE` header.
