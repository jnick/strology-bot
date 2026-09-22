from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


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
    """Готовый ответ каналу: текст (+ reply-клавиатура из однослойных кнопок)."""

    kind: str  # "text"
    text: str = ""
    buttons: List[str] = field(default_factory=list)

    @staticmethod
    def txt(value: str, buttons: List[str] = None) -> "OutgoingItem":
        return OutgoingItem(kind="text", text=value, buttons=buttons or [])