"""One-time helper: find your Telegram chat id after messaging your bot.

Run:  python -m core.alerts.get_chat_id
Requires TELEGRAM_BOT_TOKEN already set (via core.security.setup_credentials)
and at least one message sent to the bot first.
"""
from __future__ import annotations

import sys

import requests

from ..security import credentials as creds


def main() -> int:
    token = creds.get_secret("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN is not set. Run: python -m core.security.setup_credentials")
        return 1

    resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
    resp.raise_for_status()
    updates = resp.json().get("result", [])
    if not updates:
        print("No messages found yet. Send any message to your bot on Telegram, then retry.")
        return 1

    chats = {}
    for u in updates:
        msg = u.get("message") or u.get("channel_post")
        if not msg:
            continue
        chat = msg["chat"]
        chats[chat["id"]] = chat.get("username") or chat.get("first_name") or chat.get("title")

    print("Found chat(s):")
    for chat_id, label in chats.items():
        print(f"  chat_id = {chat_id}   ({label})")
    print("\nCopy the chat_id above and enter it for TELEGRAM_CHAT_ID when running:")
    print("  python -m core.security.setup_credentials")
    return 0


if __name__ == "__main__":
    sys.exit(main())
