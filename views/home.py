"""Trang chủ (được app.py điều hướng tới)."""
import streamlit as st

import ui_theme as ui
from llm import mode_label
from monitoring import events
from ui_common import RUN_STATUS, setup

setup("Trang chủ")

ui.html_block(f"""
<div class="aa-hero">
  <div class="aa-eyebrow">Văn phòng kiến trúc ảo · Multi-agent</div>
  <h1 class="aa-title" style="font-size:2.5rem">AI Architect Studio</h1>
  <div class="aa-sub" style="font-size:1.0625rem">Nhập yêu cầu bằng tiếng Việt. Năm agent phối hợp, kiểm tra chéo và
  tự sửa lỗi (tối đa 3 vòng) để xuất bộ bản vẽ, thuyết minh và dự toán dùng chung một nguồn số liệu.</div>
  <div class="aa-flow">
    {ui.pill("Yêu cầu", "neutral")}<span style="color:#98A2B3">→</span>
    {ui.pill("Brief", "brand")}<span style="color:#98A2B3">→</span>
    {ui.pill("Phương án", "brand")}<span style="color:#98A2B3">→</span>
    {ui.pill("Bản vẽ", "brand")}<span style="color:#98A2B3">→</span>
    {ui.pill("Kiểm định", "warning")}<span style="color:#98A2B3">→</span>
    {ui.pill("Dự toán", "warning")}<span style="color:#98A2B3">→</span>
    {ui.pill("3 sản phẩm", "success")}
  </div>
</div>""")
st.write("")
c1, c2, c3, _ = st.columns([1.2, 1, 1, 2])
c1.page_link("pages/1_Thiet_ke.py", label="Bắt đầu thiết kế", icon=":material/add_circle:")
c2.page_link("pages/2_Quan_ly_agent.py", label="Quản lý agent", icon=":material/hub:")
c3.page_link("pages/3_Ket_qua.py", label="Kết quả", icon=":material/inventory_2:")
st.caption(mode_label())

ui.section("Đội ngũ agent", "Mỗi agent đảm nhận một vai trò như trong văn phòng kiến trúc thật.")
cols = st.columns(5)
for col, (ic, name, role) in zip(cols, [
    ("badge", "Chủ nhiệm", "Phân tích brief, điều phối, viết thuyết minh và đóng gói hồ sơ."),
    ("architecture", "Kiến trúc sư", "Ý tưởng, 3 phương án công năng, xử lý góp ý và phản hồi."),
    ("draw", "Họa viên", "Thuật toán bố trí, xuất bản vẽ PDF + DXF có khung tên."),
    ("fact_check", "Kiểm định viên", "Quy chuẩn QCVN/TCVN (RAG), kiểm tra kỹ thuật, phong thủy."),
    ("payments", "Kỹ sư dự toán", "Diện tích quy đổi, chi phí theo hạng mục, XLSX có công thức."),
]):
    col.markdown(f'<div class="aa-feature">{ui.icon(ic)}<h4>{name}</h4><p>{role}</p></div>', unsafe_allow_html=True)

runs = events.list_runs(8)
if runs:
    st.write("")
    ui.section("Lượt thiết kế gần đây")
    st.dataframe([{"Mã": r["run_id"], "Thời điểm": r["created"].replace("T", " "),
                   "Trạng thái": RUN_STATUS.get(r["status"], r["status"]), "Yêu cầu": r["request"][:110]}
                  for r in runs], width="stretch", hide_index=True,
                 column_config={"Yêu cầu": st.column_config.TextColumn(width="large")})
