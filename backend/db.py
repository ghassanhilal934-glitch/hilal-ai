# -*- coding: utf-8 -*-
"""SQLite قاعدة بيانات Hilal AI"""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, CHAT_WINDOW_SECONDS, FREE_CHAT_DAILY_LIMIT

DB_PATH = Path(__file__).resolve().parent / "hilal.db"
_local = threading.local()


def now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


@contextmanager
def transaction():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            invite_code TEXT NOT NULL UNIQUE,
            referred_by INTEGER,
            points INTEGER NOT NULL DEFAULT 2,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payments (
            tx_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            package_id TEXT NOT NULL,
            amount REAL NOT NULL,
            points INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            mode TEXT NOT NULL,
            points INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payment_attempts (
            attempt_key TEXT PRIMARY KEY,
            failures INTEGER NOT NULL DEFAULT 0,
            first_failure REAL NOT NULL,
            last_failure REAL NOT NULL,
            blocked_until REAL
        );

        CREATE TABLE IF NOT EXISTS ad_tickets (
            jti TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            claimed INTEGER NOT NULL DEFAULT 0,
            claimed_at REAL
        );

        CREATE TABLE IF NOT EXISTS admin_sessions (
            jti TEXT PRIMARY KEY,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        -- عدّاد المحادثة المجانية: نافذة متجددة كل 24 ساعة من أول رسالة
        CREATE TABLE IF NOT EXISTS chat_usage (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            window_start REAL NOT NULL,
            used INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_ads_user_claim ON ad_tickets(user_id, claimed, claimed_at);
        CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        """
    )
    conn.commit()

    # ترح春光 آمن للقواعد الموجودة قبل إضافة ميزة الحظر
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "banned" not in cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN banned INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()


def user_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "email": row["email"],
        "points": row["points"],
        "invite_code": row["invite_code"],
        "referred_by": row["referred_by"],
        "created_at": row["created_at"],
        "banned": bool(row["banned"]) if "banned" in row.keys() else False,
    }


def has_paid(user_id: int) -> bool:
    row = get_conn().execute(
        "SELECT 1 FROM payments WHERE user_id=? AND status='confirmed' LIMIT 1",
        (user_id,),
    ).fetchone()
    return row is not None


# ---------------------- حد المحادثة المجانية (30/24h) -----------------------
def chat_status(user_id: int, paid: bool = False) -> dict:
    """حالة العدّاد دون تعديله. المشترون لا حدود لهم."""
    row = get_conn().execute(
        "SELECT window_start, used FROM chat_usage WHERE user_id=?", (user_id,)
    ).fetchone()
    ts = time.time()
    active = row is not None and ts - float(row["window_start"]) < CHAT_WINDOW_SECONDS
    used = int(row["used"]) if active else 0
    reset_at = (
        float(row["window_start"]) + CHAT_WINDOW_SECONDS
        if active else ts + CHAT_WINDOW_SECONDS
    )
    return {
        "chat_limit": FREE_CHAT_DAILY_LIMIT,
        "chat_used": used,
        "chat_remaining": None if paid else max(0, FREE_CHAT_DAILY_LIMIT - used),
        "chat_reset_at": int(reset_at),
        "chat_unlimited": bool(paid),
    }


def consume_free_chat(user_id: int, paid: bool = False) -> tuple[bool, dict]:
    """خصم رسالة واحدة من العدّاد ذرياً؛ يعيد (مسموح، الحالة الجديدة)."""
    status = chat_status(user_id, paid)
    if paid or status["chat_unlimited"]:
        return True, status
    if status["chat_remaining"] <= 0:
        return False, status

    ts = time.time()
    with transaction() as conn:
        row = conn.execute(
            "SELECT window_start, used FROM chat_usage WHERE user_id=?", (user_id,)
        ).fetchone()
        if row and ts - float(row["window_start"]) < CHAT_WINDOW_SECONDS:
            cur = conn.execute(
                "UPDATE chat_usage SET used=used+1 "
                "WHERE user_id=? AND used<?",
                (user_id, FREE_CHAT_DAILY_LIMIT),
            )
            allowed = cur.rowcount > 0
        else:
            conn.execute(
                "INSERT OR REPLACE INTO chat_usage(user_id,window_start,used) "
                "VALUES(?,?,1)",
                (user_id, ts),
            )
            allowed = True
    return allowed, chat_status(user_id, False)


def refund_free_chat(user_id: int) -> None:
    """إرجاع الرسالة إلى العدّاد عند فشل مزوّد الذكاء الاصطناعي."""
    with transaction() as conn:
        conn.execute(
            "UPDATE chat_usage SET used=MAX(0,used-1) WHERE user_id=?", (user_id,)
        )
