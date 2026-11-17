"""Agent 4 – Kiểm định viên: kiểm tra quy chuẩn (RAG), kỹ thuật (code), phong thủy, nhất quán."""
from __future__ import annotations

from agents.base import agent_node
from tools.docx_writer import vn_num as vf
from llm import invoke_text
from tools import fengshui, rag
from tools.layout_algorithm import EPS, OPEN_TYPES, room_at
from tools.rules import load_rules, max_density, min_room

NEED_LIGHT_TYPES = {"ngu", "lam_viec", "sinh_hoat", "khach", "bep", "tho"}


def _pct(v: float) -> str:
    return f"{vf(v * 100)}%".replace(".", ",")


def _overlap(a: dict, b: dict) -> float:
    w = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    h = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    return w * h if w > EPS and h > EPS else 0.0


def _adjacent(a: dict, b: dict) -> bool:
    """Hai phòng có chung một đoạn tường (> 0,3 m)."""
    if abs(a["y"] + a["h"] - b["y"]) < 1e-3 or abs(b["y"] + b["h"] - a["y"]) < 1e-3:
        return min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > 0.3
    if abs(a["x"] + a["w"] - b["x"]) < 1e-3 or abs(b["x"] + b["w"] - a["x"]) < 1e-3:
        return min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > 0.3
    return False


def has_daylight(room: dict, rooms: list[dict], layout: dict) -> bool:
    """Phòng được chiếu sáng trực tiếp: chạm mặt tiền, hoặc kề ban công / sân / giếng trời,
    hoặc chạm mặt sau khi có sân sau."""
    b = layout["building"]
    if abs(room["y"] - b["y"]) < 1e-3:
        return True
    if abs(room["y"] + room["h"] - (b["y"] + b["l"])) < 1e-3 and layout["san_sau"] > 0:
        return True
    return any(o["loai"] in OPEN_TYPES and _adjacent(room, o) for o in rooms if o is not room)


