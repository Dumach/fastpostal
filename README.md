# FastPostal

A FastAPI-based microservice for parsing postal addresses using [libpostal](https://github.com/openvenues/libpostal).

## Features

- Address parsing via libpostal
- API key authentication (production mode)
- Rate limiting (60 req/min)
- SSL support
- Health check endpoint
- Configurable worker count (auto-scaled in production)

## Requirements

- Python 3.12+
- libpostal system library

## Setup

```bash
# Clone and install
git clone <repo-url>
cd fastpostal
uv sync

# Configure environment
cp sample.env .env
# Edit .env with your settings
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8080` | Server port |
| `SSL_CERT` | - | Path to SSL certificate |
| `SSL_KEY` | - | Path to SSL private key |
| `ACCESS_KEY` | - | Comma-separated API keys |
| `ENVIRONMENT` | `PROD` | `DEV`, `DEBUG`, or `PROD` |

## Running

```bash
uv run python main.py
```

- **DEV**: Auto-reload, single worker, no auth required
- **DEBUG**: Single worker, auth required
- **PROD**: Auto-scaled workers, auth required

## API Endpoints

### `GET /`

Returns server time.

```json
{
  "server_time": "2026-08-27 12:00:00",
  "timestamp": 1756300800,
  "timezone": "UTC"
}
```

### `GET /health`

Verifies libpostal is working correctly. Returns 503 if parsing fails.

### `GET /parse?address={address}`

Parses an address into components.

**Query Parameters:**
- `address` (required): Address string to parse

**Headers (production):**
- `X-API-KEY`: Your API key

**Response:**

```json
[
  { "label": "house_number", "value": "1" },
  { "label": "road", "value": "apple park way" },
  { "label": "city", "value": "cupertino" },
  { "label": "state", "value": "california" },
  { "label": "country", "value": "united states" }
]
```

**Error Responses:**

| Code | Description |
|------|-------------|
| 401 | Invalid or missing API key |
| 422 | Invalid query parameters |
| 500 | Server error |

## License

See [license](license).
