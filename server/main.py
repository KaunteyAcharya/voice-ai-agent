"""Tatsat Real Estate voice agent server.

Serves the web client and the WebRTC signalling endpoint. Start with:

    uv run server/main.py
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Windows consoles default to a legacy code page; make emoji and Devanagari log lines safe.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from loguru import logger  # noqa: E402

from config import ROOT, load_config  # noqa: E402

CFG = load_config()

logger.remove()
logger.add(
    sys.stderr,
    level=CFG.log_level,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <level>{message}</level>",
)

from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection  # noqa: E402
from pipecat.transports.smallwebrtc.request_handler import (  # noqa: E402
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)

from bot import run_bot, webrtc_transport  # noqa: E402
from model_files import ensure_kokoro_files  # noqa: E402

CLIENT_DIR = ROOT / "client"
webrtc_handler = SmallWebRTCRequestHandler()
_calls: set[asyncio.Task] = set()


def _warm_kokoro() -> None:
    """Download Kokoro's model files (~330 MB, first run only) before the first call."""
    try:
        ensure_kokoro_files()
    except Exception as e:  # don't block startup; calls retry the download
        logger.warning(f"Kokoro TTS model not ready: {e}")


async def _prewarm_voice_lines() -> None:
    from prompts import fixed_phrases
    from voices import prewarm_phrases

    voices = {"en": CFG.edge_voice_en, "hi": CFG.edge_voice_hi}
    phrases = {lang: fixed_phrases(lang, CFG.idle_timeout_secs) for lang in voices}
    await prewarm_phrases(voices, phrases, CFG.speech_rate)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if CFG.tts_provider == "kokoro" or CFG.uses_tts_fallback:
        asyncio.get_running_loop().run_in_executor(None, _warm_kokoro)
    if CFG.tts_provider == "edge":
        _calls.add(asyncio.create_task(_prewarm_voice_lines()))
    yield
    for task in list(_calls):
        task.cancel()
    await webrtc_handler.close()


app = FastAPI(title="Tatsat Real Estate · Talk to Aditi", lifespan=lifespan)


@app.get("/api/config")
async def client_config():
    """Tell the UI which providers are active and whether setup is complete."""
    cfg = load_config()
    from llm_chain import parse_chain

    chain = [link.label for link in parse_chain(cfg)]
    return {
        "llm_chain": chain,
        "llm_backups": max(len(chain) - 1, 0),
        "stt": cfg.stt_provider,
        "llm": cfg.llm_provider,
        "tts": cfg.tts_provider,
        "tts_fallback": cfg.tts_fallback if cfg.uses_tts_fallback else None,
        "problems": cfg.problems(),
    }


@app.post("/api/offer")
async def offer(http_request: Request):
    # The Pipecat JS client sends the extra data as "requestData" (camelCase); letting
    # FastAPI bind the body straight to SmallWebRTCRequest silently dropped it, so the
    # chosen language never arrived. from_dict accepts both spellings.
    request = SmallWebRTCRequest.from_dict(await http_request.json())
    cfg = load_config()  # picks up keys added to .env since startup
    problems = cfg.problems()
    if problems:
        logger.warning(f"Call refused, setup incomplete: {'; '.join(problems)}")
        return JSONResponse({"error": "; ".join(problems)}, status_code=400)

    request_data = request.request_data or {}
    language = str(request_data.get("language", "en")) if isinstance(request_data, dict) else "en"
    language = language if language in ("en", "hi") else "en"
    logger.info(f"📲 Call requested in {language.upper()}")

    async def on_connection(connection: SmallWebRTCConnection):
        task = asyncio.create_task(run_bot(webrtc_transport(connection), cfg, language))
        _calls.add(task)
        task.add_done_callback(_calls.discard)

    return await webrtc_handler.handle_web_request(request=request, webrtc_connection_callback=on_connection)


@app.patch("/api/offer")
async def ice_candidate(request: SmallWebRTCPatchRequest):
    await webrtc_handler.handle_patch_request(request)
    return {"status": "success"}


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(CLIENT_DIR / "index.html")


app.mount("/", StaticFiles(directory=CLIENT_DIR), name="client")


def main() -> None:
    problems = CFG.problems()
    url = f"http://{CFG.host}:{CFG.port}"
    print()
    print("  🏠  Tatsat Real Estate · Talk to Aditi")
    print(f"  ➜  Open {url} in Chrome, Edge or Firefox")
    print(f"     {CFG.describe()}")
    if problems:
        print("  ⚠️  Configuration problems (calls will be refused until fixed):")
        for p in problems:
            print(f"     - {p}")
        print("     Copy .env.example to .env and add your free API keys.")
    print()
    uvicorn.run(app, host=CFG.host, port=CFG.port, log_level="warning")


if __name__ == "__main__":
    main()
