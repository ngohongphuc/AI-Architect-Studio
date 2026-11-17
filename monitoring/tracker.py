"""Đếm token, số lần gọi LLM và lưu prompt theo (run_id, agent)."""
from __future__ import annotations

import contextvars
import os
import threading
from collections import defaultdict

current_run: contextvars.ContextVar[str] = contextvars.ContextVar("current_run", default="local")
current_agent: contextvars.ContextVar[str] = contextvars.ContextVar("current_agent", default="unknown")

# Giá tham khảo USD / 1 triệu token (blended input+output), có thể ghi đè bằng LLM_PRICE_PER_MTOK
DEFAULT_PRICE = {"gemini": 0.6, "openai": 1.0, "anthropic": 6.0, "ollama": 0.0, "none": 0.0}


class Tracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict = defaultdict(lambda: defaultdict(lambda: {"tokens": 0, "calls": 0, "usd": 0.0, "prompts": []}))

    def record(self, tokens: int, prompt: str | None = None, response: str | None = None,
               run_id: str | None = None, agent: str | None = None) -> None:
        run_id = run_id or current_run.get()
        agent = agent or current_agent.get()
        with self._lock:
            d = self._data[run_id][agent]
            d["tokens"] += int(tokens or 0)
            d["usd"] += int(tokens or 0) / 1e6 * price_per_mtok(agent)
            d["calls"] += 1
            if prompt is not None:
                d["prompts"].append({"prompt": prompt[:6000], "response": (response or "")[:3000]})
                d["prompts"] = d["prompts"][-10:]

    def tokens(self, run_id: str, agent: str | None = None) -> int:
        with self._lock:
            if agent:
                return self._data[run_id][agent]["tokens"]
            return sum(v["tokens"] for v in self._data[run_id].values())

    def prompts(self, run_id: str, agent: str) -> list[dict]:
        with self._lock:
            return list(self._data[run_id][agent]["prompts"])

    def usd(self, run_id: str) -> float:
        with self._lock:
            return round(sum(v["usd"] for v in self._data[run_id].values()), 4)

    def summary(self, run_id: str) -> dict:
        with self._lock:
            return {a: {"tokens": v["tokens"], "calls": v["calls"]} for a, v in self._data[run_id].items()}


tracker = Tracker()


def _env(name: str, agent: str | None) -> str | None:
    if agent and os.getenv(f"{name}_{agent.upper()}"):
        return os.environ[f"{name}_{agent.upper()}"]
    return os.getenv(name)


def price_per_mtok(agent: str | None = None) -> float:
    """Giá USD / 1 triệu token của agent (LLM_PRICE_PER_MTOK_<AGENT> > LLM_PRICE_PER_MTOK > bảng mặc định)."""
    if _env("LLM_PRICE_PER_MTOK", agent):
        return float(_env("LLM_PRICE_PER_MTOK", agent))
    return DEFAULT_PRICE.get((_env("LLM_PROVIDER", agent) or "none").lower(), 1.0)


def estimate_cost_usd(tokens: int) -> float:
    return round(tokens / 1e6 * price_per_mtok(), 4)
