from __future__ import annotations

import asyncio
import json
import logging
import ssl
from typing import Dict, List, Optional, Tuple, Union

import httpx

from app import config
from app.channels.base import BaseChannel
from app.core.engine import Engine
from app.core.messages import Button, IncomingMessage, OutgoingItem

log = logging.getLogger(__name__)

MAX_SUPPORTED_TYPES = "bot_started,message_created,message_callback"
MIN_SEND_INTERVAL = 0.55  # API лимит: не более 2 сообщений в секунду в один диалог
TEXT_LIMIT = 3900  # API: текст до 4000 символов; режем с запасом


def keyboard_attachment(buttons: List[Button], per_row: int = 2) -> List[Dict]:
    """Сериализация кнопок ядра в вложение inline_keyboard API MAX."""
    if not buttons:
        return []
    rows = [
        [{"type": "callback", "text": b.text, "payload": b.callback} for b in buttons[i : i + per_row]]
        for i in range(0, len(buttons), per_row)
    ]
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]


def message_body(out: OutgoingItem) -> Dict:
    body = {"text": out.text}
    atts = keyboard_attachment(out.buttons)
    if atts:
        body["attachments"] = atts
    return body


def _update_chat_id(update: Dict) -> str:
    """chat_id из события: корневое поле -> user_id -> recipient.chat_id."""
    msg = update.get("message") or {}
    recipient = msg.get("recipient") or {}
    for src in (update.get("chat_id"), (update.get("user") or {}).get("user_id"), recipient.get("chat_id")):
        if src:
            return str(src)
    return ""


def build_incoming(update: Dict) -> Optional[IncomingMessage]:
    """Приводит Update MAX к IncomingMessage ядра. Возвращает None для нерелевантных событий."""
    update_type = update.get("update_type")
    user = update.get("user") or {}
    chat_id = _update_chat_id(update)
    user_id = str(user.get("user_id") or "")

    if update_type == "message_created":
        msg = update.get("message") or {}
        body = msg.get("body") or {}
        return IncomingMessage(
            channel="max",
            chat_id=chat_id,
            user_id=user_id,
            text=str(body.get("text") or ""),
        )

    if update_type == "message_callback":
        cb = update.get("callback") or {}
        cb_user = cb.get("user") or user
        return IncomingMessage(
            channel="max",
            chat_id=chat_id,
            user_id=str(cb_user.get("user_id") or user_id),
            payload=str(cb.get("payload") or cb.get("callback_id") or ""),
        )

    if update_type == "bot_started":
        payload = update.get("payload")
        return IncomingMessage(
            channel="max",
            chat_id=chat_id,
            user_id=user_id,
            payload=(str(payload) if payload else None),
        )

    return None


def build_tls_context() -> ssl.SSLContext:
    """SSL-контекст с доверием к CA Минцифры (Russian Trusted Sub CA).

    Цепочка сервера MAX: leaf -> Russian Trusted Sub CA (root не присылается и
    недоступен для скачивания). OpenSSL в python требует спуска до анкора, поэтому
    включаем PARTIAL_CHAIN: любой сертификат из нашего bundle может быть анкором.
    """
    ctx = ssl.create_default_context(cafile=config.MAX_CA_BUNDLE)
    partial = getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0)
    if partial:
        ctx.verify_flags |= partial
    return ctx


