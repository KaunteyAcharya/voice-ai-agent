"""Aditi's voice pipeline.

    browser mic ─WebRTC─▶ STT ─▶ user aggregator (Silero VAD + smart turn) ─▶ LLM chain (+ tools)
                                                                                 │
    browser speaker ◀─WebRTC─ transport out ◀─ TTS (Edge, Kokoro fallback) ◀─────┘

* LLM chain: Gemini first, Groq models as backups. A failed turn is re-run on the
  next model, so the caller isn't asked to repeat themselves (llm_chain.py).
* Fixed lines (greeting, "one moment", apology, "are you still there?") skip the
  LLM and play from cached audio (prompts.py, voices.py).

Providers are chosen in .env (see config.py). One ``run_bot`` call serves one
browser connection.
"""

from __future__ import annotations

import asyncio
import random
import re
import time

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    EndFrame,
    ErrorFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMMessagesAppendFrame,
    LLMTextFrame,
    LLMRunFrame,
    LLMUpdateSettingsFrame,
    STTUpdateSettingsFrame,
    TTSSpeakFrame,
    TTSUpdateSettingsFrame,
)
from pipecat.pipeline.llm_switcher import LLMSwitcher
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.service_switcher import ServiceSwitcher, ServiceSwitcherStrategyFailover
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame
from pipecat.services.settings import LLMSettings, TTSSettings
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.utils.text.base_text_filter import BaseTextFilter
from pipecat.workers.runner import WorkerRunner

from config import Config
from followup import FollowUpSender
from llm_chain import FlushSafeLLMSwitcher, LLMChainFailover, create_chain_llm, parse_chain
from model_files import ensure_kokoro_files
from prompts import APOLOGY, FILLERS, GOODBYE, GREETING, IDLE_GOODBYE, build_system_prompt, idle_prompt
from tools import PropertyDesk, build_tool_functions
from voices import EdgeTTSService, GeminiTTSWithKokoroFallback, preload_kokoro

PIPECAT_LANGUAGE = {"en": Language.EN_IN, "hi": Language.HI_IN}

# Whisper is steered by a short prompt: vocabulary it should expect, written in
# the script we want back (Devanagari for Hindi). Local area names matter most.
WHISPER_PROMPTS = {
    "en": "Tatsat Real Estate property call in Ahmedabad. Bopal, South Bopal, Satellite, Prahlad Nagar, SG Highway, "
    "Thaltej, Chandkheda, Gandhinagar, Gota, Vastrapur, Bodakdev, Shela, Science City. "
    "2 BHK, 3 BHK, 75 lakh, 1.2 crore, rent, EMI, site visit.",
    "hi": "तत्सत रियल एस्टेट से बातचीत। मुझे बोपल में 3 BHK फ़्लैट चाहिए, बजट 90 लाख है। सैटेलाइट, प्रह्लाद नगर, "
    "एसजी हाईवे, थलतेज, चांदखेड़ा, गांधीनगर, गोता, वस्त्रापुर। किराया, EMI, साइट विज़िट, कल शाम 5 बजे।",
}

# Gemini TTS returns a whole sentence at once and Kokoro runs at roughly real time
# on a laptop CPU, so give a sentence longer than Pipecat's 3 s default before the
# audio context is treated as stalled.
SLOW_TTS_TIMEOUT_S = 10.0
MAX_IDLE_PROMPTS = 1  # one warning, then goodbye


# ---------------------------------------------------------------------------
# Service factories
# ---------------------------------------------------------------------------


def create_stt(cfg: Config, lang: str):
    if cfg.stt_provider == "sarvam":
        from pipecat.services.sarvam.stt import SarvamSTTService

        return SarvamSTTService(
            api_key=cfg.sarvam_api_key,
            settings=SarvamSTTService.Settings(model=cfg.sarvam_stt_model, language=PIPECAT_LANGUAGE[lang]),
        )
    from pipecat.services.groq.stt import GroqSTTService

    return GroqSTTService(
        api_key=cfg.groq_api_key,
        settings=GroqSTTService.Settings(
            model=cfg.groq_stt_model,
            language=PIPECAT_LANGUAGE[lang],
            prompt=WHISPER_PROMPTS[lang],
            temperature=0.0,
        ),
    )


