from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.core.content import SIGN_NAMES


@dataclass
class Step:
    """Один шаг сбора данных действия."""

    key: str
    prompt: str
    example: str = ""
    validator: Optional[Callable[[str], Optional[str]]] = None


@dataclass
class AstroAction:
    """Действие: заголовок кнопки и вопросы для сбора данных.
    Сами расчёты — в AstroService (app/core/astro.py), метод с именем slug."""

    slug: str
    title: str
    steps: List[Step] = field(default_factory=list)


def validate_date(value: str) -> Optional[str]:
    parts = value.split(".")
    if len(parts) != 3:
        return "Дата должна быть в формате ДД.ММ.ГГГГ (например 15.03.1990)."
    try:
        datetime.datetime(int(parts[2]), int(parts[1]), int(parts[0]))
    except ValueError:
        return "Некорректная дата. Формат ДД.ММ.ГГГГ (например 15.03.1990)."
    return None


def validate_time(value: str) -> Optional[str]:
    parts = value.split(":")
    if len(parts) != 2:
        return "Время должно быть в формате ЧЧ:ММ (например 14:30)."
    try:
        datetime.time(int(parts[0]), int(parts[1]))
    except ValueError:
        return "Некорректное время. Формат ЧЧ:ММ (например 14:30)."
    return None


def validate_not_empty(value: str) -> Optional[str]:
    if not value.strip():
        return "Это поле не может быть пустым."
    return None


def validate_period(value: str) -> Optional[str]:
    if value.strip().lower() not in ("сегодня", "день", "неделя", "месяц"):
        return "Напишите: сегодня, неделя или месяц."
    return None


_SIGN_DECLINE = {
    "овна": "Овен", "овне": "Овен", "тельца": "Телец", "тельце": "Телец",
    "близнецов": "Близнецы", "близнецах": "Близнецы", "рака": "Рак", "раке": "Рак",
    "льва": "Лев", "льве": "Лев", "девы": "Дева", "деве": "Дева",
    "весов": "Весы", "весах": "Весы", "скорпиона": "Скорпион", "скорпионе": "Скорпион",
    "стрельца": "Стрелец", "стрельце": "Стрелец", "козерога": "Козерог", "козероге": "Козерог",
    "водолея": "Водолей", "водолее": "Водолей", "рыб": "Рыбы", "рыбах": "Рыбы",
}


def validate_sign(value: str) -> Optional[str]:
    """Возвращает каноническое имя знака (Им. падеж) либо текст ошибки."""
    v = value.strip().lower()
    if not v:
        return "Напишите ваш знак зодиака, например: Овен."
    if v in _SIGN_DECLINE:
        return _SIGN_DECLINE[v]
    for name in SIGN_NAMES:
        base = name.lower()
        if v == base:
            return name
    for name in SIGN_NAMES:
        base = name.lower()
        if len(v) >= 2 and (base.startswith(v) or v.startswith(base)):
            return name
    return "Не узнал знак. Напишите один из 12: " + ", ".join(SIGN_NAMES) + "."


DATE_PROMPT = "Дата рождения (ДД.ММ.ГГГГ)"
TIME_PROMPT = "Время рождения (ЧЧ:ММ). Если не знаете — напишите 12:00."
PLACE_PROMPT = "Место рождения (город)"

ACTIONS_ORDER = [
    AstroAction(
        "natal",
        "Натальная карта",
        [
            Step("birth_date", DATE_PROMPT, "15.03.1990", validate_date),
            Step("birth_time", TIME_PROMPT, "14:30", validate_time),
            Step("birth_place", PLACE_PROMPT, "Москва", validate_not_empty),
        ],
    ),
    AstroAction(
        "horoscope",
        "Гороскоп",
        [
            Step("sign", "Ваш знак зодиака", "Овен", validate_sign),
            Step("period", "На какой период прогноз?", "сегодня", validate_period),
        ],
    ),
    AstroAction(
        "compat",
        "Совместимость",
        [
            Step("date1", "Дата рождения первого человека (ДД.ММ.ГГГГ)", "15.03.1990", validate_date),
            Step("date2", "Дата рождения второго человека (ДД.ММ.ГГГГ)", "22.07.1988", validate_date),
        ],
    ),
    AstroAction(
        "question",
        "Ответ на вопрос",
        [Step("question_text", "Сформулируйте ваш вопрос", "Будет ли удачной смена работы?", validate_not_empty)],
    ),
    AstroAction("moon", "Лунный день"),
    AstroAction("retro", "Ретроградные планеты"),
    AstroAction(
        "number",
        "Число судьбы",
        [Step("birth_date", DATE_PROMPT, "15.03.1990", validate_date)],
    ),
    AstroAction(
        "solar",
        "Соляр",
        [Step("birth_date", DATE_PROMPT, "15.03.1990", validate_date)],
    ),
    AstroAction(
        "weekly",
        "Прогноз на неделю",
        [Step("birth_date", DATE_PROMPT, "15.03.1990", validate_date)],
    ),
    AstroAction("meditation", "Медитация на день"),
]

ACTIONS: dict = {a.slug: a for a in ACTIONS_ORDER}