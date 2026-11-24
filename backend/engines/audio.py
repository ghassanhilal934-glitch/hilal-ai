# -*- coding: utf-8 -*-
"""محرك الصوتيات: edge-tts + مؤثرات ffmpeg"""
from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

try:
    import edge_tts
except ImportError:  # يُفحص عند التشغيل
    edge_tts = None

DEFAULT_VOICE = "ar-SA-HamedNeural"
DEFAULT_RATE = "-18%"
DEFAULT_PITCH = "-8Hz"


async def _tts(text: str, out: Path, voice: str, rate: str, pitch: str) -> None:
    for attempt in range(1, 4):
        try:
            tts = edge_tts.Communicate(
                text, voice=voice, rate=rate, pitch=pitch, volume="+0%"
            )
            await tts.save(str(out))
            if out.exists() and out.stat().st_size > 1024:
                return
            raise RuntimeError("ملف صوتي فارغ")
        except Exception:
            if attempt == 3:
                raise
            await asyncio.sleep(2 * attempt)


def speak(text: str, out_dir: Path, voice: str = DEFAULT_VOICE,
          rate: str = DEFAULT_RATE, pitch: str = DEFAULT_PITCH,
          effects: bool = True) -> Path:
    if edge_tts is None:
        raise RuntimeError("edge-tts غير مثبّت")
    if not text or not text.strip():
        raise ValueError("النص فارغ")
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"tts_raw_{int(time.time())}.mp3"
    final = out_dir / f"audio_{int(time.time())}.mp3"
    asyncio.run(_tts(text.strip(), raw, voice, rate, pitch))

    if effects:
        cmd = [
            "ffmpeg", "-y", "-i", str(raw),
            "-filter_complex",
            "[0:a]aecho=0.8:0.85:80|160:0.22|0.14,volume=1.05[a]",
            "-map", "[a]", "-c:a", "libmp3lame", "-b:a", "160k", str(final),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True)
        raw.unlink(missing_ok=True)
        return final

    raw.rename(final)
    return final
