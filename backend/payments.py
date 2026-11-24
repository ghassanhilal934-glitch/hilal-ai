# -*- coding: utf-8 -*-
"""التحقق التلقائي من تحويلات USDT على BSC (BEP20) عبر RPC مجاني"""
from __future__ import annotations

import json
import re
import time
import urllib.request

from config import (
    BINANCE_BEP20_ADDRESS,
    BSC_RPC_URLS,
    MIN_CONFIRMATIONS,
    PACKAGES,
    PAYMENT_BLOCK_MINUTES,
    PAYMENT_MAX_FAILURES,
    TRANSFER_TOPIC,
    USDT_CONTRACT,
)
from db import get_conn, now

_TX_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_ZERO_TOPIC = "0x" + "0" * 64


class PaymentError(Exception):
    """خطأ مُترجم للمستخدم"""


def _rpc(method: str, params: list) -> object:
    payload = json.dumps(
        {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    ).encode()
    last_error: Exception | None = None
    for url in BSC_RPC_URLS:
        try:
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                data = json.load(response)
            if data.get("error"):
                raise RuntimeError(str(data["error"]))
            return data.get("result")
        except Exception as exc:  # جرّب RPC التالي
            last_error = exc
    raise PaymentError(f"تعذّر الاتصال بشبكة BSC: {str(last_error)[:160]}")


def _tx_value_to_receiver(receipt: dict) -> float:
    target = BINANCE_BEP20_ADDRESS.lower()
    contract = USDT_CONTRACT.lower()
    total = 0
    for log in receipt.get("logs", []):
        if str(log.get("address", "")).lower() != contract:
            continue
        topics = [str(t).lower() for t in log.get("topics", [])]
        if len(topics) < 3 or topics[0] != TRANSFER_TOPIC.lower():
            continue
        to_topic = topics[2]
        # آخر 40 خانة من topic تمثّل عنوان المستلم
        to_addr = "0x" + to_topic[-40:]
        if to_addr != target:
            continue
        data = log.get("data") or "0x0"
        try:
            total += int(data, 16) / 10**18
        except ValueError:
            continue
    return total


def verify_payment(tx_hash: str, package_id: str, user_id: int) -> dict:
    if not BINANCE_BEP20_ADDRESS:
        raise PaymentError("لم يتم ضبط عنوان المحفظة BINANCE_BEP20_ADDRESS في .env")
    tx_hash = (tx_hash or "").strip().lower()
    if not _TX_RE.match(tx_hash):
        raise PaymentError("معاملات TxID غير صالحة")
    package = PACKAGES.get(package_id)
    if not package:
        raise PaymentError("الباقة غير موجودة")

    conn = get_conn()
    if conn.execute("SELECT 1 FROM payments WHERE tx_hash=?", (tx_hash,)).fetchone():
        raise PaymentError("تم استخدام هذا TxID من قبل")

    receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
    if not receipt:
        raise PaymentError("لم يتم تأكيد المعاملة بعد، انتظر دقيقة ثم أعد المحاولة")
    if str(receipt.get("status", "0x0")).lower() not in ("0x1", "0x01", "1"):
        raise PaymentError("فشلت المعاملة على الشبكة")

    block_number = int(receipt.get("blockNumber", "0x0"), 16)
    latest = int(_rpc("eth_blockNumber", []), 16)
    if latest - block_number < MIN_CONFIRMATIONS:
        raise PaymentError("المعاملة تحتاج تأكيدات أكثر، حاول بعد قليل")

    received = _tx_value_to_receiver(receipt)
    expected = float(package["price_usdt"])
    if received + 1e-6 < expected:
        raise PaymentError(
            f"المبلغ المستلم {received:.4f} USDT أقل من {expected:.2f} USDT"
        )

    points = int(package["points"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """INSERT INTO payments(tx_hash,user_id,package_id,amount,points,status,created_at)
               VALUES(?,?,?,?,?,'confirmed',?)""",
            (tx_hash, user_id, package_id, received, points, now()),
        )
        conn.execute("UPDATE users SET points=points+? WHERE id=?", (points, user_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise PaymentError("هذا TxID مستخدم مسبقاً أو تعذّر حفظ الدفع")

    new_balance = conn.execute(
        "SELECT points FROM users WHERE id=?", (user_id,)
    ).fetchone()["points"]
    return {
        "ok": True,
        "package": package_id,
        "received_usdt": round(received, 4),
        "points_added": points,
        "balance": new_balance,
    }


# ---------------------------------------------------------------------------
# حماية من تخمين TxID: حظر مؤقت بعد عدة محاولات فاشلة
# ---------------------------------------------------------------------------

def check_attempt_block(attempt_key: str) -> None:
    conn = get_conn()
    row = conn.execute(
        "SELECT blocked_until FROM payment_attempts WHERE attempt_key=?",
        (attempt_key,),
    ).fetchone()
    if row and row["blocked_until"] and float(row["blocked_until"]) > time.time():
        remaining = int(float(row["blocked_until"]) - time.time()) + 1
        raise PaymentError(
            f"محاولات فاشلة كثيرة؛ حاول مرة أخرى بعد {max(1, remaining)} ثانية"
        )


def record_failed_attempt(attempt_key: str) -> None:
    conn = get_conn()
    current = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """SELECT failures, first_failure FROM payment_attempts
               WHERE attempt_key=?""",
            (attempt_key,),
        ).fetchone()
        if not row:
            failures = 1
            first = current
        else:
            failures = int(row["failures"]) + 1
            first = float(row["first_failure"])
            # نافذة متحركة: إذا مرّت ساعة من أول محاولة نبدأ من جديد
            if current - first > 3600:
                failures = 1
                first = current

        blocked_until = None
        if failures >= PAYMENT_MAX_FAILURES:
            blocked_until = current + PAYMENT_BLOCK_MINUTES * 60

        conn.execute(
            """INSERT INTO payment_attempts
                   (attempt_key, failures, first_failure, last_failure, blocked_until)
               VALUES(?,?,?,?,?)
               ON CONFLICT(attempt_key) DO UPDATE SET
                   failures=excluded.failures,
                   last_failure=excluded.last_failure,
                   blocked_until=excluded.blocked_until""",
            (attempt_key, failures, first, current, blocked_until),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def clear_failed_attempts(attempt_key: str) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM payment_attempts WHERE attempt_key=?", (attempt_key,))
    conn.commit()
