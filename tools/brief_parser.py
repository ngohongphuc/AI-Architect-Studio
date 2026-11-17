"""Phân tích yêu cầu tiếng Việt thành brief bằng quy tắc (dùng khi không có LLM,
và để kiểm tra chéo kết quả LLM)."""
from __future__ import annotations

import re
import unicodedata

from state import Brief

DIRS = ["đông nam", "đông bắc", "tây nam", "tây bắc", "đông", "tây", "nam", "bắc"]
PROVINCES = {
    "hà nội": "Hà Nội", "hn": "Hà Nội", "hồ chí minh": "TP. Hồ Chí Minh", "tp.hcm": "TP. Hồ Chí Minh",
    "tphcm": "TP. Hồ Chí Minh", "hcm": "TP. Hồ Chí Minh", "sài gòn": "TP. Hồ Chí Minh", "đà nẵng": "Đà Nẵng",
    "hải phòng": "Hải Phòng", "cần thơ": "Cần Thơ", "nha trang": "Khánh Hòa", "khánh hòa": "Khánh Hòa",
    "huế": "Huế", "bắc ninh": "Bắc Ninh", "hải dương": "Hải Dương", "nam định": "Nam Định",
    "thanh hóa": "Thanh Hóa", "nghệ an": "Nghệ An", "vinh": "Nghệ An", "quảng ninh": "Quảng Ninh",
    "bình dương": "Bình Dương", "đồng nai": "Đồng Nai", "vũng tàu": "Bà Rịa – Vũng Tàu", "đà lạt": "Lâm Đồng",
    "lâm đồng": "Lâm Đồng", "thái nguyên": "Thái Nguyên", "vĩnh phúc": "Vĩnh Phúc", "hưng yên": "Hưng Yên",
}
STYLES = {
    "tân cổ điển": "tân cổ điển", "cổ điển": "cổ điển", "tối giản": "tối giản", "minimalism": "tối giản",
    "indochine": "Indochine", "đông dương": "Indochine", "japandi": "Japandi", "bắc âu": "Bắc Âu",
    "scandinavian": "Bắc Âu", "nhiệt đới": "nhiệt đới", "hiện đại": "hiện đại",
}
WORD_NUM = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "sáu": 6}
EXTRA_KEYWORDS = {
    "ánh sáng": "Nhiều ánh sáng tự nhiên", "thông thoáng": "Thông thoáng", "sân vườn": "Có sân vườn",
    "thang máy": "Thang máy (ghi nhận – ngoài phạm vi bản vẽ sơ bộ)", "người già": "Có người cao tuổi",
    "ông bà": "Có người cao tuổi", "tiết kiệm": "Ưu tiên tiết kiệm chi phí", "cao cấp": "Hoàn thiện cao cấp",
    "sang trọng": "Hoàn thiện cao cấp", "cây xanh": "Nhiều cây xanh", "kinh doanh": "Tầng 1 kết hợp kinh doanh",
}


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def _count(text: str, noun: str) -> int | None:
    m = re.search(rf"(\d+|{'|'.join(WORD_NUM)})\s*{noun}", text)
    if not m:
        return None
    v = m.group(1)
    return int(v) if v.isdigit() else WORD_NUM[v]


