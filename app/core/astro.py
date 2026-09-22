from __future__ import annotations

from typing import Dict

PLACEHOLDER = "Функция «%s» в разработке — алгоритм появится на следующем этапе.\n\nСобранные данные: %s"


def _summary(answers: Dict[str, str]) -> str:
    if not answers:
        return "—"
    return ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in answers.items() if v)


class AstroService:
    """Расчёты. Здесь будут эфемериды, гороскопы, совместимость и т.д.
    Каждый метод вызывается из ядра по slug действия (engine.py)."""

    def natal(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Натальная карта", _summary(answers))

    def horoscope(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Гороскоп", _summary(answers))

    def compat(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Совместимость", _summary(answers))

    def question(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Ответ на вопрос", _summary(answers))

    def moon(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Лунный день", _summary(answers))

    def retro(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Ретроградные планеты", _summary(answers))

    def number(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Число судьбы", _summary(answers))

    def solar(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Соляр", _summary(answers))

    def weekly(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Прогноз на неделю", _summary(answers))

    def meditation(self, answers: Dict[str, str]) -> str:
        return PLACEHOLDER % ("Медитация на день", _summary(answers))