"""Kết nối mô hình ngôn ngữ qua LangChain (tùy chọn).

Đặt biến môi trường (hoặc file .env):
    LLM_PROVIDER = gemini | openai | anthropic | ollama | none
    LLM_MODEL    = tên model (không bắt buộc)
và API key tương ứng (GOOGLE_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY).

Khi không cấu hình hoặc gọi lỗi, các hàm trả về None và agent dùng phương án quy tắc
(rule-based) — mọi con số luôn được tính bằng Python nên kết quả vẫn đầy đủ.
"""
from __future__ import annotations

import importlib
import logging
import os
from functools import lru_cache

import config  # noqa: F401  (nạp .env trước khi đọc biến môi trường)
from monitoring.tracker import current_agent, tracker

log = logging.getLogger(__name__)

PROVIDERS = {
    "gemini": ("langchain_google_genai", "ChatGoogleGenerativeAI", "GOOGLE_API_KEY", "gemini-2.5-flash"),
    "openai": ("langchain_openai", "ChatOpenAI", "OPENAI_API_KEY", "gpt-6-luna"),
    "anthropic": ("langchain_anthropic", "ChatAnthropic", "ANTHROPIC_API_KEY", "claude-sonnet-5-5"),
    "ollama": ("langchain_ollama", "ChatOllama", None, "qwen2.5:7b"),
}


AGENTS = ["project_manager", "architect", "drafter", "reviewer", "cost_estimator"]


def _env(name: str, agent: str | None) -> str | None:
    """Đọc biến riêng của agent (vd. LLM_MODEL_ARCHITECT) trước, rồi mới tới biến chung (LLM_MODEL)."""
    if agent:
        v = os.getenv(f"{name}_{agent.upper()}")
        if v:
            return v.strip()
    v = os.getenv(name)
    return v.strip() if v else None


def agent_config(agent: str | None = None) -> dict:
    """Cấu hình LLM của một agent: provider, model, temperature."""
    agent = agent or current_agent.get()
    if agent not in AGENTS:
        agent = None
    provider = (_env("LLM_PROVIDER", agent) or "none").lower()
    default_model = PROVIDERS.get(provider, (None, None, None, ""))[3]
    return {"agent": agent, "provider": provider, "model": _env("LLM_MODEL", agent) or default_model,
            # Model suy luận của OpenAI (GPT-5/6) không nhận temperature tùy ý -> chỉ gửi khi khai báo rõ
            "temperature": float(t) if (t := _env("LLM_TEMPERATURE", agent)) else (None if provider == "openai" else 0.3)}


def provider_name(agent: str | None = None) -> str:
    return agent_config(agent)["provider"]


@lru_cache(maxsize=16)
def _build(provider: str, model: str, temperature: float | None):
    if provider not in PROVIDERS:
        return None
    module, cls, key_env, _ = PROVIDERS[provider]
    if key_env and not os.getenv(key_env):
        log.warning("Thiếu %s – chạy chế độ quy tắc", key_env)
        return None
    try:
        klass = getattr(importlib.import_module(module), cls)
    except ImportError:
        log.warning("Chưa cài %s – chạy chế độ quy tắc", module)
        return None
    kw = {"model": model}
    if temperature is not None:
        kw["temperature"] = temperature
    try:
        return klass(**kw, max_retries=1)
    except TypeError:
        return klass(**kw)


_exhausted: set[tuple[str, str]] = set()   # (provider, model) đã hết quota trong phiên này


def _quota_error(e: Exception) -> bool:
    t = f"{type(e).__name__} {e}".lower()
    return any(k in t for k in ("429", "resource_exhausted", "ratelimit", "rate limit", "quota", "insufficient_quota"))


def _mark_if_quota(e: Exception) -> bool:
    """Hết quota -> ngừng gọi model này cho tới khi khởi động lại, agent dùng phương án quy tắc."""
    if _quota_error(e):
        c = agent_config()
        if (c["provider"], c["model"]) not in _exhausted:
            log.warning("%s · %s hết quota/rate limit – chuyển sang chế độ quy tắc cho tới khi khởi động lại",
                        c["provider"], c["model"])
        _exhausted.add((c["provider"], c["model"]))
        return True
    return False


