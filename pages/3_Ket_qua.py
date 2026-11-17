"""Trang Kết quả: xem trước và tải 3 sản phẩm; lịch sử thiết kế (mục 5.2 kế hoạch)."""
from pathlib import Path

import streamlit as st

import ui_theme as ui
from monitoring import events
from monitoring.runner import manager
from tools.docx_writer import vn_num, vnd
from ui_common import RUN_STATUS, label, setup

setup("Kết quả")

runs = events.list_runs(50)
if not runs:
    ui.page_header("Bàn giao", "Kết quả", "Chưa có lượt thiết kế nào.")
    st.stop()
ids = [r["run_id"] for r in runs]
cur = st.session_state.get("run_id", ids[0])
fmt = {r["run_id"]: f"{r['run_id']} · {RUN_STATUS.get(r['status'], r['status'])} · {r['request'][:70]}" for r in runs}

h1, h2 = st.columns([1.4, 1], vertical_alignment="bottom")
with h1:
    ui.page_header("Bàn giao hồ sơ", "Kết quả", "Xem trước và tải 3 sản phẩm của lượt thiết kế.")
with h2:
    rid = st.selectbox("Lượt thiết kế (lịch sử)", ids, index=ids.index(cur) if cur in ids else 0, format_func=fmt.get)
st.session_state["run_id"] = rid
run = manager.get(rid)
state = run.state()
files = state.get("final_files") or {}
if not files:
    st.warning("Lượt thiết kế này chưa hoàn thành – chưa có đủ sản phẩm.", icon=":material/hourglass_top:")
    st.stop()

area, cost, review = state["area_table"], state.get("cost", {}), state.get("review", {})
m = st.columns(5)
m[0].metric("Số tầng", area["so_tang"])
m[1].metric("Tổng DT sàn", f"{vn_num(area['tong_dien_tich_san'])} m²")
m[2].metric("Mật độ XD", f"{vn_num(area['mat_do_xay_dung'] * 100)}%")
m[3].metric("Tổng chi phí", f"{vn_num(cost.get('tong_chi_phi', 0) / 1e9, 2)} tỷ",
            f"{cost.get('vuot_pct', 0) * 100:+.1f}% ngân sách", delta_color="inverse")
m[4].metric("Quy chuẩn", "Đạt" if review.get("dat") else "Còn lỗi", f"{state.get('iteration', 0)} vòng sửa",
            delta_color="off")

ui.section("Tải xuống", "Ba sản phẩm dùng chung một nguồn số liệu.")
FILES = [
    ("ban_ve_pdf", "picture_as_pdf", "Bộ bản vẽ", "PDF đóng tập, khổ A3", "application/pdf"),
    ("ban_ve_dxf_zip", "folder_zip", "Bản vẽ AutoCAD", "DXF từng bản vẽ (ZIP)", "application/zip"),
    ("thuyet_minh_docx", "description", "Thuyết minh", "DOCX – 10 mục",
     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("du_toan_xlsx", "table_view", "Dự toán", "XLSX có công thức",
     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
]
cols = st.columns(4)
for col, (key, ic, title, desc, mime) in zip(cols, FILES):
    p = Path(files.get(key, ""))
    with col.container(border=True):
        ui.html_block(f'<div class="aa-file">{ui.icon(ic)}<div><b>{title}</b><span>{desc}</span></div></div>')
        if p.exists():
            st.download_button(p.name, p.read_bytes(), p.name, mime, width="stretch", icon=":material/download:",
                               key=f"dl_{key}")
        else:
            st.caption("Không tìm thấy tệp.")

st.write("")
t1, t2, t3, t4 = st.tabs([":material/architecture: Bản vẽ", ":material/description: Mô tả dự án",
                          ":material/payments: Chi phí", ":material/timeline: Timeline"])
with t1:
    sheets = state["drawings"]["sheets"]
    names = [f"{s['so_hieu']} · {s['ten']}" for s in sheets]
    i = st.pills("Bản vẽ", range(len(sheets)), format_func=lambda k: names[k], default=0,
                 label_visibility="collapsed") or 0
    st.caption(f"{names[i]} · tỉ lệ {sheets[i]['ti_le']}")
    st.image(sheets[i]["png"], width="stretch")
with t2:
    with st.container(border=True):
        ui.html_block('<div class="aa-eyebrow" style="color:#667085">Ý tưởng thiết kế</div>')
        st.write(state.get("concept", ""))
    c1, c2 = st.columns([1.2, 1], gap="large")
    with c1:
        ui.section("Thống kê diện tích")
        rows = []
        for t in area["tang"]:
            for ph in t["phong"]:
                rows.append({"Tầng": t["tang"], "Phòng": ph["ten"], "Kích thước (m)": ph["kich_thuoc"],
                             "Diện tích (m²)": ph["dien_tich"]})
        st.dataframe(rows, hide_index=True, width="stretch", height=380)
    with c2:
        ui.section("Kiểm tra quy chuẩn")
        st.dataframe([{"Tiêu chí": c["muc"], "Phương án": c["hien_tai"], "Yêu cầu": c["cho_phep"],
                       "Kết quả": "✅" if c["dat"] else "❌"} for c in review.get("kiem_tra", [])],
                     hide_index=True, width="stretch", height=380)
    fs = review.get("phong_thuy", {})
    if fs.get("co_du_lieu"):
        with st.container(border=True):
            ui.html_block('<div class="aa-eyebrow" style="color:#667085">Tư vấn phong thủy</div>'
                          + ui.pill(f"Cung {fs['cung_menh']} · {fs['nhom']}", "brand") + " "
                          + ui.pill(f"Hướng {fs['huong_nha']} – {fs['sao_huong_nha']}",
                                    "success" if fs["hop_huong"] else "warning"))
            st.caption(f"Chủ nhà {fs['nam_sinh']} ({fs['can_chi']}). {fs['goi_y_bep']} {fs['goi_y_ban_tho']}")
    for issue in state.get("remaining_issues") or []:
        st.error(f"Lỗi còn tồn tại: {issue['muc']} – {issue['noi_dung']}", icon=":material/error:")
with t3:
    if cost:
        c1, c2 = st.columns([1.6, 1], gap="large")
        with c1:
            st.dataframe([{"Hạng mục": it["hang_muc"], "Khối lượng": f"{vn_num(it['kl'], 2)} {it['don_vi']}",
                           "Đơn giá": vnd(it["don_gia"]), "Thành tiền": vnd(it["thanh_tien"])}
                          for it in cost["hang_muc"]]
                         + [{"Hạng mục": "Dự phòng", "Khối lượng": "", "Đơn giá": f"{cost['du_phong_pct'] * 100:.0f}%",
                             "Thành tiền": vnd(cost["du_phong"])},
                            {"Hạng mục": "TỔNG CỘNG", "Khối lượng": "", "Đơn giá": "",
                             "Thành tiền": vnd(cost["tong_chi_phi"])}],
                         hide_index=True, width="stretch")
        with c2:
            with st.container(border=True):
                ui.html_block('<div class="aa-eyebrow" style="color:#667085">Ghi chú dự toán</div>')
                st.write(cost.get("ghi_chu", ""))
            with st.container(border=True):
                ui.html_block('<div class="aa-eyebrow" style="color:#667085">Phương án tiết kiệm</div>'
                              + ui.kv([(s["phuong_an"], "~" + vnd(s["tiet_kiem"])) for s in cost["tiet_kiem"]]))
with t4:
    with st.container(border=True):
        ui.timeline([e for e in events.get_events(rid) if e["status"] in ("done", "error")], label)