def code_checks(state: dict) -> tuple[list, list, list]:
    """Trả về (danh sách kiểm tra, lỗi, cảnh báo)."""
    brief, program, layout, area = state["brief"], state["program"], state["layout"], state["area_table"]
    rules = load_rules()
    checks, issues, warns = [], [], []
    gara = brief["yeu_cau_phong"].get("gara")

    def add(muc, hien_tai, cho_phep, dat, query, issue=None):
        c = {"muc": muc, "hien_tai": hien_tai, "cho_phep": cho_phep, "dat": dat,
             "trich_dan": rag.cite(query) if query else None}
        checks.append(c)
        if not dat and issue:
            issues.append({**issue, "muc": muc, "hien_tai": hien_tai, "cho_phep": cho_phep,
                           "trich_dan": c["trich_dan"]})

    # 1. Mật độ xây dựng
    lot = area["dien_tich_dat"]
    dmax = max_density(lot)
    d = area["mat_do_xay_dung"]
    allowed_m2 = round(dmax * lot, 2)
    add("Mật độ xây dựng", _pct(d), f"≤ {_pct(dmax)}", d <= dmax + 1e-4,
        f"mật độ xây dựng thuần tối đa lô đất nhà ở riêng lẻ {lot:.0f} m²",
        {"loai": "Quy chuẩn", "ma": "MAT_DO", "du_lieu": {"cho_phep_m2": allowed_m2},
         "noi_dung": f"Diện tích xây dựng {vf(area['dien_tich_xay_dung'])} m² vượt mức {vf(allowed_m2)} m²",
         "de_xuat": f"Thêm sân sau khoảng {vf((area['dien_tich_xay_dung'] - allowed_m2) / layout['lot']['w'])} m"})
    # 2. Số tầng
    fmax = rules["so_tang_toi_da"]["gia_tri"]
    add("Số tầng", f"{area['so_tang']} tầng", f"≤ {fmax} tầng", area["so_tang"] <= fmax, "số tầng chiều cao công trình",
        {"loai": "Quy chuẩn", "ma": "SO_TANG", "noi_dung": "Vượt số tầng cho phép", "de_xuat": "Giảm 1 tầng"})
    # 3. Chiều cao tầng
    h = rules["chieu_cao_tang"]
    hs = layout["heights"]
    ok_h = h["tang_1_min"] <= hs[0] <= h["tang_1_max"] and all(h["tang_khac_min"] <= x <= h["tang_khac_max"]
                                                              for x in hs[1:])
    thong_thuy = min(hs) - h["chieu_day_san"] - 0.1
    add("Chiều cao tầng", " / ".join(vf(x) for x in hs) + " m",
        f"T1 {h['tang_1_min']}–{h['tang_1_max']} m; tầng khác {h['tang_khac_min']}–{h['tang_khac_max']} m",
        ok_h, "chiều cao tầng nhà ở liền kề",
        {"loai": "Quy chuẩn", "ma": "CHIEU_CAO_TANG", "noi_dung": "Chiều cao tầng ngoài giới hạn",
         "de_xuat": "Điều chỉnh chiều cao tầng"})
    add("Chiều cao thông thủy", f"{vf(thong_thuy, 2)} m", f"≥ {h['thong_thuy_min']} m", thong_thuy >= h["thong_thuy_min"],
        "chiều cao thông thủy phòng ở", {"loai": "Quy chuẩn", "ma": "CHIEU_CAO_TANG",
                                        "noi_dung": "Thông thủy thấp", "de_xuat": "Tăng chiều cao tầng"})
    # 4. Cầu thang
    st, cr = layout["stair"], rules["cau_thang"]
    worst = max(st["cac_tang"], key=lambda f: f["bac_cao"])
    add("Bề rộng vế thang", f"{vf(st['ve_rong'], 2)} m", f"≥ {cr['be_rong_ve_min']} m", st["ve_rong"] >= cr["be_rong_ve_min"],
        "chiều rộng vế thang nhà ở riêng lẻ", {"loai": "Quy chuẩn", "ma": "CAU_THANG", "noi_dung": "Vế thang hẹp",
                                              "de_xuat": "Tăng bề rộng thang"})
    add("Chiều cao bậc thang", f"{worst['bac_cao'] * 1000:.0f} mm", f"≤ {cr['bac_cao_max'] * 1000:.0f} mm",
        worst["bac_cao"] <= cr["bac_cao_max"], "chiều cao bậc thang",
        {"loai": "Quy chuẩn", "ma": "CAU_THANG", "noi_dung": "Bậc thang cao", "de_xuat": "Tăng số bậc"})
    add("Chiều rộng bậc thang", f"{worst['bac_rong'] * 1000:.0f} mm", f"≥ {cr['bac_rong_min'] * 1000:.0f} mm",
        worst["bac_rong"] >= cr["bac_rong_min"], "chiều rộng mặt bậc", None)
    add("Công thức 2h + b", f"{worst['blondel']:.3f} m", f"{cr['blondel_min']}–{cr['blondel_max']} m",
        cr["blondel_min"] <= worst["blondel"] <= cr["blondel_max"], "kích thước bậc 2h + b", None)
    max_steps = max(max(f["bac_ve_1"], f["bac_ve_2"]) for f in st["cac_tang"])
    add("Số bậc mỗi vế", f"{max_steps} bậc", f"≤ {cr['so_bac_ve_max']} bậc", max_steps <= cr["so_bac_ve_max"],
        "mỗi vế thang không quá bậc chiếu nghỉ", None)

    # 5. Kích thước tối thiểu phòng + chiếu sáng
    small = []
    dark = []
    for k, fl in layout["floors"].items():
        for r in fl["rooms"]:
            m = min_room(r["loai"], gara)
            if m:
                need_a = m.get("dien_tich", 0)
                need_c = m.get("canh", 0)
                short_side = min(r["w"], r["h"])
                if r["dien_tich"] + 1e-6 < need_a or short_side + 1e-6 < need_c:
                    small.append((k, r, need_a, need_c))
            if r["loai"] in NEED_LIGHT_TYPES and not has_daylight(r, fl["rooms"], layout):
                dark.append((k, r))
    add("Diện tích, kích thước tối thiểu phòng",
        "Đủ" if not small else f"{len(small)} phòng nhỏ hơn quy định", "Theo TCVN 4451:2012", not small,
        "diện tích kích thước tối thiểu phòng ngủ phòng khách bếp")
    for k, r, need_a, need_c in small:
        issues.append({"loai": "Quy chuẩn", "ma": "PHONG_NHO", "muc": "Diện tích phòng tối thiểu",
                       "noi_dung": f"{r['ten']} tầng {k}: {vf(r['dien_tich'])} m², cạnh ngắn {vf(min(r['w'], r['h']), 2)} m",
                       "hien_tai": f"{vf(r['dien_tich'])} m²", "cho_phep": f"≥ {need_a} m², cạnh ≥ {need_c} m",
                       "de_xuat": f"Tăng diện tích {r['ten']}", "du_lieu": {"tang": int(k), "phong": r["ten"],
                                                                           "can": need_a}})
    must = set(rules["chieu_sang_bat_buoc"])
    dark_must = [(k, r) for k, r in dark if r["loai"] in must]
    add("Chiếu sáng tự nhiên phòng ở", "Đủ" if not dark_must else f"{len(dark_must)} phòng thiếu sáng",
        "Phòng ngủ, làm việc chiếu sáng trực tiếp", not dark_must, "phòng ở chiếu sáng tự nhiên trực tiếp giếng trời")
    for k, r in dark:
        item = {"loai": "Quy chuẩn", "ma": "THIEU_SANG", "muc": "Chiếu sáng tự nhiên",
                "noi_dung": f"{r['ten']} tầng {k} không tiếp giáp mặt thoáng / giếng trời",
                "de_xuat": f"Dời {r['ten']} sát giếng trời hoặc mặt tiền",
                "du_lieu": {"tang": int(k), "phong": r["ten"]}}
        (issues if r["loai"] in must else warns).append(item)

    # 6. Kiểm tra kỹ thuật bằng code
    overlaps = []
    gaps = []
    stair_rects = []
    for k, fl in layout["floors"].items():
        rooms = [r for r in fl["rooms"] if r["loai"] != "san"]
        for i, a in enumerate(rooms):
            for b in rooms[i + 1:]:
                if _overlap(a, b) > 1e-4:
                    overlaps.append(f"T{k}: {a['ten']} × {b['ten']}")
        total = sum(r["dien_tich"] for r in rooms)
        if abs(total - area["dien_tich_xay_dung"]) > 0.5:
            gaps.append(f"T{k}: tổng {vf(total, 2)} ≠ {vf(area['dien_tich_xay_dung'], 2)}")
        s = next(r for r in rooms if r["loai"] == "thang")
        stair_rects.append((s["x"], s["y"], s["w"], s["h"]))
    add("Không chồng lấn phòng", "Đạt" if not overlaps else "; ".join(overlaps[:3]), "0 chồng lấn", not overlaps,
        None, {"loai": "Kỹ thuật", "ma": "KHONG_DU_CHO", "noi_dung": "Phòng chồng lấn",
                           "de_xuat": "Bố trí lại"})
    add("Phủ kín diện tích xây dựng", "Đạt" if not gaps else "; ".join(gaps[:3]), "Tổng phòng = DT xây dựng",
        not gaps, None, {"loai": "Kỹ thuật", "ma": "KHONG_DU_CHO", "noi_dung": "Có khoảng trống",
                                        "de_xuat": "Bố trí lại"})
    aligned = len(set(stair_rects)) == 1
    add("Cầu thang thẳng hàng các tầng", "Thẳng hàng" if aligned else "Lệch", "Thẳng hàng", aligned, None,
        {"loai": "Kỹ thuật", "ma": "KHONG_DU_CHO", "noi_dung": "Cầu thang lệch giữa các tầng", "de_xuat": "Cố định lõi"})
    add("Đủ chỗ bố trí phòng", "Đạt" if layout["feasible"] else "Thiếu chiều sâu", "Mọi phòng ≥ kích thước tối thiểu",
        layout["feasible"], None, {"loai": "Kỹ thuật", "ma": "KHONG_DU_CHO",
                                                     "noi_dung": "Không đủ chiều sâu", "de_xuat": "Giảm diện tích phòng"})

    # 7. Nhất quán với brief
    yc = brief["yeu_cau_phong"]
    cnt = area["so_phong"]
    want = {"ngu": yc["phong_ngu"], "tho": 1 if yc.get("phong_tho") else 0, "gara": 1 if yc.get("gara") else 0,
            "lam_viec": 1 if yc.get("phong_lam_viec") else 0}
    miss = [f"{k}: {cnt.get(k, 0)}/{v}" for k, v in want.items() if cnt.get(k, 0) < v]
    add("Số phòng khớp yêu cầu", "Đủ" if not miss else ", ".join(miss), "Theo brief", not miss, None,
        {"loai": "Nhất quán", "ma": "THIEU_PHONG", "noi_dung": "Thiếu phòng so với yêu cầu: " + ", ".join(miss),
         "de_xuat": "Bổ sung phòng"})
    return checks, issues, warns


