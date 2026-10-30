"""Text-to-speech for Aditi.

* ``EdgeTTSService``: Microsoft Edge's free neural voices via ``edge-tts`` (no key,
  natural Hindi and Indian-English voices, about 1 s to first audio).
* ``GeminiTTSWithKokoroFallback``: Gemini TTS (free tier is only 10 requests/day).
* Both fall back to local Kokoro on the CPU when the cloud voice fails, re-speaking
  the failed sentence so nothing is skipped.
* Both cache audio: fixed lines (greeting, fillers, apology) are generated once at
  startup and play instantly; any other sentence is cached after first use.

``edge-tts`` talks to an unofficial Microsoft endpoint. It is free and widely used
but could change or stop working without notice, which is why Kokoro is kept as
the fallback.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path

import numpy as np
from loguru import logger
from pipecat.audio.utils import create_stream_resampler
from pipecat.frames.frames import ErrorFrame, Frame, TTSAudioRawFrame
from pipecat.services.google.tts import GeminiTTSService
from pipecat.services.tts_service import TTSService

from model_files import ensure_kokoro_files

CACHE_SAMPLE_RATE = 24_000
CHUNK_BYTES = 9_600  # 200 ms of 24 kHz 16-bit mono

# (voice id, text) -> 24 kHz 16-bit mono PCM. Shared by every call in the process.
_audio_cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()
_MAX_CACHED = 300


def _cache_get(voice: str, text: str) -> bytes | None:
    key = (voice, text.strip())
    audio = _audio_cache.get(key)
    if audio is not None:
        _audio_cache.move_to_end(key)
    return audio


def _cache_put(voice: str, text: str, audio: bytes) -> None:
    if not audio:
        return
    _audio_cache[(voice, text.strip())] = audio
    while len(_audio_cache) > _MAX_CACHED:
        _audio_cache.popitem(last=False)


def clamp_rate(rate: object) -> float:
    """Speaking speed multiplier (1.0 = normal, 1.25 = 25% faster), kept to 0.5-2.0."""
    try:
        return min(max(float(rate), 0.5), 2.0)
    except (TypeError, ValueError):
        return 1.0


def edge_rate(rate: float) -> str:
    """1.25 -> "+25%", the format edge-tts expects."""
    return f"{round((clamp_rate(rate) - 1) * 100):+d}%"


def edge_cache_voice(voice: str, rate: float) -> str:
    return f"{voice}@{clamp_rate(rate):.2f}"


def lang_key(language: object) -> str:
    return "hi" if str(language or "en").lower().startswith("hi") else "en"


# ---------------------------------------------------------------------------
# Kokoro (local CPU fallback)
# ---------------------------------------------------------------------------

_kokoro_model = None
_kokoro_lock = asyncio.Lock()


async def _load_kokoro():
    """Load the Kokoro ONNX model once per process (about 2 s on a laptop CPU)."""
    global _kokoro_model
    async with _kokoro_lock:
        if _kokoro_model is None:
            from kokoro_onnx import Kokoro
            from pipecat.services.kokoro import tts as kokoro_tts

            await asyncio.to_thread(ensure_kokoro_files)
            cache: Path = kokoro_tts.KOKORO_CACHE_DIR
            _kokoro_model = await asyncio.to_thread(
                Kokoro, str(cache / "kokoro-v1.0.onnx"), str(cache / "voices-v1.0.bin")
            )
    return _kokoro_model


async def preload_kokoro() -> None:
    try:
        await _load_kokoro()
    except Exception as e:
        logger.warning(f"Couldn't preload Kokoro fallback voice: {e}")


async def kokoro_pcm_chunks(
    text: str, lang: str, voice: str, speed: float = 1.0
) -> AsyncGenerator[tuple[bytes, int], None]:
    kokoro = await _load_kokoro()
    lang_code = "hi" if lang == "hi" else "en-us"
    async for samples, sample_rate in kokoro.create_stream(text, voice=voice, lang=lang_code, speed=clamp_rate(speed)):
        yield (np.clip(samples, -1, 1) * 32767).astype(np.int16).tobytes(), sample_rate


# ---------------------------------------------------------------------------
# Edge TTS
# ---------------------------------------------------------------------------


async def edge_pcm_chunks(text: str, voice: str, rate: str = "+0%") -> AsyncGenerator[bytes, None]:
    """Stream 24 kHz 16-bit mono PCM from edge-tts (which sends MP3)."""
    import av
    import edge_tts

    codec = av.CodecContext.create("mp3", "r")
    async for chunk in edge_tts.Communicate(text, voice, rate=rate).stream():
        if chunk["type"] != "audio" or not chunk.get("data"):
            continue
        for packet in codec.parse(chunk["data"]):
            for frame in codec.decode(packet):
                yield frame.to_ndarray().astype(np.int16).tobytes()
    for frame in codec.decode(None):
        yield frame.to_ndarray().astype(np.int16).tobytes()


async def edge_synthesize(text: str, voice: str, rate: float = 1.0) -> bytes:
    return b"".join([pcm async for pcm in edge_pcm_chunks(text, voice, edge_rate(rate))])


# ---------------------------------------------------------------------------
# Shared behaviour: cache + Kokoro fallback
# ---------------------------------------------------------------------------


class CachedFallbackTTSMixin:
    """Adds an audio cache and a sentence-preserving Kokoro fallback to a TTS service.

    Subclasses implement ``_primary_chunks(text, lang)`` yielding 24 kHz PCM, and
    ``_primary_voice(lang)`` naming the voice (used as the cache key).
    """

    def _setup_fallback(
        self,
        kokoro_voices: dict[str, str],
        use_kokoro_fallback: bool,
        on_fallback: Callable[[str], Awaitable[None]] | None,
        speech_rate: float = 1.0,
    ) -> None:
        self._speech_rate = clamp_rate(speech_rate)
        self._kokoro_voices = kokoro_voices
        self._use_kokoro_fallback = use_kokoro_fallback
        self._on_fallback = on_fallback
        self._using_kokoro = False
        # Separate stream resamplers: each keeps state for one stream of audio.
        self._out_resampler = create_stream_resampler()
        self._kokoro_resampler = create_stream_resampler()
        self._gemini_resampler = create_stream_resampler()

    def current_lang(self) -> str:
        return lang_key(getattr(self._settings, "language", "en"))

    async def _frames_from_pcm(self, pcm: bytes, rate: int, context_id: str):
        if rate != self.sample_rate:
            pcm = await self._out_resampler.resample(pcm, rate, self.sample_rate)
        for i in range(0, len(pcm), CHUNK_BYTES):
            yield TTSAudioRawFrame(audio=pcm[i : i + CHUNK_BYTES], sample_rate=self.sample_rate, num_channels=1, context_id=context_id)

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        lang = self.current_lang()
        voice = self._kokoro_voices[lang] if self._using_kokoro else self._primary_voice(lang)
        cache_voice = f"kokoro:{voice}@{self._speech_rate:.2f}" if self._using_kokoro else voice

        cached = _cache_get(cache_voice, text)
        if cached is not None:
            await self.stop_ttfb_metrics()
            async for frame in self._frames_from_pcm(cached, CACHE_SAMPLE_RATE, context_id):
                yield frame
            return

        if not self._using_kokoro:
            collected: list[bytes] = []
            error: str | None = None
            try:
                async for item in self._primary_chunks(text, lang):
                    if isinstance(item, ErrorFrame):
                        error = str(item.error)
                        break
                    await self.stop_ttfb_metrics()
                    collected.append(item)
                    async for frame in self._frames_from_pcm(item, CACHE_SAMPLE_RATE, context_id):
                        yield frame
            except Exception as e:  # network errors, service changes, bad responses
                error = f"{type(e).__name__}: {e}"
            if error is None and collected:
                _cache_put(voice, text, b"".join(collected))
                return
            if error is None:
                error = "no audio returned"
            if not self._use_kokoro_fallback:
                yield ErrorFrame(error=f"TTS error: {error}")
                return
            self._using_kokoro = True
            logger.warning(f"🔊 {self.name} failed ({error[:160]}); using local Kokoro for the rest of this call")
            if self._on_fallback:
                await self._on_fallback(error)
            if collected:
                return  # part of the sentence was already spoken; don't repeat it

        try:
            kvoice = self._kokoro_voices[lang]
            collected = []
            async for pcm, rate in kokoro_pcm_chunks(text, lang, kvoice, self._speech_rate):
                await self.stop_ttfb_metrics()
                if rate != CACHE_SAMPLE_RATE:
                    pcm = await self._kokoro_resampler.resample(pcm, rate, CACHE_SAMPLE_RATE)
                collected.append(pcm)
                async for frame in self._frames_from_pcm(pcm, CACHE_SAMPLE_RATE, context_id):
                    yield frame
            _cache_put(f"kokoro:{kvoice}@{self._speech_rate:.2f}", text, b"".join(collected))
        except Exception as e:
            logger.exception("Kokoro fallback failed")
            yield ErrorFrame(error=f"Kokoro fallback TTS error: {e}")


class EdgeTTSService(CachedFallbackTTSMixin, TTSService):
    def __init__(
        self,
        *,
        voices: dict[str, str],
        kokoro_voices: dict[str, str],
        use_kokoro_fallback: bool = True,
        on_fallback: Callable[[str], Awaitable[None]] | None = None,
        language=None,
        speech_rate: float = 1.0,
        **kwargs,
    ):
        from pipecat.services.settings import TTSSettings

        super().__init__(
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(model="edge-tts", voice=voices[lang_key(language)], language=language),
            **kwargs,
        )
        self._voices = voices
        self._setup_fallback(kokoro_voices, use_kokoro_fallback, on_fallback, speech_rate)

    def can_generate_metrics(self) -> bool:
        return True

    def language_to_service_language(self, language):
        return str(language)

    def _primary_voice(self, lang: str) -> str:
        return edge_cache_voice(self._voices[lang], self._speech_rate)

    async def _primary_chunks(self, text: str, lang: str):
        async for pcm in edge_pcm_chunks(text, self._voices[lang], edge_rate(self._speech_rate)):
            yield pcm


class GeminiTTSWithKokoroFallback(CachedFallbackTTSMixin, GeminiTTSService):
    def __init__(
        self,
        *,
        kokoro_voices: dict[str, str],
        use_kokoro_fallback: bool = True,
        on_fallback: Callable[[str], Awaitable[None]] | None = None,
        speech_rate: float = 1.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._setup_fallback(kokoro_voices, use_kokoro_fallback, on_fallback, speech_rate)

    def _primary_voice(self, lang: str) -> str:
        return f"gemini:{self._settings.voice}:{lang}"

    async def _primary_chunks(self, text: str, lang: str):
        async for frame in GeminiTTSService.run_tts(self, text, "gemini-primary"):
            if isinstance(frame, ErrorFrame):
                yield frame
                return
            if isinstance(frame, TTSAudioRawFrame):
                pcm = frame.audio
                if frame.sample_rate != CACHE_SAMPLE_RATE:
                    pcm = await self._gemini_resampler.resample(pcm, frame.sample_rate, CACHE_SAMPLE_RATE)
                yield pcm


def _sentences(text: str) -> list[str]:
    """Pipecat may hand a multi-sentence line to TTS one sentence at a time."""
    import re

    parts = [p.strip() for p in re.split(r"(?<=[.?!।])\s+", text) if p.strip()]
    return parts if len(parts) > 1 else []


async def prewarm_phrases(voices: dict[str, str], phrases: dict[str, list[str]], rate: float = 1.0) -> None:
    """Generate the fixed lines once at startup so they play instantly."""
    done = 0
    for lang, texts in phrases.items():
        key = edge_cache_voice(voices[lang], rate)
        for text in texts:
            for piece in [text, *_sentences(text)]:
                if _cache_get(key, piece) is not None:
                    continue
                try:
                    _cache_put(key, piece, await edge_synthesize(piece, voices[lang], rate))
                    done += 1
                except Exception as e:
                    logger.warning(f"Couldn't pre-generate voice lines with Edge TTS: {e}")
                    return
    logger.info(f"🔊 Fixed voice lines ready ({done} clips cached)")
