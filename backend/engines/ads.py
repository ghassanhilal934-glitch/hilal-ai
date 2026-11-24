# -*- coding: utf-8 -*-
"""الإعلانات مقابل النقاط: تذاكر JWT موقّعة + تحقق زمني + حد يومي."""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone

import jwt

from config import (
    ADMOB_REWARDED_ID,
    AD_DAILY_LIMIT,
    AD_MIN_SECONDS,
    AD_REWARD_POINTS,
    AD_TICKET_TTL_SECONDS,
    AD_TICKET_TYPE,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_ISSUER,
    SECRET_KEY,
    WEB_AD_DIRECT_LINK,
)
from db import get_conn, now


class AdError(Exception):
    """خطأ مُترجم للمستخدم"""


def _day_start() -> float:
    today = datetime.now(timezone.utc).date()
    return datetime(
        today.year, today.month, today.day, tzinfo=timezone.utc
    ).timestamp()


def remaining_ads(user_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        """SELECT COUNT(*) AS n FROM ad_tickets
           WHERE user_id=? AND claimed=1 AND claimed_at>=?""",
        (user_id, _day_start()),
    ).fetchone()
    return max(0, AD_DAILY_LIMIT - int(row["n"]))


def start_ticket(user_id: int) -> dict:
    conn = get_conn()
    conn.execute("BEGIN IMMEDIATE")
    try:
        used = conn.execute(
            """SELECT COUNT(*) AS n FROM ad_tickets
               WHERE user_id=? AND claimed=1 AND claimed_at>=?""",
            (user_id, _day_start()),
        ).fetchone()["n"]
        if int(used) >= AD_DAILY_LIMIT:
            raise AdError("استهلكت إعلانات اليوم؛ عد غداً")

        issued = int(time.time())
        jti = secrets.token_urlsafe(18)
        payload = {
            "sub": str(user_id),
            "jti": jti,
            "iat": issued,
            "exp": issued + min(AD_TICKET_TTL_SECONDS, 3600),
            "iss": JWT_ISSUER,
            "type": AD_TICKET_TYPE,
            "nonce": secrets.token_hex(8),
        }
        ticket = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
        conn.execute(
            """INSERT INTO ad_tickets(jti,user_id,created_at,expires_at,claimed,claimed_at)
               VALUES(?,?,?,?,0,NULL)""",
            (jti, user_id, float(issued), float(payload["exp"])),
        )
        conn.commit()
    except AdError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise AdError("تعذّر بدء الإعلان، حاول مجدداً") from exc

    return {
        "ticket": ticket,
        "watch_seconds": AD_MIN_SECONDS,
        "expires_in": AD_TICKET_TTL_SECONDS,
        "reward": AD_REWARD_POINTS,
        "ads_remaining": remaining_ads(user_id),
        "admob_rewarded_id": ADMOB_REWARDED_ID,
        "web_ad_link": WEB_AD_DIRECT_LINK,
    }


def _decode_ticket(ticket: str) -> dict:
    try:
        payload = jwt.decode(
            ticket,
            SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise AdError("تذكرة الإعلان غير صالحة") from exc
    if payload.get("type") != AD_TICKET_TYPE:
        raise AdError("تذكرة الإعلان غير صالحة")
    return payload


def claim_ticket(ticket: str, user_id: int) -> dict:
    payload = _decode_ticket(ticket)
    jti = payload["jti"]
    if int(payload["sub"]) != user_id:
        raise AdError("هذه التذكرة لمستخدم آخر")

    conn = get_conn()
    current = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT * FROM ad_tickets WHERE jti=?", (jti,)
        ).fetchone()
        if not row or int(row["user_id"]) != user_id:
            raise AdError("تذكرة الإعلان غير صالحة")
        if int(row["claimed"]):
            raise AdError("تم استخدام هذه التذكرة من قبل")
        if current > float(row["expires_at"]):
            raise AdError("انتهت صلاحية تذكرة الإعلان")
        elapsed = current - float(row["created_at"])
        if elapsed < AD_MIN_SECONDS:
            wait = int(AD_MIN_SECONDS - elapsed) + 1
            raise AdError(f"يجب مشاهدة الإعلان {wait} ثانية أخرى")

        used = conn.execute(
            """SELECT COUNT(*) AS n FROM ad_tickets
               WHERE user_id=? AND claimed=1 AND claimed_at>=?""",
            (user_id, _day_start()),
        ).fetchone()["n"]
        if int(used) >= AD_DAILY_LIMIT:
            raise AdError("استهلكت إعلانات اليوم؛ عد غداً")

        updated = conn.execute(
            """UPDATE ad_tickets SET claimed=1, claimed_at=?
               WHERE jti=? AND claimed=0""",
            (current, jti),
        )
        if updated.rowcount == 0:
            raise AdError("تم استخدام هذه التذكرة من قبل")

        conn.execute(
            "UPDATE users SET points=points+? WHERE id=?",
            (AD_REWARD_POINTS, user_id),
        )
        conn.execute(
            "INSERT INTO usage_logs(user_id,mode,points,created_at) VALUES(?,?,?,?)",
            (user_id, "ad_reward", AD_REWARD_POINTS, now()),
        )
        conn.commit()
    except AdError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise AdError("تعذّر صرف المكافأة، حاول مجدداً") from exc

    balance_row = conn.execute(
        "SELECT points FROM users WHERE id=?", (user_id,)
    ).fetchone()
    balance = float(balance_row["points"])
    return {
        "ok": True,
        "points_added": AD_REWARD_POINTS,
        "balance": int(balance) if balance.is_integer() else round(balance, 1),
        "ads_remaining": remaining_ads(user_id),
    }
