from __future__ import annotations

import datetime as _dt
import hashlib
from typing import Dict, List

from app.core import content as C
from app.core import ephemeris as E
from app.resources import cities


# ---------- утилиты ----------

def _today() -> _dt.date:
    """Сегодня по Москве (UTC+3)."""
    return (_dt.datetime.utcnow() + _dt.timedelta(hours=3)).date()


def _now_jd() -> float:
    return E.jd_of_datetime_utc(_dt.datetime.utcnow())


_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def _fdate(d: _dt.date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def _ftime_utc_to_msk(jd: float) -> str:
    dt = E.rev_to_dt(jd) + _dt.timedelta(hours=3)
    return f"{_fdate(dt.date())} в {dt.hour:02d}:{dt.minute:02d} МСК"


def _parse_date(value: str) -> tuple:
    d, m, y = map(int, value.strip().split("."))
    return y, m, d


def _parse_time(value: str) -> tuple:
    h, mi = map(int, value.strip().split(":"))
    return h, mi


def _house_of(lon: float, cusps: Dict[int, float]) -> int:
    vals = [cusps[k] for k in sorted(cusps)]
    for i in range(12):
        a, b = vals[i], vals[(i + 1) % 12]
        if a <= b:
            if a <= lon < b or (i == 11 and lon >= a):
                return i + 1
        else:
            if lon >= a or lon < b:
                return i + 1
    return 1


HOUSE_NAMES = {
    1: "личность и внешность", 2: "деньги и ресурсы", 3: "контакты, учёба, поездки",
    4: "дом, семья, корни", 5: "творчество, любовь, дети", 6: "работа, забота, здоровье",
    7: "партнёрство и брак", 8: "трансформация и общие деньги", 9: "мировоззрение и дальние поездки",
    10: "карьера и призвание", 11: "друзья и цели", 12: "подсознание и уединение",
}

OMENS = [
    "Примета дня: звёзды советуют действовать тихо, но уверенно — результат придёт раньше, чем кажется.",
    "Примета дня: если вопрос не терпит спешки — наберитесь терпения до завтра и перечитайте его ещё раз.",
    "Примета дня: ответ придёт через человека, которого вы не ждали услышать.",
    "Примета дня: сейчас лучше соглашаться на малое — оно вытянет большое.",
    "Примета дня: звёзды советуют отвечать честно, но мягко: правда без резкости открывает дорогу.",
    "Примета дня: перемены, о которых вы думаете, начнутся с маленького шага именно сегодня.",
    "Примета дня: вопрос разрешится легче, если вы сначала выспитесь и вернётесь к нему на свежую голову.",
    "Примета дня: удача приходит к тем, кто наводит порядок в делах и словах.",
]


def _cap_after_colon(text: str) -> str:
    if ": " in text:
        part = text.split(": ", 1)[1]
    else:
        part = text
    return part[0].upper() + part[1:] if part else part


# ---------- сервис ----------

class AstroService:
    """Расчёты: эфемериды, натальная карта, гороскопы, совместимость и т.д."""

    # ---- натальная карта ----
    def natal(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        y, m, d = _parse_date(answers["birth_date"])
        hh, mm = _parse_time(answers["birth_time"])
        (lat, lon, tz), known = cities.lookup_city(answers["birth_place"])
        jd = E.julday_from_local(y, m, d, hh, mm, tz)
        lons = E.planets_longitudes(jd)
        asc, cusps = E.houses_p(jd, lat, lon)
        sun_i = E.sign_of(lons[0])
        moon_i = E.sign_of(lons[1])
        asc_i = E.sign_of(asc)

        lines = ["🔮 Натальная карта"]
        lines.append(f"{_fdate(_dt.date(y, m, d))}, {hh:02d}:{mm:02d} · {answers['birth_place'].strip()}"
                     + ("" if known else " (города нет в моей базе — условно посчитал по Москве)"))
        lines.append("")

        lines.append(f"☉ Солнце в {C.SIGN_ABL[sun_i]} — {C.SIGN_SHORT[sun_i]}.")
        lines.append("☽ " + C.MOON_SIGN_TEXT[moon_i])
        lines.append(f"↑ Асцендент в {C.SIGN_ABL[asc_i]} — так вас воспринимают со стороны.")
        lines.append(f"Управитель ASC — {C.PLANETS[C.SIGN_RULER[asc_i]]} "
                     f"({C.PLANET_ROLE[C.SIGN_RULER[asc_i]]}).")
        lines.append("")

        # дома
        h_info = []
        for b in E.BODIES:
            h = _house_of(lons[b], cusps)
            h_info.append((h, b))
        angular = [(h, b) for h, b in h_info if h in (1, 4, 7, 10)]
        if angular:
            parts = [f"{C.PLANETS[b]} в {h}-м доме" for h, b in sorted(angular)]
            lines.append("Яркие позиции: " + ", ".join(parts) + ".")
        else:
            lines.append("Акценты распределены равномерно — карта «качества», а не «взрывов».")

        # баланс стихий
        counts = [0, 0, 0, 0]
        for b in E.BODIES:
            counts[C.SIGN_ELEMENT[E.sign_of(lons[b])]] += 1
        dom = max(range(4), key=lambda i: counts[i])
        eq = all(c == 4 for c in counts)
        lines.append("")
        lines.append(f"Баланс стихий: огонь {counts[0]} · земля {counts[1]} · воздух {counts[2]} · вода {counts[3]}.")
        if eq:
            lines.append("Все стихии на равных — редкость: вы гибко соединяете и дело, и чувство.")
        else:
            lines.append(C.ELEMENT_TEXT[dom])

        # стеллиум
        from collections import Counter
        by_sign = Counter(E.sign_of(v) for v in lons.values())
        stell = [i for i, n in by_sign.items() if n >= 3]
        if stell:
            names = ", ".join(C.SIGN_GEN[i] for i in stell)
            lines.append(f"Стеллиум (3+ планеты) в знаке {names} — это ваш ключевой акцент рождения.")
        lines.append("")
        lines.append("Главное: ваша сила — в осознанном проявлении солнечного знака, "
                     f"а эмоциональный ресурс идёт через {C.SIGN_ACC[moon_i]}.")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)

    # ---- гороскоп ----
    def horoscope(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        sign_name = answers["sign"]
        period = (answers.get("period") or "сегодня").strip().lower()
        if period == "день":
            period = "сегодня"
        period_word = {"сегодня": "сегодня", "неделя": "неделю", "месяц": "месяц"}.get(period, period)
        idx = C.SIGN_NAMES.index(sign_name)
        today = _today()
        jd = _now_jd()
        phase, lunar_day, _ = E.moon_phase(jd)
        moon_i = E.sign_of(E.planets_longitudes(jd)[1])
        retro = [b for b in E.retro_planets(jd) if b in (2, 3, 4, 5, 6)]

        lines = [f"🔭 Гороскоп для {C.SIGN_GEN[idx]} на {period_word}"]
        lines.append(f"{_fdate(today)}")
        lines.append("")
        pname, ptext = C.MOON_PHASES[phase]
        lines.append(f"Сегодня {lunar_day}-й лунный день, {pname.lower()}. {ptext}")
        lines.append("")
        moon_e = C.SIGN_ELEMENT[moon_i]
        user_e = C.SIGN_ELEMENT[idx]
        score = C.ELEMENT_COMPAT[(moon_e, user_e)][0]
        mood = "день обещает быть на вашей волне" if score == 3 else (
            "день нейтральный — держите ровный курс" if score == 2 else "день может напрячь — больше пауз и доброты")
        lines.append(f"Луна в {C.SIGN_ABL[moon_i]}: {mood}.")
        lines.append("")
        if retro:
            retro_line = ", ".join(C.PLANETS[b] for b in retro)
            lines.append(f"⚠ Влияние на вас: ретро {retro_line}. Стоит перепроверять договорённости "
                         f"и не торопиться с решениями.")
        lines.append("")
        lines.append(C.SIGN_DAILY[idx][1])
        if period == "неделя":
            lines.append("На неделе найдите время на восстановление и разбор накопившегося — Луна отдаст результат по шагам.")
        elif period == "месяц":
            lines.append("В этом месяце доходите до конца начатого: убывающая половина цикла поможет завершить и расчистить место для нового.")
        lines.append("")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)

    # ---- совместимость ----
    def compat(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        y1, m1, d1 = _parse_date(answers["date1"])
        y2, m2, d2 = _parse_date(answers["date2"])
        jd1 = E.jd_of_date(y1, m1, d1)
        jd2 = E.jd_of_date(y2, m2, d2)
        s1 = E.sign_of(E.planets_longitudes(jd1)[0])
        s2 = E.sign_of(E.planets_longitudes(jd2)[0])
        l1 = E.planets_longitudes(jd1)[0]
        l2 = E.planets_longitudes(jd2)[0]
        e1, e2 = C.SIGN_ELEMENT[s1], C.SIGN_ELEMENT[s2]
        asp = E.aspect(l1, l2, orb=7.0)

        lines = ["💞 Совместимость"]
        lines.append(f"· {answers['date1']} — {C.SIGN_NAMES[s1]} ({C.RULER_TEXT[C.SIGN_RULER[s1]]})")
        lines.append(f"· {answers['date2']} — {C.SIGN_NAMES[s2]} ({C.RULER_TEXT[C.SIGN_RULER[s2]]})")
        lines.append("")
        lines.append(C.ELEMENT_COMPAT[(e1, e2)][1])
        lines.append(C.SUN_ASPECTS.get(asp or "none", C.SUN_ASPECTS["none"]))
        lines.append("")

        base = C.ELEMENT_COMPAT[(e1, e2)][0]
        adj = {"trine": 1, "sextile": 1, "square": -1}.get(asp or "", 0)
        total = max(1, min(4, base + adj))
        verdict = "низкая, но интересная — союз «про работу над собой»" if total <= 1 else (
            "средняя — тёплые отношения, требующие уважения к различиям" if total == 2 else
            "хорошая — есть опора и общая энергия" if total == 3 else "высокая — редкая взаимная гармония")
        lines.append(f"Итог: совместимость {verdict}.")
        lines.append("")
        lines.append("Акценты пределах знаков; Солнце отвечает за базовый стиль и совместимость субличностей, "
                     "грунт под них ищут в натальных картах.")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)

    # ---- ответ на вопрос ----
    def question(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        q = answers["question_text"].strip()
        jd = _now_jd()
        phase, lunar_day, _ = E.moon_phase(jd)
        moon_i = E.sign_of(E.planets_longitudes(jd)[1])
        retro = E.retro_planets(jd)

        lines = ["🔮 Ваш вопрос и звёзды"]
        lines.append(f"«{q}»")
        lines.append("")
        pname, _ = C.MOON_PHASES[phase]
        lines.append(f"Сейчас {lunar_day}-й лунный день, {pname.lower()}.")
        if 1 <= phase <= 3:
            lines.append("Фаза роста — энергичное время для начинаний и переговоров: действуйте.")
        elif phase == 4:
            lines.append("Полнолуние поднимает эмоции: решения отложите, доверяйте фактам, а не порывам.")
        else:
            lines.append("Луна убывает — сейчас время завершать и разбираться с тем, что уже есть, а не стартовать.")
        lines.append("")
        if 2 in retro:
            lines.append("⚠ Меркурий ретроградный: перепроверяйте детали и договорённости, не подписывайте важное без паузы.")
        elif 3 in retro or 4 in retro:
            lines.append("⚠ Венера/Марс ретро: в чувствах и спорах лучше повременить с громкими реакциями.")
        lines.append(f"Луна в {C.SIGN_ABL[moon_i]}. " + C.MOON_SIGN_TEXT[moon_i])
        lines.append("")
        lines.append(C.LUNAR_DAYS[lunar_day][0])
        lines.append(C.LUNAR_DAYS[lunar_day][1])
        lines.append("")
        seed = int(hashlib.md5(q.lower().encode("utf-8")).hexdigest(), 16)
        lines.append(OMENS[seed % len(OMENS)])
        lines.append("")
        lines.append("Это общая подсказка ритма, а не приговор: решение всегда за вами.")
        return "\n".join(lines)

    # ---- лунный день ----
    def moon(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        jd = _now_jd()
        phase, day, _ = E.moon_phase(jd)
        moon_i = E.sign_of(E.planets_longitudes(jd)[1])
        d_do, d_dont = C.LUNAR_DAYS[day]
        pname, ptext = C.MOON_PHASES[phase]

        new_jd = E.lunar_event(jd, 0.0)
        full_jd = E.lunar_event(jd, 180.0)

        lines = ["🌙 Лунный день"]
        lines.append(f"Сегодня {_fdate(_today())}: {day}-й лунный день, {pname.lower()}.")
        lines.append("")
        lines.append("⭐ " + d_do)
        lines.append("⚠ " + d_dont)
        lines.append("")
        lines.append(ptext)
        lines.append("")
        lines.append(C.MOON_SIGN_TEXT[moon_i])
        if new_jd and full_jd:
            if new_jd <= full_jd:
                lines.append(f"\nБлижайшее новолуние — {_ftime_utc_to_msk(new_jd)}, полнолуние — {_ftime_utc_to_msk(full_jd)}.")
            else:
                lines.append(f"\nБлижайшее полнолуние — {_ftime_utc_to_msk(full_jd)}, новолуние — {_ftime_utc_to_msk(new_jd)}.")
        lines.append("")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)

    # ---- ретроградные планеты ----
    def retro(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        jd = _now_jd()
        retro = [b for b in E.retro_planets(jd) if b != 0 and b != 1]

        lines = ["🔄 Ретроградные планеты на сегодня"]
        lines.append(_fdate(_today()))
        lines.append("")
        if not retro:
            lines.append("Сегодня нет активных ретроградных планет (кроме дальних, чей пересмотр задаёт общий фон).")
            lines.append("Хороший день, чтобы договариваться, подписывать и двигаться вперёд.")
        else:
            for b in retro:
                lines.append(C.PLANETS[b] + " ретро")
                span = E.retro_span(jd, b)
                if span:
                    lines.append(f"Период: с {_fdate(E.rev_to_dt(span[0]).date())} по {_fdate(E.rev_to_dt(span[1]).date())}.")
                lines.append(C.RETRO_TEXT[b])
                lines.append("")
            lines.append("Итого: сейчас больше раздумий, ревизии и пересмотра, чем резких стартов.")
        lines.append("")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)

    # ---- число судьбы ----
    def number(self, answers: Dict[str, str]) -> str:
        y, m, d = _parse_date(answers["birth_date"])
        total = sum(int(c) for c in f"{d:02d}{m:02d}{y:04d}")

        def reduce_(s: int):
            if s in (11, 22):
                return s, True
            if s <= 9:
                return s, False
            return reduce_(sum(int(c) for c in str(s)))
        num, master = reduce_(total)
        title, strengths, love, advice = C.NUMEROLOGY[num]
        mdiv = "\u2014 мастер-число: повышенная вибрация и особая ответственность." if master else ""
        lines = ["🔢 Число судьбы"]
        lines.append(f"Дата рождения: {answers['birth_date']}")
        lines.append(f"Сумма цифр: {total} → число {num} ({title}).")
        lines.append("")
        lines.append(strengths)
        lines.append(love)
        lines.append(advice)
        if master:
            lines.append("")
            lines.append(mdiv)
        lines.append("")
        lines.append("Это базовое число жизненного пути; расклад по мечтам и способам развития можно уточнить отдельно.")
        return "\n".join(lines)

    # ---- соляр ----
    def solar(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        y, m, d = _parse_date(answers["birth_date"])
        today = _today()
        sr = E.solar_return_date(y, m, d, today.year, today.month, today.day)
        jd_birth = E.jd_of_date(y, m, d)
        natal_i = E.sign_of(E.planets_longitudes(jd_birth)[0])

        lines = ["🎂 Соляр (возврат Солнца)"]
        lines.append(f"Знак вашей даты: {C.SIGN_NAMES[natal_i]}.")
        if not sr:
            lines.append("Не смог вычислить дату соляра для этой даты — проверьте формат.")
            return "\n".join(lines)
        lines.append(f"Ближайший соляр наступит {_fdate(sr)}.")
        sr_jd = E.jd_of_date(sr.year, sr.month, sr.day)
        phase, day, _ = E.moon_phase(sr_jd)
        moon_i = E.sign_of(E.planets_longitudes(sr_jd)[1])
        lines.append("")
        lines.append(f"Солярный год задаёт свой ритм: Луна соляра в {C.SIGN_ABL[moon_i]} — "
                     + _cap_after_colon(C.MOON_SIGN_TEXT[moon_i]))
        lines.append(f"Лунный день соляра — {day}-й: " + C.LUNAR_DAYS[day][0])
        lines.append("")
        lines.append(C.SOLAR_RULES)
        lines.append("")
        lines.append("Главное наступит в первый месяц нового солнечного года — после него события ускоряются.")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)

    # ---- прогноз на неделю ----
    def weekly(self, answers: Dict[str, str]) -> str:
        if not E.available():
            return E.unavailable_text()
        y, m, d = _parse_date(answers["birth_date"])
        sign_i = E.sun_sign(y, m, d)
        user_e = C.SIGN_ELEMENT[sign_i]
        today = _today()
        monday = today - _dt.timedelta(days=today.weekday())
        wd_abbr = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

        lines = ["🗓 Прогноз на неделю"]
        lines.append(f"{_fdate(monday)} – {_fdate(monday + _dt.timedelta(days=6))} для знака {C.SIGN_NAMES[sign_i]}")
        lines.append("")
        lines.append("Луна по дням:")
        for i in range(7):
            day = monday + _dt.timedelta(days=i)
            jd = E.julday_from_local(day.year, day.month, day.day, 12, 0, 3)
            mi = E.sign_of(E.planets_longitudes(jd)[1])
            score = C.ELEMENT_COMPAT[(C.SIGN_ELEMENT[mi], user_e)][0]
            tone = "ваш день" if score == 3 else ("нейтрально" if score == 2 else "напряжённо")
            lines.append(f"· {wd_abbr[i]} {day.day:02d}.{day.month:02d} — Луна в {C.SIGN_ABL[mi]} ({tone})")
        lines.append("")
        retros = E.retro_planets(_now_jd())
        retros = [b for b in retros if b != 0 and b != 1]
        if retros:
            lines.append("Активны ретро: " + ", ".join(C.PLANETS[b] for b in retros) + " — осторожнее с договорённостями.")
        mM = E.lunar_event(E.jd_of_date(monday.year, monday.month, monday.day), 0.0, 8)
        jd_sun = E.jd_of_date(monday.year, monday.month, monday.day) + 6.0
        if mM and mM <= jd_sun:
            lines.append(f"\nВ эту неделю новолуние ({_ftime_utc_to_msk(mM)}) — после него хорошо начинать важное.")
        pF = E.lunar_event(E.jd_of_date(monday.year, monday.month, monday.day), 180.0, 8)
        if pF and pF <= jd_sun:
            lines.append(f"Также полнолуние {_ftime_utc_to_msk(pF)} — повод для кульминаций и честных разговоров.")
        lines.append("")
        lines.append(f"Рекомендация для знака: {C.SIGN_DAILY[sign_i][1]}")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)

    # ---- медитация на день ----
    def meditation(self, answers: Dict[str, str]) -> str:
        today = _today()
        wd = today.weekday()
        name, theme, focus, technique, affirm = C.WEEKDAYS[wd]

        lines = ["🧘 Медитация на день"]
        lines.append(f"{_fdate(today)} · {name}")
        lines.append("")
        lines.append(theme)
        lines.append(focus)
        lines.append("")
        lines.append("Техника: " + technique)
        lines.append("Рекомендуемое время: 10–15 минут утром, лёгкая растяжка до и короткая тишина после.")
        lines.append("")
        lines.append(f"Аффирмация: «{affirm}»")
        if E.available():
            jd = _now_jd()
            phase, day, _ = E.moon_phase(jd)
            pname, _ = C.MOON_PHASES[phase]
            moon_i = E.sign_of(E.planets_longitudes(jd)[1])
            lines.append("")
            lines.append("Лунная поддержка: " + lunar_med_hint(phase, day, moon_i))
        lines.append("")
        lines.append(C.DISCLAIMER)
        return "\n".join(lines)


def lunar_med_hint(phase: int, day: int, moon_i: int) -> str:
    if phase == 4:
        extra = "Луна в полнолуние — практика отпускания и прощения."
    elif phase <= 3:
        extra = "Растущая Луна — практика намерений и роста."
    else:
        extra = "Убывающая Луна — практика очищения и завершения."
    return f"{day}-й лунный день; {extra} Луна сейчас в {C.SIGN_ABL[moon_i]} — этим знаком окрашено состояние."