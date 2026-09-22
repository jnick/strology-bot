from __future__ import annotations

import asyncio
import logging

from app.channels.base import BaseChannel
from app.core.engine import Engine
from app.core.messages import IncomingMessage

log = logging.getLogger(__name__)


class MaxChannel(BaseChannel):
    """Каркас канала MAX (https://dev.max.ru/docs).

    Мессенджер MAX события отдаёт по Long Polling (GET platform-api2.max.ru/updates)
    либо по вебхуку. Форматы событий: bot_started (как /start в Telegram),
    message_new, callback_query. Здесь пока только остов — включается, когда появится
    токен (MAX_BOT_TOKEN). Требует верифицированный профиль юрлица/ИП/самозанятого.
    """

    name = "max"

    def __init__(self, token: str, engine: Engine):
        super().__init__(engine)
        self.token = token

    async def run(self) -> None:
        raise NotImplementedError(
            "Канал MAX не готов: нужен токен и покрытие форматов событий платформы "
            "platform-api2.max.ru (bot_started / message_new / callback_query) + инлайн/реплай-кнопки."
        )

    async def _poll(self) -> None:  # заготовка Long Polling
        import httpx

        async with httpx.AsyncClient() as client:
            while True:
                resp = await client.get(
                    "https://platform-api2.max.ru/updates",
                    headers={"Authorization": self.token},
                )
                resp.raise_for_status()
                updates = resp.json()
                for upd in updates:
                    incoming = IncomingMessage(
                        channel=self.name,
                        chat_id=str(upd.get("chat_id", "")),
                        user_id=str((upd.get("user") or {}).get("user_id", "")),
                    )
                    self.engine.process(incoming)
                await asyncio.sleep(1)