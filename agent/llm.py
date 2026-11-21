"""The one place that knows which model and provider we use, and that counts calls and tokens."""
import os
import time

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.getenv("MODEL", "openai/gpt-4o-mini")


def has_key() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY"))


def get_llm(temperature: float = 0) -> ChatOpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not set. Locally: put it in .env. On Vercel: add it under Settings, Environment Variables.")
    return ChatOpenAI(model=DEFAULT_MODEL, api_key=api_key, base_url=OPENROUTER_BASE_URL, temperature=temperature, timeout=40, max_retries=1)


def usage_of(msg) -> dict:
    u = getattr(msg, "usage_metadata", None) or {}
    return {"in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0)}


class Meter:
    """Counts model calls, tokens and seconds for one request (shown on screen)."""

    def __init__(self):
        self.calls, self.tok_in, self.tok_out, self.t0 = 0, 0, 0, time.time()

    def add(self, msg):
        self.calls += 1
        u = usage_of(msg)
        self.tok_in += u["in"]
        self.tok_out += u["out"]

    def as_dict(self) -> dict:
        return {"model": DEFAULT_MODEL if has_key() else "none (code-only mode)", "model_calls": self.calls,
                "tokens_in": self.tok_in, "tokens_out": self.tok_out, "seconds": round(time.time() - self.t0, 2)}
