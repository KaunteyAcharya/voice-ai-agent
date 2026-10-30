"""LLMs for the eval harness: the judge and the simulated caller run on Groq's free tier.

The harness needs OpenAI-compatible services (BaseOpenAILLMService subclasses),
which Groq's is. Each role gets its own Groq model, and so its own tokens-per-minute
pool: the judge runs on qwen3.8-27b, the simulated caller on gpt-oss-120b, and the
eval bot on gpt-oss-20b with Gemini as its backup (see eval_bot.py).
"""

import os

from pipecat.services.groq.llm import GroqLLMService


def _groq(config: dict) -> GroqLLMService:
    model = config.get("model", "openai/gpt-oss-120b")
    effort = "none" if model.startswith("qwen/") else "low" if "gpt-oss" in model else None
    return GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(model=model, temperature=0.2, reasoning_effort=effort),
    )


def judge(config: dict) -> GroqLLMService:
    return _groq(config)


def caller(config: dict) -> GroqLLMService:
    return _groq(config)