def get_llm(agent: str | None = None):
    """LLM cho agent hiện tại (lấy từ ngữ cảnh khi agent đang chạy) hoặc agent được chỉ định."""
    c = agent_config(agent)
    if (c["provider"], c["model"]) in _exhausted:
        return None
    return _build(c["provider"], c["model"], c["temperature"])


def llm_enabled(agent: str | None = None) -> bool:
    return get_llm(agent) is not None


def agent_model_label(agent: str) -> str:
    c = agent_config(agent)
    return f"{c['provider']} · {c['model']}" if llm_enabled(agent) else "quy tắc (không LLM)"


def mode_label() -> str:
    labels = {a: agent_model_label(a) for a in AGENTS}
    if len(set(labels.values())) == 1:
        v = labels[AGENTS[0]]
        return "Chế độ quy tắc (không dùng LLM)" if v.startswith("quy tắc") else f"LLM: {v}"
    return "LLM theo agent – " + "; ".join(f"{a}: {v}" for a, v in labels.items())


def _usage_tokens(msg) -> int:
    usage = getattr(msg, "usage_metadata", None) or {}
    if usage:
        return int(usage.get("total_tokens") or usage.get("input_tokens", 0) + usage.get("output_tokens", 0))
    meta = getattr(msg, "response_metadata", {}) or {}
    tu = meta.get("token_usage") or meta.get("usage") or {}
    return int(tu.get("total_tokens", 0) or tu.get("input_tokens", 0) + tu.get("output_tokens", 0))


def invoke_text(system: str, prompt: str, retries: int = 2) -> str | None:
    llm = get_llm()
    if llm is None:
        return None
    for attempt in range(retries + 1):
        try:
            msg = llm.invoke([("system", system + PLAIN_RULE), ("human", prompt)])
            text = msg.content if isinstance(msg.content, str) else "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in msg.content)
            tracker.record(_usage_tokens(msg), prompt=f"[SYSTEM]\n{system}\n\n[USER]\n{prompt}", response=text)
            return clean_text(text)
        except Exception as e:  # noqa: BLE001
            if _mark_if_quota(e):
                return None
            log.warning("LLM lỗi (lần %d): %s", attempt + 1, e)
    return None


PLAIN_RULE = ("\n\nChỉ trả về đúng nội dung được yêu cầu bằng tiếng Việt: không lời chào, không câu dẫn "
              "(như 'Dưới đây là...'), không tiêu đề, không markdown (không dùng *, #, gạch đầu dòng).")


def clean_text(text: str) -> str:
    """Bỏ câu dẫn đầu ('Chào bạn, đây là ...:') và ký hiệu markdown còn sót."""
    import re

    lines = [ln.strip() for ln in text.strip().splitlines()]
    while lines and (not lines[0] or (lines[0].endswith(":") and len(lines) > 1)
                     or re.match(r"^(chào|dưới đây|đây là|sau đây)", lines[0], re.I)):
        lines.pop(0)
    out = []
    for ln in lines:
        ln = re.sub(r"^\s*([*\-•]|\d+\.)\s+", "", ln)
        ln = re.sub(r"[*#]{1,3}", "", ln).strip()
        if ln:
            out.append(ln)
    if out and out[0].startswith("{"):
        return "\n".join(out)  # JSON giữ nguyên dòng
    return " ".join(out)


def invoke_structured(system: str, prompt: str, schema, retries: int = 2):
    """Gọi LLM với Pydantic structured output; tự thử lại khi JSON sai định dạng."""
    llm = get_llm()
    if llm is None:
        return None
    try:
        runnable = llm.with_structured_output(schema, include_raw=True)
    except Exception as e:  # noqa: BLE001
        log.warning("Model không hỗ trợ structured output: %s", e)
        return None
    for attempt in range(retries + 1):
        try:
            out = runnable.invoke([("system", system), ("human", prompt)])
            raw = out.get("raw")
            tracker.record(_usage_tokens(raw) if raw is not None else 0,
                           prompt=f"[SYSTEM]\n{system}\n\n[USER]\n{prompt}",
                           response=str(out.get("parsed")))
            if out.get("parsed") is not None:
                return out["parsed"]
        except Exception as e:  # noqa: BLE001
            if _mark_if_quota(e):
                return None
            log.warning("Structured output lỗi (lần %d): %s", attempt + 1, e)
    return None
