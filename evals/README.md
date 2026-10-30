# Conversation tests (Pipecat evals)

These tests talk to Aditi the way a caller would and check what she does, using Pipecat's built-in eval harness.

- **Scripted** (`scenarios/scripted.yaml`): the caller's lines are fixed. Each turn checks which tool Aditi calls (for example `search_properties` or `schedule_site_visit`) and whether her reply meets a plain-English criterion.
- **Simulated callers** (`scenarios/simulated.yaml`): an LLM plays a caller with a persona and a goal (a buyer booking a visit, a Hindi-speaking renter, someone moving or cancelling a booking, an off-topic chatter). It talks to Aditi until it's done, then a judge LLM decides whether Aditi got it right and scores every reply for voice style.

The judge and the simulated callers run on Groq's free tier (`factories.py`), each on its own Groq model (judge `qwen3.8-27b`, caller `gpt-oss-120b`, the eval bot itself `gpt-oss-20b` with Gemini as backup), so none of them shares a tokens-per-minute pool. Tests run in text mode, so no audio is generated and no speech-to-text requests are used.

## Run them

Install the eval extras once:

```bash
uv sync --group evals
```

Terminal 1, start Aditi on the eval transport. It serves one scenario after another, each with a fresh booking database:

```bash
uv run evals/eval_bot.py -t eval --port 7870
```

Terminal 2, run every scenario:

```bash
uv run python -m pipecat.evals run evals/scenarios --bot-url ws://localhost:7870 --trigger-disconnect
```

Or just one file, with a line per turn:

```bash
uv run python -m pipecat.evals run evals/scenarios/scripted.yaml --bot-url ws://localhost:7870 --trigger-disconnect --verbose
```

Use `python -m pipecat.evals` rather than the `pipecat` command, because `python -m` puts the project folder on the import path so the judge factory (`evals.factories.judge`) can be found.

## What the eval bot sets up

- A fresh in-memory booking store per scenario, with the usual pre-booked demo slots (Sapna Greens tomorrow at 11 AM is taken).
- One known customer booking for the manage-my-visit scenarios: code `SH-4242`, phone `98765 00001`, Mansi Apartments, the day after tomorrow at 3 PM.

## Notes

- Free tiers are shared and sometimes slow (Gemini can return 503 "high demand"), so an occasional failure can be the provider rather than Aditi. Re-run a failing scenario before changing the prompt.
- A full run takes roughly 10–20 minutes and uses a few hundred free Groq/Gemini requests.
