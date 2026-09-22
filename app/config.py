from __future__ import annotations

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
MAX_BOT_TOKEN = _env("MAX_BOT_TOKEN")
ENABLED_CHANNELS = [c.strip() for c in _env("ENABLED_CHANNELS", "telegram").split(",") if c.strip()]