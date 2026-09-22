from __future__ import annotations

import datetime
import sqlite3
import threading
from pathlib import Path
from typing import Optional

MOSCOW_UTC_OFFSET = datetime.timedelta(hours=3)


def local_today() -> str:
    """Сегодняшняя дата по Москве (UTC+3) в формате YYYY-MM-DD."""
    return (datetime.datetime.utcnow() + MOSCOW_UTC_OFFSET).strftime("%Y-%m-%d")


class Store:
    """Пользователи, подписки и дневное использование действий."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                channel TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT '',
                subscribed_until TEXT,
                PRIMARY KEY (channel, chat_id)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usage (
                channel TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                day TEXT NOT NULL,
                actions_used INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (channel, chat_id, day)
            )
            """
        )
        self._conn.commit()

    def is_subscribed(self, channel: str, chat_id: str, today: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT subscribed_until FROM users WHERE channel=? AND chat_id=?",
                (channel, chat_id),
            ).fetchone()
        return bool(row and row[0] and row[0] >= today)

    def consume(self, channel: str, chat_id: str, user_id: str, day: str, limit: int) -> bool:
        """Списать одно использование. True — разрешено и учтено, False — лимит исчерпан."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO users (channel, chat_id, user_id, subscribed_until) "
                "VALUES (?, ?, ?, COALESCE((SELECT subscribed_until FROM users "
                "WHERE channel=? AND chat_id=?), NULL))",
                (channel, chat_id, user_id, channel, chat_id),
            )
            row = self._conn.execute(
                "SELECT actions_used FROM usage WHERE channel=? AND chat_id=? AND day=?",
                (channel, chat_id, day),
            ).fetchone()
            used = row[0] if row else 0
            if used >= limit:
                return False
            self._conn.execute(
                "INSERT OR REPLACE INTO usage (channel, chat_id, day, actions_used) VALUES (?, ?, ?, ?)",
                (channel, chat_id, day, used + 1),
            )
            self._conn.commit()
            return True

    def used_today(self, channel: str, chat_id: str, day: str) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT actions_used FROM usage WHERE channel=? AND chat_id=? AND day=?",
                (channel, chat_id, day),
            ).fetchone()
        return row[0] if row else 0

    def grant(self, channel: str, chat_id: str, user_id: str, until: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO users (channel, chat_id, user_id, subscribed_until) "
                "VALUES (?, ?, ?, ?)",
                (channel, chat_id, user_id, until),
            )
            self._conn.commit()

    def revoke(self, channel: str, chat_id: str, user_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO users (channel, chat_id, user_id, subscribed_until) "
                "VALUES (?, ?, ?, NULL)",
                (channel, chat_id, user_id),
            )
            self._conn.commit()

    def subscription_until(self, channel: str, chat_id: str) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT subscribed_until FROM users WHERE channel=? AND chat_id=?",
                (channel, chat_id),
            ).fetchone()
        return row[0] if row else None