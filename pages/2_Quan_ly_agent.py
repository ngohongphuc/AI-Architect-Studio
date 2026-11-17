"""Trang Quản lý agent: theo dõi và điều khiển chi tiết từng agent (mục 5.1 kế hoạch)."""
import io
import json

import streamlit as st

import ui_theme as ui
from config import AGENT_ORDER
from llm import agent_model_label
from monitoring import events
from monitoring.tracker import tracker
from ui_common import (agent_stats, approval_box, auto_refresh, current_run, fmt_time, label, run_meta_html,
                       run_stepper, setup)

setup("Quản lý agent")
run = current_run()
if run is None:
    ui.page_header("Điều phối", "Quản lý agent", "Chưa có lượt thiết kế nào.")
    st.page_link("pages/1_Thiet_ke.py", label="Bắt đầu thiết kế", icon=":material/add_circle:")
    st.stop()

state = run.state()
mode = (("Duyệt sau: " + ", ".join(label(a) for a in state["approval_points"])) if state.get("approval_points")
        else ("Có duyệt thủ công" if state.get("manual_review") else "Tự động hoàn toàn"))

# ---------------- 1. Thanh điều khiển tổng ----------------
h1, h2 = st.columns([3, 1.6], vertical_alignment="bottom")
with h1:
    ui.page_header("Điều phối · Multi-agent", "Quản lý agent", mode, run_meta_html(run))
with h2:
    c = st.columns(3)
    if run.status == "running":
        if c[0].button("Tạm dừng", width="stretch", icon=":material/pause:"):
            run.pause(); st.toast("Sẽ tạm dừng sau khi agent hiện tại chạy xong")
    elif run.status == "paused":
        if c[0].button("Tiếp tục", width="stretch", type="primary", icon=":material/play_arrow:"):
            run.resume(); st.rerun()
    if c[1].button("Dừng", width="stretch", icon=":material/stop_circle:",
                   disabled=run.status not in ("running", "paused", "awaiting_approval")):
        run.stop(); st.rerun()
    if c[2].button("Làm mới", width="stretch", icon=":material/refresh:"):
        st.rerun()

# ---------------- 2. Tiến trình tổng thể ----------------
stats = agent_stats(run.run_id)
run_stepper(run, stats)
tokens = run.tokens()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Vòng sửa", f"{state.get('iteration', 0)} / {state.get('max_iterations', 3)}")
m2.metric("Thời gian", fmt_time(run.time_running()))
m3.metric("Token", f"{tokens:,}".replace(",", "."))
m4.metric("Chi phí API ước tính", f"~${run.cost_usd():.3f}")
approval_box(run, "ql")
if run.status == "error":
    st.error(f"Lỗi: {run.error}", icon=":material/error:")

# ---------------- 3. Thẻ trạng thái 5 agent ----------------
ui.section("Agent", "Trạng thái, model đang dùng và thống kê từng agent.")
cols = st.columns(5)
for i, (col, a) in enumerate(zip(cols, AGENT_ORDER), start=1):
    s = stats[a]
    status = s["status"]
    if status in ("running", "revising") and run.status != "running":
        status = "paused"
    with col.container(border=True):
        ui.html_block(ui.agent_card_html(i, label(a), a, status, agent_model_label(a), s["runs"], s["duration"],
                                         s["tokens"], s["errors"] if a in ("reviewer", "cost_estimator") else 0))
        b1, b2 = st.container(), st.container()
        if b1.button("Xem chi tiết", key=f"view_{a}", width="stretch", icon=":material/visibility:",
                     type="primary" if st.session_state.get("detail_agent", "reviewer") == a else "secondary"):
            st.session_state["detail_agent"] = a
            st.rerun()
        if b2.button("Chạy lại", key=f"rerun_{a}", width="stretch", icon=":material/replay:",
                     help="Chạy lại agent này và các bước sau",
                     disabled=run.status in ("running",) or s["runs"] == 0):
            if run.rerun_agent(a):
                st.toast(f"Chạy lại {label(a)}")
                st.rerun()
            else:
                st.warning("Không tìm thấy checkpoint để chạy lại")

# ---------------- 4. Dòng thời gian + 5. Chi tiết agent ----------------
st.write("")
tl, detail = st.columns([1, 1.5], gap="large")
with tl:
    evs = [e for e in events.get_events(run.run_id) if e["status"] in ("done", "error")]
    ui.section("Dòng thời gian", "Phản hồi lỗi được đánh dấu đỏ.")
    with st.container(height=520, border=True):
        ui.timeline(evs, label)
    buf = io.StringIO()
    buf.write("time,agent,to_agent,summary,status,version,tokens,duration_s,feedback\n")
    for e in evs:
        buf.write(",".join(str(e[k]).replace(",", ";") for k in
                           ("time", "agent", "to_agent", "summary", "status", "version", "tokens", "duration_s",
                            "feedback")) + "\n")
    st.download_button("Xuất timeline (CSV)", buf.getvalue().encode("utf-8-sig"), f"timeline_{run.run_id}.csv",
                       "text/csv", icon=":material/download:", width="stretch")

