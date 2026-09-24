from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.channels.max_ch as max_mod  # noqa: E402
import app.core.engine as engine_mod  # noqa: E402
import app.core.store as store_mod  # noqa: E402

FAKE_DAY = "2026-09-22"
SLUGS = ["natal", "horoscope", "compat", "question", "moon", "retro", "number", "solar", "weekly", "meditation"]


def assert_ok(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"FAIL {name}: {detail}")
    print(f"OK {name}")


def make_engine():
    tmp = tempfile.mkdtemp()
    db = Path(tmp) / "test.db"
    store = store_mod.Store(db)
    sessions = engine_mod.SessionStore(db)
    engine_mod.local_today = lambda: FAKE_DAY
    store_mod.local_today = lambda: FAKE_DAY
    return engine_mod.Engine(store, sessions)


def msg(chat="c1", user="u1", text=None, payload=None):
    return engine_mod.IncomingMessage(channel="t", chat_id=chat, user_id=user, text=text, payload=payload)


# ---------- парсинг событий MAX ----------

def test_build_incoming_started():
    upd = {"update_type": "bot_started", "timestamp": 1, "chat_id": 111,
           "user": {"user_id": 222}, "payload": "start"}
    inc = max_mod.build_incoming(upd)
    assert_ok("bot_started payload", inc is not None and inc.payload == "start" and inc.chat_id == "111"
              and inc.user_id == "222", str(inc))


def test_build_incoming_message():
    upd = {"update_type": "message_created", "timestamp": 1, "chat_id": 111,
           "user": {"user_id": 222},
           "message": {"body": {"text": "привет"}}}
    inc = max_mod.build_incoming(upd)
    assert_ok("message_created text", inc is not None and inc.text == "привет" and inc.chat_id == "111")


def test_build_incoming_callback():
    upd = {"update_type": "message_callback", "timestamp": 1, "chat_id": 111,
           "callback": {"callback_id": "KBD_ID", "payload": "moon",
                        "user": {"user_id": 222}}}
    inc = max_mod.build_incoming(upd)
    assert_ok("message_callback: payload кнопки, не callback_id",
              inc is not None and inc.payload == "moon", str(inc))
    assert_ok("message_callback: user из callback.user",
              inc is not None and inc.user_id == "222", str(inc))


def test_build_incoming_callback_no_message():
    upd = {"update_type": "message_callback", "timestamp": 1, "chat_id": 111,
           "callback": {"callback_id": "KBD_ID"}}
    inc = max_mod.build_incoming(upd)
    assert_ok("message_callback без payload: fallback на callback_id",
              inc is not None and inc.payload == "KBD_ID", str(inc))


def test_build_incoming_unknown():
    assert_ok("неизвестный тип -> None", max_mod.build_incoming({"update_type": "message_reaction"}) is None)
    assert_ok("пустой -> None", max_mod.build_incoming({}) is None)


def test_build_incoming_no_chat():
    upd = {"update_type": "message_callback", "user": {"user_id": 222},
           "callback": {"callback_id": "X"}}
    inc = max_mod.build_incoming(upd)
    assert_ok("fallback chat_id из user", inc is not None and inc.chat_id == "222")


# ---------- сериализация ----------

def test_keyboard_attachment():
    btns = [max_mod.Button("Да", "date_yes"), max_mod.Button("Нет", "cancel")]
    atts = max_mod.keyboard_attachment(btns)
    assert_ok("1 ряд", len(atts) == 1 and atts[0]["type"] == "inline_keyboard")
    row = atts[0]["payload"]["buttons"][0]
    assert_ok("кнопки callback", row[0] == {"type": "callback", "text": "Да", "payload": "date_yes"}
              and row[1]["payload"] == "cancel", str(row))
    assert_ok("пустой список -> []", max_mod.keyboard_attachment([]) == [])


def test_keyboard_rows():
    btns = [max_mod.Button(f"b{i}", f"p{i}") for i in range(5)]
    rows = max_mod.keyboard_attachment(btns, per_row=2)[0]["payload"]["buttons"]
    assert_ok("2 кнопки в ряду, 3 ряда", len(rows) == 3 and len(rows[0]) == 2 and len(rows[2]) == 1,
              str(rows))


def test_split_text():
    assert_ok("короткий не режется", max_mod._split_text("короткий") == ["короткий"])
    long = "x" * 10000
    parts = max_mod._split_text(long)
    assert_ok("длинный разбит", len(parts) > 1 and all(len(p) <= max_mod.TEXT_LIMIT for p in parts))
    assert_ok("не потерян контент", "".join(parts) == long)


# ---------- контроль длины: все действия в MAX ----------

def _drive(e, payload, *answers):
    items = e.process(msg(payload=payload))
    for ans in answers:
        items = e.process(msg(text=ans))
    return items


def test_texts_fit_max_limit():
    e = make_engine()
    engine_mod.config.ADMIN_IDS = [42]
    e.process(msg(chat="c1", user="42", text="/grant 2030-01-01"))
    flows = {
        "natal": ("15.03.1990", "12:00", "Москва"),
        "horoscope": ("Овен", "сегодня"),
        "compat": ("15.03.1990", "22.07.1988"),
        "question": ("Будет ли удачной смена работы?",),
        "moon": (),
        "retro": (),
        "number": ("15.03.1990",),
        "solar": ("15.03.1990",),
        "weekly": ("15.03.1990",),
        "meditation": (),
    }
    for slug in SLUGS:
        items = _drive(e, slug, *flows[slug])
        assert_ok(f"{slug}: есть результат", len(items) > 0 and all(i.text for i in items))
        assert_ok(f"{slug}: длина <= {max_mod.TEXT_LIMIT}",
                  all(len(i.text) <= max_mod.TEXT_LIMIT for i in items),
                  str([len(i.text) for i in items]))


if __name__ == "__main__":
    test_build_incoming_started()
    test_build_incoming_message()
    test_build_incoming_callback()
    test_build_incoming_callback_no_message()
    test_build_incoming_unknown()
    test_build_incoming_no_chat()
    test_keyboard_attachment()
    test_keyboard_rows()
    test_split_text()
    test_texts_fit_max_limit()
    print("\nALL OK")