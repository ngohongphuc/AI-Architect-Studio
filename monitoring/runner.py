"""Điều khiển lượt thiết kế chạy nền cho giao diện Streamlit.

- Chạy `graph.stream(..., stream_mode="updates")` trong thread riêng.
- Tạm dừng: dừng sau khi agent hiện tại chạy xong; trạng thái nằm trong checkpointer (SQLite) để chạy tiếp.
- Dừng: hủy lượt thiết kế.
- Duyệt thủ công: graph dừng ở `interrupt`, tiếp tục bằng `Command(resume=...)`.
- Chạy lại agent: tìm checkpoint gần nhất ngay trước agent đó và chạy tiếp từ đó (time travel).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

from langgraph.types import Command

from config import AGENT_ORDER
from graph import NODE_AGENT, _run_summary, build_graph, initial_state, sqlite_checkpointer
from monitoring import events
from monitoring.tracker import estimate_cost_usd, tracker

_graph = None
_graph_lock = threading.Lock()


def get_graph():
    global _graph
    with _graph_lock:
        if _graph is None:
            _graph = build_graph(sqlite_checkpointer())
        return _graph


@dataclass
class Run:
    run_id: str
    request: str
    status: str = "idle"          # running | paused | awaiting_approval | done | stopped | error
    current_node: str = ""
    started: float = field(default_factory=time.time)
    elapsed: float = 0.0
    error: str = ""
    interrupt_payload: dict | None = None
    pause_requested: bool = False
    stop_requested: bool = False
    thread: threading.Thread | None = None
    run_config: dict | None = None
    _t_start: float = 0.0

    @property
    def config(self) -> dict:
        return self.run_config or {"configurable": {"thread_id": self.run_id}, "recursion_limit": 60}

    # ------------------------------------------------------------------
    def _loop(self, inp, config=None) -> None:
        g = get_graph()
        cfg = config or self.config
        self.status = "running"
        t0 = self._t_start = time.time()
        try:
            snap = g.get_state(cfg) if inp is None else None
            self.current_node = (snap.next[0] if snap and snap.next else "project_manager")
            for update in g.stream(inp, cfg, stream_mode="updates"):
                nxt = g.get_state(self.config).next
                self.current_node = nxt[0] if nxt else ""
                if "__interrupt__" in update:
                    break
                if self.stop_requested:
                    self.status = "stopped"
                    events.update_run(self.run_id, "stopped")
                    return
                if self.pause_requested:
                    self.pause_requested = False
                    self.status = "paused"
                    events.update_run(self.run_id, "paused")
                    return
            snap = g.get_state(self.config)
            pending = [i for t in snap.tasks for i in (t.interrupts or [])]
            self.current_node = snap.next[0] if snap.next else ""
            if snap.next and pending:
                self.status = "awaiting_approval"
                self.interrupt_payload = pending[0].value
                events.update_run(self.run_id, "awaiting_approval")
            elif snap.next:
                self.status = "paused"
            else:
                self.status = "done"
                self.current_node = ""
                events.update_run(self.run_id, "done", _run_summary(snap.values))
        except Exception as e:  # noqa: BLE001
            self.status = "error"
            self.error = str(e)
            events.update_run(self.run_id, "error")
        finally:
            self.elapsed += time.time() - t0

    def _start(self, inp, config=None) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_requested = self.pause_requested = False
        self.interrupt_payload = None
        self.status = "running"          # đặt ngay để giao diện không thấy trạng thái cũ
        self.thread = threading.Thread(target=self._loop, args=(inp, config), daemon=True)
        self.thread.start()

    # ------------------------------------------------------------------
    def pause(self):
        self.pause_requested = True

    def resume(self):
        if self.status == "paused":
            self._start(None)

    def stop(self):
        self.stop_requested = True
        if self.status in ("paused", "awaiting_approval"):
            self.status = "stopped"
            events.update_run(self.run_id, "stopped")

    def answer(self, action: str, feedback: str = "", **data):
        """Trả lời điểm duyệt thủ công: approve | revise | edit (rows, settings) | stop."""
        if self.status == "awaiting_approval":
            self._start(Command(resume={"action": action, "feedback": feedback, **data}))

    def rerun_agent(self, agent: str) -> bool:
        """Chạy lại một agent (và các bước sau) từ checkpoint ngay trước lần chạy gần nhất của agent đó."""
        if self.thread and self.thread.is_alive():
            return False
        g = get_graph()
        node = "project_manager" if agent == "project_manager" else agent
        for snap in g.get_state_history(self.config):
            if snap.next and snap.next[0] == node:
                self._start(None, snap.config)
                self.run_config = None
                return True
        return False

    # ------------------------------------------------------------------
    def state(self) -> dict:
        try:
            st = get_graph().get_state(self.config).values or {}
        except Exception:  # noqa: BLE001
            st = {}
        if st.get("final_files") or (self.thread and self.thread.is_alive()):
            return st
        # Lượt chạy không có checkpoint (CLI cũ, evaluate, test) -> đọc state.json trong thư mục kết quả
        snap = load_snapshot(self.run_id)
        return snap or st

    def tokens(self) -> int:
        live = tracker.tokens(self.run_id)
        return live or sum(e["tokens"] or 0 for e in events.get_events(self.run_id) if e["status"] == "done")

    def cost_usd(self) -> float:
        return tracker.usd(self.run_id) or estimate_cost_usd(self.tokens())

    def step(self) -> tuple[int, str]:
        agent = NODE_AGENT.get(self.current_node, "")
        if self.status == "done":
            return 5, ""
        if agent in AGENT_ORDER:
            return AGENT_ORDER.index(agent) + 1, agent
        return 0, agent

    def time_running(self) -> float:
        if self.thread and self.thread.is_alive():
            return self.elapsed + time.time() - self._t_start
        if not self.elapsed:
            evs = events.get_events(self.run_id)
            return sum(e["duration_s"] or 0 for e in evs if e["status"] == "done")
        return self.elapsed


def load_snapshot(run_id: str) -> dict:
    import json
    from pathlib import Path

    from config import OUTPUT_DIR

    out = next((r["output_dir"] for r in events.list_runs(500) if r["run_id"] == run_id), None)
    path = Path(out or OUTPUT_DIR / run_id) / "state.json"
    if not path.exists():
        return {}
    try:
        st = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    st.setdefault("history", [])
    st.setdefault("log", [e["time"] + "  " + e["agent"] + ": " + e["summary"]
                          for e in events.get_events(run_id) if e["status"] == "done"])
    return st


class RunManager:
    def __init__(self):
        self.runs: dict[str, Run] = {}

    def start(self, request: str, manual_review: bool = False, max_iterations: int = 3,
              approval_points: list | None = None) -> Run:
        st = initial_state(request, manual_review=manual_review, max_iterations=max_iterations,
                           approval_points=approval_points)
        run = Run(run_id=st["run_id"], request=request)
        self.runs[run.run_id] = run
        run._start(st)
        return run

    def get(self, run_id: str) -> Run:
        if run_id not in self.runs:
            # mở lại lượt cũ từ checkpointer (lịch sử thiết kế)
            run = Run(run_id=run_id, request="")
            st = run.state()
            run.request = st.get("user_request", "")
            run.status = "done" if st.get("final_files") else ("paused" if st else "idle")
            self.runs[run_id] = run
        return self.runs[run_id]


manager = RunManager()
