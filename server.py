"""Telegram MCP server.

Wraps the Telegram Bot API as MCP tools. Configuration is read from environment
variables (typically loaded from a .env file):

    TELEGRAM_BOT_TOKEN        - required, bot token from @BotFather
    TELEGRAM_DEFAULT_CHAT_ID  - optional, used when a tool is called without
                                an explicit chat_id
    MCP_AUTH_TOKEN            - required when running over HTTP (PaaS), used as
                                the bearer token to authenticate MCP clients
                                such as ChatGPT connectors.

Run with:  python server.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

load_dotenv()

logger = logging.getLogger("telegram-mcp")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

API_BASE = "https://api.telegram.org/bot{token}/{method}"


def _bot_token() -> str:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is not set. Add it to your environment or .env file."
        )
    return token


def _default_chat_id() -> Optional[str]:
    return os.getenv("TELEGRAM_DEFAULT_CHAT_ID")


async def _call(method: str, **params: Any) -> dict[str, Any]:
    """Call a Telegram Bot API method and return the parsed JSON response.

    Raises a RuntimeError with the API's error description on failure so the
    MCP tool surfaces a clear message to the model.
    """
    url = API_BASE.format(token=_bot_token(), method=method)
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=params)
        data = resp.json()
    if not data.get("ok"):
        description = data.get("description", "unknown error")
        raise RuntimeError(f"Telegram API error in {method}: {description}")
    return data


def _chat_id(chat_id: Optional[str]) -> str:
    cid = chat_id or _default_chat_id()
    if not cid:
        raise ValueError(
            "chat_id was not provided and TELEGRAM_DEFAULT_CHAT_ID is not set."
        )
    return cid


mcp = FastMCP("telegram")


class _BearerAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that validates ``Authorization: Bearer <token>``.

    OAuth discovery endpoints under ``/.well-known/`` are left open so clients
    can negotiate authentication.
    """

    def __init__(self, app: Any, token: str) -> None:
        super().__init__(app)
        self._token = token

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        if request.url.path.startswith("/.well-known/"):
            return await call_next(request)

        header = request.headers.get("authorization", "")
        scheme, _, value = header.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(value, self._token):
            return JSONResponse(
                {"error": "unauthorized", "error_description": "Invalid or missing bearer token."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return await call_next(request)


async def _run_http(port: int) -> None:
    """Serve the MCP server over streamable-http with auth + correct host config."""
    import uvicorn

    # Bind to all interfaces and disable DNS-rebinding protection, which by
    # default only allows 127.0.0.1/localhost and rejects PaaS hostnames
    # (e.g. telegram13.zeabur.app) with HTTP 421.
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.settings.stateless_http = True
    mcp.settings.transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )

    auth_token = os.getenv("MCP_AUTH_TOKEN")
    if not auth_token:
        auth_token = secrets.token_urlsafe(32)
        logger.warning(
            "MCP_AUTH_TOKEN is not set; generated an ephemeral token for this run. "
            "Set MCP_AUTH_TOKEN in your environment to a stable value."
        )
    logger.info("MCP bearer token (first 8 chars): %s...", auth_token[:8])

    app = mcp.streamable_http_app()
    app.add_middleware(_BearerAuthMiddleware, token=auth_token)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level=mcp.settings.log_level.lower(),
    )
    await uvicorn.Server(config).serve()


@mcp.tool()
async def get_me() -> str:
    """Return basic information about the bot (id, name, username, etc.)."""
    data = await _call("getMe")
    return json.dumps(data.get("result", {}), indent=2)


@mcp.tool()
async def send_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
    disable_notification: bool = False,
    reply_to_message_id: Optional[int] = None,
) -> str:
    """Send a text message to a chat.

    Args:
        text: The message text (1-4096 chars).
        chat_id: Target chat ID. Defaults to TELEGRAM_DEFAULT_CHAT_ID.
        parse_mode: Optional formatting mode: "Markdown", "MarkdownV2", or "HTML".
        disable_notification: If true, sends silently (no sound).
        reply_to_message_id: Optional ID of a message to reply to.
    """
    params: dict[str, Any] = {
        "chat_id": _chat_id(chat_id),
        "text": text,
        "disable_notification": disable_notification,
    }
    if parse_mode:
        params["parse_mode"] = parse_mode
    if reply_to_message_id is not None:
        params["reply_to_message_id"] = reply_to_message_id

    data = await _call("sendMessage", **params)
    return json.dumps(data.get("result", {}), indent=2)


