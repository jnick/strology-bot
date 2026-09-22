from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
MAX_BOT_TOKEN = _env("MAX_BOT_TOKEN")
ENABLED_CHANNELS = [c.strip() for c in _env("ENABLED_CHANNELS", "telegram").split(",") if c.strip()]

DB_PATH = Path(_env("DB_PATH", str(BASE_DIR / "data" / "strology.db")))
FREE_DAILY_LIMIT = int(_env("FREE_DAILY_LIMIT", "1"))
ADMIN_IDS = [int(x) for x in _env("ADMIN_IDS", "").split(",") if x.strip().isdigit()]