"""Luồng LangGraph: 5 agent, 2 vòng lặp phản hồi (quy chuẩn, ngân sách), duyệt thủ công bằng interrupt."""
from __future__ import annotations

import copy
import sqlite3
import uuid
from datetime import datetime

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from agents import architect, cost_estimator, drafter, project_manager, reviewer
from config import AGENT_LABELS, CHECKPOINT_DB, MAX_ITERATIONS, OUTPUT_DIR
from monitoring import events
from state import DesignState

# Điểm duyệt thủ công sau mỗi agent: node agent -> (node duyệt, tiêu đề)
APPROVALS = {
    "project_manager": ("approve_brief", "Duyệt brief (Chủ nhiệm)"),
    "architect": ("approve_program", "Chọn & chốt phương án công năng (Kiến trúc sư)"),
    "drafter": ("approve_drawing", "Duyệt mặt bằng / bản vẽ (Họa viên)"),
    "reviewer": ("approve_review", "Duyệt kết quả kiểm định (Kiểm định viên)"),
    "cost_estimator": ("approve_cost", "Duyệt dự toán (Kỹ sư dự toán)"),
    "pm_report": ("approve_final", "Chốt hồ sơ cuối (Chủ nhiệm)"),
}
APPROVAL_LABELS = {k: v[1] for k, v in APPROVALS.items()}
AGENT_NODES = ["project_manager", "architect", "drafter", "reviewer", "cost_estimator", "pm_report"]
# Bước "đi tiếp" khi người dùng bỏ qua phản hồi lỗi của Kiểm định viên / Kỹ sư dự toán
FORWARD = {"reviewer": "cost_estimator", "cost_estimator": "pm_report"}

# Tên node trong đồ thị -> agent
NODE_AGENT = {"project_manager": "project_manager", "architect": "architect", "drafter": "drafter",
              "reviewer": "reviewer", "cost_estimator": "cost_estimator", "pm_report": "project_manager",
              **{v[0]: "user" for v in APPROVALS.values()}}


def needs_approval(state: dict, node: str) -> bool:
    points = state.get("approval_points")
    if points is None:   # tương thích cũ: manual_review = duyệt sau Kiến trúc sư và Kiểm định viên
        points = ["architect", "reviewer"] if state.get("manual_review") else []
    return node in points


def _ev(state: dict, summary: str, to: str = "", feedback: bool = False) -> dict:
    now = datetime.now().strftime("%H:%M:%S")
    ev = {"time": now, "agent": "user", "status": "done", "to_agent": to, "summary": summary, "tokens": 0,
          "duration_s": 0.0, "version": 0, "feedback": feedback}
    events.emit(state.get("run_id", "local"), ev)
    names = {**AGENT_LABELS, "pm_report": "Chủ nhiệm", "end": "Kết thúc",
             **{v[0]: "điểm duyệt" for v in APPROVALS.values()}}
    return {"events": [ev], "log": [f"{now}  Người dùng → {names.get(to, to or '—')}: {summary}"]}