with detail:
    sel = st.session_state.get("detail_agent", "reviewer")
    ui.section(f"Chi tiết · {label(sel)}", "Đầu vào, đầu ra, lịch sử các phiên bản và prompt đã dùng.")
    INPUTS = {
        "project_manager": lambda s: {"user_request": s.get("user_request")},
        "architect": lambda s: {"brief": s.get("brief"), "phan_hoi_gan_nhat": s.get("feedback") or "—"},
        "drafter": lambda s: {"program": s.get("program")},
        "reviewer": lambda s: {"area_table": s.get("area_table"), "layout_core": (s.get("layout") or {}).get("core")},
        "cost_estimator": lambda s: {"area_table": s.get("area_table"),
                                     "ngan_sach": (s.get("brief") or {}).get("ngan_sach")},
    }
    OUTPUTS = {
        "project_manager": lambda s: {"brief": s.get("brief"), "final_files": s.get("final_files")},
        "architect": lambda s: {"concept": s.get("concept"), "program": s.get("program")},
        "drafter": lambda s: {"area_table": s.get("area_table"), "drawings": s.get("drawings")},
        "reviewer": lambda s: s.get("review"),
        "cost_estimator": lambda s: s.get("cost"),
    }
    t_out, t_in, t_hist, t_prompt = st.tabs([":material/output: Đầu ra", ":material/input: Đầu vào",
                                             ":material/history: Lịch sử phiên bản", ":material/terminal: Prompt"])
    with t_in:
        st.json(INPUTS[sel](state) or {}, expanded=1)
    with t_out:
        if sel == "drafter" and state.get("drawings"):
            pngs = [s for s in state["drawings"]["sheets"]]
            choice = st.selectbox("Bản vẽ", [f"{s['so_hieu']} – {s['ten']}" for s in pngs])
            st.image(pngs[[f"{s['so_hieu']} – {s['ten']}" for s in pngs].index(choice)]["png"])
        if sel == "reviewer" and state.get("review"):
            r = state["review"]
            ui.html_block(ui.pill("Đạt" if r["dat"] else "Không đạt", "success" if r["dat"] else "danger")
                          + f'<span style="margin-left:10px;color:#475467">{ui.esc(r.get("nhan_xet", ""))}</span>')
            st.dataframe([{"Tiêu chí": c["muc"], "Phương án": c["hien_tai"], "Yêu cầu": c["cho_phep"],
                           "Kết quả": "✅" if c["dat"] else "❌",
                           "Căn cứ": (c.get("trich_dan") or {}).get("trich", "")} for c in r["kiem_tra"]],
                         hide_index=True, width="stretch")
        with st.expander("Dữ liệu đầu ra (JSON)", expanded=sel not in ("drafter", "reviewer")):
            st.json(OUTPUTS[sel](state) or {}, expanded=1)
    with t_hist:
        hist = [h for h in state.get("history", []) if h["agent"] == sel]
        if not hist:
            st.caption("Chưa có lịch sử.")
        elif sel == "drafter" and len(hist) > 1:
            c1, c2 = st.columns([3, 1])
            vs = c1.multiselect("So sánh phiên bản", [f"v{h['version']}" for h in hist],
                                default=[f"v{hist[0]['version']}", f"v{hist[-1]['version']}"])
            floor = c2.number_input("Tầng", 1, 6, 1)
            cols = st.columns(max(1, len(vs)))
            for c, v in zip(cols, vs):
                h = next(x for x in hist if f"v{x['version']}" == v)
                imgs = (h["output"] or {}).get("mat_bang", [])
                c.markdown(f"**{v}** · mật độ {(h['output'] or {}).get('mat_do', 0) * 100:.0f}% · "
                           f"DT sàn {(h['output'] or {}).get('tong_dien_tich_san', 0):.1f} m²")
                if floor <= len(imgs):
                    c.image(imgs[floor - 1])
        for h in hist:
            with st.expander(f"v{h['version']} · vòng {h['iteration']} · {h['time']} — {h['summary']}"):
                st.json(h["output"] if isinstance(h["output"], (dict, list)) else {"output": h["output"]}, expanded=1)
    with t_prompt:
        prompts = tracker.prompts(run.run_id, sel)
        if not prompts:
            st.caption("Agent chưa gọi LLM trong phiên này (chế độ quy tắc hoặc lượt đã chạy ở phiên trước).")
        for i, p in enumerate(prompts, 1):
            with st.expander(f"Lần gọi {i}"):
                st.code(p["prompt"])
                st.markdown("**Phản hồi**")
                st.code(p["response"])

with st.expander("Nhật ký trạng thái chung (log)", icon=":material/receipt_long:"):
    st.code("\n".join(state.get("log", [])))
    st.download_button("Tải state.json", json.dumps({k: v for k, v in state.items() if k != "history"},
                                                    ensure_ascii=False, indent=1, default=str),
                       f"state_{run.run_id}.json", icon=":material/download:")
auto_refresh(run)
