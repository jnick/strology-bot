from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.core.engine as engine_mod  # noqa: E402
import app.core.store as store_mod  # noqa: E402

FAKE_DAY = "2026-09-22"


def make_engine():
    tmp = tempfile.mkdtemp()
    db = Path(tmp) / "test.db"
    store = store_mod.Store(db)
    sessions = engine_mod.SessionStore(db)
    e = engine_mod.Engine(store, sessions)
    engine_mod.local_today = lambda: FAKE_DAY
    store_mod.local_today = lambda: FAKE_DAY
    return e


def msg(chat="c1", user="u1", text=None, payload=None):
    return engine_mod.IncomingMessage(
        channel="t", chat_id=chat, user_id=user, text=text, payload=payload
    )


def texts_of(items):
    return [i.text for i in items]


def assert_ok(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAIL {name}: {detail}")
    print(f"OK {name}")


def test_menu():
    e = make_engine()
    items = e.process(msg(text="/start"))
    assert_ok("start -> 1 item", len(items) == 1)
    assert_ok("menu текст", "Приветствие №1" in items[0].text)
    assert_ok("10 кнопок", len(items[0].buttons) == 10, str(len(items[0].buttons)))
    nav = ["nata" if False else "natal", "horoscope", "compat", "question", "moon",
           "retro", "number", "solar", "weekly", "meditation"]
    assert_ok("slug'ы меню", [b.callback for b in items[0].buttons] == nav)


def test_free_limit_and_sub_flow():
    e = make_engine()
    e.process(msg(payload="natal"))
    blocked = e.process(msg(payload="horoscope"))
    assert_ok("лимит исчерпан", "исчерпан" in blocked[0].text, blocked[0].text)
    assert_ok("кнопки подписка/меню", [b.callback for b in blocked[0].buttons] == ["sub", "menu"])

    # подписка через админа
    engine_mod.config.ADMIN_IDS = [42]
    grant = e.process(msg(chat="c1", user="42", text="/grant 2030-01-01"))
    assert_ok("grant", "активна до 2030-01-01" in grant[0].text, grant[0].text)
    # теперь безлимит: множественные действия в тот же день
    for slug in ("natal", "horoscope", "compat"):
        r = e.process(msg(payload=slug))
        assert_ok(f"безлимит {slug}", len(r) == 1)
    revoke = e.process(msg(chat="c1", user="42", text="/revoke"))
    assert_ok("revoke", "отозвана" in revoke[0].text)
    blocked2 = e.process(msg(payload="moon"))
    assert_ok("снова лимит после revoke", "исчерпан" in blocked2[0].text)


def test_deny_non_admin():
    e = make_engine()
    engine_mod.config.ADMIN_IDS = [42]
    r = e.process(msg(user="bad", text="/grant 2030-01-01"))
    assert_ok("не-админ отклонён", "Нет доступа" in r[0].text)


def test_natal_steps_and_result():
    e = make_engine()
    e.process(msg(payload="natal"))
    bad = e.process(msg(text="31.02.1990"))
    assert_ok("некорректная дата отклонена", "Некорректная дата" in bad[0].text, bad[0].text)
    q1 = e.process(msg(text="15.03.1990"))
    assert_ok("шаг 1 принят, вопрос 2", "Вопрос 2 из 3" in q1[0].text, q1[0].text)
    q2 = e.process(msg(text="12:00"))
    assert_ok("шаг 2", "Вопрос 3 из 3" in q2[0].text)
    fin = e.process(msg(text="Москва"))
    assert_ok("результат", "Натальная карта" in fin[0].text, fin[0].text)
    assert_ok("данные собраны", "birth date: 15.03.1990" in fin[0].text, fin[0].text)
    assert_ok("кнопка в меню", fin[0].buttons[0].callback == "menu")
    assert_ok("сессия очищена", e.sessions.get("t", "c1") is None)


def test_moon_no_steps():
    e = make_engine()
    e.process(msg(payload="moon"))
    # без лимита само действие уже сконсимировано, но moon без шагов сразу результат
    e2 = make_engine()  # свежая БД
    r = e2.process(msg(payload="moon"))
    assert_ok("moon сразу результат", "Лунный день" in r[0].text)


def test_cancel_during_collecting():
    e = make_engine()
    e.process(msg(payload="natal"))
    r = e.process(msg(payload="cancel"))
    assert_ok("cancel", "отменено" in r[0].text.lower())
    assert_ok("сессия очищена", e.sessions.get("t", "c1") is None)


def test_day_reset():
    e = make_engine()
    e.process(msg(payload="natal"))
    blocked = e.process(msg(payload="horoscope"))
    assert_ok("лимит в тот же день", "исчерпан" in blocked[0].text)
    # следующий день
    engine_mod.local_today = lambda: "2026-09-23"
    ok = e.process(msg(payload="horoscope"))
    assert_ok("новый день сброс", "Гороскоп" in ok[0].text, ok[0].text)


if __name__ == "__main__":
    test_menu()
    test_free_limit_and_sub_flow()
    test_deny_non_admin()
    test_natal_steps_and_result()
    test_moon_no_steps()
    test_cancel_during_collecting()
    test_day_reset()
    print("\nALL OK")