def _payload(state: dict, node: str) -> dict:
    """Nội dung hiển thị cho người duyệt (tùy agent vừa chạy)."""
    from agents.architect import program_to_rows

    p = {"title": APPROVALS[node][1], "agent": node, "next": state.get("route"), "brief": state.get("brief"),
         "user_request": state.get("user_request"), "trao_doi": state.get("trao_doi", [])[-10:],
         "forward": FORWARD.get(node) if state.get("route") == "architect" else None}
    prog = state.get("program")
    if prog:
        h = prog.get("chieu_cao_tang", {})
        p.update(rows=program_to_rows(prog), lot=state["brief"]["lo_dat"], concept=state.get("concept", ""),
                 settings={"san_truoc": prog.get("san_truoc", 0.0), "san_sau": prog.get("san_sau", 0.0),
                           "cap_hoan_thien": prog.get("cap_hoan_thien", "khá"), "tang_1": h.get("tang_1", 3.6),
                           "tang_khac": h.get("tang_khac", 3.3)},
                 phuong_an_hien_tai=prog.get("phuong_an"))
    if node == "architect":
        p["options"] = [{k: v for k, v in o.items() if k != "program"} | {"rows": program_to_rows(o["program"])}
                        for o in state.get("options") or []]
    elif node == "drafter" and state.get("drawings"):
        p["sheets"] = [{"so_hieu": x["so_hieu"], "ten": x["ten"], "png": x["png"]} for x in state["drawings"]["sheets"]]
        a = state["area_table"]
        p["area"] = {"so_tang": a["so_tang"], "tong_dien_tich_san": a["tong_dien_tich_san"],
                     "mat_do": a["mat_do_xay_dung"]}
    elif node == "reviewer":
        r = state.get("review", {})
        p["review"] = {k: r.get(k) for k in ("dat", "nhan_xet", "loi", "canh_bao", "kiem_tra")}
    elif node == "cost_estimator":
        c = state.get("cost", {})
        p["cost"] = {k: c.get(k) for k in ("tong_chi_phi", "ngan_sach", "vuot_pct", "chi_phi_m2_san", "cap_hoan_thien",
                                           "ghi_chu", "hang_muc", "du_phong", "tiet_kiem")}
    elif node == "pm_report":
        p["final_files"] = state.get("final_files")
    return p


def make_approval(node: str):
    """Node duyệt thủ công đặt sau agent `node`. Giữ nguyên nhánh agent đã chọn trừ khi người dùng thay đổi."""

    def approval(state: dict) -> dict:
        if not needs_approval(state, node):
            return {}
        decision = interrupt(_payload(state, node))
        d = decision if isinstance(decision, dict) else {"action": str(decision)}
        action = d.get("action", "approve")
        me = APPROVALS[node][0]
        if action == "approve":
            return {**_ev(state, f"Đồng ý: {APPROVALS[node][1]}", state.get("route", ""))}
        if action == "stop":
            return {"route": "end", **_ev(state, "Dừng thiết kế", "", True)}
        if action == "rerun":
            upd = {"route": node}
            if node == "architect":
                upd.update(program=None, options=[])      # lập lại các phương án từ brief
            return {**upd, **_ev(state, f"Chạy lại {node}", node)}
        if action == "forward" and FORWARD.get(node):
            return {"route": FORWARD[node], "remaining_issues": state.get("review", {}).get("loi", []) if node ==
                    "reviewer" else state.get("remaining_issues", []),
                    **_ev(state, "Bỏ qua phản hồi lỗi, đi tiếp", FORWARD[node], True)}
        if action == "revise":
            text = (d.get("feedback") or "").strip()
            if not text:
                return {"route": me}
            return {"route": "architect", "feedback_source": "user",
                    "feedback": [{"loai": "Người dùng", "ma": "USER", "muc": "Góp ý", "noi_dung": text, "de_xuat": text,
                                  "lich_su": state.get("trao_doi", [])[-6:]}],
                    **_ev(state, f"Góp ý: {text}", "architect", True)}
        if action == "choose":
            opt = next((o for o in state.get("options") or [] if o["id"] == d.get("option")), None)
            if opt is None:
                return {"route": me}
            prog = copy.deepcopy(opt["program"])
            prog.setdefault("lich_su_sua", []).append(f"Chủ nhà chọn {opt['ten']}")
            nxt = me if d.get("then_edit") else "drafter"
            return {"program": prog, "route": nxt, **_ev(state, f"Chọn {opt['ten']}", nxt)}
        if action == "edit":
            from agents.architect import apply_user_edit

            try:
                program, brief, changes = apply_user_edit(state["program"], d.get("rows", []), d.get("settings", {}),
                                                          state["brief"])
            except ValueError as e:
                return {"route": me, **_ev(state, f"Chỉnh sửa không hợp lệ: {e}", "", True)}
            return {"route": "drafter", "program": program, "brief": brief,
                    **_ev(state, "Chốt chỉnh sửa: " + "; ".join(changes), "drafter")}
        if action == "edit_brief":
            from pydantic import ValidationError

            from state import Brief

            try:
                brief = Brief(**d["brief"]).model_dump()
            except (ValidationError, KeyError, TypeError) as e:
                return {"route": me, **_ev(state, f"Yêu cầu không hợp lệ: {e}", "", True)}
            return {"brief": brief, "program": None, "options": [], "feedback": [], "iteration": 0,
                    "remaining_issues": [], "route": "architect",
                    **_ev(state, "Sửa yêu cầu thiết kế → Kiến trúc sư lập lại phương án", "architect", True)}
        if action == "edit_request":
            text = (d.get("request") or "").strip()
            if not text:
                return {"route": me}
            return {"user_request": text, "program": None, "options": [], "feedback": [], "iteration": 0,
                    "remaining_issues": [], "route": "project_manager",
                    **_ev(state, f"Viết lại yêu cầu: {text[:80]}", "project_manager", True)}
        return {"route": me}

    approval.__name__ = APPROVALS[node][0]
    return approval


