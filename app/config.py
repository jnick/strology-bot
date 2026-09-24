from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
MAX_BOT_TOKEN = _env("MAX_BOT_TOKEN")
MAX_API_URL = _env("MAX_API_URL", "https://platform-api2.max.ru")
MAX_DELIVERY = _env("MAX_DELIVERY", "poll")  # "poll" | "webhook"
MAX_POLL_LIMIT = int(_env("MAX_POLL_LIMIT", "100"))
MAX_POLL_TIMEOUT = int(_env("MAX_POLL_TIMEOUT", "30"))
MAX_TLS_VERIFY = _env("MAX_TLS_VERIFY", "1") == "1"
MAX_CA_BUNDLE = _env("MAX_CA_BUNDLE", str(BASE_DIR / "certs" / "russian-trusted-sub-ca.pem"))
MAX_WEBHOOK_URL = _env("MAX_WEBHOOK_URL")
ENABLED_CHANNELS = [c.strip() for c in _env("ENABLED_CHANNELS", "telegram").split(",") if c.strip()]

DB_PATH = Path(_env("DB_PATH", str(BASE_DIR / "data" / "strology.db")))
FREE_DAILY_LIMIT = int(_env("FREE_DAILY_LIMIT", "1"))
ADMIN_IDS = [int(x) for x in _env("ADMIN_IDS", "").split(",") if x.strip().isdigit()]