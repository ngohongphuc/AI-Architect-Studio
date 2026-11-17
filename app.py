"""Điểm vào Streamlit – điều hướng có tên tiếng Việt và icon.   Chạy:  streamlit run app.py"""
import streamlit as st

pages = [
    st.Page("views/home.py", title="Trang chủ", icon=":material/space_dashboard:", default=True),
    st.Page("pages/1_Thiet_ke.py", title="Thiết kế", icon=":material/edit_square:", url_path="Thiet_ke"),
    st.Page("pages/2_Quan_ly_agent.py", title="Quản lý agent", icon=":material/hub:", url_path="Quan_ly_agent"),
    st.Page("pages/3_Ket_qua.py", title="Kết quả", icon=":material/inventory_2:", url_path="Ket_qua"),
]
st.navigation(pages).run()
