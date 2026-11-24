# -*- coding: utf-8 -*-
"""علامة مائية نصية أنيقة عبر ffmpeg للمستخدمين المجانيين فقط."""
from __future__ import annotations

import subprocess
from pathlib import Path

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/data/data/com.termux/files/usr/share/fonts/dejavu-sans/DejaVuSans.ttf",
    "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/system/fonts/Roboto-Regular.ttf",
]


def font_path() -> str | None:
    return next((p for p in _FONT_CANDIDATES if Path(p).exists()), None)


def text_filter(font_size: int = 26, margin: int = 22) -> str:
    """فلتر drawtext أنيق: نص أبيض شبه شفاف داخل صندوق داكن ناعم."""
    font = font_path()
    prefix = f"fontfile={font}:" if font else ""
    return (
        f"drawtext={prefix}text='Hilal AI':fontcolor=white@0.92:"
        f"fontsize={font_size}:x=w-tw-{margin}:y=h-th-{margin}:"
        "box=1:boxcolor=black@0.34:boxborderw=8"
    )


def apply_to_image(source: Path, out_dir: Path | None = None) -> Path:
    """يضيف العلامة إلى صورة ويحفظ نسخة باسم جديد (بدون تعديل الأصل)."""
    if not source.is_file():
        raise ValueError("الصورة غير موجودة")
    out_dir = out_dir or source.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"wm_{source.name}"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source), "-vf", text_filter(), "-frames:v", "1", str(target),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-800:])
    return target
