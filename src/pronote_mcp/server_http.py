from __future__ import annotations

import contextlib
import hmac
import logging
import os
import sys

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


class BearerAuthMiddleware(BaseHTTPMiddleware):
    EXEMPT_PATHS = {"/health", "/healthz"}

    def __init__(self, app, expected_token: str):
        super().__init__(app)
        self._expected = expected_token.encode("utf-8")

    async def dispatch(self, request, call_next):
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            logger.warning(
                "Auth missing from %s on %s",
                request.client.host if request.client else "?",
                request.url.path,
            )
            return JSONResponse(
                {"error": "Missing or malformed Authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        provided = auth[7:].strip().encode("utf-8")
        if not hmac.compare_digest(provided, self._expected):
            logger.warning(
                "Invalid token from %s on %s",
                request.client.host if request.client else "?",
                request.url.path,
            )
            return JSONResponse({"error": "Invalid token"}, status_code=401)

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
