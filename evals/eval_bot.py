"""Aditi, served on Pipecat's eval transport for automated conversation tests.

Start it (it listens on ws://localhost:7870 and serves one scenario after another):

    uv run evals/eval_bot.py -t eval --port 7870

then run the scenarios from another terminal (see evals/README.md):

    uv run pipecat eval run evals/scenarios --bot-url ws://localhost:7870 --trigger-disconnect

Every scenario gets a fresh pipeline and a fresh in-memory booking store, so
results don't depend on what an earlier scenario booked. The store holds the
usual pre-booked demo slots plus one known customer booking (code SH-4242 for
98765 00001) for the manage-my-visit scenarios.
"""

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server"))

from loguru import logger  # noqa: E402
from pipecat.evals.transport import EvalTransportParams  # noqa: E402
from pipecat.runner.types import RunnerArguments  # noqa: E402
from pipecat.runner.utils import create_transport  # noqa: E402

from bookings import BookingStore  # noqa: E402
from bot import run_bot  # noqa: E402
from config import load_config  # noqa: E402
from parsing import today_ist  # noqa: E402
from tools import PropertyDesk  # noqa: E402

EVAL_CUSTOMER_PHONE = "9876500001"
EVAL_CUSTOMER_CODE = "SH-4242"

transport_params = {
    "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


def fresh_store() -> BookingStore:
    from datetime import timedelta

    store = BookingStore(":memory:")
    today = today_ist()
    store.seed(today)
    visit_day = (today + timedelta(days=2)).isoformat()
    with store._lock, store._db:  # a known booking to view, move and cancel
        store._db.execute(
            "INSERT INTO bookings (code, property_id, name, phone, date, time, created_at, updated_at)"
            " VALUES (?, 'SH-109', 'Meera', ?, ?, '15:00', datetime('now'), datetime('now'))",
            (EVAL_CUSTOMER_CODE, EVAL_CUSTOMER_PHONE, visit_day),
        )
    return store


async def bot(runner_args: RunnerArguments):
    # The judge (qwen) and simulated caller (gpt-oss-120b) run on Groq too; give the bot
    # its own Groq model (gpt-oss-20b) with Gemini as backup, so the three never share
    # one tokens-per-minute pool.
    cfg = replace(
        load_config(),
        llm_provider="groq",
        groq_llm_model="openai/gpt-oss-20b",
        llm_fallback_chain=("gemini:gemini-3.1-flash-lite",),
    )
    session = 0
    while True:
        session += 1
        logger.info(f"🧪 Eval session {session}: waiting for the harness")
        transport = await create_transport(runner_args, transport_params)
        desk = PropertyDesk(language="en", store=fresh_store())
        await run_bot(transport, cfg, "en", desk=desk)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
