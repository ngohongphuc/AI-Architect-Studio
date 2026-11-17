"""Hàm dùng chung cho các trang Streamlit."""
from __future__ import annotations

import time

import streamlit as st

from config import AGENT_LABELS, AGENT_ORDER
from monitoring import events
from monitoring.runner import manager

import ui_theme as ui

STATUS_ICON = {k: v[0] for k, v in ui.AGENT_STATUS.items()}
RUN_STATUS = {k: v[0] for k, v in ui.RUN_STATUS_TONE.items()}


def setup(title: str) -> None:
    st.set_page_config(page_title=f"{title} · AI Architect Studio", page_icon=":material/architecture:",
                       layout="wide")
    ui.inject()


def current_run():
    rid = st.session_state.get("run_id")
    if not rid:
        runs = events.list_runs(1)
        if runs:
            rid = runs[0]["run_id"]
            st.session_state["run_id"] = rid
    return manager.get(rid) if rid else None


def agent_stats(run_id: str) -> dict:
    """Thống kê từng agent từ dòng sự kiện."""
    evs = events.get_events(run_id)
    stats = {a: {"status": "waiting", "runs": 0, "tokens": 0, "duration": 0.0, "errors": 0, "last": ""}
             for a in AGENT_ORDER}
    for e in evs:
        a = e["agent"]
        if a not in stats:
            continue
        s = stats[a]
        s["status"] = e["status"]
        if e["status"] == "done":
            s["runs"] += 1
            s["tokens"] += e["tokens"] or 0
            s["duration"] += e["duration_s"] or 0
            s["last"] = e["summary"]
            if e["feedback"]:
                s["errors"] += 1
        elif e["status"] == "error":
            s["last"] = e["summary"]
    return stats