def fengshui_checks(state: dict) -> tuple[dict, list, list, list]:
    brief, layout = state["brief"], state["layout"]
    gd, ld = brief["gia_dinh"], brief["lo_dat"]
    info = fengshui.analyze(gd.get("nam_sinh_chu_nha"), gd.get("gioi_tinh_chu_nha", "nam"), ld["huong"])
    checks, issues, warns = [], [], []
    if info.get("co_du_lieu") and not info["hop_huong"]:
        warns.append({"loai": "Phong thủy", "muc": "Hướng nhà",
                      "noi_dung": f"Hướng {ld['huong']} là {info['sao_huong_nha']} với cung {info['cung_menh']}",
                      "de_xuat": f"Xoay cửa chính / bàn thờ về {', '.join(info['huong_tot'])}"})
    floors = layout["floors"]
    n = layout["so_tang"]
    # WC trên phòng thờ
    wc_over = []
    for k in range(1, n):
        for tho in (r for r in floors[str(k)]["rooms"] if r["loai"] == "tho"):
            for wc in (r for r in floors[str(k + 1)]["rooms"] if r["loai"] == "wc"):
                if _overlap(tho, wc) > 0.05:
                    wc_over.append((k, k + 1))
    checks.append({"noi_dung": "Không đặt WC phía trên phòng thờ", "dat": not wc_over})
    for k, k2 in wc_over:
        issues.append({"loai": "Phong thủy", "ma": "WC_TREN_THO", "muc": "Vị trí WC",
                       "noi_dung": f"WC tầng {k2} nằm trên phòng thờ tầng {k}",
                       "de_xuat": f"Dời WC tầng {k2} ra phía sau", "du_lieu": {"tang_wc": k2}})
    # Bếp kề WC
    bep_wc = []
    for k, fl in floors.items():
        for bep in (r for r in fl["rooms"] if r["loai"] == "bep"):
            for wc in (r for r in fl["rooms"] if r["loai"] == "wc"):
                if _adjacent(bep, wc):
                    bep_wc.append(int(k))
    checks.append({"noi_dung": "Bếp không kề sát / đối diện WC", "dat": not bep_wc})
    for k in bep_wc:
        issues.append({"loai": "Phong thủy", "ma": "BEP_KE_WC", "muc": "Vị trí bếp",
                       "noi_dung": f"Bếp tầng {k} chung tường với WC", "de_xuat": "Đổi vị trí WC",
                       "du_lieu": {"tang": k}})
    # Phòng thờ ở tầng trên cùng
    tho_floor = [int(k) for k, fl in floors.items() if any(r["loai"] == "tho" for r in fl["rooms"])]
    if tho_floor:
        ok = max(tho_floor) == n
        checks.append({"noi_dung": "Phòng thờ đặt ở tầng trên cùng", "dat": ok})
        if not ok:
            warns.append({"loai": "Phong thủy", "muc": "Phòng thờ",
                          "noi_dung": "Phòng thờ không ở tầng trên cùng", "de_xuat": "Ưu tiên đặt phòng thờ tầng trên cùng"})
    # WC ở tâm nhà
    b = layout["building"]
    cx, cy = b["w"] / 2, b["y"] + b["l"] / 2
    center_wc = [k for k, fl in floors.items() if (r := room_at(fl["rooms"], cx, cy)) and r["loai"] == "wc"]
    checks.append({"noi_dung": "WC không nằm ở tâm nhà", "dat": not center_wc})
    if center_wc:
        warns.append({"loai": "Phong thủy", "muc": "WC giữa nhà",
                      "noi_dung": f"WC tầng {', '.join(center_wc)} nằm ở tâm nhà",
                      "de_xuat": "Có thể dời WC lệch khỏi tâm nhà ở giai đoạn thiết kế kỹ thuật"})
    return info, checks, issues, warns


