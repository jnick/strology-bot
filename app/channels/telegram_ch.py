from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from app.channels.base import BaseChannel
from app.core.engine import Engine
from app.core.messages import IncomingMessage, OutgoingItem
from app.core.texts import BUTTON_START

log = logging.getLogger(__name__)


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, token: str, engine: Engine):
        super().__init__(engine)
        self.token = token

    async def run(self) -> None:
        bot = Bot(self.token)
        dp = Dispatcher()

        @dp.message(F.text.in_({"/start", BUTTON_START}))
        async def on_start(message: Message) -> None:
            incoming = IncomingMessage(
                channel=self.name,
                chat_id=str(message.chat.id),
                user_id=str(message.from_user.id or ""),
                text=message.text or "",
            )
            await self._reply(bot, message, incoming)

        @dp.message()
        async def on_message(message: Message) -> None:
            incoming = IncomingMessage(
                channel=self.name,
                chat_id=str(message.chat.id),
                user_id=str(message.from_user.id or ""),
                text=message.text or "",
            )
            await self._reply(bot, message, incoming)

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    async def _reply(self, bot: Bot, message: Message, incoming: IncomingMessage) -> None:
        for out in self.engine.process(incoming):
            await self._send(bot, message.chat.id, out)

    async def _send(self, bot: Bot, chat_id: int, out: OutgoingItem) -> None:
        kwargs = {}
        if out.buttons:
            kwargs["reply_markup"] = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=b) for b in out.buttons]],
                resize_keyboard=True,
            )
        try:
            if out.kind == "text":
                await bot.send_message(chat_id, out.text, **kwargs)
        except Exception:
            log.exception("Ошибка отправки ответа в Telegram")