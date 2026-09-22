from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime  # noqa: E402

from app.core import ephemeris as E  # noqa: E402
from app.core.astro import AstroService  # noqa: E402


def assert_ok(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAIL {name}: {detail}")
    print(f"OK {name}")


A = AstroService()

# ---------- ephemeris ----------

jd = E.julday_from_local(1990, 3, 15, 12, 0, 3)
sun_i = E.sign_of(E.planets_longitudes(jd)[0])
assert_ok("sun sign 15.03.1990 is Pisces(11)", sun_i == 11, f"got {sun_i}")

jd2 = E.julday_from_local(1986, 4, 6, 12, 0, 3)
sun2 = E.sign_of(E.planets_longitudes(jd2)[0])
assert_ok("sun sign 06.04.1986 is Aries(0)", sun2 == 0, f"got {sun2}")

phase, day, _ = E.moon_phase(E.jd_of_datetime_utc(datetime.datetime.utcnow()))
assert_ok("lunar day in 1..30", 1 <= day <= 30, f"got {day}")
assert_ok("phase in 0..7", 0 <= phase <= 7, f"got {phase}")

nn = E.lunar_event(jd, 0.0)
pf = E.lunar_event(jd, 180.0)
assert_ok("lunar_event finds new moon", nn is not None)
assert_ok("lunar_event finds full moon", pf is not None)
assert_ok("new moon before full moon", nn < pf)

retro = E.retro_planets(jd)
for b in retro:
    assert_ok(f"retro list item {b} is valid", 0 <= b <= 9)

sr = E.solar_return_date(1990, 3, 15, 2026, 9, 22)
assert_ok("solar return in 2027 (15.03)", sr is not None and sr.year == 2027, f"got {sr}")
sr2 = E.solar_return_date(1986, 4, 6, 2026, 9, 22)
assert_ok("solar return in 2027 (06.04)", sr2 is not None and sr2.year == 2027, f"got {sr2}")

h = E.houses_p(jd, 55.7558, 37.6173)
assert_ok("houses produces asc and 12 cusps", 0 <= h[0] < 360 and len(h[1]) == 12)

# ---------- numerology ----------
def reduce_(total):
    if total in (11, 22):
        return total
    if total <= 9:
        return total
    return reduce_(sum(int(c) for c in str(total)))


def life(day, mon, year):
    t = sum(int(c) for c in f"{day:02d}{mon:02d}{year:04d}")
    return reduce_(t)


assert_ok("number 15.03.1990 -> 1", life(15, 3, 1990) == 1, f"got {life(15, 3, 1990)}")
assert_ok("master 11.02.1987 -> 11", life(11, 2, 1987) == 11, f"got {life(11, 2, 1987)}")
assert_ok("master 29.09.2000 -> 22", life(29, 9, 2000) == 22, f"got {life(29, 9, 2000)}")

# ---------- cities ----------
from app.resources import cities  # noqa: E402

loc, known = cities.lookup_city("Красноярск")
assert_ok("city krasnoyarsk known", known and abs(loc[0] - 56.0) < 0.5, f"got {loc}")
loc2, known2 = cities.lookup_city("гжзлх")
assert_ok("unknown city fallback to moscow", not known2 and abs(loc2[1] - 37.6) < 0.5)

# ---------- service smoke (format only) ----------
NATAL = {"birth_date": "15.03.1990", "birth_time": "14:30", "birth_place": "Москва"}
HORO = {"sign": "Овен", "period": "сегодня"}
COMPAT = {"date1": "15.03.1990", "date2": "22.07.1988"}
QUESTION = {"question_text": "Будет ли удачной смена работы?"}
NUMBER = {"birth_date": "15.03.1990"}
SOLAR = {"birth_date": "15.03.1990"}
WEEKLY = {"birth_date": "15.03.1990"}

checks = [
    ("natal", A.natal(NATAL)),
    ("horoscope", A.horoscope(HORO)),
    ("compat", A.compat(COMPAT)),
    ("question", A.question(QUESTION)),
    ("moon", A.moon({})),
    ("retro", A.retro({})),
    ("number", A.number(NUMBER)),
    ("solar", A.solar(SOLAR)),
    ("weekly", A.weekly(WEEKLY)),
    ("meditation", A.meditation({})),
]
for name, text in checks:
    assert_ok(f"{name} produces text > 50 chars", len(text) > 50, f"len={len(text)}")
    if name == "natal":
        assert_ok("natal mentions zodiac sign", "Рыб" in text or "Солнце" in text)
    if name == "horoscope":
        assert_ok("horoscope contains sign name", "Овна" in text)
    if name == "compat":
        assert_ok("compat mentions both signs", "Рыб" in text and "Лев" in text)

print(f"\nВсего проверок пройдено: {12 + len(checks)}")