def stt_language_delta(cfg: Config, lang: str):
    if cfg.stt_provider == "sarvam":
        from pipecat.services.sarvam.stt import SarvamSTTService

        return SarvamSTTService.Settings(language=PIPECAT_LANGUAGE[lang])
    from pipecat.services.groq.stt import GroqSTTService

    return GroqSTTService.Settings(language=PIPECAT_LANGUAGE[lang], prompt=WHISPER_PROMPTS[lang])


# Some models write stage directions such as "[call ends]" or "*smiles*"; never speak them.
STAGE_DIRECTION = re.compile(r"\[[^\]]*\]|\*[^*]+\*|\([^)]*(?:pause|laugh|smile|sigh|call)[^)]*\)", re.IGNORECASE)
HANG_UP_HINT = re.compile(r"\[[^\]]*(?:end|hang)[^\]]*\]", re.IGNORECASE)


# Bullets and markdown a model sometimes writes even when told not to.
LIST_MARKER = re.compile(r"(^|\n)\s*(?:[-*•]|\d+[.)])\s+")
MARKDOWN = re.compile(r"\*\*|__|#+\s")

# Aditi is a woman, but models often use masculine first-person Hindi verbs
# ("मैं कर सकता हूँ"). These patterns only ever occur in the first person.
FEMININE_FIXES = [
    (re.compile(r"(\S+?)ता (हूँ|हूं)"), r"\1ती \2"),      # सकता/देखता/करता हूँ -> सकती/देखती/करती हूँ
    (re.compile(r"\bरहा (हूँ|हूं)"), r"रही \1"),           # रहा हूँ -> रही हूँ
    (re.compile(r"(गया|चुका|सका) (हूँ|हूं)"), lambda m: {"गया": "गई", "चुका": "चुकी", "सका": "सकी"}[m.group(1)] + " " + m.group(2)),
    (re.compile(r"(ूँ|ूं|ऊँ|ऊं)गा"), r"\1गी"),               # करूँगा/बताऊँगा -> करूँगी/बताऊँगी
]


def clean_for_speech(text: str) -> str:
    text = MARKDOWN.sub("", text)  # first, so "**Sapna Greens**" keeps its words
    text = STAGE_DIRECTION.sub("", text)
    text = LIST_MARKER.sub(r"\1", text)
    for pattern, replacement in FEMININE_FIXES:
        text = pattern.sub(replacement, text)
    return text


class SpeechTextFilter(BaseTextFilter):
    """Cleans every sentence before it is spoken (see clean_for_speech)."""

    async def filter(self, text: str) -> str:
        return clean_for_speech(text)


def kokoro_voice(cfg: Config, lang: str) -> str:
    return cfg.kokoro_voice_hi if lang == "hi" else cfg.kokoro_voice_en


def create_tts(cfg: Config, provider: str, lang: str, on_fallback=None):
    language = PIPECAT_LANGUAGE[lang]
    kokoro_voices = {"en": cfg.kokoro_voice_en, "hi": cfg.kokoro_voice_hi}
    use_fallback = cfg.tts_fallback == "kokoro"

    if provider == "sarvam":
        from pipecat.services.sarvam.tts import SarvamTTSService

        return SarvamTTSService(
            api_key=cfg.sarvam_api_key,
            settings=SarvamTTSService.Settings(
                model="bulbul:v3", voice=cfg.sarvam_tts_voice, language=language, pace=cfg.speech_rate
            ),
        )
    if provider == "kokoro":
        from pipecat.services.kokoro.tts import KokoroTTSService

        return KokoroTTSService(
            settings=KokoroTTSService.Settings(voice=kokoro_voice(cfg, lang), language=language, speed=cfg.speech_rate),
            stop_frame_timeout_s=SLOW_TTS_TIMEOUT_S,
            text_filters=[SpeechTextFilter()],
        )
    if provider == "gemini":
        from pipecat.services.google.tts import GeminiTTSService

        return GeminiTTSWithKokoroFallback(
            api_key=cfg.google_api_key,
            settings=GeminiTTSService.Settings(model=cfg.gemini_tts_model, voice=cfg.gemini_tts_voice, language=language),
            kokoro_voices=kokoro_voices,
            use_kokoro_fallback=use_fallback,
            on_fallback=on_fallback,
            speech_rate=cfg.speech_rate,  # used by the Kokoro fallback; Gemini TTS has no speed setting
            stop_frame_timeout_s=SLOW_TTS_TIMEOUT_S,
            text_filters=[SpeechTextFilter()],
        )
    return EdgeTTSService(
        voices={"en": cfg.edge_voice_en, "hi": cfg.edge_voice_hi},
        kokoro_voices=kokoro_voices,
        use_kokoro_fallback=use_fallback,
        on_fallback=on_fallback,
        language=language,
        speech_rate=cfg.speech_rate,
        stop_frame_timeout_s=SLOW_TTS_TIMEOUT_S,
        text_filters=[SpeechTextFilter()],
    )


