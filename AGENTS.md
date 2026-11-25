# AGENTS.md

FastAPI microservice that parses postal addresses via libpostal (the `postal` PyPI package bundles the compiled libpostal binaries — no system library install needed).

## Commands

- `uv sync` — install deps (Python 3.12, pinned in `.python-version`)
- `uv run serve` — run the server (console script for `fastpostal.serve:serve`; reads `.env`, default port 8080)
- `uv run pytest` — run tests; single test: `uv run pytest tests/test_endpoints.py::TestParseProd::test_no_auth_returns_401`
- `uv run ruff check .` — lint (ruff is configured in `pyproject.toml` but not a project dependency; it still resolves via uv). Line length 120, rules E/F only, F401 ignored.
- `ty check .` — static type analysis (system `ty` binary; not a project dependency).

## How it's wired

- The app is a proper package: `src/fastpostal/` (`app.py`, `config.py`, `models.py`, `parse_service.py`, `logging_config.py`, `serve.py`). The single run command is the `serve` console script (`fastpostal.serve:serve`), which systemd runs via `uv run serve`.
- `parse_service.py` is the only module that imports `postal`; `app.py` routes call `parse_service.parse()` / `parse_service.health_mismatches()`. It calls `parse_address` through the `postal.parser` module at call time so tests keep patching `postal.parser.parse_address`.
- All configuration lives in `fastpostal/config.py`: `Settings` (pydantic-settings, reads `.env`) plus a cached `get_settings()`.
- `fastpostal/app.py` exposes a `create_app(settings)` app factory (defaults to `get_settings()`); the module-level `app = create_app()` is the bridge that makes `uvicorn fastpostal.app:app` work.
- `ENVIRONMENT` (default `PROD` when unset) controls behavior:
  - `DEV` — auth bypassed, auto-reload
  - `DEBUG` — auth required, debug log level
  - `PROD` — auth required
- Env vars are read once at startup: changes to `ENVIRONMENT`, `ACCESS_KEY`, etc. require a restart. `.env` is read by pydantic-settings, which never overrides vars already set, so real env vars win over `.env`.
- Auth for `/parse`: `X-API-KEY` header **or** `token` query param; `ACCESS_KEY` env var holds comma-separated keys. `/` and `/health` are exempt from auth.
- Rate limit is 60 req/min per IP, but slowapi state is in-memory **per worker process** — in PROD the effective cap is 60 × workers. A strict global limit needs a shared backend (e.g. Redis). slowapi's private handler is wrapped by `rate_limit_handler` in `app.py` to satisfy Starlette's exception-handler signature (and `ty`).
- Config fails fast at startup: DEBUG/PROD require `ACCESS_KEY`; `SSL_CERT`/`SSL_KEY` must be set together and exist (validated in `Settings._fail_fast`).
- `FORWARDED_ALLOW_IPS` defaults to local proxies only (`127.0.0.1,::1`); set it if the reverse proxy is remote. A trusted proxy can rewrite the client IP, which also resets its rate-limit bucket — keep the list short.
- Logging: `serve.py` passes `build_log_config(settings.log_path, settings.log_level)` (in `logging_config.py`) to uvicorn. `LOG_PATH` (default `./logs`) receives `access.log` (rotating, 1 MB × 5). App logs come from `fastpostal.*` loggers (`logging.getLogger(__name__)`) and go to both stderr and `access.log`, mirroring the old `uvicorn.default` logger.
- Deployed via systemd: `config/fastpostal.service` runs `uv run serve`. Note its `WorkingDirectory=/home/alex/fastpostal` does not match this repo's location — verify before deploying or changing it.

## Tests

- Tests mock `postal.parser.parse_address`; only the live `/health` endpoint exercises real parsing (it parses a fixed Cupertino address and returns 503 on label mismatch, 500 on exception). `tests/test_parse_service.py` covers the service directly (component mapping, mismatch detection), `tests/test_config.py` the fail-fast validation.
- Tests build a fresh per-mode app with `create_app(Settings(environment=..., access_key=...))` (fixtures in `tests/test_endpoints.py`) — no env vars, no `sys.modules` purging. Each app instance gets its own slowapi limiter state.
