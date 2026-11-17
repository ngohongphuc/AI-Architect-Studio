"""Hệ thống thiết kế "Modern" cho giao diện Streamlit.

Design tokens
-------------
- Màu: nền #F6F7FB, bề mặt #FFFFFF, viền #E4E7EC, chữ #101828 / phụ #475467 / mờ #667085,
  nhấn Indigo #4F46E5. Mỗi tông trạng thái có cặp (chữ, nền) đạt tương phản ≥ 4.5:1 (WCAG AA).
- Chữ: Inter. Eyebrow 12px/600 viết hoa · H1 32px/800 · H2 24px/700 · H3 18px/650 · body 15px · caption 13px.
- Bo góc: 10px (nút, ô nhập) · 12px (thẻ nhỏ) · 16px (thẻ lớn) · 999px (pill).
- Khoảng cách: thang 4px – 4 · 8 · 12 · 16 · 24 · 32 · 48.
- Đổ bóng: xs (viền tách nền) và sm (thẻ nổi).
"""
from __future__ import annotations

import html

import streamlit as st

# (chữ, nền, viền) cho từng tông
TONES = {
    "neutral": ("#344054", "#F2F4F7", "#E4E7EC"),
    "info": ("#175CD3", "#EFF8FF", "#B2DDFF"),
    "brand": ("#4338CA", "#EEF2FF", "#C7D2FE"),
    "success": ("#067647", "#ECFDF3", "#ABEFC6"),
    "warning": ("#B54708", "#FFFAEB", "#FEDF89"),
    "danger": ("#B42318", "#FEF3F2", "#FECDCA"),
}

AGENT_STATUS = {  # trạng thái agent -> (nhãn, tông)
    "waiting": ("Chờ", "neutral"), "running": ("Đang chạy", "info"), "revising": ("Đang sửa", "warning"),
    "done": ("Hoàn thành", "success"), "error": ("Lỗi", "danger"), "paused": ("Tạm dừng", "neutral"),
}
RUN_STATUS_TONE = {  # trạng thái lượt chạy -> (nhãn, tông)
    "running": ("Đang chạy", "info"), "paused": ("Tạm dừng", "neutral"), "awaiting_approval": ("Chờ duyệt", "warning"),
    "done": ("Hoàn thành", "success"), "stopped": ("Đã dừng", "neutral"), "error": ("Lỗi", "danger"),
    "idle": ("Chưa chạy", "neutral"),
}
AGENT_ICON = {"project_manager": "badge", "architect": "architecture", "drafter": "draw",
              "reviewer": "fact_check", "cost_estimator": "payments", "user": "person"}

