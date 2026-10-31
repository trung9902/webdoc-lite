"""Danh mục bảng nghiệp vụ thoát nước GĐ2 và bộ nạp từ tệp Excel mẫu.

Tên bảng và tên cột trong CSDL là chữ thường không dấu; mô tả cột giữ tiêu đề gốc của tệp Excel.
Bảng `khach_hang` không có trong tệp mẫu (dữ liệu khách hàng do bài tập cấp riêng); danh mục
vẫn khai báo để áp quyền cấp bảng gaa.table.khach_hang.
"""
from __future__ import annotations

import pandas as pd
import sqlalchemy as sa

from .sql_connector import TableSpec

ORG = "SXD-TH"   # mã tổ chức WebDoc sở hữu CSDL nghiệp vụ này

SHEETS: dict[str, dict[str, str]] = {
    "phuong": {"Mã": "ma", "Phường": "phuong", "Vĩ độ tâm (giả lập)": "vi_do_tam",
               "Kinh độ tâm (giả lập)": "kinh_do_tam"},
    "doan_cong": {
        "Mã đoạn": "ma_doan", "Phường": "phuong", "Tuyến": "tuyen", "Loại": "loai", "Vật liệu": "vat_lieu",
        "Đường kính (mm)": "duong_kinh_mm", "Chiều dài khai báo (m)": "chieu_dai_khai_bao_m",
        "Chiều dài hình học (m)": "chieu_dai_hinh_hoc_m", "Nút đầu": "nut_dau", "Nút cuối": "nut_cuoi",
        "Cao độ đáy đầu (m)": "cao_do_day_dau_m", "Cao độ đáy cuối (m)": "cao_do_day_cuoi_m",
        "Độ dốc": "do_doc", "Năm xây dựng": "nam_xay_dung", "Tình trạng": "tinh_trang",
        "Bồi lắng (cm)": "boi_lang_cm", "Nguồn": "nguon", "Mức tin cậy": "muc_tin_cay",
        "Trạng thái": "trang_thai", "Lô nhập": "lo_nhap"},
    "ho_ga_cua_xa": {
        "Mã nút": "ma_nut", "Phường": "phuong", "Loại": "loai", "X VN-2000 (m)": "x_vn2000_m",
        "Y VN-2000 (m)": "y_vn2000_m", "Vĩ độ WGS84": "vi_do_wgs84", "Kinh độ WGS84": "kinh_do_wgs84",
        "Cao độ nắp (m)": "cao_do_nap_m", "Cao độ đáy (m)": "cao_do_day_m", "Nguồn": "nguon",
        "Trạng thái": "trang_thai"},
    "diem_ngap": {
        "Mã điểm ngập": "ma_diem_ngap", "Phường": "phuong", "Vị trí": "vi_tri", "X VN-2000": "x_vn2000",
        "Y VN-2000": "y_vn2000", "Vĩ độ": "vi_do", "Kinh độ": "kinh_do",
        "Độ sâu lớn nhất (cm)": "do_sau_lon_nhat_cm", "Thời gian ngập (giờ)": "thoi_gian_ngap_gio",
        "Diện tích (m²)": "dien_tich_m2", "Nguồn": "nguon", "Xác nhận UBND phường": "xac_nhan_ubnd",
        "Trạng thái": "trang_thai"},
    "tram_bom": {"Mã trạm bơm": "ma_tram_bom", "Phường": "phuong", "Công suất (m³/h)": "cong_suat_m3h",
                 "Số máy": "so_may", "Năm xây dựng": "nam_xay_dung", "Trạng thái": "trang_thai"},
    "ho_dieu_hoa": {"Mã hồ": "ma_ho", "Phường": "phuong", "Diện tích (ha)": "dien_tich_ha",
                    "Cao độ đáy (m)": "cao_do_day_m", "Mực nước điều tiết (m)": "muc_nuoc_dieu_tiet_m",
                    "Trạng thái": "trang_thai"},
}


def _cols(sheet: str) -> dict[str, str]:
    return {col: header for header, col in SHEETS[sheet].items()}


_COORDS = "han_che"
_WARD_STATUS = {"area_col": "phuong", "status_col": "trang_thai"}

TABLES = [
    TableSpec("phuong", "Danh mục phường", "7 phường, tâm giả lập.", _cols("phuong")),
    TableSpec("doan_cong", "Đoạn cống", "Mỗi dòng một đoạn cống giữa hai nút.", _cols("doan_cong"), **_WARD_STATUS),
    TableSpec("ho_ga_cua_xa", "Hố ga, cửa xả", "Mỗi dòng một nút mạng lưới; tọa độ là dữ liệu hạn chế.",
              _cols("ho_ga_cua_xa"), {c: _COORDS for c in ("x_vn2000_m", "y_vn2000_m", "vi_do_wgs84", "kinh_do_wgs84")},
              **_WARD_STATUS),
    TableSpec("diem_ngap", "Điểm ngập", "Mỗi dòng một điểm ngập; tọa độ là dữ liệu hạn chế.", _cols("diem_ngap"),
              {c: _COORDS for c in ("x_vn2000", "y_vn2000", "vi_do", "kinh_do")}, **_WARD_STATUS),
    TableSpec("tram_bom", "Trạm bơm", "Mỗi dòng một trạm bơm.", _cols("tram_bom"), **_WARD_STATUS),
    TableSpec("ho_dieu_hoa", "Hồ điều hòa", "Mỗi dòng một hồ điều hòa.", _cols("ho_dieu_hoa"), **_WARD_STATUS),
    TableSpec("khach_hang", "Khách hàng", "Khách hàng sử dụng dịch vụ thoát nước.",
              {"ma_khach_hang": "mã khách hàng", "phuong": "phường", "loai_khach_hang": "loại khách hàng",
               "tieu_thu_m3_thang": "lượng nước thải (m³/tháng)"},
              area_col="phuong", required_perm="gaa.table.khach_hang"),
]


def load_xlsx(xlsx_path: str, engine: sa.Engine) -> None:
    """Nạp các sheet dữ liệu của Bo_du_lieu_mau_GD2.xlsx vào CSDL (thay bảng nếu đã có)."""
    for sheet, mapping in SHEETS.items():
        df = pd.read_excel(xlsx_path, sheet_name=sheet)[list(mapping)].rename(columns=mapping)
        df.to_sql(sheet, engine, if_exists="replace", index=False)
