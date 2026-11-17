"""Chạy AI Architect Studio từ dòng lệnh.

    python main.py "Lô đất 5×20m, hướng Đông Nam, Hà Nội, 3 phòng ngủ, phòng thờ, gara xe máy, ngân sách 2,5 tỷ"
    python main.py --sample
"""
from __future__ import annotations

import argparse
import logging
import time

from config import AGENT_LABELS, MAX_ITERATIONS
from graph import run_design
from llm import mode_label

SAMPLE = ("Lô đất 5×20m, mặt tiền hướng Đông Nam, ở Hà Nội. Gia đình 4 người (vợ chồng sinh năm 1990 và 1992, "
          "2 con nhỏ). Cần 3 phòng ngủ, 1 phòng thờ, có gara xe máy. Ngân sách 2,5 tỷ. Phong cách hiện đại, "
          "nhiều ánh sáng tự nhiên.")


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Architect Studio – multi-agent thiết kế nhà ở")
    ap.add_argument("request", nargs="?", help="Yêu cầu thiết kế bằng tiếng Việt")
    ap.add_argument("--sample", action="store_true", help="Dùng yêu cầu mẫu trong kế hoạch")
    ap.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    request = SAMPLE if args.sample or not args.request else args.request
    print(f"▶ {mode_label()}\n▶ Yêu cầu: {request}\n")
    t0 = time.time()

    def on_update(update: dict):
        for node, val in update.items():
            for line in (val or {}).get("log", []) if isinstance(val, dict) else []:
                print("  " + line)

    final = run_design(request, max_iterations=args.max_iterations, on_update=on_update)
    print(f"\n✔ Hoàn thành sau {time.time() - t0:.1f} s – {final.get('iteration', 0)} vòng sửa")
    for k, v in (final.get("final_files") or {}).items():
        print(f"  {k:18s} {v}")
    issues = final.get("remaining_issues") or []
    if issues:
        print("⚠ Lỗi còn tồn tại:", "; ".join(i["noi_dung"] for i in issues))
    _ = AGENT_LABELS


if __name__ == "__main__":
    main()