CSS = """
<style>
:root{
  --bg:#F6F7FB; --surface:#FFFFFF; --subtle:#F9FAFB; --border:#E4E7EC; --border-strong:#D0D5DD;
  --text:#101828; --text-2:#475467; --text-3:#667085;
  --brand:#4F46E5; --brand-600:#4338CA; --brand-50:#EEF2FF;
  --r-sm:10px; --r-md:12px; --r-lg:16px;
  --shadow-xs:0 1px 2px rgba(16,24,40,.05);
  --shadow-sm:0 1px 3px rgba(16,24,40,.08),0 1px 2px rgba(16,24,40,.04);
}
/* ---------- Bố cục & khoảng trắng ---------- */
[data-testid="stMainBlockContainer"], .block-container{
  max-width:1280px; padding-top:2.25rem !important; padding-bottom:4rem !important;
  padding-left:2.5rem !important; padding-right:2.5rem !important;
}
[data-testid="stVerticalBlock"]{ gap:1rem; }
[data-testid="stHeader"]{ background:transparent; }
hr{ margin:2rem 0 !important; border-color:var(--border) !important; }

/* ---------- Typography ---------- */
html, body, [class*="st-"]{ -webkit-font-smoothing:antialiased; }
h1,h2,h3,h4{ letter-spacing:-0.02em; color:var(--text); }
h1{ line-height:1.15 !important; }
p, li{ line-height:1.6; }
[data-testid="stCaptionContainer"], .stCaption{ color:var(--text-3) !important; }
code{ border-radius:6px; }

/* ---------- Thẻ có viền (st.container(border=True)) ---------- */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]){
  background:var(--surface); box-shadow:var(--shadow-xs);
}
div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"][class*="border"]{
  background:var(--surface); box-shadow:var(--shadow-xs);
}

/* ---------- Metric -> thẻ số liệu ---------- */
[data-testid="stMetric"]{
  background:var(--surface); border:1px solid var(--border); border-radius:var(--r-md);
  padding:16px 18px; box-shadow:var(--shadow-xs);
}
[data-testid="stMetricLabel"] p{ font-size:.75rem !important; font-weight:600 !important;
  text-transform:uppercase; letter-spacing:.06em; color:var(--text-3) !important; }
[data-testid="stMetricValue"]{ font-size:1.5rem !important; font-weight:700 !important; color:var(--text) !important;
  letter-spacing:-0.02em; }

/* ---------- Nút ---------- */
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button{
  font-weight:600; min-height:2.5rem; transition:all .15s ease; box-shadow:var(--shadow-xs);
}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]{
  box-shadow:0 1px 2px rgba(79,70,229,.25), 0 0 0 1px rgba(79,70,229,.1);
}
.stButton > button:hover{ transform:translateY(-1px); }

/* ---------- Tabs dạng segmented ---------- */
[data-baseweb="tab-list"]{ gap:4px; background:#EEF1F6; padding:4px; border-radius:var(--r-md); width:fit-content;
  max-width:100%; overflow-x:auto; }
[data-baseweb="tab-list"] button[role="tab"]{ border-radius:9px; padding:6px 14px; height:auto; }
[data-baseweb="tab-list"] button[role="tab"][aria-selected="true"]{ background:var(--surface); box-shadow:var(--shadow-sm); }
[data-baseweb="tab-list"] button[role="tab"] p{ font-weight:600; font-size:.875rem; }
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"]{ display:none; }
[data-testid="stTabs"] [data-baseweb="tab-panel"]{ padding-top:1.25rem; }

/* ---------- Ô nhập, bảng, expander, alert ---------- */
[data-testid="stTextArea"] textarea{ line-height:1.55; }
[data-testid="stDataFrame"], [data-testid="stDataFrameResizable"]{ border-radius:var(--r-md); overflow:hidden; }
[data-testid="stExpander"] details{ border-radius:var(--r-md); background:var(--surface); }
[data-testid="stExpander"] summary p{ font-weight:600; }
[data-testid="stAlert"]{ border-radius:var(--r-md); }
[data-testid="stImage"] img{ border-radius:var(--r-md); border:1px solid var(--border); background:#fff; }
[data-testid="stSidebarNav"] a{ border-radius:var(--r-sm); }
[data-testid="stChatMessage"]{ border-radius:var(--r-lg); background:var(--surface); border:1px solid var(--border); }

/* ---------- Thành phần tùy biến ---------- */
.aa-header{ display:flex; justify-content:space-between; align-items:flex-end; gap:24px; margin:0 0 8px; flex-wrap:wrap; }
.aa-eyebrow{ font-size:.75rem; font-weight:600; letter-spacing:.08em; text-transform:uppercase; color:var(--brand-600);
  margin-bottom:6px; }
.aa-title{ font-size:2rem; font-weight:800; letter-spacing:-0.025em; line-height:1.15; color:var(--text); margin:0; }
.aa-sub{ font-size:1rem; color:var(--text-2); margin-top:8px; max-width:720px; line-height:1.55; }
.aa-section{ margin:12px 0 4px; }
.aa-approval-head{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap;
  padding-bottom:16px; margin-bottom:4px; border-bottom:1px solid #F2F4F7; }
.aa-approval-head h3{ margin:0; font-size:1.25rem; font-weight:700; letter-spacing:-0.01em; }
.aa-section h3{ font-size:1.125rem; font-weight:650; margin:0; letter-spacing:-0.01em; color:var(--text); }
.aa-section p{ font-size:.875rem; color:var(--text-3); margin:4px 0 0; }
.aa-pill{ display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px; font-size:.75rem;
  font-weight:600; line-height:1.4; border:1px solid; white-space:nowrap; }
.aa-pill .dot{ width:6px; height:6px; border-radius:50%; background:currentColor; }
.aa-pill.live .dot{ animation:aa-pulse 1.4s ease-in-out infinite; }
@keyframes aa-pulse{ 0%,100%{opacity:1} 50%{opacity:.25} }
.aa-meta{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; color:var(--text-3); font-size:.8125rem; }
.aa-meta code{ font-size:.75rem; background:#F2F4F7; color:var(--text-2); padding:2px 8px; }

/* Thẻ agent */
.aa-agent{ display:flex; flex-direction:column; gap:10px; }
.aa-agent-top{ display:flex; align-items:center; gap:10px; }
.aa-icon{ width:36px; height:36px; border-radius:10px; display:grid; place-items:center; background:var(--brand-50);
  color:var(--brand-600); font-family:'Material Symbols Rounded'; font-size:20px; flex:none; }
.aa-agent-name{ font-weight:650; font-size:.9375rem; color:var(--text); line-height:1.2; }
.aa-agent-step{ font-size:.75rem; color:var(--text-3); }
.aa-agent-stats{ display:grid; grid-template-columns:repeat(3,1fr); gap:6px; padding-top:10px; border-top:1px solid #F2F4F7; }
.aa-stat b{ display:block; font-size:.9375rem; color:var(--text); font-weight:650; }
.aa-stat span{ font-size:.75rem; color:var(--text-3); white-space:nowrap; }
.aa-model{ font-size:.75rem; color:var(--text-3); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }

/* Stepper */
.aa-stepper{ display:flex; align-items:center; gap:0; background:var(--surface); border:1px solid var(--border);
  border-radius:var(--r-lg); padding:18px 20px; box-shadow:var(--shadow-xs); overflow-x:auto; }
.aa-step{ display:flex; align-items:center; gap:10px; min-width:max-content; }
.aa-step-dot{ width:30px; height:30px; border-radius:50%; display:grid; place-items:center; font-size:.8125rem;
  font-weight:700; border:2px solid var(--border-strong); color:var(--text-3); background:#fff; flex:none; }
.aa-step-label{ font-size:.8125rem; font-weight:600; color:var(--text-2); }
.aa-step-sub{ font-size:.6875rem; color:var(--text-3); }
.aa-step.done .aa-step-dot{ background:#ECFDF3; border-color:#17B26A; color:#067647; }
.aa-step.active .aa-step-dot{ background:var(--brand); border-color:var(--brand); color:#fff;
  box-shadow:0 0 0 4px rgba(79,70,229,.15); }
.aa-step.warn .aa-step-dot{ background:#FFFAEB; border-color:#F79009; color:#B54708; }
.aa-step.err .aa-step-dot{ background:#FEF3F2; border-color:#F04438; color:#B42318; }
.aa-step-line{ flex:1; height:2px; background:var(--border); margin:0 14px; min-width:24px; border-radius:2px; }
.aa-step-line.done{ background:#17B26A; }

/* Timeline */
.aa-tl{ position:relative; padding-left:4px; }
.aa-tl-item{ display:grid; grid-template-columns:64px 18px 1fr; gap:10px; align-items:start; padding:8px 0; }
.aa-tl-time{ font-family:'JetBrains Mono',monospace; font-size:.75rem; color:var(--text-3); padding-top:2px; }
.aa-tl-dot{ width:10px; height:10px; border-radius:50%; margin-top:5px; background:#D0D5DD; box-shadow:0 0 0 3px #F2F4F7; }
.aa-tl-item.ok .aa-tl-dot{ background:#17B26A; box-shadow:0 0 0 3px #DCFAE6; }
.aa-tl-item.bad .aa-tl-dot{ background:#F04438; box-shadow:0 0 0 3px #FEE4E2; }
.aa-tl-item.user .aa-tl-dot{ background:var(--brand); box-shadow:0 0 0 3px #E0EAFF; }
.aa-tl-route{ font-size:.8125rem; font-weight:600; color:var(--text); }
.aa-tl-route .arrow{ color:var(--text-3); font-weight:400; margin:0 4px; }
.aa-tl-msg{ font-size:.875rem; color:var(--text-2); line-height:1.5; margin-top:2px; }
.aa-tl-item.bad .aa-tl-msg{ color:#B42318; }
.aa-tl-meta{ font-size:.6875rem; color:var(--text-3); margin-top:2px; }

/* Thẻ tính năng (trang chủ) */
.aa-feature{ background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg); padding:20px;
  box-shadow:var(--shadow-xs); min-height:200px; }
.aa-feature .aa-icon{ margin-bottom:14px; }
.aa-feature h4{ font-size:.9375rem; font-weight:650; margin:0 0 4px; }
.aa-feature p{ font-size:.8125rem; color:var(--text-3); margin:0; line-height:1.5; }
.aa-hero{ background:linear-gradient(135deg,#EEF2FF 0%,#F6F7FB 55%,#ECFDF3 100%); border:1px solid var(--border);
  border-radius:20px; padding:36px 40px; }
.aa-flow{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:18px; }
.aa-flow .aa-pill{ font-size:.8125rem; padding:5px 12px; }

/* Thẻ phương án */
.aa-option h4{ margin:0; font-size:1rem; font-weight:700; }
.aa-kv{ display:grid; grid-template-columns:1fr auto; gap:6px 12px; font-size:.8125rem; margin-top:8px; }
.aa-kv span{ color:var(--text-3); } .aa-kv b{ color:var(--text); font-weight:600; text-align:right; }

/* Tệp tải xuống */
.aa-file{ display:flex; gap:12px; align-items:center; }
.aa-file .aa-icon{ background:#F2F4F7; color:#344054; }
.aa-file b{ font-size:.875rem; display:block; } .aa-file span{ font-size:.75rem; color:var(--text-3); }
</style>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,400,0..1,0&display=block">
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""))


def html_block(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Thành phần
# ---------------------------------------------------------------------------
def pill(text: str, tone: str = "neutral", live: bool = False) -> str:
    fg, bg, bd = TONES.get(tone, TONES["neutral"])
    return (f'<span class="aa-pill{" live" if live else ""}" style="color:{fg};background:{bg};border-color:{bd}">'
            f'<span class="dot"></span>{esc(text)}</span>')


def run_pill(status: str) -> str:
    text, tone = RUN_STATUS_TONE.get(status, (status, "neutral"))
    return pill(text, tone, live=status == "running")


def icon(name: str) -> str:
    return f'<div class="aa-icon">{esc(name)}</div>'


def page_header(eyebrow: str, title: str, subtitle: str = "", meta_html: str = "") -> None:
    html_block(f'<div class="aa-header"><div><div class="aa-eyebrow">{esc(eyebrow)}</div>'
               f'<h1 class="aa-title">{esc(title)}</h1>'
               + (f'<div class="aa-sub">{esc(subtitle)}</div>' if subtitle else "")
               + "</div>" + (f'<div class="aa-meta">{meta_html}</div>' if meta_html else "") + "</div>")


def section(title: str, subtitle: str = "") -> None:
    html_block(f'<div class="aa-section"><h3>{esc(title)}</h3>' + (f"<p>{esc(subtitle)}</p>" if subtitle else "")
               + "</div>")


def stepper(steps: list[tuple[str, str, str]]) -> None:
    """steps: [(nhãn, phụ đề, trạng thái: todo|active|done|warn|err)]."""
    parts = []
    for i, (lab, sub, stt) in enumerate(steps, start=1):
        mark = "✓" if stt == "done" else ("!" if stt in ("warn", "err") else str(i))
        cls = {"done": "done", "active": "active", "warn": "warn", "err": "err"}.get(stt, "")
        parts.append(f'<div class="aa-step {cls}"><div class="aa-step-dot">{mark}</div><div>'
                     f'<div class="aa-step-label">{esc(lab)}</div><div class="aa-step-sub">{esc(sub)}</div></div></div>')
        if i < len(steps):
            parts.append(f'<div class="aa-step-line {"done" if stt == "done" else ""}"></div>')
    html_block(f'<div class="aa-stepper">{"".join(parts)}</div>')


def agent_card_html(step: int, name: str, agent: str, status: str, model: str, runs: int, duration: float,
                    tokens: int, errors: int = 0) -> str:
    text, tone = AGENT_STATUS.get(status, (status, "neutral"))
    err = (f'<div class="aa-tl-meta" style="color:#B42318">{errors} lần gửi phản hồi lỗi</div>' if errors else "")
    return (f'<div class="aa-agent"><div class="aa-agent-top">{icon(AGENT_ICON.get(agent, "smart_toy"))}<div>'
            f'<div class="aa-agent-step">Bước {step}</div><div class="aa-agent-name">{esc(name)}</div></div></div>'
            f'<div>{pill(text, tone, live=status in ("running", "revising"))}</div>'
            f'<div class="aa-model" title="{esc(model)}">{esc(model)}</div>'
            f'<div class="aa-agent-stats"><div class="aa-stat"><b>{runs}</b><span>Lần</span></div>'
            f'<div class="aa-stat"><b>{duration:.1f}</b><span>Giây</span></div>'
            f'<div class="aa-stat"><b>{f"{tokens:,}".replace(",", ".")}</b><span>Token</span></div></div>{err}</div>')


def timeline(items: list[dict], label_fn) -> None:
    """items: sự kiện AgentEvent (đã lọc done/error)."""
    if not items:
        st.caption("Chưa có hoạt động.")
        return
    rows = []
    for e in items:
        cls = "bad" if (e.get("feedback") or e.get("status") == "error") else ("user" if e["agent"] == "user" else "ok")
        to = label_fn(e["to_agent"]) if e.get("to_agent") else "Kết thúc"
        meta = ""
        if e["agent"] != "user":
            meta = f'<div class="aa-tl-meta">v{e.get("version", 0)} · {float(e.get("duration_s") or 0):.1f}s · ' \
                   f'{e.get("tokens") or 0} token</div>'
        rows.append(f'<div class="aa-tl-item {cls}"><div class="aa-tl-time">{esc(e["time"])}</div>'
                    f'<div class="aa-tl-dot"></div><div><div class="aa-tl-route">{esc(label_fn(e["agent"]))}'
                    f'<span class="arrow">→</span>{esc(to)}</div><div class="aa-tl-msg">{esc(e["summary"])}</div>{meta}'
                    f'</div></div>')
    html_block(f'<div class="aa-tl">{"".join(rows)}</div>')


def kv(rows: list[tuple[str, str]]) -> str:
    return '<div class="aa-kv">' + "".join(f"<span>{esc(k)}</span><b>{v}</b>" for k, v in rows) + "</div>"
