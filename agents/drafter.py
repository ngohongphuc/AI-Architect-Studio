"""Agent 3 – Họa viên: bố trí phòng bằng thuật toán, lập bảng diện tích, xuất bộ bản vẽ."""
from __future__ import annotations

from pathlib import Path

from agents.base import agent_node
from tools.docx_writer import vn_num as vf
from tools.drawing_set import export_drawings
from tools.layout_algorithm import LayoutError, build_area_table, compute_layout


@agent_node("drafter")
def run(state: dict) -> dict:
    brief, program = state["brief"], state["program"]
    version = (state.get("versions") or {}).get("drafter", 0) + 1
    try:
        layout = compute_layout(brief, program)
    except LayoutError as e:
        # Không bố trí được: trả bố cục rỗng để Kiểm định viên báo lỗi và Kiến trúc sư sửa
        raise RuntimeError(f"Không thể bố trí mặt bằng: {e}") from e
    area = build_area_table(layout, brief)
    out_dir = Path(state["output_dir"]) / f"v{version}"
    drawings = export_drawings(brief, program, layout, area, out_dir, version=version)
    n_rooms = sum(1 for fl in layout["floors"].values() for r in fl["rooms"]
                  if r["loai"] not in ("hanh_lang", "thang", "gieng_troi", "san"))
    summary = (f"Mặt bằng nháp v{version}: {layout['so_tang']} tầng, {n_rooms} không gian, "
               f"DT sàn {vf(area['tong_dien_tich_san'])} m², {len(drawings['sheets'])} bản vẽ")
    return {"layout": layout, "area_table": area, "drawings": drawings, "route": "reviewer", "_summary": summary,
            "_to": "reviewer",
            "_output": {"mat_bang": [s["png"] for s in drawings["sheets"] if s["ten"].startswith("Mặt bằng tầng")],
                        "dien_tich_xay_dung": area["dien_tich_xay_dung"],
                        "mat_do": area["mat_do_xay_dung"],
                        "tong_dien_tich_san": area["tong_dien_tich_san"],
                        "pdf": drawings["pdf"]}}
