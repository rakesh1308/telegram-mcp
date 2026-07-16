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

The server speaks MCP over stdio. Configure your MCP client (Kilo, Claude Desktop,
etc.) to launch it via stdio.

### Example MCP client config

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