class MaxClient:
    """HTTP-клиент API MAX (platform-api2.max.ru)."""

    def __init__(self, token: str, base_url: str, verify: Union[bool, ssl.SSLContext] = True):
        self._headers = {"Authorization": token}
        self._base_url = base_url.rstrip("/")
        self._verify = verify
        self._client: Optional[httpx.AsyncClient] = None

    async def _c(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                verify=self._verify,
                timeout=httpx.Timeout(100.0, connect=20.0),
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_me(self) -> Dict:
        resp = await (await self._c()).get("/me")
        resp.raise_for_status()
        return resp.json()

    async def get_updates(
        self,
        marker: Optional[int] = None,
        limit: int = 100,
        timeout: int = 30,
        types: str = MAX_SUPPORTED_TYPES,
    ) -> Tuple[List[Dict], Optional[int]]:
        params = {"limit": min(max(limit, 1), 1000), "timeout": min(max(timeout, 0), 90), "types": types}
        if marker is not None:
            params["marker"] = marker
        resp = await (await self._c()).get("/updates", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("updates") or [], data.get("marker")

    async def send_message(self, chat_id: str, text: str, buttons: List[Button]) -> bool:
        return await self._send("/messages", params={"chat_id": chat_id}, text=text, buttons=buttons)

    async def answer_callback(self, callback_id: str, text: str, buttons: List[Button]) -> bool:
        body = message_body(OutgoingItem.txt(text, buttons)) if text or buttons else None
        params = {"callback_id": callback_id}
        payload = {"message": body} if body else {}
        return await self._request("POST", "/answers", params=params, json=payload)

    async def set_commands(self, commands: List[Tuple[str, str]]) -> None:
        body = {"commands": [{"name": name, "description": desc} for name, desc in commands]}
        await self._request("PATCH", "/me/commands", json=body)

    async def _send(self, url: str, params: Dict, text: str, buttons: List[Button]) -> bool:
        pieces = _split_text(text or "") or [""]
        ok = True
        n = len(pieces)
        for i, piece in enumerate(pieces):
            item = OutgoingItem.txt(piece, buttons=buttons if i == n - 1 else [])
            if not piece and not item.buttons:
                continue
            if not await self._request("POST", url, params=params, json=message_body(item)):
                ok = False
        return ok

    async def _request(self, method: str, url: str, params: Optional[Dict] = None, json: Optional[Dict] = None) -> bool:
        try:
            resp = await (await self._c()).request(method, url, params=params, json=json)
            if resp.status_code == 429:
                log.warning("Max: 429, пауза 2s")
                await asyncio.sleep(2)
                resp = await (await self._c()).request(method, url, params=params, json=json)
            resp.raise_for_status()
            if url == "/answers":
                try:
                    log.info("Max: /answers тело: %.150r", resp.json())
                except Exception:
                    pass
            return True
        except Exception:
            log.exception("Max: ошибка запроса %s %s", method, url)
            return False


def _split_text(text: str) -> List[str]:
    """Разбивка очень длинного текста без потери контента (чтобы не превысить TEXT_LIMIT)."""
    if len(text) <= TEXT_LIMIT:
        return [text]
    pieces: List[str] = []
    cur = ""
    for line in text.split("\n"):
        if len(line) > TEXT_LIMIT:
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.extend(line[i : i + TEXT_LIMIT] for i in range(0, len(line), TEXT_LIMIT))
            continue
        if len(cur) + len(line) + 1 > TEXT_LIMIT:
            if cur:
                pieces.append(cur)
            cur = ""
        cur = line if not cur else cur + "\n" + line
    if cur:
        pieces.append(cur)
    return pieces


class MaxChannel(BaseChannel):
    """Канал MAX (VK): REST API platform-api2.max.ru, доставка событий - Long Polling."""

    name = "max"

    def __init__(self, token: str, engine: Engine):
        super().__init__(engine)
        self.token = token
        self._last_sent: Dict[str, float] = {}
        self._bot_id: Optional[str] = None

    async def run(self) -> None:
        verify = build_tls_context() if config.MAX_TLS_VERIFY else False
        self.client = MaxClient(self.token, config.MAX_API_URL, verify=verify)
        me = await self.client.get_me()
        self._bot_id = str(me.get("user_id") or "")
        log.info("Max: бот '%s' (user_id=%s)", me.get("name"), me.get("user_id"))
        try:
            await self.client.set_commands(
                [
                    ("start", "Запустить бота"),
                    ("status", "Статус подписки"),
                    ("help", "Помощь"),
                ]
            )
        except Exception:
            log.warning("Max: не удалось обновить список команд", exc_info=True)

        if config.MAX_DELIVERY == "webhook":
            raise NotImplementedError(
                "Webhook MAX ещё не реализован: нужен публичный HTTPS-URL (MAX_WEBHOOK_URL). "
                "Сейчас используйте MAX_DELIVERY=poll."
            )
        await self._poll()

    async def _poll(self) -> None:
        marker: Optional[int] = None
        while True:
            try:
                updates, marker = await self.client.get_updates(
                    marker=marker,
                    limit=config.MAX_POLL_LIMIT,
                    timeout=config.MAX_POLL_TIMEOUT,
                )
                for upd in updates or []:
                    try:
                        await self._handle(upd)
                    except Exception:
                        log.exception("Max: ошибка обработки события %s", str(upd)[:200])
            except Exception:
                log.exception("Max: ошибка Long Polling")
                await asyncio.sleep(5)

    async def _handle(self, update: Dict) -> None:
        incoming = build_incoming(update)
        if incoming is None:
            log.debug("Max: событие пропущено: %s", json.dumps(update, ensure_ascii=False)[:300])
            return
        if not incoming.chat_id:
            log.warning("Max: пустой chat_id в событии: %s", json.dumps(update, ensure_ascii=False)[:300])
        update_type = update.get("update_type")
        sender_id = str((update.get("user") or {}).get("user_id") or "")
        log.info("Max: событие %s chat=%s user=%s payload=%r text=%r",
                 update_type, incoming.chat_id, incoming.user_id, incoming.payload,
                 (incoming.text or "")[:60])
        if update_type == "message_created" and sender_id and self._bot_id and sender_id == self._bot_id:
            log.info("Max: эхо-сообщение бота пропущено (%s)", sender_id)
            return
        callback_id = None
        if update_type == "message_callback":
            cb = update.get("callback") or {}
            callback_id = cb.get("callback_id")
        items = self.engine.process(incoming)
        first = True
        for out in items:
            await self._throttle(incoming.chat_id)
            if callback_id is not None and first and out.text:
                log.info("Max: ответ каллбэка: %.60r", out.text)
                await self.client.answer_callback(callback_id, out.text, out.buttons)
            else:
                log.info("Max: отправка: %.60r", out.text)
                await self.client.send_message(incoming.chat_id, out.text, out.buttons)
            first = False

    async def _throttle(self, chat_id: str) -> None:
        """Соблюдение лимита API MAX: <=2 сообщений/сек в один диалог."""
        loop = asyncio.get_event_loop()
        now = loop.time()
        prev = self._last_sent.get(chat_id)
        if prev is not None:
            wait = MIN_SEND_INTERVAL - (now - prev)
            if wait > 0:
                await asyncio.sleep(wait)
        self._last_sent[chat_id] = loop.time()