# -*- coding: utf-8 -*-
"""المصادقة الآمنة: passlib + JWT تنتهي صلاحيتها تلقائياً"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import string
import time
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_ISSUER, SECRET_KEY
from db import get_conn, now, user_to_dict

# bcrypt مُفضّل عند توفره (الاستضافة العادية)، وpbkdf2_sha256 بديل قوي على Termux/arm64
try:  # pragma: no cover - يعتمد على المنصة
    import bcrypt  # noqa: F401
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False

_SCHEMES = ["bcrypt", "pbkdf2_sha256"] if _HAS_BCRYPT else ["pbkdf2_sha256"]
pwd_context = CryptContext(
    schemes=_SCHEMES,
    deprecated="auto",
    pbkdf2_sha256__rounds=310_000,
)

# توافق مع كلمات المرور القديمة المخزّنة بنظام salt$digest
def _legacy_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 180_000
    ).hex()
    return f"{salt}${digest}"


def _verify_legacy(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), 180_000
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except Exception:
        return False


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, stored: str) -> bool:
    try:
        if pwd_context.verify(password, stored):
            return True
    except Exception:
        pass
    return _verify_legacy(password, stored)


def make_invite_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _clean_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not email or "@" not in email or len(email) > 254 or ".." in email:
        raise ValueError("البريد الإلكتروني غير صالح")
    if "\x00" in email or any(ord(c) < 32 for c in email):
        raise ValueError("البريد الإلكتروني غير صالح")
    return email


def register(email: str, password: str, invite_code: str | None = None) -> dict:
    email = _clean_email(email)
    if len(password) < 8:
        raise ValueError("كلمة المرور يجب أن تكون 8 أحرف على الأقل")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("كلمة المرور طويلة جداً (72 بايت كحد أقصى)")

    conn = get_conn()
    if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        raise ValueError("هذا البريد مسجّل مسبقاً")

    referrer_id = None
    if invite_code:
        code = (invite_code or "").strip().upper()
        if len(code) > 32:
            raise ValueError("رمز الدعوة غير صالح")
        row = conn.execute(
            "SELECT id FROM users WHERE invite_code=?", (code,)
        ).fetchone()
        if row is None:
            raise ValueError("رمز الدعوة غير صالح")
        referrer_id = row["id"]

    code = make_invite_code()
    while conn.execute("SELECT 1 FROM users WHERE invite_code=?", (code,)).fetchone():
        code = make_invite_code()

    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            """INSERT INTO users(email,password_hash,invite_code,referred_by,points,created_at)
               VALUES(?,?,?,?,2,?)""",
            (email, hash_password(password), code, referrer_id, now()),
        )
        user_id = cur.lastrowid
        if referrer_id:
            conn.execute("UPDATE users SET points=points+1 WHERE id=?", (referrer_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return user_to_dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())


def create_token(user_id: int, email: str) -> str:
    issued = int(time.time())
    jti = secrets.token_urlsafe(18)
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": issued,
        "exp": issued + JWT_EXPIRE_MINUTES * 60,
        "iss": JWT_ISSUER,
        "type": "access",
        "jti": jti,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions(token,user_id,created_at) VALUES(?,?,?)",
        (jti, user_id, now()),
    )
    conn.commit()
    return token


def login(email: str, password: str) -> str | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM users WHERE email=?", (_clean_email(email),)
    ).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    if "banned" in row.keys() and row["banned"]:
        return None
    return create_token(row["id"], row["email"])


def _decode(token: str) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def user_from_token(token: str) -> dict | None:
    payload = _decode(token)
    if not payload:
        return None
    conn = get_conn()
    session = conn.execute(
        "SELECT 1 FROM sessions WHERE token=? AND user_id=?",
        (payload["jti"], int(payload["sub"])),
    ).fetchone()
    if not session:
        return None
    row = conn.execute(
        "SELECT * FROM users WHERE id=?", (int(payload["sub"]),)
    ).fetchone()
    if not row or (row.keys() and "banned" in row.keys() and row["banned"]):
        return None
    return user_to_dict(row) if row else None


def revoke_token(token: str) -> bool:
    payload = _decode(token)
    if not payload:
        return False
    conn = get_conn()
    cur = conn.execute("DELETE FROM sessions WHERE token=?", (payload["jti"],))
    conn.commit()
    return cur.rowcount > 0


def get_points(user_id: int) -> float | int:
    row = get_conn().execute("SELECT points FROM users WHERE id=?", (user_id,)).fetchone()
    if not row:
        return 0
    value = float(row["points"])
    return int(value) if value.is_integer() else round(value, 1)


def spend_points(user_id: int, cost: float, mode: str = "charge") -> bool:
    """خصم ذري بمعاملة قاعدة بيانات — يمنع السباق وتجاوز الرصيد."""
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        cur = conn.execute(
            "UPDATE users SET points=points-? WHERE id=? AND points>=?",
            (cost, user_id, cost),
        )
        if cur.rowcount == 0:
            conn.rollback()
            return False
        conn.execute(
            "INSERT INTO usage_logs(user_id,mode,points,created_at) VALUES(?,?,?,?)",
            (user_id, mode, -cost, now()),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


def add_points(user_id: int, points: float, mode: str = "refund") -> None:
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("UPDATE users SET points=points+? WHERE id=?", (points, user_id))
        conn.execute(
            "INSERT INTO usage_logs(user_id,mode,points,created_at) VALUES(?,?,?,?)",
            (user_id, mode, points, now()),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
