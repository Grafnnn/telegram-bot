"""Startup guard for the Telegram bot container."""

import os
import sys

TOKEN_PLACEHOLDER = "put_token_here"


def main() -> int:
    """Validate TELEGRAM_BOT_TOKEN before starting the bot process."""

    token = os.getenv("TELEGRAM_BOT_TOKEN", TOKEN_PLACEHOLDER)
    if not token or token == TOKEN_PLACEHOLDER:
        print(
            "TELEGRAM_BOT_TOKEN is not configured. Copy .env.example to .env, "
            "replace put_token_here with a real bot token, and restart the bot container.",
            file=sys.stderr,
        )
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
