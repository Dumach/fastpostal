# FastPostal

A FastAPI-based microservice for parsing postal addresses using [libpostal](https://github.com/openvenues/libpostal).

## Features

- Address parsing via libpostal
- API key authentication (production mode)
- Rate limiting (60 req/min)
- SSL support
- Health check endpoint
- Auto-scaled worker count (CPU core count in production)

## Requirements

- Python 3.12+

(libpostal is bundled with the `postal` package — no system library install needed.)

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
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8080` | Server port |
| `SSL_CERT` | - | Path to SSL certificate |
| `SSL_KEY` | - | Path to SSL private key |
| `ACCESS_KEY` | - | Comma-separated API keys |
| `ENVIRONMENT` | `PROD` | `DEV`, `DEBUG`, or `PROD` |
| `LOG_PATH` | `./logs` | Directory for `access.log` (rotating, 1 MB x 5) |

Note: values already set in the environment win over `.env` (dotenv does not override), and env vars are read once at startup — restart after changing them.

## Running

```bash
uv run serve
```

- **DEV**: Auto-reload, single worker, no auth required
- **DEBUG**: Single worker, auth required, debug log level
- **PROD**: Workers = CPU core count, auth required

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

Verifies libpostal is working correctly by parsing a fixed address. Returns 503 if parsed labels mismatch, 500 if parsing raises.

### `GET /parse?address={address}`

Parses an address into components.

**Query Parameters:**
- `address` (required): Address string to parse

**Auth (production):**
- `X-API-KEY` header, **or**
- `token` query parameter (e.g. `/parse?address=...&token=...`)

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
| 429 | Rate limit exceeded (60 req/min per IP) |
| 500 | Server error |

## License

See [license](license).
