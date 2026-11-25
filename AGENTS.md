# AGENTS.md

FastAPI microservice that parses postal addresses via libpostal (the `postal` PyPI package bundles the compiled libpostal binaries — no system library install needed).

## Commands

- `uv sync` — install deps (Python 3.12, pinned in `.python-version`)
- `uv run python main.py` — run the server (reads `.env`, default port 8080)
- `uv run pytest` — run tests; single test: `uv run pytest tests/test_endpoints.py::TestParseProd::test_no_auth_returns_401`
- `uv run ruff check .` — lint (ruff is configured in `pyproject.toml` but not a project dependency; it still resolves via uv). Line length 120, rules E/F only, F401 ignored.

## How it's wired

- `main.py` (root) parses env vars at import time and launches uvicorn with `src.app:app`; `src/app.py` imports `mode`/`ACCESS_KEYS` back from `main`. Don't restructure these imports without updating the tests.
- `ENVIRONMENT` (default `PROD` when unset) controls behavior:
  - `DEV` — auth bypassed, auto-reload, 1 worker
  - `DEBUG` — auth required, 1 worker, debug log level
  - `PROD` — auth required, `cpu_count()` workers
- Env vars are read once at import: changes to `ENVIRONMENT`, `ACCESS_KEY`, etc. require a restart. `load_dotenv()` never overrides vars already set, so real env vars win over `.env`.
- Auth for `/parse`: `X-API-KEY` header **or** `token` query param; `ACCESS_KEY` env var holds comma-separated keys. `/` and `/health` are exempt from auth.
- All endpoints are rate-limited to 60 req/min per IP (slowapi).
- `LOG_PATH` (default `./logs`) receives `access.log` (rotating, 1 MB × 5).
- Deployed via systemd: `config/fastpostal.service` runs `uv run main.py`. Note its `WorkingDirectory=/home/alex/fastpostal` does not match this repo's location — verify before deploying or changing it.

## Tests

- Tests mock `postal.parser.parse_address`; only the live `/health` endpoint exercises real parsing (it parses a fixed Cupertino address and returns 503 on label mismatch, 500 on exception).
- Mode-dependent tests re-import `src.app` by purging `sys.modules` and setting `ENVIRONMENT`/`ACCESS_KEY` first (`_get_app` in `tests/test_endpoints.py`). Keep that pattern when adding mode-specific tests.
