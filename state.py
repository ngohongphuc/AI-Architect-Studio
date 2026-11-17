"""Định nghĩa trạng thái dùng chung (DesignState), sự kiện (AgentEvent) và schema brief."""
from __future__ import annotations

import operator
from typing import Annotated, Optional, TypedDict

from pydantic import BaseModel, Field


class AgentEvent(TypedDict, total=False):
    time: str          # "14:03:22"
    agent: str         # "reviewer"
    status: str        # "running" | "done" | "revising" | "error"
    to_agent: str      # Agent nhận việc tiếp theo
    summary: str       # "Mật độ XD 100% > 90%"
    tokens: int
    duration_s: float
    version: int       # Lần chạy thứ mấy của agent
    feedback: bool     # True nếu là phản hồi lỗi (tô đỏ trên timeline)


class DesignState(TypedDict, total=False):
    run_id: str
    user_request: str        # Yêu cầu gốc
    brief: dict              # Brief có cấu trúc          (Agent 1)
    concept: str             # Ý tưởng thiết kế          (Agent 2)
    program: dict            # Danh sách phòng theo tầng (Agent 2)
    layout: dict             # Tọa độ, kích thước phòng  (Agent 3)
    area_table: dict         # Thống kê diện tích        (Agent 3)
    drawings: dict           # Đường dẫn PDF, DXF        (Agent 3)
    review: dict             # Kết quả kiểm tra          (Agent 4)
    cost: dict               # Kết quả chi phí           (Agent 5)
    cost_file: str           # Đường dẫn du_toan.xlsx    (Agent 5)
    description_file: str    # Đường dẫn thuyet_minh     (Agent 1)
    iteration: int           # Số vòng sửa hiện tại
    max_iterations: int      # Giới hạn số vòng sửa
    manual_review: bool      # Bật duyệt thủ công
    feedback: list           # Phản hồi đang chờ Kiến trúc sư xử lý
    feedback_source: str     # "reviewer" | "cost_estimator" | "user"
    route: str               # Nhánh tiếp theo do agent quyết định
    remaining_issues: list   # Lỗi còn tồn tại khi hết số vòng sửa
    versions: dict           # Số lần chạy của từng agent
    output_dir: str
    final_files: dict
    approval_points: list    # các agent cần duyệt thủ công sau khi chạy xong
    options: list            # các phương án Kiến trúc sư đề xuất để chủ nhà chọn
    trao_doi: Annotated[list, operator.add]  # hội thoại chủ nhà ↔ kiến trúc sư
    log: Annotated[list, operator.add]       # Nhật ký hoạt động các agent
    events: Annotated[list, operator.add]    # Danh sách AgentEvent
    history: Annotated[list, operator.add]   # Đầu ra từng phiên bản (so sánh v1, v2, v3)


# ---------------------------------------------------------------------------
# Schema brief (dùng cho structured output của LLM và kiểm tra dữ liệu)
# ---------------------------------------------------------------------------
class LoDat(BaseModel):
    rong: float = Field(description="Chiều rộng mặt tiền lô đất (m)")
    dai: float = Field(description="Chiều sâu lô đất (m)")
    huong: str = Field("Nam", description="Hướng mặt tiền: Bắc, Nam, Đông, Tây, Đông Nam, ...")
    tinh: str = Field("Hà Nội", description="Tỉnh/thành phố")


class GiaDinh(BaseModel):
    so_nguoi: int = 4
    nam_sinh_chu_nha: Optional[int] = Field(None, description="Năm sinh chủ nhà (người đứng tên)")
    gioi_tinh_chu_nha: str = Field("nam", description="nam | nữ")
    nam_sinh_thanh_vien: list[int] = Field(default_factory=list)


class YeuCauPhong(BaseModel):
    phong_ngu: int = 3
    phong_tho: int = 0
    gara: Optional[str] = Field(None, description="'xe máy' | 'ô tô' | None")
    phong_lam_viec: int = 0
    so_tang: Optional[int] = Field(None, description="Số tầng nếu khách yêu cầu")


class Brief(BaseModel):
    lo_dat: LoDat
    gia_dinh: GiaDinh = Field(default_factory=GiaDinh)
    yeu_cau_phong: YeuCauPhong = Field(default_factory=YeuCauPhong)
    ngan_sach: int = Field(description="Ngân sách (VNĐ)")
    phong_cach: str = "hiện đại"
    yeu_cau_khac: list[str] = Field(default_factory=list)
    gia_dinh_bo_sung: list[str] = Field(default_factory=list, description="Các giả định tự điền khi thiếu thông tin")