@mcp.tool()
async def send_photo(
    photo_url: str,
    caption: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
    disable_notification: bool = False,
) -> str:
    """Send a photo to a chat from a public URL.

    Args:
        photo_url: Direct URL to the image (JPEG, PNG, etc.).
        caption: Optional caption (0-1024 chars).
        chat_id: Target chat ID. Defaults to TELEGRAM_DEFAULT_CHAT_ID.
        parse_mode: Optional formatting mode for the caption.
        disable_notification: If true, sends silently.
    """
    params: dict[str, Any] = {
        "chat_id": _chat_id(chat_id),
        "photo": photo_url,
        "disable_notification": disable_notification,
    }
    if caption:
        params["caption"] = caption
    if parse_mode:
        params["parse_mode"] = parse_mode

    data = await _call("sendPhoto", **params)
    return json.dumps(data.get("result", {}), indent=2)


@mcp.tool()
async def send_document(
    document_url: str,
    caption: Optional[str] = None,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
    disable_notification: bool = False,
) -> str:
    """Send a document/file to a chat from a public URL.

    Args:
        document_url: Direct URL to the file (PDF, ZIP, etc.).
        caption: Optional caption.
        chat_id: Target chat ID. Defaults to TELEGRAM_DEFAULT_CHAT_ID.
        parse_mode: Optional formatting mode for the caption.
        disable_notification: If true, sends silently.
    """
    params: dict[str, Any] = {
        "chat_id": _chat_id(chat_id),
        "document": document_url,
        "disable_notification": disable_notification,
    }
    if caption:
        params["caption"] = caption
    if parse_mode:
        params["parse_mode"] = parse_mode

    data = await _call("sendDocument", **params)
    return json.dumps(data.get("result", {}), indent=2)


@mcp.tool()
async def send_location(
    latitude: float,
    longitude: float,
    chat_id: Optional[str] = None,
    disable_notification: bool = False,
) -> str:
    """Send a point on the map to a chat.

    Args:
        latitude: Latitude of the location.
        longitude: Longitude of the location.
        chat_id: Target chat ID. Defaults to TELEGRAM_DEFAULT_CHAT_ID.
        disable_notification: If true, sends silently.
    """
    data = await _call(
        "sendLocation",
        chat_id=_chat_id(chat_id),
        latitude=latitude,
        longitude=longitude,
        disable_notification=disable_notification,
    )
    return json.dumps(data.get("result", {}), indent=2)


@mcp.tool()
async def edit_message(
    message_id: int,
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = None,
) -> str:
    """Edit the text of a message previously sent by the bot.

    Args:
        message_id: ID of the message to edit (must be from the same chat).
        text: New message text.
        chat_id: Chat ID the message belongs to. Defaults to TELEGRAM_DEFAULT_CHAT_ID.
        parse_mode: Optional formatting mode.
    """
    params: dict[str, Any] = {
        "chat_id": _chat_id(chat_id),
        "message_id": message_id,
        "text": text,
    }
    if parse_mode:
        params["parse_mode"] = parse_mode

    data = await _call("editMessageText", **params)
    return json.dumps(data.get("result", {}), indent=2)


@mcp.tool()
async def delete_message(message_id: int, chat_id: Optional[str] = None) -> str:
    """Delete a message previously sent by the bot.

    Args:
        message_id: ID of the message to delete.
        chat_id: Chat ID the message belongs to. Defaults to TELEGRAM_DEFAULT_CHAT_ID.
    """
    data = await _call("deleteMessage", chat_id=_chat_id(chat_id), message_id=message_id)
    return json.dumps(data.get("result", {}), indent=2)


@mcp.tool()
async def get_updates(
    offset: Optional[int] = None,
    timeout: int = 0,
    allowed_updates: Optional[list[str]] = None,
    limit: Optional[int] = None,
) -> str:
    """Receive incoming updates for the bot.

    Args:
        offset: Identifier of the first update to return; pass the last
                update_id + 1 to acknowledge earlier updates.
        timeout: Long polling timeout in seconds (0 = short poll).
        allowed_updates: List of update types to receive (e.g. ["message"]).
        limit: Limits the number of updates to be retrieved (1-100).
    """
    params: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        params["offset"] = offset
    if limit is not None:
        params["limit"] = limit
    if allowed_updates is not None:
        params["allowed_updates"] = allowed_updates

    data = await _call("getUpdates", **params)
    return json.dumps(data.get("result", []), indent=2)


def main() -> None:
    """Run the MCP server.

    Transport selection:
      * If the ``PORT`` environment variable is set (typical on PaaS platforms
        like Zeabur, Railway, Render, Heroku, Fly.io), run ``streamable-http``
        bound to ``0.0.0.0:$PORT`` so the platform's HTTP health check passes.
        Bearer-token auth is enforced via the ``MCP_AUTH_TOKEN`` env var.
      * Otherwise fall back to stdio transport for local MCP clients
        (Kilo, Claude Desktop, etc.).
    """
    paas_port = os.getenv("PORT")
    if paas_port:
        try:
            port = int(paas_port)
        except ValueError:
            raise RuntimeError(f"PORT env var is not an integer: {paas_port!r}")
        asyncio.run(_run_http(port))
    else:
        logger.info("Starting Telegram MCP server (stdio) for local MCP client")
        mcp.run()


if __name__ == "__main__":
    main()