def review_design(state: dict) -> dict:
    checks, issues, warns = code_checks(state)
    fs_info, fs_checks, fs_issues, fs_warns = fengshui_checks(state)
    issues += fs_issues
    warns += fs_warns
    # loại trùng mã + dữ liệu
    seen, uniq = set(), []
    for i in issues:
        key = (i.get("ma"), str(i.get("du_lieu")), i.get("noi_dung"))
        if key not in seen:
            seen.add(key)
            uniq.append(i)
    review = {"dat": not uniq, "loi": uniq, "canh_bao": warns, "kiem_tra": checks, "phong_thuy": fs_info,
              "phong_thuy_bo_tri": fs_checks, "vong": state.get("iteration", 0)}
    if uniq:
        txt = invoke_text("Bạn là kỹ sư thẩm tra thiết kế nhà ở Việt Nam.",
                          "Tóm tắt ngắn gọn (≤ 60 từ) các lỗi sau cho kiến trúc sư sửa:\n" +
                          "\n".join(f"- {i['muc']}: {i['noi_dung']} (đề xuất: {i['de_xuat']})" for i in uniq))
        review["nhan_xet"] = txt or "; ".join(f"{i['muc']}: {i['noi_dung']}" for i in uniq)
    else:
        review["nhan_xet"] = f"Phương án đạt {len(checks)} tiêu chí kiểm tra; {len(warns)} khuyến nghị."
    return review


