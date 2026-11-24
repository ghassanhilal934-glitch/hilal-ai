#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hilal AI — مولّد الهوية البصرية باستخدام مكتبة Pillow.

يولّد:
  assets/icon.png      512×512    أيقونة التطبيق (خلفية سوداء نقية #000000)
  assets/splash.png    1080×1920  شاشة الترحيب + عبارة الراعي الرسمي
  web/logo.png         128×128    شعار الواجهة العلوية
  chrome_extension/icon*.png      أيقونات إضافة كروم 16/32/48/128

التصميم: حرف "H" كبير ذهبي لامع، وبجانبه الأيمن كلمة "Ai" متناسقة بالأبيض
مع لمسة ذهبية على نقطة الحرف i. لا توجد أي عناصر أخرى على الخلفية السوداء.

التثبيت:  python -m pip install Pillow
التشغيل:  python web_and_android/tools/make_assets.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    HAS_PIL = True
except ImportError:  # بيئة محدودة الشبكة: نستخدم ffmpeg كبديل، وPillow هو المسار الأساسي في CI
    HAS_PIL = False

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
WEB = ROOT / "web"
EXT = ROOT / "chrome_extension"
for d in (ASSETS, WEB, EXT):
    d.mkdir(parents=True, exist_ok=True)

BLACK = (0, 0, 0, 255)
SPONSOR = "Official Sponsor: Ghassan Hilal"

# تدرّج ذهبي لامع من الأعلى إلى الأسفل
GOLD_TOP = (255, 246, 206)
GOLD_MID = (255, 205, 96)
GOLD_LOW = (205, 140, 44)
GOLD_END = (247, 200, 108)
WHITE_TOP = (255, 255, 255)
WHITE_LOW = (222, 226, 238)

# أبعاد آمنة للذاكرة على أندرويد (1080×1920 ≈ 8MB عند فك الترميز بدل ~30MB)
ICON_SIZE = 512
SPLASH_SIZE = (1080, 1920)

GOLD_STOPS = [
    (0.0, GOLD_TOP), (0.30, GOLD_MID), (0.55, GOLD_LOW),
    (0.75, GOLD_MID), (1.0, GOLD_END),
]
WHITE_STOPS = [(0.0, WHITE_TOP), (0.62, WHITE_LOW), (1.0, GOLD_MID)]


def find_font(*names: str, bold: bool = True) -> str:
    """يبحث عن خط مناسب في مسارات النظام ويعيد أول ملف موجود."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
        if bold else "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/system/fonts/Roboto-Bold.ttf" if bold else "/system/fonts/Roboto-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/system/fonts/Roboto-Regular.ttf",
    ]
    candidates.extend(names)
    for path in candidates:
        if Path(path).is_file():
            return path
    raise RuntimeError("لم يتم العثور على خط TTF مناسب")


def gradient(size: tuple[int, int], stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    """صورة تدرّج رأسي تُستخدم كـ fill لقناع النص."""
    w, h = size
    strip = Image.new("RGB", (1, max(h, 1)))
    px = strip.load()
    for y in range(max(h, 1)):
        t = y / max(h - 1, 1)
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / max(p1 - p0, 1e-6)
                px[0, y] = tuple(int(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                break
        else:
            px[0, y] = stops[-1][1]
    return strip.resize((w, max(h, 1)))


def draw_text_shiny(
    base: Image.Image,
    text: str,
    font_path: str,
    font_size: int,
    center_x: float,
    center_y: float,
    colors: list[tuple[float, tuple[int, int, int]]],
    letter_spacing: int = 0,
) -> tuple[float, float, float, float]:
    """يرسم نصاً بتدرّج لامع داخل الحروف فقط، ويعيد إحداثيات الصندوق."""
    font = ImageFont.truetype(font_path, font_size)
    if letter_spacing and hasattr(ImageDraw.Draw(base), "textlength"):
        # رسم حرف بحرف للتحكم في المسافات
        probe = ImageDraw.Draw(base)
        widths = []
        for ch in text:
            box = probe.textbbox((0, 0), ch, font=font)
            widths.append(box[2] - box[0])
        total = sum(widths) + letter_spacing * (len(text) - 1)
        x = center_x - total / 2
        boxes = []
        for ch, cw in zip(text, widths):
            boxes.append((ch, x))
            x += cw + letter_spacing
    else:
        probe = ImageDraw.Draw(base)
        box = probe.textbbox((0, 0), text, font=font)
        total = box[2] - box[0]
        boxes = [(text, center_x - total / 2)]

    # حساب أعلى/أسفل النص لضبط التوسيط الرأسي بدقة
    top = min(ImageDraw.Draw(base).textbbox((0, 0), ch, font=font)[1] for ch, _ in boxes)
    bottom = max(ImageDraw.Draw(base).textbbox((0, 0), ch, font=font)[3] for ch, _ in boxes)
    y = center_y - (top + bottom) / 2

    mask = Image.new("L", base.size, 0)
    md = ImageDraw.Draw(mask)
    for ch, cx in boxes:
        md.text((cx, y), ch, font=font, fill=255)

    # تدرّج اللمعان داخل الحروف: خط فاتح رفيع أعلى الحرف يمنح إحساس الذهب المصقول
    fill = gradient(base.size, colors).convert("RGBA")
    shine = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shine)
    for ch, cx in boxes:
        sd.text((cx, y), ch, font=font, fill=(255, 255, 255, 55))
    shine = shine.filter(ImageFilter.GaussianBlur(2))
    fill = Image.alpha_composite(fill, shine)

    base.paste(fill, (0, 0), mask)
    return (center_x - total / 2, y + top, center_x + total / 2, y + bottom)


def render(size: int | tuple[int, int], sponsor: bool = False) -> Image.Image:
    """يرسم شعار H Ai على خلفية سوداء نقية، مع الراعي في شاشة الترحيب.

    يقبل size إما رقماً مربعاً (الأيقونة) أو زوجاً (عرض، ارتفاع) للـ splash.
    """
    width, height = (size, size) if isinstance(size, int) else size
    side = min(width, height)
    img = Image.new("RGBA", (width, height), BLACK)

    h_font = find_font(bold=True)
    ai_font = find_font(bold=True)

    h_size = int(side * 0.60)
    ai_size = int(side * 0.315)
    gap = int(side * 0.035)

    probe = ImageDraw.Draw(img)
    hb = probe.textbbox((0, 0), "H", font=ImageFont.truetype(h_font, h_size))
    ab = probe.textbbox((0, 0), "Ai", font=ImageFont.truetype(ai_font, ai_size))
    hw = hb[2] - hb[0]
    aw = ab[2] - ab[0]
    total = hw + gap + aw

    start_x = (width - total) / 2 - hb[0]
    center_y = height / 2

    # H ذهبي لامع large
    draw_text_shiny(img, "H", h_font, h_size, start_x + hw / 2, center_y, GOLD_STOPS)

    # Ai أبيض متناسق مع وميض ذهبي خفيف
    ai_x = start_x + hw + gap - ab[0]
    draw_text_shiny(
        img, "Ai", ai_font, ai_size,
        ai_x + aw / 2, center_y + h_size * 0.02, WHITE_STOPS,
    )

    if sponsor:
        draw_text_shiny(
            img, SPONSOR, find_font(bold=False), int(side * 0.028),
            width / 2, height * 0.90,
            [(0.0, GOLD_TOP), (0.55, GOLD_MID), (1.0, GOLD_END)],
        )

    return img.convert("RGB")


def _font_or_die() -> str:
    for p in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/system/fonts/Roboto-Bold.ttf",
    ):
        if Path(p).is_file():
            return p
    raise RuntimeError("لم يتم العثور على خط عريض (TTF)")


def _ffmpeg_wordmark(size: int | tuple[int, int], path: Path, sponsor: bool = False) -> None:
    """مسار بديل حين لا تتوفر Pillow: رسم النص بخط حقيقي عبر ffmpeg."""
    width, height = (size, size) if isinstance(size, int) else size
    side = min(width, height)
    font = _font_or_die()
    h_size = int(side * 0.585)
    ai_size = int(side * 0.31)
    off = max(2, int(side * 0.006))
    # معاينة بصرية: هذه القيمة توسّط مجموعة "H Ai" أفقياً
    shift = int(side * 0.06)
    h_v = int(side * 0.02)
    ai_v = int(side * 0.045)
    filters = [
        f"drawtext=fontfile={font}:text='H':fontsize={h_size}:"
        f"fontcolor=0xFFD98A:shadowcolor=0x7A521C:shadowx={off}:shadowy={off}:"
        f"x=w/2-tw-{off}+{shift}:y=(h-th)/2-{h_v}",
        f"drawtext=fontfile={font}:text='Ai':fontsize={ai_size}:"
        f"fontcolor=0xF2F4FA:shadowcolor=0x000000:shadowx={off}:shadowy={off}:"
        f"x=w/2+{off}+{shift}:y=(h-th)/2+{ai_v}",
    ]
    if sponsor:
        s_size = max(14, int(side * 0.026))
        filters.append(
            f"drawtext=fontfile={font}:text='Official Sponsor\\: Ghassan Hilal':"
            f"fontsize={s_size}:fontcolor=0xFFD98A:"
            f"x=(w-tw)/2:y=h-th-{int(side * 0.06)}"
        )
    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}",
        "-vf", vf, "-frames:v", "1", str(path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)


def _save_all_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("Pillow غير مثبت و ffmpeg غير متاح. ثبّت Pillow: python -m pip install Pillow")
    _ffmpeg_wordmark(ICON_SIZE, ASSETS / "icon.png")
    _ffmpeg_wordmark(SPLASH_SIZE, ASSETS / "splash.png", sponsor=True)
    print(f"✓ {ASSETS / 'icon.png'}  ({ICON_SIZE}×{ICON_SIZE})")
    print(f"✓ {ASSETS / 'splash.png'}  ({SPLASH_SIZE[0]}×{SPLASH_SIZE[1]})")
    for size in (16, 32, 48, 128):
        subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(ASSETS / "icon.png"), "-vf", f"scale={size}:{size}",
            "-frames:v", "1", str(EXT / f"icon{size}.png"),
        ], check=True, capture_output=True, text=True, timeout=60)
    shutil.copy2(EXT / "icon128.png", EXT / "icon.png")
    shutil.copy2(EXT / "icon128.png", WEB / "logo.png")
    print("✓ web/logo.png و chrome_extension/icon*.png")


def save_all() -> None:
    if not HAS_PIL:
        _save_all_ffmpeg()
        return

    icon = render(ICON_SIZE)
    splash = render(SPLASH_SIZE, sponsor=True)
    # compress_level=9 يبقي الحجم صغيراً دون تغيير الأبعاد أو جودة العرض
    icon.save(ASSETS / "icon.png", "PNG", optimize=True, compress_level=9)
    splash.save(ASSETS / "splash.png", "PNG", optimize=True, compress_level=9)
    print(f"✓ {ASSETS / 'icon.png'}  ({ICON_SIZE}×{ICON_SIZE})")

    # شعار الواجهة العلوية
    web_logo = icon.resize((128, 128), Image.LANCZOS)
    web_logo.save(WEB / "logo.png", "PNG", optimize=True)
    print(f"✓ {WEB / 'logo.png'}  (128×128)")

    # أيقونات إضافة كروم
    for s in (16, 32, 48, 128):
        small = icon.resize((s, s), Image.LANCZOS)
        small.save(EXT / f"icon{s}.png", "PNG", optimize=True)
    icon.resize((128, 128), Image.LANCZOS).save(EXT / "icon.png", "PNG", optimize=True)
    print("✓ chrome_extension/icon{16,32,48,128}.png")

    # شاشة الترحيب جاهزة أيضاً للنسخ إلى موارد أندرويد عبر install_android_assets.py
    print(f"✓ {ASSETS / 'splash.png'}  ({SPLASH_SIZE[0]}×{SPLASH_SIZE[1]})")


if __name__ == "__main__":
    try:
        save_all()
    except Exception as exc:
        print(f"✗ فشل توليد الأصول: {exc}", file=sys.stderr)
        raise
