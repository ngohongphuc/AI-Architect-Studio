"""Agent 1 – Chủ nhiệm dự án: phân tích brief, theo dõi vòng sửa, viết thuyết minh, đóng gói hồ sơ."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from agents.base import agent_node
from llm import invoke_structured, invoke_text, llm_enabled
from monitoring.events import export_timeline
from state import Brief
from tools.brief_parser import parse_request
from tools.docx_writer import vn_num, vnd, write_description_docx

SYSTEM_BRIEF = ("Bạn là chủ nhiệm dự án kiến trúc. Trích xuất yêu cầu thiết kế nhà ở từ lời khách hàng thành JSON "
                "đúng schema. Không bịa thông tin: trường nào khách không nói thì để mặc định và ghi vào "
                "gia_dinh_bo_sung là giả định. Ngân sách đổi ra VNĐ (2,5 tỷ = 2500000000).")


def analyze_brief(request: str) -> dict:
    rule = parse_request(request)
    if not llm_enabled():
        return rule
    out = invoke_structured(SYSTEM_BRIEF, request, Brief)
    if out is None:
        rule["gia_dinh_bo_sung"].append("LLM không trả kết quả hợp lệ – dùng bộ phân tích quy tắc")
        return rule
    brief = out.model_dump()
    # Kiểm tra chéo: các số liệu quan trọng phải khớp bộ phân tích quy tắc khi khách có nói rõ
    for path in (("lo_dat", "rong"), ("lo_dat", "dai"), ("yeu_cau_phong", "phong_ngu")):
        a, b = brief[path[0]][path[1]], rule[path[0]][path[1]]
        if a != b and not any(path[1] in s.lower() for s in rule["gia_dinh_bo_sung"]):
            brief[path[0]][path[1]] = b
    if not brief.get("ngan_sach"):
        brief["ngan_sach"] = rule["ngan_sach"]
    brief["gia_dinh_bo_sung"] = sorted(set(brief.get("gia_dinh_bo_sung", [])) | set(rule["gia_dinh_bo_sung"]))
    return brief


@agent_node("project_manager")
def run_brief(state: dict) -> dict:
    brief = analyze_brief(state["user_request"])
    Path(state["output_dir"]).mkdir(parents=True, exist_ok=True)
    ld, yc = brief["lo_dat"], brief["yeu_cau_phong"]
    summary = (f"Gửi brief: lô {ld['rong']:g}×{ld['dai']:g} m hướng {ld['huong']}, {yc['phong_ngu']} PN"
               f"{', phòng thờ' if yc.get('phong_tho') else ''}{', gara ' + yc['gara'] if yc.get('gara') else ''}, "
               f"ngân sách {vn_num(brief['ngan_sach'] / 1e9, 2)} tỷ")
    return {"brief": brief, "iteration": 0, "program": None, "options": [], "route": "architect",
            "_summary": summary, "_to": "architect", "_output": brief}


def _texts(state: dict) -> dict:
    """Các đoạn văn bản tự do của thuyết minh (LLM viết lại nếu có, luôn có bản mẫu)."""
    area, layout, program = state["area_table"], state["layout"], state["program"]
    core = layout["core"]
    texts = {}
    for t in area["tang"]:
        names = []
        for ph in t["phong"]:
            if ph["loai"] in ("hanh_lang",) or ph["ten"] in names:
                continue
            names.append(ph["ten"])
        names = [n if n.startswith("WC") else n[0].lower() + n[1:] for n in names]
        base = f"bố trí lần lượt từ mặt tiền vào trong gồm {', '.join(names)}; diện tích sàn {vn_num(t['dien_tich_san'])} m²"
        texts[f"tang_{t['tang']}"] = base + "."
    texts["thong_gio"] = (
        f"Giếng trời rộng {vn_num(core['sky_w'])} m × {vn_num(core['l'])} m đặt cạnh cầu thang, xuyên suốt từ tầng 1 lên mái, "
        f"trên phủ mái kính có lam nhôm che nắng. Các phòng phía trước và phía sau lõi thang đều có cửa sổ mở ra giếng "
        f"trời hoặc mặt tiền, tạo thông gió xuyên phòng theo hiệu ứng ống khói. "
        + ("Ban công các tầng lùi 1,2 m vào trong giúp che nắng trực tiếp cho mặt tiền. " if any(
            r["loai"] == "ban_cong" for fl in layout["floors"].values() for r in fl["rooms"]) else "")
        + (f"Sân sau sâu {vn_num(layout['san_sau'])} m giúp lấy gió và ánh sáng cho phòng phía sau."
           if layout["san_sau"] > 0 else ""))
    fs = state.get("review", {}).get("phong_thuy", {})
    if fs.get("co_du_lieu"):
        texts["phong_thuy"] = (f"Gia chủ cung {fs['cung_menh']} thuộc {fs['nhom']}; nhà hướng {fs['huong_nha']} "
                               f"({fs['sao_huong_nha']}) – {'hợp mệnh' if fs['hop_huong'] else 'chưa hợp mệnh, nên bố trí cửa chính, bàn thờ và bếp quay về các hướng tốt để hóa giải'}.")
    cost = state.get("cost")
    if cost:
        texts["chi_phi"] = cost.get("ghi_chu", "")
    if llm_enabled():
        prompt = ("Viết lại các đoạn sau cho văn phong thuyết minh kiến trúc chuyên nghiệp, giữ nguyên MỌI con số, "
                  "không thêm số liệu. Trả về JSON cùng khóa.\n" + json.dumps(texts, ensure_ascii=False))
        out = invoke_text("Bạn là chủ nhiệm đồ án kiến trúc.", prompt)
        if out:
            try:
                start, end = out.index("{"), out.rindex("}") + 1
                new = json.loads(out[start:end])
                texts.update({k: v for k, v in new.items() if k in texts and isinstance(v, str)})
            except ValueError:
                pass
    return texts


@agent_node("project_manager")
def run_report(state: dict) -> dict:
    out = Path(state["output_dir"])
    drawings = state["drawings"]
    # Bản vẽ cuối = phiên bản cuối của Họa viên; sao chép ra thư mục gốc
    shutil.copy(drawings["pdf"], out / "ban_ve.pdf")
    shutil.copy(drawings["dxf_zip"], out / "ban_ve_dxf.zip")
    if (out / "dxf").exists():
        shutil.rmtree(out / "dxf")
    shutil.copytree(drawings["dxf_dir"], out / "dxf")
    doc_path = write_description_docx(state, _texts(state), out / "thuyet_minh.docx")
    export_timeline(state.get("run_id", "local"), out / "timeline.csv")
    final = {"ban_ve_pdf": str(out / "ban_ve.pdf"), "ban_ve_dxf_zip": str(out / "ban_ve_dxf.zip"),
             "thuyet_minh_docx": str(doc_path), "du_toan_xlsx": state.get("cost_file", ""),
             "timeline_csv": str(out / "timeline.csv")}
    snapshot = {k: v for k, v in state.items() if k not in ("events", "history", "log")}
    snapshot["final_files"] = final
    (out / "state.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    issues = state.get("remaining_issues") or []
    cost = state.get("cost", {})
    summary = (f"Hoàn thành hồ sơ: 3 sản phẩm, tổng {vnd(cost.get('tong_chi_phi', 0))}, "
               f"{state.get('iteration', 0)} vòng sửa" + (f", còn {len(issues)} lỗi" if issues else ""))
    return {"description_file": str(doc_path), "final_files": final, "route": "end", "_summary": summary, "_to": "",
            "_output": final}