@agent_node("reviewer")
def run(state: dict) -> dict:
    review = review_design(state)
    it = state.get("iteration", 0)
    max_it = state.get("max_iterations", 3)
    if review["dat"]:
        n_ok = sum(c["dat"] for c in review["kiem_tra"])
        return {"review": review, "route": "cost_estimator", "remaining_issues": [],
                "_summary": f"✅ Đạt {n_ok}/{len(review['kiem_tra'])} tiêu chí, {len(review['canh_bao'])} khuyến nghị",
                "_to": "cost_estimator", "_output": review}
    first = review["loi"][0]
    short = f"{first['muc']} {first.get('hien_tai', '')} {('> ' + first['cho_phep'].lstrip('≤ ')) if first.get('cho_phep', '').startswith('≤') else ''}".strip()
    extra = f" (+{len(review['loi']) - 1} lỗi)" if len(review["loi"]) > 1 else ""
    if it < max_it:
        return {"review": review, "route": "architect", "feedback": review["loi"], "feedback_source": "reviewer",
                "iteration": it + 1, "_summary": f"❌ {short or first['noi_dung']}{extra}", "_to": "architect",
                "_feedback": True, "_output": review}
    return {"review": review, "route": "cost_estimator", "remaining_issues": review["loi"],
            "_summary": f"⚠️ Hết {max_it} vòng sửa, còn {len(review['loi'])} lỗi – chuyển dự toán",
            "_to": "cost_estimator", "_feedback": True, "_output": review}
