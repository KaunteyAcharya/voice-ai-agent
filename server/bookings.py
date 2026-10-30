"""Site-visit bookings in SQLite.

A single file (``data/tatsat.db`` by default, ``BOOKINGS_DB`` to change it) so
bookings survive a server restart, using only Python's built-in ``sqlite3``.
A few slots are pre-booked on every start (relative to today) so the demo can
show the "that slot is taken" path.
"""

from __future__ import annotations

import random
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,
    property_id TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    date        TEXT    NOT NULL,          -- YYYY-MM-DD
    time        TEXT    NOT NULL,          -- HH:MM, 24-hour
    status      TEXT    NOT NULL DEFAULT 'confirmed',  -- confirmed | cancelled
    seeded      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
);
-- One active booking per property and slot; cancelled rows don't block it.
CREATE UNIQUE INDEX IF NOT EXISTS one_booking_per_slot
    ON bookings(property_id, date, time) WHERE status = 'confirmed';
CREATE INDEX IF NOT EXISTS bookings_by_phone ON bookings(phone);

-- Callers who left a number for follow-up, and what they were interested in.
CREATE TABLE IF NOT EXISTS leads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone       TEXT    NOT NULL,
    name        TEXT,
    language    TEXT    NOT NULL DEFAULT 'en',
    interested  TEXT    NOT NULL DEFAULT '[]',   -- JSON list of property ids
    created_at  TEXT    NOT NULL
);

-- Every follow-up message, whether it was sent or only previewed.
CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    phone       TEXT    NOT NULL,
    channel     TEXT    NOT NULL,               -- whatsapp | preview
    status      TEXT    NOT NULL,               -- sent | preview | failed
    detail      TEXT,
    body        TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
"""

# Slots taken on every start, so the demo shows the "slot is taken" path.
# (property, days from today, time); "sat" means the coming Saturday.
SEEDED_SLOTS = [
    ("SH-102", 1, "11:00"),
    ("SH-102", 1, "16:00"),
    ("SH-102", "sat", "11:00"),
    ("SH-102", "sat", "12:00"),
    ("SH-101", 1, "17:00"),
    ("SH-105", "sat", "11:00"),
    ("SH-110", 1, "18:00"),
]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _row(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


class BookingStore:
    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock, self._db:
            self._db.executescript(SCHEMA)

    # -- setup ---------------------------------------------------------------

    def seed(self, today: date) -> None:
        """Replace the pre-booked demo slots with fresh ones relative to ``today``."""
        saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
        with self._lock, self._db:
            self._db.execute("DELETE FROM bookings WHERE seeded = 1")
            for pid, offset, slot in SEEDED_SLOTS:
                day = saturday if offset == "sat" else today + timedelta(days=offset)
                self._db.execute(
                    "INSERT OR IGNORE INTO bookings (code, property_id, name, phone, date, time, seeded, created_at, updated_at)"
                    " VALUES (?, ?, '(reserved)', '0000000000', ?, ?, 1, ?, ?)",
                    (f"SEED-{pid}-{day.isoformat()}-{slot}", pid, day.isoformat(), slot, _now(), _now()),
                )

    # -- queries -------------------------------------------------------------

    def is_taken(self, property_id: str, day: str, slot: str, ignore_code: str | None = None) -> bool:
        with self._lock:
            row = self._db.execute(
                "SELECT code FROM bookings WHERE property_id = ? AND date = ? AND time = ? AND status = 'confirmed'",
                (property_id, day, slot),
            ).fetchone()
        return row is not None and row["code"] != ignore_code

    def get(self, code: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT * FROM bookings WHERE code = ?", (code,)).fetchone()
        return _row(row) if row else None

    def find_by_phone(self, phone: str, from_day: str | None = None) -> list[dict]:
        """Active, real (not seeded) bookings for a phone number, soonest first."""
        query = "SELECT * FROM bookings WHERE phone = ? AND status = 'confirmed' AND seeded = 0"
        args: list = [phone]
        if from_day:
            query += " AND date >= ?"
            args.append(from_day)
        with self._lock:
            rows = self._db.execute(query + " ORDER BY date, time", args).fetchall()
        return [_row(r) for r in rows]

    # -- changes -------------------------------------------------------------

    def _new_code(self) -> str:
        while True:
            code = f"SH-{random.randint(1000, 9999)}"
            if self.get(code) is None:
                return code

    def create(self, property_id: str, name: str, phone: str, day: str, slot: str) -> dict | None:
        """Book a slot; returns the booking, or None if someone else got it first."""
        code = self._new_code()
        try:
            with self._lock, self._db:
                self._db.execute(
                    "INSERT INTO bookings (code, property_id, name, phone, date, time, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (code, property_id, name, phone, day, slot, _now(), _now()),
                )
        except sqlite3.IntegrityError:
            return None
        return self.get(code)

    def reschedule(self, code: str, day: str, slot: str) -> dict | None:
        """Move a booking to a new slot; returns the updated booking, or None if the slot is taken."""
        try:
            with self._lock, self._db:
                self._db.execute(
                    "UPDATE bookings SET date = ?, time = ?, updated_at = ? WHERE code = ? AND status = 'confirmed'",
                    (day, slot, _now(), code),
                )
        except sqlite3.IntegrityError:
            return None
        return self.get(code)

    def cancel(self, code: str) -> dict | None:
        with self._lock, self._db:
            self._db.execute(
                "UPDATE bookings SET status = 'cancelled', updated_at = ? WHERE code = ? AND status = 'confirmed'",
                (_now(), code),
            )
        return self.get(code)

    # -- follow-up leads and messages ----------------------------------------

    def save_lead(self, phone: str, name: str | None, language: str, interested: list[str]) -> int:
        import json

        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO leads (phone, name, language, interested, created_at) VALUES (?, ?, ?, ?, ?)",
                (phone, name, language, json.dumps(interested), _now()),
            )
        return cur.lastrowid

    def log_message(self, phone: str, channel: str, status: str, body: str, detail: str | None = None) -> int:
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO messages (phone, channel, status, detail, body, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (phone, channel, status, detail, body, _now()),
            )
        return cur.lastrowid

    def leads(self) -> list[dict]:
        with self._lock:
            return [_row(r) for r in self._db.execute("SELECT * FROM leads ORDER BY id").fetchall()]

    def messages(self) -> list[dict]:
        with self._lock:
            return [_row(r) for r in self._db.execute("SELECT * FROM messages ORDER BY id").fetchall()]

    def clear(self) -> None:
        """Delete everything (used by tests and the eval bot)."""
        with self._lock, self._db:
            for table in ("bookings", "leads", "messages"):
                self._db.execute(f"DELETE FROM {table}")
