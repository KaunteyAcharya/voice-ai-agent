"""Settings read from .env, with friendly validation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class Config:
    stt_provider: str
    llm_provider: str
    tts_provider: str
    tts_fallback: str
    llm_fallback_chain: tuple[str, ...]

    groq_api_key: str
    google_api_key: str
    sarvam_api_key: str

    groq_stt_model: str
    sarvam_stt_model: str
    gemini_llm_model: str
    groq_llm_model: str
    sarvam_llm_model: str
    gemini_tts_model: str
    gemini_tts_voice: str
    kokoro_voice_en: str
    kokoro_voice_hi: str
    edge_voice_en: str
    edge_voice_hi: str
    sarvam_tts_voice: str

    speech_rate: float
    message_channel: str
    whatsapp_token: str
    whatsapp_phone_number_id: str
    whatsapp_api_version: str
    vad_stop_secs: float
    idle_timeout_secs: float

    host: str
    port: int
    log_level: str

    def problems(self) -> list[str]:
        """Return human-readable configuration errors (empty list = OK)."""
        issues = []
        valid = {
            "STT_PROVIDER": (self.stt_provider, {"groq", "sarvam"}),
            "LLM_PROVIDER": (self.llm_provider, {"gemini", "groq", "sarvam"}),
            "TTS_PROVIDER": (self.tts_provider, {"edge", "gemini", "kokoro", "sarvam"}),
            "TTS_FALLBACK": (self.tts_fallback, {"kokoro", "none"}),
        }
        for name, (value, allowed) in valid.items():
            if value not in allowed:
                issues.append(f"{name}={value!r} is not one of {sorted(allowed)}")

        keys = {"groq": self.groq_api_key, "gemini": self.google_api_key, "sarvam": self.sarvam_api_key}
        key_names = {"groq": "GROQ_API_KEY", "gemini": "GOOGLE_API_KEY", "sarvam": "SARVAM_API_KEY"}
        for stage, provider in (("STT", self.stt_provider), ("LLM", self.llm_provider), ("TTS", self.tts_provider)):
            if provider in keys and not keys[provider]:
                issues.append(f"{stage}_PROVIDER={provider} needs {key_names[provider]} in .env")
        return issues

    def describe(self) -> str:
        tts = self.tts_provider + (f" (fallback: {self.tts_fallback})" if self.uses_tts_fallback else "")
        backups = sum(1 for item in self.llm_fallback_chain if item.split(":", 1)[0] in self._keyed_providers())
        llm = self.llm_provider + (f" (+{backups} backups)" if backups else "")
        return f"STT={self.stt_provider}  LLM={llm}  TTS={tts}"

    def _keyed_providers(self) -> set[str]:
        keys = {"groq": self.groq_api_key, "gemini": self.google_api_key, "sarvam": self.sarvam_api_key}
        return {p for p, k in keys.items() if k}

    @property
    def uses_tts_fallback(self) -> bool:
        return self.tts_fallback == "kokoro" and self.tts_provider != "kokoro"


def load_config() -> Config:
    """Read .env fresh each time, so keys pasted while the server runs take effect."""
    load_dotenv(ROOT / ".env", override=True)
    return Config(
        stt_provider=_env("STT_PROVIDER", "groq").lower(),
        llm_provider=_env("LLM_PROVIDER", "groq").lower(),
        tts_provider=_env("TTS_PROVIDER", "edge").lower(),
        tts_fallback=_env("TTS_FALLBACK", "kokoro").lower(),
        llm_fallback_chain=tuple(
            item.strip()
            for item in _env(
                "LLM_FALLBACK_CHAIN", "groq:qwen/qwen3.8-27b,groq:openai/gpt-oss-20b,gemini:gemini-3.1-flash-lite"
            ).split(",")
            if item.strip()
        ),
        groq_api_key=_env("GROQ_API_KEY"),
        google_api_key=_env("GOOGLE_API_KEY"),
        sarvam_api_key=_env("SARVAM_API_KEY"),
        groq_stt_model=_env("GROQ_STT_MODEL", "whisper-large-v3"),
        sarvam_stt_model=_env("SARVAM_STT_MODEL", "saaras:v3"),
        gemini_llm_model=_env("GEMINI_LLM_MODEL", "gemini-3.1-flash-lite"),
        groq_llm_model=_env("GROQ_LLM_MODEL", "openai/gpt-oss-120b"),
        sarvam_llm_model=_env("SARVAM_LLM_MODEL", "sarvam-105b"),
        gemini_tts_model=_env("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview"),
        gemini_tts_voice=_env("GEMINI_TTS_VOICE", "Sulafat"),
        kokoro_voice_en=_env("KOKORO_VOICE_EN", "hf_alpha"),
        kokoro_voice_hi=_env("KOKORO_VOICE_HI", "hf_alpha"),
        edge_voice_en=_env("EDGE_VOICE_EN", "en-IN-NeerjaNeural"),
        edge_voice_hi=_env("EDGE_VOICE_HI", "hi-IN-SwaraNeural"),
        sarvam_tts_voice=_env("SARVAM_TTS_VOICE", "priya"),
        speech_rate=min(max(float(_env("SPEECH_RATE", "1.0")), 0.5), 2.0),
        message_channel=_env("MESSAGE_CHANNEL", "preview").lower(),
        whatsapp_token=_env("WHATSAPP_TOKEN"),
        whatsapp_phone_number_id=_env("WHATSAPP_PHONE_NUMBER_ID"),
        whatsapp_api_version=_env("WHATSAPP_API_VERSION", "v26.0"),
        vad_stop_secs=float(_env("VAD_STOP_SECS", "0.4")),
        idle_timeout_secs=float(_env("IDLE_TIMEOUT_SECS", "10")),
        host=_env("HOST", "localhost"),
        port=int(_env("PORT", "7860")),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
    )