def fmt_time(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    return f"{m:02d}:{s:02d}"


def auto_refresh(run, interval: float = 1.0) -> None:
    if run is not None and run.status == "running":
        time.sleep(interval)
        st.rerun()


# ---------------------------------------------------------------------------
# Khung duyệt thủ công (dùng chung cho mọi điểm duyệt)
# ---------------------------------------------------------------------------
NEXT_LABEL = {"architect": "Kiến trúc sư", "drafter": "Họa viên", "reviewer": "Kiểm định viên",
              "cost_estimator": "Kỹ sư dự toán", "pm_report": "Chủ nhiệm (lập hồ sơ)", "end": "Kết thúc",
              "project_manager": "Chủ nhiệm", "approve_program": "Chọn phương án"}


def _sig(p: dict) -> str:
    import hashlib
    import json

    return hashlib.md5(json.dumps(p, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:8]


def _money(v) -> str:
    return f"{(v or 0) / 1e9:.2f} tỷ".replace(".", ",")


def _show_result(p: dict, k: str) -> None:
    """Kết quả agent vừa chạy."""
    agent = p.get("agent")
    if agent == "project_manager":
        b = p["brief"]
        ld, gd, yc = b["lo_dat"], b["gia_dinh"], b["yeu_cau_phong"]
        c = st.columns(4)
        c[0].metric("Lô đất", f"{ld['rong']:g} × {ld['dai']:g} m", ld["huong"], delta_color="off")
        c[1].metric("Phòng ngủ", yc["phong_ngu"], f"thờ: {'có' if yc.get('phong_tho') else 'không'}", delta_color="off")
        c[2].metric("Gara", yc.get("gara") or "không", f"{yc.get('so_tang') or 'KTS đề xuất'} tầng", delta_color="off")
        c[3].metric("Ngân sách", _money(b["ngan_sach"]), b.get("phong_cach"), delta_color="off")
        if b.get("gia_dinh_bo_sung"):
            st.info("Giả định: " + "; ".join(b["gia_dinh_bo_sung"]), icon=":material/info:")
        with st.expander("Brief đầy đủ (JSON)"):
            st.json(b)
    elif agent in ("architect",) and p.get("rows"):
        st.write(p.get("concept", ""))
        _rooms_by_floor(p["rows"])
    elif agent == "drafter" and p.get("sheets"):
        a = p["area"]
        c = st.columns(3)
        c[0].metric("Số tầng", a["so_tang"])
        c[1].metric("Tổng DT sàn", f"{a['tong_dien_tich_san']:.1f} m²".replace(".", ","))
        c[2].metric("Mật độ XD", f"{a['mat_do'] * 100:.1f}%".replace(".", ","))
        names = [f"{x['so_hieu']} – {x['ten']}" for x in p["sheets"]]
        i = st.selectbox("Bản vẽ", range(len(names)), format_func=lambda j: names[j], key=f"{k}_sheet")
        st.image(p["sheets"][i]["png"], width="stretch")
    elif agent == "reviewer" and p.get("review"):
        r = p["review"]
        if r["dat"]:
            st.success("Đạt. " + (r.get("nhan_xet") or ""), icon=":material/verified:")
        else:
            st.error("Chưa đạt. " + (r.get("nhan_xet") or ""), icon=":material/error:")
        for i in r.get("loi") or []:
            st.markdown(f"- **{i.get('muc')}** — {i.get('noi_dung')}  \n  :gray[Đề xuất: {i.get('de_xuat')}]")
        for w in r.get("canh_bao") or []:
            st.caption(f"Khuyến nghị · {w.get('muc')}: {w.get('noi_dung')}")
        with st.expander("Bảng kiểm tra chi tiết"):
            st.dataframe([{"Tiêu chí": c["muc"], "Phương án": c["hien_tai"], "Yêu cầu": c["cho_phep"],
                           "Kết quả": "✅" if c["dat"] else "❌"} for c in r.get("kiem_tra") or []],
                         hide_index=True, width="stretch")
    elif agent == "cost_estimator" and p.get("cost"):
        c = p["cost"]
        m = st.columns(3)
        m[0].metric("Tổng chi phí", _money(c["tong_chi_phi"]), f"{c['vuot_pct'] * 100:+.1f}% ngân sách",
                    delta_color="inverse")
        m[1].metric("Ngân sách", _money(c["ngan_sach"]))
        m[2].metric("Gói hoàn thiện", c["cap_hoan_thien"])
        st.write(c.get("ghi_chu", ""))
        st.dataframe([{"Hạng mục": it["hang_muc"], "Thành tiền": f"{it['thanh_tien']:,.0f} đ".replace(",", ".")}
                      for it in c.get("hang_muc") or []], hide_index=True, width="stretch")
        for t in c.get("tiet_kiem") or []:
            st.caption(f"Tiết kiệm · {t['phuong_an']}: ~{_money(t['tiet_kiem'])}")
    elif agent == "pm_report":
        st.success("Hồ sơ đã lập xong. Đồng ý để chốt, hoặc góp ý / sửa yêu cầu để thiết kế lại.",
                   icon=":material/task_alt:")
        for name, path in (p.get("final_files") or {}).items():
            st.caption(f"{name} · `{path}`")


def _rooms_by_floor(rows: list[dict]) -> None:
    floors: dict[int, list] = {}
    for r in rows:
        floors.setdefault(r["tang"], []).append(r)
    cols = st.columns(max(1, len(floors)))
    for c, (t, rs) in zip(cols, sorted(floors.items())):
        with c.container(border=True):
            ui.html_block(f'<div class="aa-eyebrow" style="color:#667085">Tầng {t}</div>'
                          + ui.kv([(r["ten"], f"{r['dien_tich']:g} m²".replace(".", ",")) for r in rs]))


def _options_tab(run, p: dict, k: str) -> None:
    opts = p.get("options") or []
    cur = p.get("phuong_an_hien_tai")
    st.caption("Chọn một phương án để chốt (chuyển Họa viên vẽ) hoặc chọn rồi chỉnh sửa thêm. Chỉ số là ước tính nhanh.")
    cols = st.columns(len(opts))
    for c, o in zip(cols, opts):
        m = o["chi_so"]
        with c.container(border=True):
            badge = ui.pill("Đang chọn", "brand") if o["id"] == cur else ""
            ui.html_block(f'<div class="aa-option"><div style="display:flex;justify-content:space-between;gap:8px;'
                          f'align-items:center"><h4>{ui.esc(o["ten"])}</h4>{badge}</div></div>')
            st.caption(o["mo_ta"])
            if "loi" in m:
                st.error(m["loi"])
            else:
                dens = ui.pill(f"{m['mat_do'] * 100:.0f}%", "success" if m["dat_mat_do"] else "danger")
                over = m["vuot_pct"] * 100
                cost_tone = "success" if over <= 0 else ("warning" if over <= 10 else "danger")
                ui.html_block(ui.kv([("Số tầng", str(m["so_tang"])),
                                     ("DT sàn", f"{m['tong_dien_tich_san']:.1f} m²".replace(".", ",")),
                                     ("Mật độ (≤ " + format(m["mat_do_toi_da"] * 100, ".0f") + "%)", dens),
                                     ("Chi phí", _money(m["chi_phi"])),
                                     ("So với ngân sách", ui.pill(f"{over:+.1f}%".replace(".", ","), cost_tone)),
                                     ("Sân sau · gói", f"{m['san_sau']:g} m · {ui.esc(m['cap_hoan_thien'])}")]))
            with st.expander("Danh sách phòng"):
                for r in o["rows"]:
                    st.caption(f"Tầng {r['tang']} · {r['ten']} — {r['dien_tich']:g} m²")
            if st.button("Chọn & chốt", key=f"{k}_pick_{o['id']}", type="primary", width="stretch",
                         icon=":material/check_circle:"):
                run.answer("choose", option=o["id"]); st.rerun()
            if st.button("Chọn rồi chỉnh sửa", key=f"{k}_pickedit_{o['id']}", width="stretch",
                         icon=":material/edit:"):
                run.answer("choose", option=o["id"], then_edit=True); st.rerun()


def _program_editor(run, p: dict, k: str) -> None:
    """Bảng chỉnh sửa trực tiếp chương trình công năng."""
    from agents.architect import GRADES, POSITIONS, ROOM_TYPES

    code_of = {v: c for c, v in ROOM_TYPES.items()}
    rows = [{"Tầng": r["tang"], "Tên phòng": r["ten"], "Loại": ROOM_TYPES.get(r["loai"], r["loai"]),
             "Diện tích (m²)": r["dien_tich"], "Vị trí": r["vi_tri"]} for r in p["rows"]]
    s_ = p["settings"]
    lot_l = float((p.get("lot") or {}).get("dai", 30))
    with st.form(f"{k}_form_edit"):
        st.caption("Sửa ô trong bảng, thêm dòng ở cuối, chọn dòng rồi 🗑 để xóa. Cầu thang + giếng trời là lõi cố định. "
                   "Bấm “Áp dụng & chốt” để Họa viên vẽ lại theo bảng này.")
        edited = st.data_editor(
            rows, num_rows="dynamic", width="stretch", hide_index=True, key=f"{k}_ed",
            column_config={
                "Tầng": st.column_config.NumberColumn(min_value=1, max_value=5, step=1, required=True),
                "Tên phòng": st.column_config.TextColumn(required=True),
                "Loại": st.column_config.SelectboxColumn(options=list(ROOM_TYPES.values()), required=True),
                "Diện tích (m²)": st.column_config.NumberColumn(min_value=1.0, max_value=200.0, step=0.5, required=True),
                "Vị trí": st.column_config.SelectboxColumn(options=POSITIONS, required=True,
                                                          help="mặt tiền → trước → giữa (sát giếng trời) → sau")})
        c = st.columns(5)
        san_truoc = c[0].number_input("Sân trước (m)", 0.0, lot_l / 2, float(s_["san_truoc"]), 0.5)
        san_sau = c[1].number_input("Sân sau (m)", 0.0, lot_l / 2, float(s_["san_sau"]), 0.5)
        grade = c[2].selectbox("Gói hoàn thiện", GRADES,
                               GRADES.index(s_["cap_hoan_thien"]) if s_["cap_hoan_thien"] in GRADES else 2)
        h1 = c[3].number_input("Cao tầng 1 (m)", 3.0, 4.5, float(s_["tang_1"]), 0.1)
        hk = c[4].number_input("Cao tầng khác (m)", 3.0, 4.2, float(s_["tang_khac"]), 0.1)
        submit = st.form_submit_button("Áp dụng & chốt chỉnh sửa", type="primary", icon=":material/save:")
    if submit:
        out = [{"tang": r.get("Tầng"), "ten": r.get("Tên phòng"), "loai": code_of.get(r.get("Loại")),
                "dien_tich": r.get("Diện tích (m²)"), "vi_tri": r.get("Vị trí")} for r in edited]
        bad = [i for i, r in enumerate(out, 1) if (r["ten"] or r["loai"]) and
               (not r["loai"] or not r["dien_tich"] or not r["tang"])]
        if bad:
            st.error(f"Dòng {bad} thiếu tầng / loại / diện tích.")
        else:
            run.answer("edit", rows=out, settings={"san_truoc": san_truoc, "san_sau": san_sau, "cap_hoan_thien": grade,
                                                   "tang_1": h1, "tang_khac": hk})
            st.rerun()


def _chat_tab(run, p: dict, k: str) -> None:
    st.caption("Nói chuyện tự nhiên với Kiến trúc sư, ví dụ: “nhà hơi tối”, “bố mẹ già lên xuống khó”, "
               "“phòng khách 30 m2 và bếp rộng hơn”, “chuyển phòng thờ lên tầng 4”, “tiết kiệm hơn”.")
    for h in p.get("trao_doi") or []:
        with st.chat_message("user"):
            st.write(h["nguoi_dung"])
        with st.chat_message("assistant", avatar=":material/architecture:"):
            st.write(h["kien_truc_su"])
    with st.form(f"{k}_form_chat", clear_on_submit=True):
        text = st.text_area("Góp ý của bạn", height=80, label_visibility="collapsed",
                            placeholder="Nhập mong muốn của bạn…")
        if st.form_submit_button("Gửi cho Kiến trúc sư", type="primary", icon=":material/send:"):
            if text.strip():
                run.answer("revise", text.strip()); st.rerun()
            else:
                st.warning("Hãy nhập nội dung.")


def _brief_tab(run, p: dict, k: str) -> None:
    from tools.brief_parser import DIRS

    b = p.get("brief") or {}
    if not b:
        st.caption("Chưa có brief.")
        return
    ld, gd, yc = b["lo_dat"], b["gia_dinh"], b["yeu_cau_phong"]
    dirs = [d.title() for d in DIRS]
    styles = ["hiện đại", "tối giản", "tân cổ điển", "Indochine", "Japandi", "Bắc Âu", "nhiệt đới", "cổ điển"]
    st.caption("Sửa yêu cầu → Kiến trúc sư lập lại 3 phương án từ yêu cầu mới (vòng sửa được đặt lại).")
    with st.form(f"{k}_form_brief"):
        c = st.columns(4)
        rong = c[0].number_input("Rộng lô (m)", 3.0, 20.0, float(ld["rong"]), 0.1)
        dai = c[1].number_input("Dài lô (m)", 8.0, 60.0, float(ld["dai"]), 0.5)
        huong = c[2].selectbox("Hướng mặt tiền", dirs, dirs.index(ld["huong"]) if ld["huong"] in dirs else 4)
        tinh = c[3].text_input("Tỉnh / thành", ld["tinh"])
        c = st.columns(4)
        so_nguoi = c[0].number_input("Số người", 1, 20, int(gd["so_nguoi"]))
        nam = c[1].number_input("Năm sinh chủ nhà (0 = không rõ)", 0, 2025, int(gd.get("nam_sinh_chu_nha") or 0))
        gt = c[2].selectbox("Giới tính chủ nhà", ["nam", "nữ"], 0 if gd.get("gioi_tinh_chu_nha", "nam") == "nam" else 1)
        ns = c[3].number_input("Ngân sách (tỷ)", 0.3, 100.0, float(b["ngan_sach"]) / 1e9, 0.1)
        c = st.columns(5)
        pn = c[0].number_input("Phòng ngủ", 1, 8, int(yc["phong_ngu"]))
        tho = c[1].checkbox("Phòng thờ", bool(yc.get("phong_tho")))
        lv = c[2].checkbox("Phòng làm việc", bool(yc.get("phong_lam_viec")))
        gara_opts = ["không", "xe máy", "ô tô"]
        gara = c[3].selectbox("Gara", gara_opts, gara_opts.index(yc.get("gara") or "không"))
        so_tang = c[4].number_input("Số tầng (0 = KTS đề xuất)", 0, 5, int(yc.get("so_tang") or 0))
        c = st.columns(2)
        pc = c[0].selectbox("Phong cách", styles, styles.index(b.get("phong_cach")) if b.get("phong_cach") in styles else 0)
        khac = c[1].text_input("Yêu cầu khác (cách nhau dấu phẩy)", ", ".join(b.get("yeu_cau_khac", [])))
        if st.form_submit_button("Cập nhật yêu cầu & thiết kế lại", type="primary", icon=":material/restart_alt:"):
            new = {"lo_dat": {"rong": rong, "dai": dai, "huong": huong, "tinh": tinh},
                   "gia_dinh": {**gd, "so_nguoi": so_nguoi, "nam_sinh_chu_nha": nam or None, "gioi_tinh_chu_nha": gt},
                   "yeu_cau_phong": {"phong_ngu": pn, "phong_tho": int(tho), "phong_lam_viec": int(lv),
                                     "gara": None if gara == "không" else gara, "so_tang": so_tang or None},
                   "ngan_sach": int(ns * 1e9), "phong_cach": pc,
                   "yeu_cau_khac": [x.strip() for x in khac.split(",") if x.strip()],
                   "gia_dinh_bo_sung": b.get("gia_dinh_bo_sung", [])}
            run.answer("edit_brief", brief=new); st.rerun()
    with st.form(f"{k}_form_req"):
        req = st.text_area("Hoặc viết lại toàn bộ yêu cầu bằng lời (Chủ nhiệm sẽ phân tích lại từ đầu)",
                           p.get("user_request", ""), height=90)
        if st.form_submit_button("Gửi yêu cầu mới cho Chủ nhiệm", icon=":material/edit_note:"):
            run.answer("edit_request", request=req); st.rerun()


def approval_box(run, key: str = "ap") -> None:
    """Khung duyệt thủ công khi graph dừng ở interrupt (sau bất kỳ agent nào)."""
    if run is None or run.status != "awaiting_approval":
        return
    p = run.interrupt_payload or {}
    k = f"{key}_{p.get('agent')}_{_sig({x: p.get(x) for x in ('agent', 'next', 'rows', 'trao_doi', 'phuong_an_hien_tai')})}"
    agent = p.get("agent")
    with st.container(border=True):
        nxt = p.get("next")
        back = nxt == "architect" and agent != "project_manager"
        ui.html_block(
            f'<div class="aa-approval-head"><div><div class="aa-eyebrow">Điểm duyệt thủ công</div>'
            f'<h3>{ui.esc(p.get("title", "Chờ duyệt"))}</h3>'
            f'<div class="aa-sub" style="font-size:.875rem;margin-top:6px">Nếu đồng ý, bước tiếp theo: '
            f'<b>{ui.esc(NEXT_LABEL.get(nxt, nxt))}</b>'
            f'{" — agent đang gửi phản hồi lỗi về Kiến trúc sư" if back else ""}</div></div>'
            f'{ui.pill("Chờ bạn duyệt", "warning", live=True)}</div>')
        actions = [("ok", "Đồng ý & tiếp tục", ":material/check_circle:", "primary", "approve")]
        if p.get("forward"):
            actions.append(("fw", "Bỏ qua lỗi, đi tiếp", ":material/skip_next:", "secondary", "forward"))
        actions += [("rerun", f"Chạy lại {label(agent)}", ":material/replay:", "secondary", "rerun"),
                    ("stop", "Dừng", ":material/stop_circle:", "secondary", "stop")]
        widths = [1.4] + [1.2] * (len(actions) - 2) + [0.8]
        cols = st.columns(widths + [max(0.1, 6 - sum(widths))])
        for c, (sk, text, ic, kind, act) in zip(cols, actions):
            if c.button(text, key=f"{k}_{sk}", type=kind, width="stretch", icon=ic):
                run.answer(act); st.rerun()
        names = [":material/insights: Kết quả"]
        if agent == "architect" and p.get("options"):
            names.append(":material/dashboard: Chọn phương án")
        if p.get("rows"):
            names.append(":material/table_edit: Chỉnh sửa phương án")
        names += [":material/forum: Trao đổi với KTS", ":material/edit_note: Sửa yêu cầu"]
        tabs = dict(zip(names, st.tabs(names)))
        with tabs[names[0]]:
            _show_result(p, k)
        for n, t in tabs.items():
            with t:
                if "Chọn phương án" in n:
                    _options_tab(run, p, k)
                elif "Chỉnh sửa phương án" in n:
                    _program_editor(run, p, k)
                elif "Trao đổi" in n:
                    _chat_tab(run, p, k)
                elif "Sửa yêu cầu" in n:
                    _brief_tab(run, p, k)


def label(agent: str) -> str:
    extra = {"pm_report": "Chủ nhiệm", "end": "Kết thúc", "approve_program": "Duyệt phương án"}
    return AGENT_LABELS.get(agent, extra.get(agent, agent or "—"))


def run_stepper(run, stats: dict) -> None:
    """Thanh 5 bước theo agent: hoàn thành / đang chạy / có phản hồi lỗi / chờ."""
    _, current = run.step()
    steps = []
    for a in AGENT_ORDER:
        s = stats[a]
        if run.status in ("running",) and a == current:
            stt, sub = "active", "Đang chạy"
        elif s["status"] == "error":
            stt, sub = "err", "Lỗi"
        elif s["runs"]:
            stt = "warn" if s["errors"] and a in ("reviewer", "cost_estimator") and s["status"] != "done" else "done"
            sub = f"{s['runs']} lần chạy" + (f" · {s['errors']} phản hồi" if s["errors"] else "")
        else:
            stt, sub = "todo", "Chờ"
        if run.status == "awaiting_approval" and a == current:
            stt, sub = "active", "Chờ duyệt"
        steps.append((label(a), sub, stt))
    ui.stepper(steps)


def run_meta_html(run, extra: str = "") -> str:
    return f"{ui.run_pill(run.status)}<code>{ui.esc(run.run_id)}</code>{extra}"
