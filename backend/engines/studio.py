# -*- coding: utf-8 -*-
"""استوديو التصميم وتعديل الصور — فلاتر ffmpeg مجانية بدون مفاتيح API."""
from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path

from engines.watermark import apply_to_image


def _filter_for(instruction: str) -> str:
    """يختار سلسلة فلاتر مناسبة من أمر المستخدم (عربي أو إنجليزي)."""
    text = (instruction or "").lower()
    sharpen = "unsharp=5:5:0.7:5:5:0.0"

    if any(k in text for k in ("أبيض", "ابيض", "اسود", "أسود", "black and white", "b&w", "mono")):
        return f"hue=s=0,eq=contrast=1.18:brightness=0.02,{sharpen}"
    if any(k in text for k in ("سينمائ", "cinematic", "فيلم", "film")):
        return (
            "eq=contrast=1.20:saturation=0.88:brightness=0.01,"
            "colorbalance=rs=0.03:bs=-0.05,vignette=0.35," + sharpen
        )
    if any(k in text for k in ("تجميل", "بشرة", "تنعيم", "beauty", "smooth", "portrait")):
        return "eq=brightness=0.05:contrast=1.06:saturation=1.06,gblur=1," + sharpen
    if any(k in text for k in ("قديم", "فينتاج", "vintage", "sepia")):
        return (
            "colorchannelmixer=rr=0.93:rg=0.28:rb=0.05:"
            "gr=0.12:gg=0.82:gb=0.05:br=0.05:bg=0.10:bb=0.70,"
            "eq=contrast=1.08,vignette=0.30," + sharpen
        )
    if any(k in text for k in ("إضاءة", "اضاءة", "مشرق", "ساطع", "bright", "light", "تحسين")):
        return f"eq=brightness=0.09:contrast=1.14:saturation=1.12,{sharpen}"
    # الخيار الافتراضي: تحسين تلقائي متوازن
    return f"eq=brightness=0.04:contrast=1.12:saturation=1.10,vignette=0.18,{sharpen}"


def edit_image(source: Path, out_dir: Path, instruction: str = "",
               watermark: bool = False) -> Path:
    """تحسين/تجميل/فلترة صورة مرفوعة وإخراج نسخة جديدة بصيغة JPG."""
    if not source.is_file():
        raise ValueError("الصورة غير موجودة")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg غير متاح لتعديل الصور")
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"studio_{int(time.time())}_{uuid.uuid4().hex[:6]}.jpg"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-vf", _filter_for(instruction),
        "-frames:v", "1", "-q:v", "2",
        str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0 or not target.is_file():
        raise RuntimeError(result.stderr[-800:] or "فشل تعديل الصورة")
    if watermark:
        return apply_to_image(target, out_dir)
    return target


def design_prompt(description: str, kind: str = "auto") -> str:
    """يحوّل طلب المستخدم إلى وصف بصري مناسب لتوليد التصميم عبر Pollinations."""
    desc = (description or "").strip()
    text = desc.lower()
    if kind == "brand" or any(k in text for k in ("شعار", "براند", "logo", "brand", "هوية")):
        prefix = "minimal modern logo design for a brand, centred emblem, clean vector style, "
    elif kind == "ad" or any(k in text for k in ("إعلان", "اعلان", "منتج", "product", "ad ")):
        prefix = "high-end product advertisement poster, professional studio lighting, "
    elif kind == "social" or any(k in text for k in ("منشور", "سوشيال", "social", "post")):
        prefix = "engaging social media post design, balanced layout, modern typography space, "
    else:
        prefix = "professional graphic design, harmonious composition, high detail, "
    return (
        prefix
        + desc
        + ". leave clean empty space for Arabic copy, elegant colours, 1:1 poster, no watermark"
    )
