"""The LLM chain: a primary model plus backups, tried in order on failure.

Free tiers fail in ordinary ways: Gemini answers 503 "high demand" or 429
quota, Groq answers 429 when its tokens-per-minute pool is spent, and any of
them can hang. ``LLMChainFailover`` moves to the next model on any such error;
``bot.py`` then re-runs the same turn on the new model, so the caller never
hears "please repeat that" for a problem on our side.
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from pipecat.frames.frames import ErrorFrame, Frame, PipelineFlushFrame
from pipecat.pipeline.llm_switcher import LLMSwitcher
from pipecat.pipeline.service_switcher import ServiceSwitcherStrategyManual
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.utils.errors import ErrorCategory

from config import Config

# Give up on a request that hasn't started answering after this long and move on.
FIRST_TOKEN_TIMEOUT_S = 9.0  # Gemini's free tier can take 6-8 s with tools at busy times
STREAM_IDLE_TIMEOUT_S = 10.0


@dataclass(frozen=True)
class ChainLink:
    provider: str  # gemini | groq | sarvam
    model: str

    @property
    def label(self) -> str:
        return f"{self.provider}:{self.model}"


def parse_chain(cfg: Config) -> list[ChainLink]:
    """Primary model first, then each backup that has an API key."""
    primary_model = {
        "gemini": cfg.gemini_llm_model,
        "groq": cfg.groq_llm_model,
        "sarvam": cfg.sarvam_llm_model,
    }[cfg.llm_provider]
    links = [ChainLink(cfg.llm_provider, primary_model)]
    keys = {"gemini": cfg.google_api_key, "groq": cfg.groq_api_key, "sarvam": cfg.sarvam_api_key}
    for item in cfg.llm_fallback_chain:
        provider, _, model = item.partition(":")
        provider, model = provider.strip().lower(), model.strip()
        if provider not in keys or not model:
            logger.warning(f"Ignoring LLM_FALLBACK_CHAIN entry {item!r} (use provider:model)")
            continue
        if not keys[provider]:
            continue
        link = ChainLink(provider, model)
        if link not in links:
            links.append(link)
    return links


def create_chain_llm(cfg: Config, link: ChainLink, system_prompt: str):
    if link.provider == "groq":
        from pipecat.services.groq.llm import GroqLLMService

        # GPT-OSS accepts low/medium/high; Qwen needs "none", or Groq streams its
        # <think> reasoning inline and Aditi would read it aloud.
        effort = "none" if link.model.startswith("qwen/") else "low" if "gpt-oss" in link.model else None
        llm = GroqLLMService(
            api_key=cfg.groq_api_key,
            settings=GroqLLMService.Settings(
                model=link.model, system_instruction=system_prompt, temperature=0.4, reasoning_effort=effort
            ),
        )
        # The OpenAI client otherwise waits up to 10 minutes for a stuck request.
        llm._client = llm._client.with_options(timeout=STREAM_IDLE_TIMEOUT_S, max_retries=0)
        return llm
    if link.provider == "sarvam":
        from pipecat.services.sarvam.llm import SarvamLLMService

        reasoning = "low" if link.model in SarvamLLMService._REASONING_MODELS else None
        return SarvamLLMService(
            api_key=cfg.sarvam_api_key,
            settings=SarvamLLMService.Settings(
                model=link.model, system_instruction=system_prompt, temperature=0.4, reasoning_effort=reasoning
            ),
        )
    from pipecat.services.google.llm import GoogleLLMService

    return GoogleLLMService(
        api_key=cfg.google_api_key,
        settings=GoogleLLMService.Settings(
            model=link.model,
            system_instruction=system_prompt,
            temperature=0.4,
            # Voice needs speed more than deep reasoning.
            thinking=GoogleLLMService.ThinkingConfig(thinking_level="minimal")
            if link.model.startswith("gemini-3")
            else None,
        ),
        # Without retry_on_timeout this bounds the wait for the first chunk too.
        stream_idle_timeout_secs=FIRST_TOKEN_TIMEOUT_S,
    )


class LLMChainFailover(ServiceSwitcherStrategyManual):
    """Switch to the next model in the chain on any provider error.

    Pipecat's stock failover only switches away from a service that has become
    unusable (e.g. a bad key); a 503 or 429 is "recoverable", so it would keep
    sending turns to the struggling model. A live call can't wait, so any
    provider error moves on. Tool-handler errors (category APPLICATION) say
    nothing about the model and are ignored. The chain wraps around, so a model
    that failed earlier is tried again later in the call.
    """

    async def handle_error(self, error: ErrorFrame):
        failed = error.processor or self._active_service
        if failed is not self._active_service:
            return None
        if getattr(error, "category", None) == ErrorCategory.APPLICATION:
            return None
        current = self._services.index(self._active_service)
        for offset in range(1, len(self._services)):
            candidate = self._services[(current + offset) % len(self._services)]
            if candidate.is_usable:
                logger.warning(f"🧠 {failed.name} failed ({str(error.error)[:120]}); switching to {candidate.name}")
                return await self._set_active_if_available(candidate)
        return None


class FlushSafeLLMSwitcher(LLMSwitcher):
    """Pipecat's LLMSwitcher, but it lets the pipeline's flush probe through.

    In Pipecat 1.12 the switcher's parallel branches never hand a
    ``PipelineFlushFrame`` back out, so ``PipelineWorker.flush_pipeline()`` waits
    forever. RTVI "send-text" (used by the eval harness, and by clients that type
    to the bot) flushes before delivering the text, so the question was never
    answered. The probe only checks that queued work has drained, so it can pass
    straight through.
    """

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        if isinstance(frame, PipelineFlushFrame):
            await FrameProcessor.process_frame(self, frame, direction)
            await self.push_frame(frame, direction)
            return
        await super().process_frame(frame, direction)
