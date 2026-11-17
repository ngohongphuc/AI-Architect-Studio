# AI Architect Studio – Hệ thống multi-agent tự động thiết kế nhà ở

Văn phòng kiến trúc ảo gồm 5 agent (Chủ nhiệm, Kiến trúc sư, Họa viên, Kiểm định viên, Kỹ sư dự toán) phối hợp
qua LangGraph, có **2 vòng lặp phản hồi** (quy chuẩn, ngân sách; tối đa 3 vòng). Người dùng nhập yêu cầu tiếng Việt,
hệ thống xuất **3 sản phẩm** dùng chung một nguồn số liệu:

| Sản phẩm | File |
|---|---|
| Bộ bản vẽ thiết kế sơ bộ (tổng thể, mặt bằng các tầng, mái, mặt đứng, mặt cắt; có khung tên) | `ban_ve.pdf`, `ban_ve_dxf.zip` (DXF từng bản vẽ, layer riêng) |
| Thuyết minh thiết kế (10 mục theo kế hoạch) | `thuyet_minh.docx` |
| Ước tính chi phí (5 sheet, ô thành tiền là công thức Excel) | `du_toan.xlsx` |

## Cài đặt

```bash
python3.13 -m venv .venv            # Python ≥ 3.11
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # (tùy chọn) cấu hình LLM
```

## Chạy

```bash
streamlit run app.py                 # giao diện web: Thiết kế | Quản lý agent | Kết quả
python main.py --sample              # dòng lệnh, dùng yêu cầu mẫu trong kế hoạch
python main.py "Đất 4x15 hướng Tây, Đà Nẵng, 2 phòng ngủ, ngân sách 1,8 tỷ"
python evaluate.py --ablation        # đánh giá 12 yêu cầu, so sánh có / không vòng lặp
pytest -q                            # 34 test
```

Kết quả lưu trong `outputs/<mã lượt>/` (thư mục `v1/`, `v2/`… là bản vẽ nháp của từng vòng sửa).

## LLM là tùy chọn

Theo nguyên tắc của kế hoạch *“LLM chỉ viết phần văn bản, không tự nghĩ ra số liệu”*, mọi phép tính (bố trí, kiểm
tra quy chuẩn, phong thủy, chi phí) đều làm bằng Python / công thức Excel. Khi không cấu hình LLM
(`LLM_PROVIDER=none`), hệ thống chạy **chế độ quy tắc**: brief được phân tích bằng regex, văn bản thuyết minh
dùng mẫu, và vẫn ra đủ 3 sản phẩm. Khi bật LLM (Gemini / OpenAI / Claude / Ollama), LLM sẽ:
- trích xuất brief bằng Pydantic structured output (tự thử lại khi sai định dạng, rồi kiểm tra chéo với bộ phân tích quy tắc);
- viết lại đoạn ý tưởng, các đoạn thuyết minh, nhận xét kiểm định và ghi chú dự toán.

**Gán model riêng cho từng agent:** thêm hậu tố tên agent vào biến môi trường trong `.env`
(`_PROJECT_MANAGER`, `_ARCHITECT`, `_DRAFTER`, `_REVIEWER`, `_COST_ESTIMATOR`). Agent nào không khai báo thì dùng
`LLM_PROVIDER` / `LLM_MODEL` chung. Ví dụ:

```
LLM_PROVIDER=gemini                 # mặc định cho mọi agent
GOOGLE_API_KEY=...
LLM_MODEL_PROJECT_MANAGER=gemini-2.5-pro
LLM_PROVIDER_ARCHITECT=anthropic
LLM_MODEL_ARCHITECT=claude-sonnet-5-5
ANTHROPIC_API_KEY=...
LLM_TEMPERATURE_ARCHITECT=0.7
LLM_PROVIDER_REVIEWER=ollama        # chạy offline
LLM_PROVIDER_DRAFTER=none           # Họa viên không cần LLM
```

Token và prompt từng lần gọi được ghi lại, hiển thị ở trang Quản lý agent.

## Duyệt thủ công & tương tác với Kiến trúc sư

Trên trang **Thiết kế** chọn chế độ: *Tự động hoàn toàn*, *Duyệt thủ công tại tất cả các bước* hoặc *Tự chọn bước
cần duyệt* (sau Chủ nhiệm, Kiến trúc sư, Họa viên, Kiểm định viên, Kỹ sư dự toán, hồ sơ cuối). Tại mỗi điểm duyệt:

