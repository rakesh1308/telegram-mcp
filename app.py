"""Vercel ASGI entry point for the stateless Telegram MCP server."""
import hmac
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.responses import JSONResponse
from server import mcp
from mcp.server.transport_security import TransportSecuritySettings

# Telegram URLs contain credentials; prevent HTTP client request logging.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

mcp.settings.stateless_http = True
mcp.settings.json_response = True
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=[host for host in [os.getenv("VERCEL_URL"), os.getenv("VERCEL_PROJECT_PRODUCTION_URL"), "telegram-mcp.vercel.app", "localhost:*", "127.0.0.1:*"] if host],
    allowed_origins=["https://chatgpt.com"],
)
mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def require_auth(request, call_next):
    if request.url.path in ("/", "/health"):
        return await call_next(request)
    # Clients use the configured bot token as their bearer credential.
    token = os.getenv("MCP_AUTH_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    supplied = request.headers.get("authorization", "")
    if not token or not hmac.compare_digest(supplied.encode(), ("Bearer " + token).encode()):
        return JSONResponse(
            {"error": "Unauthorized"}, status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await call_next(request)


@app.get("/")
@app.get("/health")
async def health():
    return {"status": "ok", "service": "telegram-mcp", "endpoint": "/mcp"}


app.mount("/", mcp_app)
