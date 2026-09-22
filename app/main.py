from __future__ import annotations

import asyncio
import logging
import sys

from app import config
from app.channels.max_ch import MaxChannel
from app.channels.telegram_ch import TelegramChannel
from app.core.engine import Engine
from app.core.session import SessionStore
from app.core.store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("strology")


def main() -> None:
    store = Store(config.DB_PATH)
    sessions = SessionStore(config.DB_PATH)
    engine = Engine(store, sessions)

    channels = []
    for name in config.ENABLED_CHANNELS:
        if name == "telegram" and config.TELEGRAM_BOT_TOKEN:
            channels.append(TelegramChannel(config.TELEGRAM_BOT_TOKEN, engine))
            log.info("Включён канал telegram")
        elif name == "max" and config.MAX_BOT_TOKEN:
            channels.append(MaxChannel(config.MAX_BOT_TOKEN, engine))
            log.info("Включён канал max")
        else:
            log.warning("Канал '%s' не включён: неизвестен или не задан токен", name)

    if not channels:
        log.error("Ни один канал не настроен. Проверьте TELEGRAM_BOT_TOKEN / MAX_BOT_TOKEN в .env")
        sys.exit(1)

    async def _run_all() -> None:
        await asyncio.gather(*(ch.run() for ch in channels))

    asyncio.run(_run_all())


if __name__ == "__main__":
    main()