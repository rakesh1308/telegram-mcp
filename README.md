# Telegram MCP

A [Model Context Protocol](https://modelcontextprotocol.io/) server that wraps the
[Telegram Bot API](https://core.telegram.org/bots/api), exposing common bot actions
as MCP tools (e.g. `send_message`, `send_photo`, `get_updates`).

## Requirements

- Python 3.10+
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- A target chat ID (your user ID, a group ID, or a channel ID)

## Setup

1. Clone the repo and create a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # macOS / Linux
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and fill in your values:

   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_DEFAULT_CHAT_ID=123456789
   ```

   `TELEGRAM_DEFAULT_CHAT_ID` is used when a tool is invoked without an explicit
   `chat_id` argument, so you don't have to repeat it on every call.

## Run

```bash
python server.py
```

By default the server speaks MCP over **stdio** (for local clients). If the
`PORT` environment variable is set, it switches to **streamable-http** on
`0.0.0.0:$PORT` so it works on PaaS platforms.

### Example MCP client config (local stdio)

```json
{
  "mcpServers": {
    "telegram": {
      "command": "python",
      "args": ["C:/path/to/telegram/server.py"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "123456:ABC...",
        "TELEGRAM_DEFAULT_CHAT_ID": "123456789"
      }
    }
  }
}
```

### Example MCP client config (remote HTTP)

```json
{
  "mcpServers": {
    "telegram": {
      "url": "https://your-deployment.example.com/mcp",
      "transport": "streamable-http"
    }
  }
}
```

For ChatGPT: Settings → Connectors → Add Custom Connector →
URL `https://<service>.zeabur.app/mcp`, no authentication.

## Deploy

The repo includes a `Procfile` and a `Dockerfile`. `server.py` auto-switches to
`streamable-http` when `PORT` is set, so no code changes are needed per
platform.

### Zeabur

1. Push the repo (already done) and connect it in Zeabur's dashboard.
2. Zeabur sets `PORT` automatically; no extra config is required if you ship
   a `Procfile` (`web: python server.py`) or a `Dockerfile` (both included).
3. Set these env vars in the service settings:
   - `TELEGRAM_BOT_TOKEN` (required)
   - `TELEGRAM_DEFAULT_CHAT_ID` (optional)
4. Hit `https://<your-service>.zeabur.app/mcp` from any MCP HTTP client.

### Railway / Render / Fly.io

Same story — set `PORT`, `TELEGRAM_BOT_TOKEN`, optionally `TELEGRAM_DEFAULT_CHAT_ID`,
and the included `Procfile` / `Dockerfile` will start the server.

## Tools

| Tool              | Description                                          |
| ----------------- | ---------------------------------------------------- |
| `get_me`          | Returns basic information about the bot.             |
| `send_message`    | Sends a text message (Markdown/HTML supported).      |
| `send_photo`      | Sends a photo from a URL.                            |
| `send_document`   | Sends a document/file from a URL.                    |
| `send_location`   | Sends a point on the map.                            |
| `edit_message`    | Edits the text of a previously sent message.         |
| `delete_message`  | Deletes a message (bot must have sent it).           |
| `get_updates`     | Returns incoming updates (offset/timeout supported). |

All `send_*` tools default `chat_id` to the `TELEGRAM_DEFAULT_CHAT_ID` env var.

## Security

- Never commit your `.env` file — it is in `.gitignore`.
- Treat your bot token like a password. Anyone with it can send messages on
  behalf of your bot.
- Consider restricting the bot's scope (private chats only, specific groups, etc.).