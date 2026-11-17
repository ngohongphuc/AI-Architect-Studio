"""Agent 5 – Kỹ sư dự toán: diện tích quy đổi, chi phí theo hạng mục, so sánh ngân sách, file du_toan.xlsx."""
from __future__ import annotations

from pathlib import Path

from agents.base import agent_node
from config import BUDGET_TOLERANCE
from llm import invoke_text
from tools.docx_writer import vn_num, vnd
from tools.xlsx_writer import write_cost_xlsx
from tools.cost_calc import compute_cost


def cost_notes(cost: dict) -> str:
    base = (f"Tổng chi phí dự kiến {vnd(cost['tong_chi_phi'])} cho {vn_num(cost['dt_san_hoan_thien'])} m² sàn hoàn thiện "
            f"(bình quân {vnd(cost['chi_phi_m2_san'])}/m²), gói hoàn thiện '{cost['cap_hoan_thien']}'. ")
    if cost["vuot_pct"] > BUDGET_TOLERANCE:
        base += (f"Vượt ngân sách {vn_num(cost['vuot_pct'] * 100)}%; phương án tiết kiệm hiệu quả nhất: "
                 f"{max(cost['tiet_kiem'], key=lambda s: s['tiet_kiem'])['phuong_an']}.")
    elif cost["vuot_pct"] > 0:
        base += f"Vượt nhẹ {vn_num(cost['vuot_pct'] * 100)}% (trong ngưỡng 10%), có thể bù bằng dự phòng hoặc thương lượng."
    else:
        base += f"Trong ngân sách, còn dư {vnd(-cost['chenh_lech'])}."
    txt = invoke_text("Bạn là kỹ sư dự toán xây dựng nhà phố tại Việt Nam.",
                      "Viết 2–3 câu ghi chú cho chủ nhà dựa trên thông tin sau, giữ nguyên mọi con số, "
                      f"không thêm số mới:\n{base}")
    return txt or base


@agent_node("cost_estimator")
def run(state: dict) -> dict:
    budget = state["brief"]["ngan_sach"]
    cost = compute_cost(state["area_table"], state["layout"], state["program"], budget)
    notes = cost_notes(cost)
    cost["ghi_chu"] = notes
    path = write_cost_xlsx(cost, state["area_table"], state["brief"], Path(state["output_dir"]) / "du_toan.xlsx", notes)
    it, max_it = state.get("iteration", 0), state.get("max_iterations", 3)
    total_ty = cost["tong_chi_phi"] / 1e9
    if cost["vuot_pct"] > BUDGET_TOLERANCE and it < max_it:
        fb = [{"loai": "Ngân sách", "ma": "VUOT_NGAN_SACH", "muc": "Vượt ngân sách",
               "hien_tai": f"{vn_num(total_ty, 2)} tỷ", "cho_phep": f"≤ {vn_num(budget / 1e9 * (1 + BUDGET_TOLERANCE), 2)} tỷ",
               "noi_dung": f"Chi phí vượt {vn_num(cost['vuot_pct'] * 100)}% ngân sách",
               "de_xuat": "; ".join(s["phuong_an"] for s in cost["tiet_kiem"][:2]),
               "du_lieu": {"vuot_pct": cost["vuot_pct"]}}]
        return {"cost": cost, "cost_file": str(path), "route": "architect", "feedback": fb,
                "feedback_source": "cost_estimator", "iteration": it + 1, "_feedback": True, "_to": "architect",
                "_summary": f"❌ {vn_num(total_ty, 2)} tỷ, vượt ngân sách {vn_num(cost['vuot_pct'] * 100)}% > 10%",
                "_output": {k: cost[k] for k in ("tong_chi_phi", "vuot_pct", "cap_hoan_thien", "chi_phi_m2_san")}}
    status = "✅" if cost["vuot_pct"] <= BUDGET_TOLERANCE else "⚠️ hết vòng sửa,"
    return {"cost": cost, "cost_file": str(path), "route": "pm_report", "_to": "project_manager",
            "_summary": f"{status} {vn_num(total_ty, 2)} tỷ ({'+' if cost['vuot_pct'] >= 0 else ''}{vn_num(cost['vuot_pct'] * 100)}% so với ngân sách)",
            "_output": {k: cost[k] for k in ("tong_chi_phi", "vuot_pct", "cap_hoan_thien", "chi_phi_m2_san")}}
