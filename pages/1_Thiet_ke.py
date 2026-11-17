"""Trang Thiết kế: nhập yêu cầu, bấm Thiết kế, theo dõi nhanh tiến trình."""
import streamlit as st

import ui_theme as ui
from config import MAX_ITERATIONS
from graph import APPROVAL_LABELS
from llm import mode_label
from main import SAMPLE
from monitoring import events
from monitoring.runner import manager
from ui_common import (agent_stats, approval_box, auto_refresh, current_run, label, run_meta_html, run_stepper,
                       setup)

setup("Thiết kế")
ui.page_header("Bước 1 · Yêu cầu", "Thiết kế mới",
               "Mô tả lô đất, gia đình, số phòng, ngân sách và phong cách bằng lời tự nhiên.",
               ui.pill(mode_label(), "brand"))

EXAMPLES = {
    "Mẫu trong kế hoạch (5×20, Hà Nội)": SAMPLE,
    "Nhà nhỏ 4×15, Đà Nẵng": "Đất 4x15m hướng Tây ở Đà Nẵng, vợ chồng trẻ sinh 1995, cần 2 phòng ngủ, ngân sách 1,8 tỷ, "
                             "phong cách tối giản.",
    "Nhà lớn 6×25, gara ô tô": "Lô đất 6x25m hướng Bắc tại TP.HCM, gia đình 6 người có ông bà, chủ nhà sinh năm 1980. "
                               "Cần 4 phòng ngủ, phòng thờ, phòng làm việc, gara ô tô. Ngân sách 6 tỷ, phong cách hiện đại.",
}
POINTS = {k: v for k, v in APPROVAL_LABELS.items()}

left, right = st.columns([1.75, 1], gap="large")
with left:
    with st.container(border=True):
        ex = st.selectbox("Bắt đầu từ ví dụ", list(EXAMPLES))
        req = st.text_area("Yêu cầu thiết kế", EXAMPLES[ex], height=170,
                           help="Ví dụ: kích thước lô, hướng, tỉnh/thành, số người, năm sinh chủ nhà, số phòng ngủ, "
                                "phòng thờ, gara, ngân sách, phong cách.")
with right:
    with st.container(border=True):
        ui.html_block('<div class="aa-eyebrow" style="color:#667085">Cấu hình lượt chạy</div>')
        mode = st.radio("Chế độ chạy", ["Tự động hoàn toàn", "Duyệt thủ công tại tất cả các bước",
                                        "Tự chọn bước cần duyệt"])
        points: list = []
        if mode == "Duyệt thủ công tại tất cả các bước":
            points = list(POINTS)
        elif mode == "Tự chọn bước cần duyệt":
            points = st.multiselect("Dừng chờ duyệt sau các bước", list(POINTS), default=["architect", "reviewer"],
                                    format_func=POINTS.get)
        max_it = st.number_input("Số vòng sửa tối đa", 0, 5, MAX_ITERATIONS)
        if points:
            st.caption("Tại mỗi điểm duyệt: đồng ý, chạy lại agent, trao đổi với Kiến trúc sư, chọn / chỉnh sửa "
                       "phương án, sửa yêu cầu hoặc dừng.")
        if st.button("Bắt đầu thiết kế", type="primary", width="stretch", disabled=not req.strip(),
                     icon=":material/rocket_launch:"):
            run = manager.start(req.strip(), max_iterations=int(max_it), approval_points=points)
            st.session_state["run_id"] = run.run_id
            st.rerun()

run = current_run()
if run:
    st.divider()
    head, links = st.columns([3, 1.4], vertical_alignment="bottom")
    with head:
        ui.section("Tiến trình lượt thiết kế")
        ui.html_block(f'<div class="aa-meta" style="margin-top:8px">{run_meta_html(run)}</div>')
    with links:
        st.page_link("pages/2_Quan_ly_agent.py", label="Mở trang quản lý agent", icon=":material/hub:")
        if run.status == "done":
            st.page_link("pages/3_Ket_qua.py", label="Xem và tải kết quả", icon=":material/inventory_2:")
    stats = agent_stats(run.run_id)
    run_stepper(run, stats)
    approval_box(run, "tk")
    if run.status == "error":
        st.error(run.error, icon=":material/error:")
    if run.status == "done":
        st.success("Đã có đủ 3 sản phẩm: bản vẽ, thuyết minh và dự toán.", icon=":material/task_alt:")
    with st.container(border=True):
        ui.html_block('<div class="aa-eyebrow" style="color:#667085">Hoạt động gần đây</div>')
        evs = [e for e in events.get_events(run.run_id) if e["status"] in ("done", "error")][-8:]
        ui.timeline(evs[::-1], label)
auto_refresh(run)
