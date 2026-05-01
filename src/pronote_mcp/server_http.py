from __future__ import annotations

import contextlib
import hmac
import logging
import os
import sys
import time
from collections import defaultdict

import uvicorn
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Mount, Route

from .logging_setup import setup_logging
from .tools import register_tools

load_dotenv()
setup_logging()
logger = logging.getLogger(__name__)

# Rate-limit settings: lock out an IP for _LOCKOUT_SECONDS after
# _MAX_FAILURES consecutive auth failures within that window.
_MAX_FAILURES = 5
_LOCKOUT_SECONDS = 60


class BearerAuthMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/health", "/healthz"}

    def __init__(self, app, expected_token: str):
        super().__init__(app)
        self._expected = expected_token.encode("utf-8")
        # Maps IP → list of monotonic timestamps of recent failures.
        # Access is safe in a single-process asyncio server (uvicorn default):
        # all mutations occur in synchronous code between await points so the
        # event loop never interleaves two dispatches mid-mutation. If the
        # server is ever scaled to multiple worker processes each process will
        # maintain its own independent counter, which is acceptable.
        self._failures: dict[str, list[float]] = defaultdict(list)

    def _is_locked_out(self, ip: str) -> bool:
        if ip not in self._failures:
            return False
        now = time.monotonic()
        cutoff = now - _LOCKOUT_SECONDS
        recent = [t for t in self._failures[ip] if t > cutoff]
        self._failures[ip] = recent
        return len(recent) >= _MAX_FAILURES

    def _record_failure(self, ip: str) -> None:
        self._failures[ip].append(time.monotonic())

    def _clear_failures(self, ip: str) -> None:
        self._failures.pop(ip, None)

    async def dispatch(self, request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        ip = request.client.host if request.client else None
        if ip is None:
            return JSONResponse(
                {"error": "Unable to determine client address"},
                status_code=400,
            )

        if self._is_locked_out(ip):
            logger.warning(
                "Rate-limited auth attempt from %s on %s",
                ip,
                request.url.path,
            )
            return JSONResponse(
                {"error": "Too many failed authentication attempts. Try again later."},
                status_code=429,
                headers={"Retry-After": str(_LOCKOUT_SECONDS)},
            )

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            self._record_failure(ip)
            logger.warning(
                "Auth missing from %s on %s",
                ip,
                request.url.path,
            )
            return JSONResponse(
                {"error": "Missing or malformed Authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        provided = auth[7:].strip().encode("utf-8")
        if not hmac.compare_digest(provided, self._expected):
            self._record_failure(ip)
            logger.warning(
                "Invalid token from %s on %s",
                ip,
                request.url.path,
            )
            return JSONResponse({"error": "Invalid token"}, status_code=401)

        self._clear_failures(ip)
        return await call_next(request)


async def health(_request):
    return PlainTextResponse("ok")


def _require_token() -> str:
    token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    if not token:
        print(
            "FATAL: MCP_AUTH_TOKEN env var is required for HTTP mode.\n"
            "Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_urlsafe(48))\"",
            file=sys.stderr,
        )
        sys.exit(1)
    if len(token) < 24:
        print(
            f"FATAL: MCP_AUTH_TOKEN is too short ({len(token)} chars). "
            f"Use at least 24 characters (recommended: 48+).",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def build_app() -> Starlette:
    token = _require_token()

    mcp = FastMCP("pronote-mcp", stateless_http=True, json_response=True)
    register_tools(mcp)

    mcp_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(_app):
        async with mcp.session_manager.run():
            yield

    return Starlette(
        debug=False,
        lifespan=lifespan,
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/healthz", health, methods=["GET"]),
            Mount("/", app=mcp_app),
        ],
        middleware=[
            Middleware(BearerAuthMiddleware, expected_token=token),
        ],
    )


def main() -> None:
    host = os.environ.get("MCP_HTTP_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_HTTP_PORT", "8765"))

    if host == "0.0.0.0":
        logger.warning("Binding to 0.0.0.0 — make sure you are behind a reverse proxy with HTTPS!")

    app = build_app()
    logger.info("Starting pronote-mcp HTTP server on %s:%s (path /mcp/)", host, port)

    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
