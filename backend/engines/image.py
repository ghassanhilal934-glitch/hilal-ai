# -*- coding: utf-8 -*-
"""محرك الصور: Pollinations Image + Gradio (تغيير الملابس/الغرفة مع الحفاظ على الوجه)"""
from __future__ import annotations

import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from config import HF_TOKEN, POLLINATIONS_IMAGE_URL, VTON_SPACE


def generate(prompt: str, out_dir: Path, seed: int | None = None,
             watermark: bool = False) -> Path:
    if not prompt or not prompt.strip():
        raise ValueError("وصف الصورة فارغ")
    seed = seed if seed is not None else int(time.time()) % 100000
    url = (
        POLLINATIONS_IMAGE_URL
        + urllib.parse.quote(prompt.strip())
        + f"?width=768&height=768&seed={seed}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"image_{int(time.time())}_{seed}.jpg"

    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HilalAI/1.0"})
            with urllib.request.urlopen(req, timeout=120) as response:
                data = response.read()
            if len(data) < 1024:
                raise RuntimeError("صورة فارغة")
            target.write_bytes(data)
            if watermark:
                from engines.watermark import apply_to_image
                return apply_to_image(target, out_dir)
            return target
        except urllib.error.HTTPError as exc:
            if attempt == 3:
                raise RuntimeError(f"فشل توليد الصورة: HTTP {exc.code}") from exc
            time.sleep(5)
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"فشل توليد الصورة: {exc}") from exc
            time.sleep(5)
    raise RuntimeError("تعذّر توليد الصورة")


def tryon(person_image: Path, style_image: Path, description: str,
          out_dir: Path, watermark: bool = False) -> Path:
    """يستخدم مساحة Gradio مجانية لتبديل الملابس/الخلفية مع الحفاظ على الوجه."""
    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:
        raise RuntimeError("gradio_client غير مثبّت") from exc

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"tryon_{int(time.time())}.png"
    kwargs = {"verbose": False}
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN

    try:
        client = Client(VTON_SPACE, **kwargs)
        result = client.predict(
            handle_file(str(person_image)),
            handle_file(str(style_image)),
            api_name="/generate_image",
        )
        path = result.get("path") if isinstance(result, dict) else result
        shutil.copy2(path, target)
        if watermark:
            from engines.watermark import apply_to_image
            return apply_to_image(target, out_dir)
        return target
    except Exception:
        # خطة بديلة: إعادة رسم الوصف على Pollinations (لا تحافظ على الوجه بدقة)
        prompt = (
            f"same person, same facial identity, {description}, "
            "photorealistic, cinematic lighting, high detail"
        )
        return generate(prompt, out_dir, watermark=watermark)
