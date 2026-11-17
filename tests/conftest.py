"""Test luôn chạy chế độ quy tắc (không gọi API thật) để nhanh, ổn định và không tốn quota."""
import os

os.environ["LLM_PROVIDER"] = "none"
for _k in list(os.environ):
    if _k.startswith("LLM_PROVIDER_"):
        os.environ[_k] = "none"
