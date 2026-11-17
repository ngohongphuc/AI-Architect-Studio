"""Cấu hình chung của AI Architect Studio."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
MONITOR_DIR = ROOT / "monitoring"
LOG_DB = MONITOR_DIR / "logs.db"
CHECKPOINT_DB = MONITOR_DIR / "checkpoints.db"
RULES_FILE = DATA_DIR / "rules.json"
PRICE_FILE = DATA_DIR / "don_gia.xlsx"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Đọc file .env đơn giản (KEY=VALUE), không ghi đè biến đã có."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()

# Tổng số vòng sửa tối đa (vòng quy chuẩn + vòng ngân sách)
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "3"))
# Ngưỡng vượt ngân sách để quay lại Kiến trúc sư
BUDGET_TOLERANCE = float(os.getenv("BUDGET_TOLERANCE", "0.10"))

PROJECT_NAME = "AI Architect Studio"

AGENT_LABELS = {
    "project_manager": "Chủ nhiệm",
    "architect": "Kiến trúc sư",
    "drafter": "Họa viên",
    "reviewer": "Kiểm định viên",
    "cost_estimator": "Kỹ sư dự toán",
    "user": "Người dùng",
}
AGENT_ORDER = ["project_manager", "architect", "drafter", "reviewer", "cost_estimator"]
