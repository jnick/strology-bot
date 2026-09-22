from __future__ import annotations

import logging
from typing import List

from app.core.messages import IncomingMessage, OutgoingItem
from app.core.texts import BUTTON_START, GREETING_1

log = logging.getLogger(__name__)


class Engine:
    """Ядро бота: обрабатывает нормализованные события, не знает про мессенджеры."""

    def process(self, incoming: IncomingMessage) -> List[OutgoingItem]:
        text = (incoming.text or "").strip()
        if incoming.payload or text in ("/start", BUTTON_START):
            return [OutgoingItem.txt(GREETING_1, buttons=[BUTTON_START])]
        return []