| Thao tác | Tác dụng |
|---|---|
| ✅ Đồng ý & tiếp tục | Đi theo nhánh agent đã chọn |
| ⏭ Bỏ qua lỗi, đi tiếp | (Kiểm định / Dự toán) không quay lại Kiến trúc sư |
| ↻ Chạy lại agent | Chạy lại agent vừa xong |
| 🏛 Chọn phương án | Kiến trúc sư đề xuất 3 phương án A (cân bằng) / B (tiết kiệm) / C (thoáng & cao cấp) kèm chỉ số ước tính; chọn để chốt hoặc chọn rồi chỉnh sửa |
| ✏️ Chỉnh sửa phương án | Bảng phòng theo tầng + sân, gói hoàn thiện, chiều cao tầng; áp dụng → Họa viên vẽ lại |
| 💬 Trao đổi với Kiến trúc sư | Góp ý bằng lời tự nhiên (“nhà hơi tối”, “bố mẹ già lên xuống khó”, “chuyển phòng thờ lên tầng 4”…). Có LLM: hiểu theo ngữ cảnh brief + phương án + lịch sử trao đổi; không có LLM: bộ quy tắc |
| 📝 Sửa yêu cầu thiết kế | Sửa brief (lô đất, phòng, ngân sách, phong cách…) → lập lại phương án; hoặc viết lại yêu cầu bằng lời → Chủ nhiệm phân tích lại |
| ⏹ Dừng | Hủy lượt thiết kế |

Từ code: `run_design(request, approval_points=...)` / `manager.start(request, approval_points="all")`.

## Kiến trúc

```
project_manager → [duyệt] → architect → [duyệt] → drafter → [duyệt] → reviewer → [duyệt] ─┬─(vi phạm)→ architect
                                                                                        └─(đạt)→ cost_estimator
cost_estimator → [duyệt] ─┬─(vượt ngân sách > 10%)→ architect
                          └─→ pm_report → [duyệt] → END
```
Mỗi node `[duyệt]` chỉ dừng (`interrupt`) khi bước đó nằm trong `approval_points`; nếu không thì đi thẳng. Checkpointer SQLite
(`monitoring/checkpoints.db`) cho phép tạm dừng / tiếp tục, chạy lại một agent (time travel) và mở lại lượt cũ.

| Thư mục / file | Nội dung |
|---|---|
| `state.py` | `DesignState`, `AgentEvent`, schema `Brief` (Pydantic) |
| `graph.py` | Luồng LangGraph, điểm duyệt thủ công |
| `agents/` | 5 agent; `base.py` là decorator đo thời gian, token, phát `AgentEvent`, lưu lịch sử phiên bản |
| `tools/layout_algorithm.py` | Thuật toán xếp phòng nhà ống: lõi (giếng trời, thang chữ U, sảnh) cố định thẳng hàng, chia dải theo chiều sâu, cửa đi / cửa sổ, bảng diện tích |
| `tools/sheet.py` | Tờ bản vẽ trung gian, xuất cùng lúc ra Matplotlib (PDF/PNG) và ezdxf (DXF) |
| `tools/drawing_plan.py`, `drawing_elevation.py`, `title_block.py`, `drawing_set.py` | Các bản vẽ KT-01 … KT-08 |
| `tools/rag.py` | Tra cứu quy chuẩn / phong thủy (BM25; ChromaDB nếu `USE_CHROMA=1`) |
| `tools/fengshui.py` | Cung mệnh Bát trạch, hướng tốt / xấu |
| `tools/cost_calc.py`, `xlsx_writer.py` | Diện tích quy đổi, chi phí, file XLSX có công thức |
| `tools/docx_writer.py` | Thuyết minh DOCX |
| `monitoring/` | `events.py` (SQLite timeline), `tracker.py` (token), `runner.py` (chạy nền, tạm dừng, chạy lại, duyệt) |
| `data/` | `rules.json` (tham số kiểm tra), tài liệu tóm tắt QCVN/TCVN/phong thủy, `don_gia.xlsx` |

## Dữ liệu cần nhóm bổ sung / kiểm chứng

- `data/quy_chuan/*.md` là **bản tóm tắt** để RAG chạy được. Hãy thêm PDF gốc QCVN 01:2021/BXD, TCVN 4451:2012 và
  quy định địa phương vào thư mục này (RAG tự đọc PDF); đối chiếu lại các tham số trong `data/rules.json`.
- `data/don_gia.xlsx` là đơn giá **tham khảo giả định** (tạo bằng `python -m tools.make_don_gia`); cần cập nhật
  theo báo giá thị trường thực tế mà nhóm thu thập.
- Phong thủy chỉ mang tính tư vấn.

## Giới hạn hiện tại

- Nhà ống trên lô chữ nhật, 1–5 tầng, mỗi tầng tối đa 2 phòng chính (trước / sau lõi) + 1 phòng nhỏ; mặt bằng sơ bộ,
  không tính kết cấu.
- Thuật toán bố trí là bản cơ bản (heuristic); hướng nâng cao: OR-Tools / thuật toán di truyền.
