# -*- coding: utf-8 -*-
"""محرك الفيديو الناطق: تقسيم + MuseTalk + ffmpeg + علامة مائية للمجانيين"""
from __future__ import annotations

import math
import shutil
import subprocess
import time
from pathlib import Path

from config import HF_TOKEN, MUSE_SPACE
from engines.watermark import text_filter


def _run(cmd: list[str], timeout: int = 1800) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1200:])


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return round(float(result.stdout.strip()), 3)


def _split(audio: Path, duration: float, folder: Path,
           chunk_seconds: int) -> list[tuple[Path, float]]:
    count = max(1, math.ceil(duration / chunk_seconds))
    length = duration / count
    pieces = []
    for i in range(count):
        start = i * length
        part_len = min(length, duration - start)
        out = folder / f"part_{i + 1:03d}.mp3"
        _run([
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(audio),
            "-t", f"{part_len:.3f}", "-c:a", "libmp3lame", "-b:a", "128k", str(out),
        ])
        pieces.append((out, part_len))
    return pieces


def _still(image: Path, audio: Path, out: Path, length: float) -> None:
    _run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
        "-t", f"{length:.3f}", "-vf", "scale=512:-2,fps=25",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(out),
    ])


def _concat(clips: list[Path], out: Path) -> None:
    listing = out.parent / "video_list.txt"
    listing.write_text(
        "".join(f"file '{str(p).replace(chr(39), chr(92) + chr(39))}'\n" for p in clips),
        encoding="utf-8",
    )
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", "-an", str(out),
    ])


def _watermark_filter() -> str:
    # خط أصغر قليلاً للفيديو العمودي 512×912
    return text_filter(font_size=20, margin=18)


def create(image: Path, audio: Path, out_dir: Path,
           watermark: bool = False, chunk_seconds: int = 12) -> Path:
    if not image.is_file() or not audio.is_file():
        raise ValueError("الصورة أو الصوت غير موجودين")
    out_dir.mkdir(parents=True, exist_ok=True)
    duration = _duration(audio)
    work = out_dir / f"video_work_{int(time.time())}"
    work.mkdir(parents=True, exist_ok=True)

    try:
        from gradio_client import Client, handle_file
    except ImportError as exc:
        raise RuntimeError("gradio_client غير مثبّت") from exc

    kwargs = {"verbose": False}
    if HF_TOKEN:
        kwargs["token"] = HF_TOKEN
    client = Client(MUSE_SPACE, **kwargs)

    clips: list[Path] = []
    pieces = _split(audio, duration, work, chunk_seconds)
    for i, (part, length) in enumerate(pieces, start=1):
        base = work / f"base_{i:03d}.mp4"
        target = work / f"talk_{i:03d}.mp4"
        _still(image, part, base, length)
        try:
            result = client.predict(
                handle_file(str(part)),
                handle_file(str(base)),
                25, "Medium",
                api_name="/generate_lipsync_video",
            )
            path = result[0] if isinstance(result, (list, tuple)) else result
            if isinstance(path, dict):
                path = path.get("video")
            shutil.copy2(path, target)
        except Exception:
            shutil.copy2(base, target)
        clips.append(target)

    silent = work / "silent.mp4"
    _concat(clips, silent)

    zoom = "min(1+on*0.00006,1.10)"
    video_chain = (
        "[0:v]fps=25,scale=512:912:force_original_aspect_ratio=increase,"
        "crop=512:912,"
        f"zoompan=z='{zoom}':d=1:x='iw/2-(iw/zoom/2)':"
        "y='ih/2-(ih/zoom/2)':s=512x912:fps=25,"
        "eq=saturation=0.75:contrast=1.10,noise=alls=5:allf=t+u,vignette=PI/4"
    )
    if watermark:
        video_chain += "," + _watermark_filter()
    video_chain += "[v]"
    audio_chain = (
        "[1:a]aecho=0.8:0.85:80|160:0.20|0.12[a]"
    )

    final = out_dir / f"video_{int(time.time())}.mp4"
    _run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(audio),
        "-filter_complex", video_chain + ";" + audio_chain,
        "-map", "[v]", "-map", "[a]", "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
        "-movflags", "+faststart", str(final),
    ], timeout=3600)
    return final
