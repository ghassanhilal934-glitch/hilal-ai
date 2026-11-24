#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ثبّت أيقونة H Ai وشاشة الترحيب داخل مشروع Capacitor الأندرويد.

يُستدعى في GitHub Actions بعد `npx cap add android`، ويمكن تشغيله محلياً:
  python web_and_android/tools/install_android_assets.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "android"
ICON = ROOT / "assets" / "icon.png"
SPLASH = ROOT / "assets" / "splash.png"

DENSITIES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}


def main() -> None:
    if not ANDROID.is_dir():
        print("ℹ️ لا يوجد مجلد android بعد؛ شغّل npx cap add android أولاً. تم التخطي.")
        return
    if not ICON.is_file() or not SPLASH.is_file():
        raise SystemExit("شغّل make_assets.py أولاً لتوليد icon.png و splash.png")
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("مطلوب Pillow: python -m pip install Pillow") from exc

    res = ANDROID / "app" / "src" / "main" / "res"
    icon = Image.open(ICON).convert("RGBA")

    for folder, size in DENSITIES.items():
        target_dir = res / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        scaled = icon.resize((size, size), Image.LANCZOS)
        for name in ("ic_launcher.png", "ic_launcher_round.png"):
            scaled.save(target_dir / name, "PNG", optimize=True)
        print(f"✓ {folder}/ic_launcher.png ({size}px)")

    # نلغي أيقونة adaptive القديمة كي تُستخدم صورة H Ai مباشرة على كل الإصدارات
    adaptive = res / "mipmap-anydpi-v26"
    if adaptive.is_dir():
        for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
            f = adaptive / name
            if f.exists():
                f.unlink()
                print(f"✓ تمت إزالة {name} القديمة")

    # شاشة الترحيب: nodpi تمنع التشويه وتحافظ على التوسيط
    for folder in ("drawable", "drawable-nodpi"):
        d = res / folder
        d.mkdir(parents=True, exist_ok=True)
        Image.open(SPLASH).convert("RGB").save(d / "splash.png", "PNG", optimize=True)
        print(f"✓ {folder}/splash.png")

    # تأكد أنManifest يشير إلى أيقونتنا
    manifest = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8", errors="ignore")
        if "@mipmap/ic_launcher" not in text:
            text = text.replace(
                "<application ", '<application android:icon="@mipmap/ic_launcher" ', 1
            )
            manifest.write_text(text, encoding="utf-8")
            print("✓ تم ضبط android:icon في AndroidManifest.xml")


if __name__ == "__main__":
    main()
