from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.channels.base import BaseChannel
from app.core.engine import Engine
from app.core.messages import Button, IncomingMessage, OutgoingItem

log = logging.getLogger(__name__)


def _keyboard(buttons, per_row: int = 2) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=b.text, callback_data=b.callback) for b in buttons[i:i + per_row]]
        for i in range(0, len(buttons), per_row)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


class TelegramChannel(BaseChannel):
    name = "telegram"

    def __init__(self, token: str, engine: Engine):
        super().__init__(engine)
        self.token = token

    async def run(self) -> None:
        bot = Bot(self.token)
        dp = Dispatcher()

        @dp.callback_query()
        async def on_callback(query: CallbackQuery) -> None:
            await query.answer()
            if query.message is None:
                return
            incoming = IncomingMessage(
                channel=self.name,
                chat_id=str(query.message.chat.id),
                user_id=str(query.from_user.id or ""),
                payload=query.data or "",
            )
            await self._respond(bot, query.message.chat.id, incoming)

        @dp.message()
        async def on_message(message: Message) -> None:
            incoming = IncomingMessage(
                channel=self.name,
                chat_id=str(message.chat.id),
                user_id=str(message.from_user.id or ""),
                text=message.text or "",
            )
            await self._respond(bot, message.chat.id, incoming)

        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    async def _respond(self, bot: Bot, chat_id: int, incoming: IncomingMessage) -> None:
        for out in self.engine.process(incoming):
            await self._send(bot, chat_id, out)

    async def _send(self, bot: Bot, chat_id: int, out: OutgoingItem) -> None:
        kwargs = {}
        if out.buttons:
            kwargs["reply_markup"] = _keyboard(out.buttons)
        try:
            if out.kind == "text":
                await bot.send_message(chat_id, out.text, **kwargs)
        except Exception:
            log.exception("Ошибка отправки ответа в Telegram")