def parse_request(request: str) -> dict:
    """Trả về dict brief (theo schema Brief) và danh sách giả định."""
    t = _norm(request)
    assumptions: list[str] = []

    # --- Lô đất ---
    rong = dai = None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*m?\s*[x×*]\s*(\d+(?:[.,]\d+)?)", t)
    if m:
        rong, dai = _num(m.group(1)), _num(m.group(2))
    else:
        mr = re.search(r"(?:rộng|mặt tiền)\s*(\d+(?:[.,]\d+)?)", t)
        md = re.search(r"(?:dài|sâu)\s*(\d+(?:[.,]\d+)?)", t)
        if mr and md:
            rong, dai = _num(mr.group(1)), _num(md.group(1))
    if not rong:
        rong, dai = 5.0, 20.0
        assumptions.append("Kích thước lô đất: không rõ, giả định 5×20 m")
    if rong > dai:
        rong, dai = dai, rong

    huong = None
    m = re.search(r"hướng\s+(" + "|".join(DIRS) + r")", t)
    if m:
        huong = m.group(1).title()
    else:
        huong = "Nam"
        assumptions.append("Hướng mặt tiền: không rõ, giả định hướng Nam")

    tinh = None
    for key in sorted(PROVINCES, key=len, reverse=True):
        if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", t):
            tinh = PROVINCES[key]
            break
    if not tinh:
        tinh = "Hà Nội"
        assumptions.append("Địa điểm: không rõ, giả định Hà Nội (áp dụng quy định chung)")

    # --- Gia đình ---
    so_nguoi = _count(t, "người")
    if not so_nguoi:
        so_nguoi = 4
        assumptions.append("Số người: không rõ, giả định 4 người")
    years = [int(y) for y in re.findall(r"(?<!\d)(19[3-9]\d|20[0-2]\d)(?!\d)", t)]
    gioi_tinh = "nam"
    nam_sinh = None
    mh = re.search(r"chồng\D{0,20}?(19\d\d|20[0-2]\d)", t)
    mw = re.search(r"vợ\D{0,20}?(19\d\d|20[0-2]\d)", t)
    if mh and not re.search(r"vợ chồng", t[max(0, mh.start() - 4):mh.end()]):
        nam_sinh = int(mh.group(1))
    elif years:
        nam_sinh = years[0]
        if re.search(r"(chủ nhà|gia chủ)\s*(là\s*)?nữ|\bchị\b.*sinh", t) or (mw and not mh and "vợ chồng" not in t):
            gioi_tinh = "nữ"
    if not nam_sinh:
        assumptions.append("Năm sinh chủ nhà: không có, bỏ qua phân tích cung mệnh")

    # --- Phòng ---
    phong_ngu = _count(t, "phòng ngủ") or _count(t, "pn")
    if not phong_ngu:
        phong_ngu = max(2, min(5, so_nguoi - 1))
        assumptions.append(f"Số phòng ngủ: không rõ, đề xuất {phong_ngu} phòng theo số người")
    phong_tho = 0 if re.search(r"không\s*(cần|có)?\s*phòng thờ", t) else (1 if "phòng thờ" in t or "thờ cúng" in t else 0)
    gara = None
    if re.search(r"gara|garage|để xe|chỗ đỗ xe|đỗ xe", t):
        gara = "ô tô" if re.search(r"ô tô|oto|ôtô|xe hơi|xe con", t) else "xe máy"
    phong_lam_viec = 1 if re.search(r"phòng làm việc|phòng đọc|thư viện", t) else 0
    so_tang = None
    m = re.search(r"(\d+)\s*tầng", t)
    if m and 1 <= int(m.group(1)) <= 7:
        so_tang = int(m.group(1))
    else:
        assumptions.append("Số tầng: để Kiến trúc sư đề xuất")

    # --- Ngân sách ---
    ngan_sach = None
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(tỷ|tỉ)\s*(\d{1,3})?(?:\s*triệu)?", t)
    if m:
        ngan_sach = _num(m.group(1)) * 1e9
        if m.group(3):
            ngan_sach += int(m.group(3)) * 1e6
    else:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*triệu", t)
        if m:
            ngan_sach = _num(m.group(1)) * 1e6
    if not ngan_sach:
        ngan_sach = rong * dai * 0.9 * 4 * 6_500_000
        assumptions.append(f"Ngân sách: không rõ, ước theo suất đầu tư ≈ {ngan_sach / 1e9:.2f} tỷ")

    phong_cach = None
    for key in sorted(STYLES, key=len, reverse=True):
        if key in t:
            phong_cach = STYLES[key]
            break
    if not phong_cach:
        phong_cach = "hiện đại"
        assumptions.append("Phong cách: không rõ, giả định hiện đại")

    extras = sorted({v for k, v in EXTRA_KEYWORDS.items() if k in t})

    brief = Brief(
        lo_dat={"rong": rong, "dai": dai, "huong": huong, "tinh": tinh},
        gia_dinh={"so_nguoi": so_nguoi, "nam_sinh_chu_nha": nam_sinh, "gioi_tinh_chu_nha": gioi_tinh,
                  "nam_sinh_thanh_vien": years},
        yeu_cau_phong={"phong_ngu": phong_ngu, "phong_tho": phong_tho, "gara": gara,
                       "phong_lam_viec": phong_lam_viec, "so_tang": so_tang},
        ngan_sach=int(round(ngan_sach)),
        phong_cach=phong_cach,
        yeu_cau_khac=extras,
        gia_dinh_bo_sung=assumptions,
    )
    return brief.model_dump()
