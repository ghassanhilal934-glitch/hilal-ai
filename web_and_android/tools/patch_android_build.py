#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""يصلح إعدادات البناء الأندرويدي قبل إنشاء APK.

يُستدعى في GitHub Actions مباشرة بعد `npx cap add android` (ويُعاد تشغيله بعد
`npx cap sync android` كإجراء وقائي). يقوم بثلاثة أشياء idempotent:

1. إضافة APPLICATION_ID الخاص بـ AdMob داخل وسم <application>.
2. ضبط android:usesCleartextTraffic="true" و android:networkSecurityConfig
   للسماح بطلبات HTTP أثناء التطوير.
3. ضبط android.allowMixedContent = true في capacitor.config.json.

يمكن تشغيله محلياً:  python web_and_android/tools/patch_android_build.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
XML_DIR = ROOT / "android" / "app" / "src" / "main" / "res" / "xml"
NETWORK_SECURITY = XML_DIR / "network_security_config.xml"
CAPACITOR_CONFIG = ROOT / "capacitor.config.json"

ADMOB_META_NAME = "com.google.android.gms.ads.APPLICATION_ID"
ADMOB_APP_ID = "ca-app-pub-3940256099942544~3347511713"

NETWORK_SECURITY_XML = """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <base-config cleartextTrafficPermitted="true" />
</network-security-config>
"""


def ensure_capacitor_config() -> None:
    """تفعيل allowMixedContent في إعدادات Capacitor (يُقرأ وقت التشغيل)."""
    if not CAPACITOR_CONFIG.is_file():
        print("ℹ️ capacitor.config.json غير موجود؛ تم التخطي")
        return
    config = json.loads(CAPACITOR_CONFIG.read_text(encoding="utf-8"))
    android_cfg = config.setdefault("android", {})
    if android_cfg.get("allowMixedContent") is True:
        print("✓ allowMixedContent مفعّل بالفعل في capacitor.config.json")
        return
    android_cfg["allowMixedContent"] = True
    CAPACITOR_CONFIG.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("✓ تم ضبط android.allowMixedContent = true")


def ensure_network_security_file() -> None:
    """ملف قاعدة الأمان الذي يسمح بالترافيك غير المشفر."""
    XML_DIR.mkdir(parents=True, exist_ok=True)
    if NETWORK_SECURITY.is_file() and "cleartextTrafficPermitted" in NETWORK_SECURITY.read_text(
        encoding="utf-8", errors="ignore"
    ):
        return
    NETWORK_SECURITY.write_text(NETWORK_SECURITY_XML, encoding="utf-8")
    print("✓ network_security_config.xml")


def set_application_attribute(opening_tag: str, name: str, value: str) -> str:
    """يضيف أو يحدّث خاصية داخل وسم <application ...> دون لمس باقي الملف."""
    pattern = rf'({re.escape(name)}\s*=\s*)(["\'])(.*?)\2'
    if re.search(pattern, opening_tag):
        return re.sub(pattern, rf'\g<1>"{value}"', opening_tag, count=1)
    return opening_tag[:-1].rstrip() + f' {name}="{value}">'


def patch_manifest() -> None:
    if not MANIFEST.is_file():
        print("ℹ️ لا يوجد AndroidManifest.xml بعد؛ شغّل npx cap add android أولاً. تم التخطي.")
        return

    text = MANIFEST.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"<application\b[^>]*>", text)
    if not match:
        raise SystemExit("✗ لم يتم العثور على وسم <application> في AndroidManifest.xml")

    # 1) خصائص وسم <application>
    opening = match.group(0)
    opening = set_application_attribute(opening, "android:usesCleartextTraffic", "true")
    opening = set_application_attribute(
        opening, "android:networkSecurityConfig", "@xml/network_security_config"
    )
    text = text[: match.start()] + opening + text[match.end() :]

    # 2) معرّف AdMob داخل <application> (بدونه يرمي Google Mobile Ads استثناءً عند الإقلاع)
    if ADMOB_META_NAME not in text:
        match = re.search(r"<application\b[^>]*>", text)
        meta_tag = (
            f'        <meta-data android:name="{ADMOB_META_NAME}" '
            f'android:value="{ADMOB_APP_ID}"/>'
        )
        text = text[: match.end()] + "\n" + meta_tag + text[match.end() :]

    MANIFEST.write_text(text, encoding="utf-8")
    print("✓ APPLICATION_ID و usesCleartextTraffic و networkSecurityConfig في AndroidManifest.xml")


def main() -> None:
    ensure_capacitor_config()
    ensure_network_security_file()
    patch_manifest()


if __name__ == "__main__":
    main()
