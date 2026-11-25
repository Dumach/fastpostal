"""Uvicorn entrypoint: load settings and run the app."""

import uvicorn

from fastpostal.config import Environment, get_settings
from fastpostal.logging_config import log_config


def serve() -> None:
    """Load settings and start the uvicorn server."""
    settings = get_settings()
    uvicorn.run(
        "fastpostal.app:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        log_config=log_config,
        reload=settings.environment == Environment.DEV,
        ssl_certfile=settings.ssl_cert,
        ssl_keyfile=settings.ssl_key,
        workers=settings.workers,
        proxy_headers=True,  # Trust X-Forwarded headers from reverse proxy
        forwarded_allow_ips="*",  # Allow forwarded headers from any IP
    )


if __name__ == "__main__":
    serve()
