"""Đọc bộ tham số quy chuẩn (data/rules.json) và các hàm tra cứu."""
from __future__ import annotations

import json
from functools import lru_cache

from config import RULES_FILE


@lru_cache(maxsize=1)
def load_rules() -> dict:
    return json.loads(RULES_FILE.read_text(encoding="utf-8"))


def max_density(lot_area: float) -> float:
    """Mật độ xây dựng thuần tối đa (0–1) theo QCVN 01:2021 Bảng 2.8, nội suy tuyến tính."""
    table = load_rules()["mat_do_xay_dung"]["bang"]
    if lot_area <= table[0][0]:
        return table[0][1]
    if lot_area >= table[-1][0]:
        return table[-1][1]
    for (a1, d1), (a2, d2) in zip(table, table[1:]):
        if a1 <= lot_area <= a2:
            return round(d1 + (d2 - d1) * (lot_area - a1) / (a2 - a1), 4)
    return table[-1][1]


def min_room(loai: str, gara: str | None = None) -> dict:
    """Diện tích và cạnh tối thiểu theo loại phòng (rỗng nếu không quy định)."""
    table = load_rules()["dien_tich_toi_thieu"]
    if loai == "gara" and gara == "ô tô":
        return table["gara_o_to"]
    return table.get(loai, {})
