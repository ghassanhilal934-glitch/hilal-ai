# -*- coding: utf-8 -*-
"""لوحة تحكم المدير: مصادقة منفصلة + إحصائيات + إدارة المستخدمين."""
from __future__ import annotations

import hmac
import secrets
import time

import jwt

from config import (
    ADMIN_PASSWORD,
    ADMIN_SESSION_MINUTES,
    JWT_ALGORITHM,
    JWT_ISSUER,
    SECRET_KEY,
)
from db import get_conn, now, user_to_dict

ADMIN_TYPE = "hilal_admin"


class AdminError(Exception):
    """خطأ مُترجم للوحة المدير"""


def is_configured() -> bool:
    return bool(ADMIN_PASSWORD)


def login(password: str) -> str:
    if not is_configured():
        raise AdminError("لوحة المدير غير مفعّلة: أضف ADMIN_PASSWORD إلى ملف .env")
    if not hmac.compare_digest(str(password or ""), ADMIN_PASSWORD):
        raise AdminError("كلمة مرور المدير غير صحيحة")

    issued = int(time.time())
    jti = secrets.token_urlsafe(18)
    payload = {
        "sub": "admin",
        "jti": jti,
        "iat": issued,
        "exp": issued + ADMIN_SESSION_MINUTES * 60,
        "iss": JWT_ISSUER,
        "type": ADMIN_TYPE,
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
    conn = get_conn()
    conn.execute(
        "INSERT INTO admin_sessions(jti,created_at,expires_at) VALUES(?,?,?)",
        (jti, float(issued), float(payload["exp"])),
    )
    conn.commit()
    return token


def verify_token(token: str) -> bool:
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
        if payload.get("type") != ADMIN_TYPE or payload.get("sub") != "admin":
            return False
    except jwt.PyJWTError:
        return False
    conn = get_conn()
    row = conn.execute(
        "SELECT expires_at FROM admin_sessions WHERE jti=?", (payload["jti"],)
    ).fetchone()
    return bool(row and float(row["expires_at"]) > time.time())


def logout(token: str) -> None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        conn = get_conn()
        conn.execute("DELETE FROM admin_sessions WHERE jti=?", (payload.get("jti"),))
        conn.commit()
    except jwt.PyJWTError:
        pass


def _log(action: str, detail: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO admin_logs(action,detail,created_at) VALUES(?,?,?)",
        (action, detail, now()),
    )


def stats() -> dict:
    conn = get_conn()
    users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    paid = conn.execute(
        "SELECT COUNT(DISTINCT user_id) AS n FROM payments WHERE status='confirmed'"
    ).fetchone()["n"]
    revenue = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS s FROM payments WHERE status='confirmed'"
    ).fetchone()["s"]
    points = conn.execute(
        "SELECT COALESCE(SUM(points),0) AS s FROM users"
    ).fetchone()["s"]
    ads = conn.execute(
        "SELECT COUNT(*) AS n FROM ad_tickets WHERE claimed=1"
    ).fetchone()["n"]
    today_signups = conn.execute(
        "SELECT COUNT(*) AS n FROM users WHERE created_at>=date('now')"
    ).fetchone()["n"]
    return {
        "users": int(users),
        "paid_users": int(paid),
        "revenue_usdt": round(float(revenue), 2),
        "points_in_circulation": round(float(points), 1),
        "ads_claimed": int(ads),
        "signups_today": int(today_signups),
    }


def users(limit: int = 100) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT u.*,
                  (SELECT COUNT(*) FROM payments p
                   WHERE p.user_id=u.id AND p.status='confirmed') AS paid_count
           FROM users u ORDER BY u.id DESC LIMIT ?""",
        (max(1, min(limit, 500)),),
    ).fetchall()
    return [
        {
            **user_to_dict(r),
            "paid_count": int(r["paid_count"]),
        }
        for r in rows
    ]


def payments(limit: int = 100) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT p.*, u.email FROM payments p
           JOIN users u ON u.id=p.user_id
           ORDER BY p.created_at DESC LIMIT ?""",
        (max(1, min(limit, 500)),),
    ).fetchall()
    return [
        {
            "tx_hash": r["tx_hash"],
            "email": r["email"],
            "package_id": r["package_id"],
            "amount": r["amount"],
            "points": r["points"],
            "status": r["status"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def add_points(email: str, points: float, note: str = "") -> dict:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise AdminError("بريد غير صالح")
    try:
        amount = float(points)
    except (TypeError, ValueError) as exc:
        raise AdminError("عدد النقاط غير صالح") from exc
    if amount == 0 or abs(amount) > 10000:
        raise AdminError("عدد النقاط خارج النطاق المسموح")

    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT id, points FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            raise AdminError("المستخدم غير موجود")
        new_balance = round(float(row["points"]) + amount, 2)
        conn.execute("UPDATE users SET points=? WHERE id=?", (new_balance, row["id"]))
        conn.execute(
            "INSERT INTO usage_logs(user_id,mode,points,created_at) VALUES(?,?,?,?)",
            (row["id"], "admin_adjust", amount, now()),
        )
        _log("add_points", f"{email}: {amount:+} -> {new_balance} | {note[:100]}")
        conn.commit()
    except AdminError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise AdminError("تعذّر تحديث النقاط") from exc
    return {"email": email, "added": amount, "balance": new_balance}


def set_banned(email: str, banned: bool) -> dict:
    email = (email or "").strip().lower()
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            raise AdminError("المستخدم غير موجود")
        conn.execute(
            "UPDATE users SET banned=? WHERE id=?", (1 if banned else 0, row["id"])
        )
        if banned:
            conn.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
        _log("ban" if banned else "unban", email)
        conn.commit()
    except AdminError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise AdminError("تعذّر تحديث حالة المستخدم") from exc
    return {"email": email, "banned": bool(banned)}
