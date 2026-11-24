# -*- coding: utf-8 -*-
"""محرك المحادثة: Pollinations Text API (مجاني بدون مفتاح)"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from config import POLLINATIONS_TEXT_URL

SYSTEM = (
    "أنت مساعد ذكي عربي اسمه Hilal AI. أجب بالعربية الفصحى البسيطة، "
    "بأسلوب ودي وواضح ومنظّم. استخدم قوائم قصيرة عند الحاجة."
)

# مساعد الدراسة: مجاني 100%، معلّم ذكي يتكيّف مع لغة الطالب
STUDY_SYSTEM = (
    "أنت «مساعد الدراسة» في Hilal AI، معلّم ذكي وصبور وخبير في كل المواد الدراسية. "
    "مهمتك: شرح الدروس بأسلوب بسيط ومنظّم، تلخيص النصوص الطويلة إلى أهم الأفكار، "
    "حل المسائل خطوة بخطوة مع توضيح سبب كل خطوة، وصنع اختبارات تدريبية "
    "(اختيار من متعدد أو أسئلة قصيرة) مع الإجابات الصحيحة في النهاية. "
    "حدّد لغة الطالب من رسالته: إن كتب بالعربية فأجب بالعربية الفصحى الواضحة، "
    "وإن كتب بالإنجليزية فأجب بالإنجليزية. لا تخلط بين اللغتين. "
    "استخدم عناوين وقوائم قصيرة وأمثلة عملية، وشجّع الطالب على المحاولة."
)

CAPTION_SYSTEM = (
    "أنت كاتب إعلانات محترف في Hilal AI. اكتب نصاً إعلانياً عربياً قصيراً وجذاباً "
    "جاهزاً للنسخ (سطران إلى أربعة أسطر) يصف التصميم أو الصورة المطلوبة، "
    "مع عبارة تحثّ على اتخاذ إجراء. لا تضف شرحاً أو عناوين غير مطلوبة."
)


def _retry_after(header: str | None) -> int:
    if not header:
        return 46
    try:
        return max(1, int(header))
    except ValueError:
        return 46


def chat(prompt: str, system: str | None = None) -> str:
    if not prompt or not prompt.strip():
        raise ValueError("الرسالة فارغة")
    body = json.dumps(
        {
            "messages": [
                {"role": "system", "content": system or SYSTEM},
                {"role": "user", "content": prompt.strip()},
            ],
            "temperature": 0.8,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    for attempt in range(1, 4):
        req = urllib.request.Request(
            POLLINATIONS_TEXT_URL,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "text/plain",
                "User-Agent": "HilalAI/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=150) as response:
                text = response.read().decode("utf-8", errors="replace").strip()
            if not text:
                raise RuntimeError("استجابة فارغة من محرك النص")
            return text
        except urllib.error.HTTPError as exc:
            if exc.code == 402:
                wait = _retry_after(exc.headers.get("Retry-After"))
                time.sleep(wait)
                continue
            if attempt == 3:
                raise RuntimeError(f"خطأ من مزوّد النص: HTTP {exc.code}") from exc
            time.sleep(3)
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"تعذّر توليد النص: {exc}") from exc
            time.sleep(3)
    raise RuntimeError("تعذّر الحصول على رد من محرك النص")


def study(prompt: str) -> str:
    """مساعد الدراسة: نفس المحرك المجاني مع توجيه نظام تعليمي ثابت."""
    return chat(prompt, STUDY_SYSTEM)


def caption(prompt: str) -> str:
    """نص إعلاني جاهز للنسخ يرافق تصميمات الاستوديو."""
    return chat(prompt, CAPTION_SYSTEM)

