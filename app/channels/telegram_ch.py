from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.channels.base import BaseChannel
from app.core.engine import Engine
from app.core.messages import IncomingMessage, OutgoingItem
from app.core.texts import BUTTON_START

log = logging.getLogger(__name__)

CALLBACK_START = "start"


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
            await self._handle(bot, message.chat.id, str(message.from_user.id or ""), message.text or "")

        @dp.message()
        async def on_message(message: Message) -> None:
            await self._handle(bot, message.chat.id, str(message.from_user.id or ""), message.text or "")

        @dp.callback_query(F.data == CALLBACK_START)
        async def on_start_click(query: CallbackQuery) -> None:
            await query.answer()
            await self._handle(bot, query.message.chat.id, str(query.from_user.id or ""), BUTTON_START)

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    async def _handle(self, bot: Bot, chat_id: int, user_id: str, text: str) -> None:
        incoming = IncomingMessage(
            channel=self.name,
            chat_id=str(chat_id),
            user_id=user_id,
            text=text,
        )
        for out in self.engine.process(incoming):
            await self._send(bot, chat_id, out)

    async def _send(self, bot: Bot, chat_id: int, out: OutgoingItem) -> None:
        kwargs = {}
        if out.buttons:
            kwargs["reply_markup"] = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=b, callback_data=CALLBACK_START) for b in out.buttons]
                ]
            )
        try:
            if out.kind == "text":
                await bot.send_message(chat_id, out.text, **kwargs)
        except Exception:
            log.exception("Ошибка отправки ответа в Telegram")