def is_empty_audio_warning(error: ErrorFrame) -> bool:
    """Pipecat reports a TTS turn with no text (e.g. after an LLM error) as an error; it's harmless."""
    return "completed with no audio" in str(error.error)


class PrimaryTTSFailover(ServiceSwitcherStrategyFailover):
    """Fail over from Sarvam TTS to Kokoro on any synthesis error.

    (Edge and Gemini TTS fall back to Kokoro inside the service instead; see voices.py.)
    """

    async def handle_error(self, error: ErrorFrame):
        primary = self._services[0]
        failed = error.processor or self._active_service
        if is_empty_audio_warning(error):
            return None
        if failed is primary and primary.is_usable and self._active_service is primary:
            logger.warning(f"Primary TTS failed ({error.error}); switching to Kokoro")
            await primary.set_usable(False)
        return await super().handle_error(error)


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------


def webrtc_transport(connection: SmallWebRTCConnection) -> SmallWebRTCTransport:
    return SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )


async def run_bot(transport, cfg: Config, language: str = "en", desk: PropertyDesk | None = None) -> None:
    """Run one call over ``transport`` (WebRTC in the app, the eval transport under evals)."""
    language = language if language in PIPECAT_LANGUAGE else "en"
    logger.info(f"Starting call in {language.upper()} — {cfg.describe()}")

    background: set[asyncio.Task] = set()

    def spawn(coro) -> None:
        task = asyncio.create_task(coro)
        background.add(task)
        task.add_done_callback(background.discard)

    if cfg.tts_provider == "kokoro" or cfg.uses_tts_fallback:
        try:
            await asyncio.to_thread(ensure_kokoro_files)  # instant once downloaded
        except Exception as e:
            logger.error(f"Kokoro model download failed: {e}")
            if cfg.tts_provider == "kokoro":
                raise
        if cfg.tts_provider in ("edge", "gemini"):
            spawn(preload_kokoro())  # so a mid-call switch to the fallback voice is quick

    desk = desk or PropertyDesk(language=language)
    stt = create_stt(cfg, language)

    # --- LLM chain -----------------------------------------------------------
    chain = parse_chain(cfg)
    llms = [create_chain_llm(cfg, link, build_system_prompt(language)) for link in chain]
    link_of = {svc: link for svc, link in zip(llms, chain)}
    llm = FlushSafeLLMSwitcher(llms=llms, strategy_type=LLMChainFailover) if len(llms) > 1 else llms[0]
    logger.info("🧠 LLM chain: " + " → ".join(link.label for link in chain))

    # --- TTS -----------------------------------------------------------------
    async def on_tts_fallback(reason: str) -> None:
        await notify_ui({"type": "notice", "level": "warn", "text": "Cloud voice unavailable, using the offline voice"})

    primary_tts = create_tts(cfg, cfg.tts_provider, language, on_fallback=on_tts_fallback)
    if cfg.uses_tts_fallback and cfg.tts_provider == "sarvam":
        backup_tts = create_tts(cfg, "kokoro", language)
        tts = ServiceSwitcher(services=[primary_tts, backup_tts], strategy_type=PrimaryTTSFailover)
        tts_members = [primary_tts, backup_tts]
    else:
        tts = primary_tts
        tts_members = [primary_tts]

    def tts_language_delta(service, lang: str) -> TTSSettings:
        from pipecat.services.kokoro.tts import KokoroTTSService

        if isinstance(service, KokoroTTSService):
            return TTSSettings(language=PIPECAT_LANGUAGE[lang], voice=kokoro_voice(cfg, lang))
        return TTSSettings(language=PIPECAT_LANGUAGE[lang])

    async def notify_ui(payload: dict) -> None:
        await worker.queue_frames([RTVIServerMessageFrame(data=payload)])

    async def say(text: str) -> None:
        """Speak a fixed line without involving the LLM (not added to the context)."""
        await worker.queue_frames([TTSSpeakFrame(text, append_to_context=False)])

    # --- Language switching -------------------------------------------------
    async def switch_language(target: str, via_llm) -> bool:
        if target == desk.language:
            return False
        logger.info(f"🌐 Switching language {desk.language} → {target}")
        desk.language = target
        # STT sits upstream of the LLM; TTS downstream. Pushing from the LLM in
        # both directions means the TTS update lands before Aditi's next sentence.
        await via_llm.push_frame(STTUpdateSettingsFrame(delta=stt_language_delta(cfg, target)), FrameDirection.UPSTREAM)
        for service in tts_members:
            await via_llm.push_frame(TTSUpdateSettingsFrame(delta=tts_language_delta(service, target), service=service))
        # New system prompt for every model in the chain, for every later turn.
        prompt = build_system_prompt(target)
        for service in llms:
            await service.queue_frame(LLMUpdateSettingsFrame(delta=LLMSettings(system_instruction=prompt), service=service))
        await notify_ui({"type": "language", "language": target})
        return True

    async def hang_up() -> None:
        if state["ending"]:
            return
        state["ending"] = True
        logger.info("👋 Caller is done — saying goodbye and ending the call")
        await worker.queue_frames([TTSSpeakFrame(GOODBYE[desk.language], append_to_context=False), EndFrame()])

    sender = FollowUpSender(
        cfg.message_channel, cfg.whatsapp_token, cfg.whatsapp_phone_number_id, cfg.whatsapp_api_version
    )
    context = LLMContext(tools=build_tool_functions(desk, switch_language, hang_up, sender))
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=cfg.vad_stop_secs)),
            user_idle_timeout=cfg.idle_timeout_secs,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        # Keep running when one service breaks: we fail over or apologise instead.
        processor_unusable_policy=ProcessorUnusablePolicy.CONTINUE,
    )

    # --- Failover: re-run the same turn on the next model --------------------
    state = {"failovers": 0, "last_apology": 0.0, "idle_prompts": 0, "greeted": False, "filler_said": False, "ending": False}

    async def apologise() -> None:
        now = time.monotonic()
        if now - state["last_apology"] > 8:
            state["last_apology"] = now
            logger.info(f"🙏 Apologising to caller: {APOLOGY[desk.language]}")
            await say(APOLOGY[desk.language])

    if isinstance(llm, LLMSwitcher):

        @llm.strategy.event_handler("on_service_switched")
        async def on_llm_switched(strategy, service):
            state["failovers"] += 1
            label = link_of[service].label if service in link_of else service.name
            await notify_ui({"type": "llm", "model": label})
            if state["failovers"] < len(llms):
                logger.info(f"🔁 Re-running the turn on {label}")
                await worker.queue_frames([LLMRunFrame()])
            else:
                logger.error("Every model in the LLM chain failed for this turn")
                await apologise()

    @worker.event_handler("on_pipeline_error")
    async def on_pipeline_error(worker, frame: ErrorFrame):
        if is_empty_audio_warning(frame):
            logger.debug(f"Ignoring empty TTS turn: {frame.error}")
            return
        source = frame.processor
        source_name = getattr(source, "name", "pipeline")
        category = getattr(frame, "category", None)
        logger.error(f"❌ {source_name}: {str(frame.error)[:300]} (category={getattr(category, 'value', category)})")
        if source is None or source in tts_members:
            return  # TTS failures fall back to Kokoro; nothing to say out loud
        await notify_ui({"type": "notice", "level": "error", "text": "Aditi hit a problem and is apologising"})
        await apologise()

    # --- Fillers while tools run --------------------------------------------
    for service in llms:

        @service.event_handler("on_function_calls_started")
        async def on_function_calls_started(service, function_calls):
            names = {getattr(call, "function_name", "") for call in function_calls}
            if state["filler_said"] or names <= {"set_language", "end_call"}:
                return  # one "one moment" per turn is enough
            state["filler_said"] = True
            await tts.queue_frame(TTSSpeakFrame(random.choice(FILLERS[desk.language]), append_to_context=False))

    # --- Turn bookkeeping and logs ------------------------------------------
    @user_aggregator.event_handler("on_user_turn_stopped")
    async def on_user_turn_stopped(aggregator, strategy, message):
        state["failovers"] = 0
        state["idle_prompts"] = 0
        state["filler_said"] = False
        if message.content:
            logger.info(f"🧑 Caller: {message.content}")

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn_stopped(aggregator, message):
        if message.content:
            state["failovers"] = 0
            suffix = " (interrupted)" if getattr(message, "interrupted", False) else ""
            logger.info(f"🤖 Aditi: {message.content}{suffix}")
            # Safety net: a model that writes "[call ends]" instead of calling end_call.
            if HANG_UP_HINT.search(message.content) and not state["ending"]:
                await hang_up()

    @user_aggregator.event_handler("on_user_turn_idle")
    async def on_user_turn_idle(aggregator):
        if not state["greeted"] or state["ending"]:
            return
        state["idle_prompts"] += 1
        if state["idle_prompts"] <= MAX_IDLE_PROMPTS:
            logger.info(f"⏳ Caller silent for {cfg.idle_timeout_secs:g} s — warning before ending the call")
            await say(idle_prompt(desk.language, cfg.idle_timeout_secs))
        else:
            logger.info("⏳ Caller still silent — ending the call")
            state["ending"] = True
            await worker.queue_frames([TTSSpeakFrame(IDLE_GOODBYE[desk.language], append_to_context=False), EndFrame()])

    # --- Greeting: fixed line, once the browser is ready to play audio ------
    async def greet(reason: str) -> None:
        if state["greeted"]:
            return
        state["greeted"] = True
        logger.info(f"📞 Greeting caller ({reason})")
        # Sent as if the LLM had said it: no LLM request, the audio comes from the
        # cache, and the greeting still lands in the context, the transcript and
        # the eval harness's view of the conversation like any other reply.
        await worker.queue_frames(
            [LLMFullResponseStartFrame(), LLMTextFrame(GREETING[desk.language]), LLMFullResponseEndFrame()]
        )

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await greet("client ready")

    @worker.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        # The page's example-question chips send {type: "ask", data: {text}}.
        text = str((message.data or {}).get("text", "")).strip() if isinstance(message.data, dict) else ""
        if message.type != "ask" or not text:
            return
        logger.info(f"🧑 Caller (typed): {text}")
        state["failovers"] = 0
        state["idle_prompts"] = 0
        state["filler_said"] = False
        await rtvi.interrupt_bot()
        await worker.queue_frames([LLMMessagesAppendFrame(messages=[{"role": "user", "content": text}], run_llm=True)])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("📞 Client connected")

        async def greet_if_client_silent():
            # Older clients never send client-ready; don't leave them in silence.
            await asyncio.sleep(3)
            await greet("no client-ready after 3 s")

        spawn(greet_if_client_silent())

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("📴 Client disconnected")
        await runner.cancel()

    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    try:
        await runner.run()
    except Exception:
        logger.exception("Call crashed")
    for task in background:
        task.cancel()
    logger.info("Call ended")


if __name__ == "__main__":
    # Convenience: `python server/bot.py` starts the full server too.
    from main import main

    main()
