"""CSDL nghiệp vụ (ngoài WebDoc): tiêu thụ nước, khách hàng... đọc trực tiếp bằng kết nối CHỈ ĐỌC.

Khai báo trong hồ sơ nghiệp vụ (profile.yaml, mục `business_db`):
  url: đường dẫn SQLite (mặc định) hoặc URL SQLAlchemy (postgresql://..., mysql+pymysql://...)
  datasets: tên tập dữ liệu -> {table, title, description, columns: {cột: {desc, class?}}}

Chỉ đọc đúng bảng/cột đã khai báo (định danh kiểm bằng regex, không lấy từ LLM). Dữ liệu nạp vào
DatasetMeta như các nguồn khác, nên Data Gateway áp cùng RBAC/ABAC (lọc phường, trạng thái, che cột).
Biến GAA_BUSINESS_DB ghi đè `url`. Nếu là tệp SQLite mặc định chưa có, tự sinh dữ liệu mẫu (GIẢ LẬP).
"""
from __future__ import annotations

import os
import re
import sqlite3

import pandas as pd

from .backends import _meta_from_frame
from .domain import ROOT, DomainProfile
from .policy import DatasetMeta

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
MAX_ROWS = 50_000

# ---- dữ liệu mẫu: sản lượng nước tiêu thụ theo kỳ, phường, loại khách hàng (giả lập, tất định)
WARD_BASE_M3 = {"Hạc Thành": 182_000, "Hàm Rồng": 126_000, "Nguyệt Viên": 98_000, "Đông Tiến": 87_000,
                "Đông Quang": 74_000, "Đông Sơn": 112_000, "Quảng Phú": 69_000}
CUSTOMER_MIX = {"Hộ gia đình": (0.62, 14.5), "Kinh doanh": (0.26, 48.0), "Cơ quan": (0.12, 115.0)}  # tỷ trọng, m³/KH/tháng
SEASON = (0.92, 0.88, 0.95, 1.02, 1.08, 1.12, 1.15, 1.13, 1.06, 1.00, 0.95, 0.94)
GROWTH_2026 = 1.04


def sample_rows() -> list[tuple]:
    rows = []
    for year, last_month in ((2025, 12), (2026, 9)):
        g = GROWTH_2026 if year == 2026 else 1.0
        for m in range(1, last_month + 1):
            for wi, (ward, base) in enumerate(WARD_BASE_M3.items()):
                for ti, (kind, (share, per_cust)) in enumerate(CUSTOMER_MIX.items()):
                    jitter = 1 + ((wi * 7 + ti * 3 + m * 5) % 9 - 4) / 100      # ±4 %, tất định
                    m3 = round(base * share * SEASON[m - 1] * g * jitter)
                    rows.append((f"{year}-{m:02d}", year, m, ward, kind, round(base * share * g / per_cust), m3,
                                 "Chính thức"))
    return rows


def create_sample_db(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    c = sqlite3.connect(path)
    try:
        with c:
            c.execute("DROP TABLE IF EXISTS tieu_thu_nuoc")
            c.execute("""CREATE TABLE tieu_thu_nuoc (
                ky TEXT NOT NULL, nam INTEGER NOT NULL, thang INTEGER NOT NULL, phuong TEXT NOT NULL,
                loai_khach_hang TEXT NOT NULL, so_khach_hang INTEGER NOT NULL, san_luong_m3 INTEGER NOT NULL,
                trang_thai TEXT NOT NULL)""")
            c.executemany("INSERT INTO tieu_thu_nuoc VALUES (?,?,?,?,?,?,?,?)", sample_rows())
    finally:
        c.close()


# ---------------------------------------------------------------------------
def _read_sqlite(path: str, sql: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        return pd.read_sql_query(sql, conn)
    finally:
        conn.close()


def _read_sqlalchemy(url: str, sql: str) -> pd.DataFrame:
    import sqlalchemy as sa   # chỉ cần khi dùng PostgreSQL/MySQL
    eng = sa.create_engine(url, execution_options={"postgresql_readonly": True})
    try:
        with eng.connect() as conn:
            return pd.read_sql_query(sa.text(sql), conn)
    finally:
        eng.dispose()


class BusinessDbBackend:
    def __init__(self, domain: DomainProfile, cfg: dict | None = None) -> None:
        cfg = cfg if cfg is not None else domain.raw.get("business_db", {})
        default = cfg.get("url", "data/csdl_nghiep_vu.sqlite")
        url = os.getenv("GAA_BUSINESS_DB") or default
        self.is_sqlite = "://" not in url
        self.url = os.path.join(ROOT, url) if self.is_sqlite and not os.path.isabs(url) else url
        if self.is_sqlite and not os.path.exists(self.url):
            if url != default:
                raise ValueError(f"Không tìm thấy CSDL nghiệp vụ: {self.url}")
            create_sample_db(self.url)
        self.datasets: dict[str, DatasetMeta] = {}
        for name, spec in cfg.get("datasets", {}).items():
            table, cols = spec.get("table", name), list(spec["columns"])
            bad = [x for x in [table, *cols] if not _IDENT.match(x)]
            if bad:
                raise ValueError(f"Tên bảng/cột không hợp lệ trong business_db.{name}: {bad}")
            sql = "SELECT " + ", ".join(f'"{c}"' for c in cols) + f' FROM "{table}" LIMIT {MAX_ROWS}'
            df = _read_sqlite(self.url, sql) if self.is_sqlite else _read_sqlalchemy(self.url, sql)
            self.datasets[name] = _meta_from_frame(domain, name, spec, df)
