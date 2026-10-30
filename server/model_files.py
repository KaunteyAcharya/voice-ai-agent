"""Safe one-time download of the Kokoro TTS model files.

Pipecat's own helper writes straight to the final path and only checks that the
file exists, so an interrupted first run (Ctrl+C, network drop) leaves a
truncated model behind forever. Here we download to a ``.part`` file, check the
size against the server's Content-Length, and only then move it into place.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import requests
from loguru import logger

MIN_SIZES = {
    # Sanity floor used when the size can't be checked online.
    "kokoro-v1.0.onnx": 300_000_000,
    "voices-v1.0.bin": 25_000_000,
}


def _remote_size(url: str) -> int | None:
    try:
        resp = requests.head(url, allow_redirects=True, timeout=20)
        length = resp.headers.get("Content-Length")
        return int(length) if resp.ok and length else None
    except requests.RequestException:
        return None


def _download(url: str, dest: Path, expected: int | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    logger.info(f"⬇️  Downloading {dest.name} (one time only)…")
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = expected or int(resp.headers.get("Content-Length") or 0)
        done, next_report = 0, 0.25
        with open(tmp, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total and done / total >= next_report:
                    logger.info(f"   {dest.name}: {done * 100 // total}%")
                    next_report += 0.25
    if total and tmp.stat().st_size != total:
        tmp.unlink(missing_ok=True)
        raise OSError(f"Incomplete download of {dest.name}")
    os.replace(tmp, dest)


def ensure_file(url: str, dest: Path) -> None:
    expected = _remote_size(url)
    if dest.exists():
        size = dest.stat().st_size
        if expected is not None and size == expected:
            return
        if expected is None and size >= MIN_SIZES.get(dest.name, 1):
            return
        logger.warning(f"{dest.name} looks incomplete ({size:,} bytes); downloading again")
    _download(url, dest, expected)


_lock = threading.Lock()
_ready = False


def ensure_kokoro_files() -> None:
    """Make sure both Kokoro files are complete. Safe to call from several threads."""
    global _ready
    if _ready:
        return
    from pipecat.services.kokoro import tts as kokoro_tts

    with _lock:
        if _ready:
            return
        ensure_file(kokoro_tts.KOKORO_MODEL_URL, kokoro_tts.KOKORO_CACHE_DIR / "kokoro-v1.0.onnx")
        ensure_file(kokoro_tts.KOKORO_VOICES_URL, kokoro_tts.KOKORO_CACHE_DIR / "voices-v1.0.bin")
        _ready = True
        logger.info("Kokoro TTS model ready")
