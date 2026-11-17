"""Gửi / nhận AgentEvent: lưu vào SQLite (monitoring/logs.db) và phát cho listener trong bộ nhớ."""
from __future__ import annotations

import csv
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import AGENT_LABELS, LOG_DB

_lock = threading.Lock()
_listeners: dict[str, list] = {}


@contextmanager
def _conn():
    LOG_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(LOG_DB, timeout=10)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _lock, _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY, created TEXT, request TEXT, status TEXT,
            output_dir TEXT, summary TEXT);
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, time TEXT, agent TEXT,
            status TEXT, to_agent TEXT, summary TEXT, tokens INTEGER, duration_s REAL,
            version INTEGER, feedback INTEGER);
        """)


def record_run(run_id: str, request: str, output_dir: str) -> None:
    init_db()
    with _lock, _conn() as con:
        con.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?)",
                    (run_id, datetime.now().isoformat(timespec="seconds"), request, "running", output_dir, "{}"))


def update_run(run_id: str, status: str, summary: dict | None = None) -> None:
    init_db()
    with _lock, _conn() as con:
        if summary is not None:
            con.execute("UPDATE runs SET status=?, summary=? WHERE run_id=?",
                        (status, json.dumps(summary, ensure_ascii=False), run_id))
        else:
            con.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))


def list_runs(limit: int = 50) -> list[dict]:
    init_db()
    with _lock, _conn() as con:
        rows = con.execute("SELECT run_id, created, request, status, output_dir, summary FROM runs "
                           "ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
    return [{"run_id": r[0], "created": r[1], "request": r[2], "status": r[3], "output_dir": r[4],
             "summary": json.loads(r[5] or "{}")} for r in rows]


def emit(run_id: str, event: dict) -> None:
    init_db()
    with _lock, _conn() as con:
        con.execute("INSERT INTO events (run_id,time,agent,status,to_agent,summary,tokens,duration_s,version,feedback)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (run_id, event.get("time"), event.get("agent"), event.get("status"), event.get("to_agent", ""),
                     event.get("summary", ""), event.get("tokens", 0), event.get("duration_s", 0.0),
                     event.get("version", 0), int(bool(event.get("feedback")))))
    for cb in list(_listeners.get(run_id, [])):
        try:
            cb(event)
        except Exception:  # noqa: BLE001
            pass


def get_events(run_id: str) -> list[dict]:
    init_db()
    with _lock, _conn() as con:
        rows = con.execute("SELECT time,agent,status,to_agent,summary,tokens,duration_s,version,feedback "
                           "FROM events WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    keys = ["time", "agent", "status", "to_agent", "summary", "tokens", "duration_s", "version", "feedback"]
    return [dict(zip(keys, r)) for r in rows]


def subscribe(run_id: str, callback) -> None:
    _listeners.setdefault(run_id, []).append(callback)


def export_timeline(run_id: str, path: Path) -> Path:
    """Xuất dòng thời gian (chỉ các sự kiện hoàn thành / lỗi) ra CSV để đưa vào báo cáo."""
    events = [e for e in get_events(run_id) if e["status"] in ("done", "error")]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Thời điểm", "Agent gửi", "Agent nhận", "Nội dung", "Trạng thái", "Lần chạy",
                    "Token", "Thời gian (s)", "Phản hồi lỗi"])
        for e in events:
            w.writerow([e["time"], AGENT_LABELS.get(e["agent"], e["agent"]),
                        AGENT_LABELS.get(e["to_agent"], e["to_agent"] or ""), e["summary"], e["status"],
                        e["version"], e["tokens"], e["duration_s"], "có" if e["feedback"] else ""])
    return path
