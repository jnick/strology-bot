from __future__ import annotations

"""Обёртка над Swiss Ephemeris (Moshier-режим, без файлов данных).

Реализует: положения планет, знак по долготе, ретроградность, аспекты,
лунный день и фазу, дома Плацидус, дату соляра.
Все временные аргументы принимаются в UTC."""

import datetime as _dt
from typing import Dict, List, Optional, Tuple

try:
    import swisseph as _swe
    _swe.set_ephe_path("")
    _AVAILABLE = True
except Exception:  # pragma: no cover
    _swe = None
    _AVAILABLE = False

_FLAGS = 0x0800 | 0x0100  # FLG_MOSEPH | FLG_SPEED

BODIES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]  # Солнце..Плутон


def available() -> bool:
    return _AVAILABLE


def unavailable_text() -> str:
    return "Сейчас сервис расчётов временно недоступен. Попробуйте позже — даты сохраняются, я вернусь к ним сразу после перезапуска."


# --- внутренние утилиты ---------------------------------------------------
def _julday(y: int, m: int, d: int, h: float) -> float:
    return _swe.julday(y, m, d, h)


def julday_from_local(y: int, m: int, d: int, hour: int, minute: int, tz_h: float) -> float:
    """Локальное гражданское время -> JD UTC."""
    dt = _dt.datetime(y, m, d, hour, minute) - _dt.timedelta(hours=tz_h)
    h = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    return _swe.julday(dt.year, dt.month, dt.day, h)


def jd_of_date(y: int, m: int, d: int) -> float:
    return _swe.julday(y, m, d, 12.0)


def jd_of_datetime_utc(dt: _dt.datetime) -> float:
    h = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
    return _swe.julday(dt.year, dt.month, dt.day, h)


def rev_to_dt(jd: float) -> _dt.datetime:
    y, m, d, h = _swe.revjul(jd)
    return _dt.datetime(int(y), int(m), int(d)) + _dt.timedelta(hours=h - 12.0)


def _lon(jd: float, body: int) -> float:
    x, _ = _swe.calc_ut(jd, body, _FLAGS)
    return float(x[0])


def _speed(jd: float, body: int) -> float:
    x, _ = _swe.calc_ut(jd, body, _FLAGS)
    return float(x[3])


def norm360(a: float) -> float:
    return a % 360.0


def signed_delta(a: float, b: float) -> float:
    """Кратчайшая (со знаком) дуга от a к b: в (-180..180]."""
    return (b - a + 180.0) % 360.0 - 180.0


# --- публичное API --------------------------------------------------------
def sign_of(lon: float) -> int:
    return int(norm360(lon) // 30) % 12


def planets_longitudes(jd: float) -> Dict[int, float]:
    return {b: _lon(jd, b) for b in BODIES}


def is_retro(jd: float, body: int) -> bool:
    return _speed(jd, body) < 0.0


def retro_planets(jd: float) -> List[int]:
    return [b for b in BODIES if is_retro(jd, b)]


def retro_span(jd: float, body: int, lookback: int = 130, lookfwd: int = 120) -> Optional[Tuple[float, float]]:
    """Если планета ретроградна в jd — возвращает (start_jd, end_jd), иначе None."""
    if not is_retro(jd, body):
        return None
    start = jd
    while start - jd > -lookback and is_retro(start, body):
        start -= 1.0
    end = jd
    while end - jd < lookfwd and is_retro(end, body):
        end += 1.0
    return start, end


def sun_sign(y: int, m: int, d: int) -> int:
    return sign_of(_lon(jd_of_date(y, m, d), 0))


def moon_phase(jd: float) -> Tuple[int, int, float]:
    """Возвращает (фаза 0..7, лунный день 1..30, элонгация 0..360)."""
    elong = norm360(_lon(jd, 1) - _lon(jd, 0))
    phase = int((elong + 22.5) // 45.0) % 8
    day = int(elong // 12.0) + 1
    return phase, day, elong


def aspect(a: float, b: float, orb: float = 6.0) -> Optional[str]:
    delta = min(norm360(abs(a - b)), 360.0 - norm360(abs(a - b)))
    for name, angle in (("conjunction", 0.0), ("sextile", 60.0),
                        ("square", 90.0), ("trine", 120.0),
                        ("opposition", 180.0)):
        if abs(delta - angle) <= orb:
            return name
    return None


def houses_p(jd: float, lat: float, lon: float) -> Tuple[float, Dict[int, float]]:
    """Асцендент и 12 домов (Плацидус): (asc_longitude, {дом: куспид_долгота})."""
    cusps, ascmc = _swe.houses(jd, lat, lon, b"P")
    houses = {}
    start = 1 if len(cusps) == 12 else 0
    for i in range(12):
        houses[i + start] = float(cusps[i])
    return float(ascmc[0]), houses


def solar_return_date(y: int, m: int, d: int, from_y: int, from_m: int, from_d: int) -> Optional[_dt.date]:
    """Дата ближайшего возврата Солнца (соляр), идя от from_date."""
    jd_birth = jd_of_date(y, m, d)
    natal = _lon(jd_birth, 0)
    jd0 = _julday(from_y, from_m, from_d, 0.0)

    def dist(j: float) -> float:
        return signed_delta(natal, _lon(j, 0))

    prev = dist(jd0)
    for i in range(1, 372):
        cur = dist(jd0 + i)
        if prev < 0.0 <= cur:
            lo, hi = jd0 + i - 1, jd0 + i
            for _ in range(40):
                mid = (lo + hi) / 2.0
                if dist(mid) < 0.0:
                    lo = mid
                else:
                    hi = mid
            return rev_to_dt((lo + hi) / 2.0).date()
        prev = cur
    return None


def lunar_event(jd_start: float, target_deg: float, days: int = 32) -> Optional[float]:
    """JD ближайшего момента, когда элонгация пересекает target_deg (0=новолуние, 180=полнолуние)."""
    def el(j: float) -> float:
        return norm360(_lon(j, 1) - _lon(j, 0))

    def sd(j: float) -> float:
        return signed_delta(target_deg, el(j))

    jd = jd_start
    prev = sd(jd)
    for i in range(1, days * 2 + 1):
        jd2 = jd_start + i * 0.5
        cur = sd(jd2)
        if prev < 0.0 <= cur:
            lo, hi = jd, jd2
            for _ in range(40):
                mid = (lo + hi) / 2.0
                if sd(mid) < 0.0:
                    lo = mid
                else:
                    hi = mid
            return (lo + hi) / 2.0
        prev, jd = cur, jd2
    return None