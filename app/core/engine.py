from __future__ import annotations

import datetime
import logging
from typing import Dict, List, Optional

from app import config
from app.core import texts
from app.core.actions import ACTIONS, ACTIONS_ORDER
from app.core.astro import AstroService
from app.core.messages import Button, IncomingMessage, OutgoingItem
from app.core.session import SessionStore
from app.core.store import Store, local_today

log = logging.getLogger(__name__)

# Шаги, где используется сохранённая дата рождения, и распознаваемые «Да».
DATE_CONFIRM_KEYS = ("birth_date",)
DATE_YES_TOKENS = {
    "да", "даа", "да,", "использовать", "используй", "да использую",
    "да используй", "верно", "дальше", "yes", "у", "уа", "ага", "угу", "+",
}


def is_date_yes(value: str) -> bool:
    v = (value or "").strip()
    v = "".join(ch for ch in v.lower() if ch not in ",.!?;:…")
    v = v.strip()
    if v in DATE_YES_TOKENS:
        return True
    if v.startswith("да "):
        return True
    return False


class Engine:
    """Ядро бота: «/start», меню из 10 действий, лимиты, подписка, сбор данных по шагам.
    Не знает, из какого канала пришло событие."""

    def __init__(
        self,
        store: Store,
        sessions: SessionStore,
        astro: Optional[AstroService] = None,
    ):
        self.store = store
        self.sessions = sessions
        self.astro = astro or AstroService()

    # ---------- входная точка ----------

    def process(self, incoming: IncomingMessage) -> List[OutgoingItem]:
        text = (incoming.text or "").strip()
        low = text.lower()
        payload = (incoming.payload or "").strip()

        if low.startswith("/grant"):
            return self._grant(incoming, low)
        if low.startswith("/revoke"):
            return self._revoke(incoming)
        if low.startswith("/status"):
            return self._status(incoming)
        if low.startswith("/help"):
            return [OutgoingItem.txt(texts.HELP_TEXT, buttons=[texts.BTN_MENU])]

        sess = self.sessions.get(incoming.channel, incoming.chat_id)
        if sess and sess["state"] == "collecting":
            return self._collect(incoming, sess, text, payload)

        if payload == "menu" or not payload:
            return [self._menu_message()]
        if payload == "cancel":
            return [OutgoingItem.txt(texts.CANCEL_TEXT, buttons=[texts.BTN_MENU])]
        if payload == "sub":
            return [OutgoingItem.txt(texts.SUB_INFO_TEXT, buttons=[texts.BTN_MENU])]
        if payload in ACTIONS:
            return self._begin_action(incoming, payload)
        return [self._menu_message()]

    # ---------- меню и статус ----------

    def _menu_message(self) -> OutgoingItem:
        buttons = [Button(a.title, a.slug) for a in ACTIONS_ORDER]
        return OutgoingItem.txt(texts.MENU_TEXT, buttons=buttons)

    def _status(self, incoming: IncomingMessage) -> List[OutgoingItem]:
        day = local_today()
        used = self.store.used_today(incoming.channel, incoming.chat_id, day)
        until = self.store.subscription_until(incoming.channel, incoming.chat_id)
        if until and until >= day:
            return [OutgoingItem.txt(f"Подписка активна до {until} (включительно).\nИспользовано сегодня: {used} действий.")]
        free_left = max(0, config.FREE_DAILY_LIMIT - used)
        return [OutgoingItem.txt(f"Подписки нет.\nБесплатных действий на сегодня осталось: {free_left}.")]

    # ---------- действия и шаги ----------

    def _begin_action(self, incoming: IncomingMessage, slug: str) -> List[OutgoingItem]:
        action = ACTIONS[slug]
        day = local_today()
        if not self.store.is_subscribed(incoming.channel, incoming.chat_id, day):
            if not self.store.consume(
                incoming.channel, incoming.chat_id, incoming.user_id, day, config.FREE_DAILY_LIMIT
            ):
                return [OutgoingItem.txt(texts.LIMIT_TEXT, buttons=[texts.BTN_SUB, texts.BTN_MENU])]
        if not action.steps:
            return [self._finish(incoming, action, {})]
        self.sessions.save(incoming.channel, incoming.chat_id, action.slug, 0, {}, "collecting")
        return [
            OutgoingItem.txt(
                self._step_text(action, 0, {}, incoming),
                buttons=self._step_buttons(incoming, {}, action, 0),
            )
        ]

    def _collect(
        self,
        incoming: IncomingMessage,
        sess: dict,
        text: str,
        payload: str,
    ) -> List[OutgoingItem]:
        if payload == "menu":
            self.sessions.clear(incoming.channel, incoming.chat_id)
            return [self._menu_message()]
        if payload in ACTIONS:
            self.sessions.clear(incoming.channel, incoming.chat_id)
            return self._begin_action(incoming, payload)
        if payload == "cancel" or text.strip().lower().startswith("/cancel"):
            self.sessions.clear(incoming.channel, incoming.chat_id)
            return [OutgoingItem.txt(texts.CANCEL_TEXT, buttons=[texts.BTN_MENU])]
        if payload == "sub":
            self.sessions.clear(incoming.channel, incoming.chat_id)
            return [OutgoingItem.txt(texts.SUB_INFO_TEXT, buttons=[texts.BTN_MENU])]

        action = ACTIONS.get(sess["action"])
        if action is None:
            self.sessions.clear(incoming.channel, incoming.chat_id)
            return [self._menu_message()]

        index = sess["index"]
        if index >= len(action.steps):
            self.sessions.clear(incoming.channel, incoming.chat_id)
            return [self._finish(incoming, action, sess["answers"])]

        step = action.steps[index]
        answers = dict(sess["answers"])
        saved = self._saved_date(incoming, answers, step)
        value = text.strip()

        if saved and (payload == "date_yes" or is_date_yes(value)):
            answers[step.key] = saved
            value = saved
        else:
            if step.validator:
                error = step.validator(value)
                if error:
                    return [
                        OutgoingItem.txt(
                            error + "\n\n" + self._step_text(action, index, answers, incoming),
                            buttons=self._step_buttons(incoming, answers, action, index),
                        )
                    ]
            answers[step.key] = value
            if step.key in DATE_CONFIRM_KEYS:
                self.store.save_birth_date(incoming.channel, incoming.user_id, value)
        index += 1

        if index >= len(action.steps):
            self.sessions.clear(incoming.channel, incoming.chat_id)
            return [self._finish(incoming, action, answers)]

        self.sessions.save(incoming.channel, incoming.chat_id, action.slug, index, answers, "collecting")
        return [
            OutgoingItem.txt(
                self._step_text(action, index, answers, incoming),
                buttons=self._step_buttons(incoming, answers, action, index),
            )
        ]

    def _finish(self, incoming: IncomingMessage, action, answers: Dict[str, str]) -> OutgoingItem:
        result = getattr(self.astro, action.slug)(answers)
        return OutgoingItem.txt(result, buttons=[texts.BTN_MENU])

    def _saved_date(self, incoming: IncomingMessage, answers: Dict[str, str], step) -> Optional[str]:
        """Сохранённая дата, если её можно предложить для этого шага."""
        if step.key not in DATE_CONFIRM_KEYS:
            return None
        if answers.get(step.key):
            return None
        return self.store.get_birth_date(incoming.channel, incoming.user_id)

    def _step_text(self, action, index: int, answers: Dict[str, str], incoming: IncomingMessage) -> str:
        step = action.steps[index]
        saved = self._saved_date(incoming, answers, step)
        if saved:
            prompt = texts.DATE_CONFIRM_TEMPLATE.format(date=saved)
        else:
            prompt = step.prompt
        text = f"{action.title}. Вопрос {index + 1} из {len(action.steps)}\n{prompt}"
        if not saved and step.example:
            text += f"\nНапример: {step.example}"
        return text

    def _step_buttons(
        self, incoming: IncomingMessage, answers: Dict[str, str], action, index: int
    ) -> List[Button]:
        step = action.steps[index]
        saved = self._saved_date(incoming, answers, step)
        return [texts.BTN_DATE_YES, texts.BTN_CANCEL] if saved else [texts.BTN_CANCEL]

    # ---------- подписка (админ-команды) ----------

    def _is_admin(self, incoming: IncomingMessage) -> bool:
        return incoming.user_id in {str(a) for a in config.ADMIN_IDS}

    def _grant(self, incoming: IncomingMessage, low: str) -> List[OutgoingItem]:
        if not self._is_admin(incoming):
            return [OutgoingItem.txt("Нет доступа к этой команде.")]
        parts = low.split()
        if len(parts) != 2:
            return [OutgoingItem.txt("Формат: /grant ГГГГ-ММ-ДД — безлимит до этой даты включительно.")]
        until = parts[1]
        try:
            datetime.datetime.strptime(until, "%Y-%m-%d")
        except ValueError:
            return [OutgoingItem.txt("Некорректная дата. Формат: ГГГГ-ММ-ДД.")]
        self.store.grant(incoming.channel, incoming.chat_id, incoming.user_id, until)
        return [OutgoingItem.txt(f"Подписка активна до {until} (включительно).")]

    def _revoke(self, incoming: IncomingMessage) -> List[OutgoingItem]:
        if not self._is_admin(incoming):
            return [OutgoingItem.txt("Нет доступа к этой команде.")]
        self.store.revoke(incoming.channel, incoming.chat_id, incoming.user_id)
        return [OutgoingItem.txt("Подписка отозвана.")]