def _route(state: dict) -> str:
    return state.get("route") or "end"


def build_graph(checkpointer=None):
    g = StateGraph(DesignState)
    g.add_node("project_manager", project_manager.run_brief)
    g.add_node("architect", architect.run)
    g.add_node("drafter", drafter.run)
    g.add_node("reviewer", reviewer.run)
    g.add_node("cost_estimator", cost_estimator.run)
    g.add_node("pm_report", project_manager.run_report)
    targets = {n: n for n in AGENT_NODES} | {v[0]: v[0] for v in APPROVALS.values()} | {"end": END}
    for node in AGENT_NODES:
        name = APPROVALS[node][0]
        g.add_node(name, make_approval(node))
        g.add_edge(node, name)                         # agent -> điểm duyệt (đi thẳng nếu không bật duyệt)
        g.add_conditional_edges(name, _route, targets)  # điểm duyệt -> nhánh agent đã chọn / người dùng chọn
    g.add_edge(START, "project_manager")
    return g.compile(checkpointer=checkpointer or MemorySaver())


def sqlite_checkpointer():
    from langgraph.checkpoint.sqlite import SqliteSaver

    CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver(sqlite3.connect(CHECKPOINT_DB, check_same_thread=False))


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:4]


def initial_state(request: str, run_id: str | None = None, manual_review: bool = False,
                  max_iterations: int = MAX_ITERATIONS, approval_points: list | None = None) -> dict:
    """approval_points: các node agent cần duyệt sau khi chạy (vd ["architect", "reviewer"]); "all" = mọi bước."""
    run_id = run_id or new_run_id()
    out = OUTPUT_DIR / run_id
    events.record_run(run_id, request, str(out))
    if approval_points == "all":
        approval_points = list(AGENT_NODES)
    if approval_points is None:
        approval_points = ["architect", "reviewer"] if manual_review else []
    return {"run_id": run_id, "user_request": request, "output_dir": str(out), "iteration": 0,
            "max_iterations": max_iterations, "manual_review": bool(approval_points),
            "approval_points": list(approval_points), "versions": {}, "feedback": []}


def run_design(request: str, manual_review: bool = False, max_iterations: int = MAX_ITERATIONS,
               on_update=None, persist: bool = True) -> dict:
    """Chạy trọn luồng (không dừng) – dùng cho CLI, đánh giá và test.

    Mặc định lưu checkpoint vào SQLite để mở lại được trên giao diện (trang Kết quả / Quản lý agent).
    """
    graph = build_graph(sqlite_checkpointer() if persist else None)
    state = initial_state(request, manual_review=manual_review, max_iterations=max_iterations)
    config = {"configurable": {"thread_id": state["run_id"]}, "recursion_limit": 60}
    try:
        for update in graph.stream(state, config, stream_mode="updates"):
            if on_update:
                on_update(update)
        final = graph.get_state(config).values
        events.update_run(state["run_id"], "done", _run_summary(final))
        return final
    except Exception:
        events.update_run(state["run_id"], "error")
        raise


def _run_summary(final: dict) -> dict:
    cost = final.get("cost", {})
    return {"so_tang": final.get("area_table", {}).get("so_tang"), "tong_chi_phi": cost.get("tong_chi_phi"),
            "vong_sua": final.get("iteration"), "dat": final.get("review", {}).get("dat"),
            "files": final.get("final_files", {})}
