from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Button:
    """Кнопка в ответе: текст и callback_data (передаётся обратно в ядро)."""

    text: str
    callback: str


@dataclass
class IncomingMessage:
    """Нормализованное входящее событие из любого канала."""

    channel: str
    chat_id: str
    user_id: str
    text: Optional[str] = None
    payload: Optional[str] = None


@dataclass
class OutgoingItem:
    """Готовый ответ каналу: текст (+ инлайн-кнопки)."""

    kind: str  # "text"
    text: str = ""
    buttons: List[Button] = field(default_factory=list)

    @staticmethod
    def txt(value: str, buttons: List[Button] = None) -> "OutgoingItem":
        return OutgoingItem(kind="text", text=value, buttons=buttons or [])