"""Nguồn siêu dữ liệu tài liệu cho intent `file_search` (định dạng, dung lượng, phường, ngày tải lên).

  WebDocDocuments : gọi GET /api/v1/documents/filter của WebDoc bằng token của CHÍNH người dùng
                    (on-behalf-of). WebDoc áp "lọc lần 1" (tổ chức, phường, PRIVATE, DRAFT).
  SampleDocuments : bản sao danh sách tài liệu mẫu của WebDoc Lite (DataSeeder) để chạy độc lập,
                    tự áp cùng quy tắc xem như WebDoc.

LLM chỉ đề xuất bộ lọc; `sanitize` giữ lại đúng các tham số API cho phép, kiểm kiểu từng giá trị.
`recheck` áp lại quy tắc phường/riêng tư trên kết quả trả về (GAA không tin tuyệt đối nguồn).
Chỉ siêu dữ liệu đi qua LLM, không có nội dung OCR.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

from .policy import Subject

FIELDS = ("id", "title", "originalFilename", "type", "sizeBytes", "sizeKb", "pageCount", "status", "accessLevel",
          "area", "departmentName", "createdBy", "createdAt")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TYPE = re.compile(r"^[a-z0-9]{2,5}$")


class DocumentSourceError(RuntimeError):
    pass


def _n(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


@dataclass
class DocFilter:
    q: str | None = None             # có trong tên tệp hoặc tiêu đề
    type: str | None = None          # pdf, png, docx, xlsx...
    area: str | None = None          # phường
    minSizeKb: float | None = None   # >= (KB = 1024 byte)
    maxSizeKb: float | None = None   # < (loại trừ: 100 KB không tính là "dưới 100 KB")
    date_from: str | None = None     # ngày tải lên từ (YYYY-MM-DD, gồm cả ngày này)
    date_to: str | None = None       # ngày tải lên đến (gồm cả ngày này)

    def params(self) -> dict:
        p = {k: v for k, v in asdict(self).items() if v not in (None, "")}
        if "date_from" in p:
            p["from"] = p.pop("date_from")
        if "date_to" in p:
            p["to"] = p.pop("date_to")
        return p


def sanitize(raw: object, known_areas: list[str] = ()) -> tuple[DocFilter, list[str]]:
    """Bộ lọc do LLM đề xuất -> DocFilter hợp lệ. Trả kèm danh sách điều kiện bị bỏ."""
    f, dropped = DocFilter(), []
    if not isinstance(raw, dict):
        return f, ([f"bộ lọc không phải đối tượng: {raw!r}"] if raw else [])
    alias = {"from": "date_from", "to": "date_to"}
    for k, v in raw.items():
        key = alias.get(k, k)
        if v in (None, ""):
            continue
        if key == "q" and isinstance(v, str) and len(v) <= 100:
            f.q = v.strip()
        elif key == "type" and isinstance(v, str) and _TYPE.match(v.lower().lstrip(".")):
            f.type = v.lower().lstrip(".")
        elif key == "area" and isinstance(v, str) and len(v) <= 64:
            match = [a for a in known_areas if _n(a) == _n(v)]
            f.area = match[0] if match else v.strip()
        elif key in ("minSizeKb", "maxSizeKb") and isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0:
            setattr(f, key, float(v))
        elif key in ("date_from", "date_to") and isinstance(v, str) and _DATE.match(v):
            setattr(f, key, v)
        else:
            dropped.append(f"{k}={v!r}")
    return f, dropped


def recheck(s: Subject, docs: list[dict]) -> tuple[list[dict], int]:
    """Áp lại quy tắc xem tối thiểu trên kết quả nguồn trả về: phường của người dùng, tài liệu riêng tư."""
    keep = []
    for d in docs:
        own = d.get("createdBy") == s.user_id
        if d.get("accessLevel") == "PRIVATE" and not own:
            continue
        if s.areas and not own and "cross_org" not in s.permissions and d.get("area") not in s.areas:
            continue
        keep.append({k: d.get(k) for k in FIELDS})
    return keep, len(docs) - len(keep)


# ---------------------------------------------------------------------------
class WebDocDocuments:
    name = "webdoc"

    def __init__(self, base_url: str | None = None, areas: list[str] = (), path: str = "/api/v1/documents/filter"):
        self.base = (base_url or os.getenv("GAA_WEBDOC_DOCS_URL") or os.getenv("GAA_WEBDOC_URL", "http://127.0.0.1:8090")).rstrip("/")
        self.path, self.areas = path, list(areas)

    def known_areas(self) -> list[str]:
        return self.areas

    def search(self, s: Subject, f: DocFilter, token: str | None) -> list[dict]:
        if not token:
            raise DocumentSourceError("Nguồn tài liệu WebDoc cần token của người dùng")
        out, page = [], 0
        while True:
            qs = urllib.parse.urlencode({**f.params(), "page": page, "size": 200})
            req = urllib.request.Request(f"{self.base}{self.path}?{qs}",
                                         headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = json.loads(r.read())
            except urllib.error.HTTPError as e:
                raise DocumentSourceError(f"WebDoc trả {e.code} cho tra cứu tài liệu") from e
            except Exception as e:  # noqa: BLE001
                raise DocumentSourceError(f"Không gọi được API tài liệu WebDoc: {e}") from e
            out += body.get("list", [])
            page += 1
            if len(out) >= int(body.get("total", 0)) or not body.get("list") or page >= 50:
                return out


def _java_hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    return h - (1 << 32) if h >= 1 << 31 else h


def _java_rem(a: int, b: int) -> int:
    return a - b * int(a / b)


def _sample_rows(org: str) -> list[dict]:
    """Giống DataSeeder.demoDocuments của WebDoc Lite (cùng tên tệp, dung lượng, phường, ngày, người tạo)."""
    infra, drain, data = "Phòng Hạ tầng", "Phòng Thoát nước", "Phòng Quản lý dữ liệu"
    rows = []

    def add(title, fn, typ, size, area, dept, by, date, status="PUBLISHED", access="INTERNAL", pages=0):
        rows.append({"id": len(rows) + 1, "title": title, "originalFilename": fn, "type": typ, "sizeBytes": abs(size),
                     "sizeKb": round(abs(size) / 1024, 1), "pageCount": pages, "status": status, "accessLevel": access,
                     "area": area, "departmentName": dept, "createdBy": by, "createdAt": f"{date}T09:00:00",
                     "_org": org})

    for code, title, area, dept, by, date in (
            ("HS-01", "Hồ sơ hoàn công tuyến cống Quang Trung", "Hạc Thành", infra, "capnhat.ht", "2025-06-25"),
            ("HS-02", "Hồ sơ hoàn công tuyến cống Lê Lợi", "Hàm Rồng", infra, "capnhat.ht", "2025-05-12"),
            ("HS-03", "Hồ sơ hoàn công tuyến cống Hải Thượng Lãn Ông", "Đồng Tiến", drain, "qtkt.gd2", "2025-07-03"),
            ("HS-04", "Hồ sơ hoàn công hồ điều hòa Đông Quang", "Đông Quang", drain, "qtkt.gd2", "2025-08-19"),
            ("HS-05", "Hồ sơ nạo vét tuyến cống Nguyễn Trãi", "Nguyệt Viên", infra, "capnhat.ht", "2025-09-02"),
            ("HS-06", "Hồ sơ hoàn công trạm bơm Quảng Phú", "Quảng Phú", drain, "qtkt.gd2", "2025-10-11"),
            ("HS-07", "Hồ sơ hoàn công tuyến cống Đông Sơn 2", "Đông Sơn", drain, "doichieu.ds", "2025-11-05"),
            ("HS-08", "Hồ sơ cải tạo hố ga Hạc Thành", "Hạc Thành", infra, "capnhat.ht", "2025-12-01"),
            ("HS-09", "Hồ sơ hoàn công tuyến cống Quang Trung (bản lưu)", "Hạc Thành", infra, "capnhat.ht", "2026-01-15"),
            ("HS-10", "Biên bản nghiệm thu nạo vét Tuyến ĐS-1", "Đông Sơn", drain, "doichieu.ds", "2026-02-10")):
        add(title, code + ".pdf", "pdf", 1_000_000 + _java_rem(_java_hash(code), 900_000), area, dept, by, date, pages=3)
    for no, kb, area, date in (("01", 79, "Đồng Tiến", "2026-01-02"), ("06", 58, "Nguyệt Viên", "2026-01-08"),
                               ("09", 51, "Đông Sơn", "2025-09-07"), ("10", 94, "Đồng Tiến", "2026-03-22"),
                               ("12", 79, "Hạc Thành", "2025-12-17"), ("14", 43, "Đồng Tiến", "2026-03-25"),
                               ("15", 48, "Hạc Thành", "2025-09-14"), ("17", 90, "Nguyệt Viên", "2026-04-05"),
                               ("18", 44, "Đông Quang", "2026-03-06")):
        add(f"Ảnh hiện trạng {no}", f"anh_hien_trang_{no}.png", "png", kb * 1024 + 300, area, infra, "qtkt.gd2", date)
    add("Sơ đồ tổng thể", "so_do_tong_the.png", "png", 100 * 1024, "Hàm Rồng", data, "qtkt.gd2", "2026-02-01")
    for no, kb, area, date in (("02", 256, "Hàm Rồng", "2026-01-20"), ("03", 512, "Quảng Phú", "2026-02-14"),
                               ("05", 1200, "Đông Quang", "2026-03-02"), ("07", 140, "Hạc Thành", "2026-03-09")):
        add(f"Ảnh hiện trạng {no}", f"anh_hien_trang_{no}.png", "png", kb * 1024, area, infra, "qtkt.gd2", date)
    add("Báo cáo hiện trạng hệ thống thoát nước", "bao_cao_hien_trang.pdf", "pdf", 2400 * 1024, None, data, "qtdl.gd2", "2026-01-12")
    add("Bảng tổng hợp khối lượng", "tong_hop_khoi_luong.xlsx", "xlsx", 380 * 1024, None, data, "qtdl.gd2", "2026-02-18")
    add("Quyết định phê duyệt dự án", "quyet_dinh_phe_duyet.docx", "docx", 85 * 1024, None, data, "qtkt.gd2", "2025-12-20")
    add("Kế hoạch nạo vét 2026 (bản nháp)", "ke_hoach_nao_vet_2026.docx", "docx", 64 * 1024, "Đông Sơn", drain,
        "doichieu.ds", "2026-03-30", status="DRAFT")
    add("Ghi chú nội bộ của quản lý", "ghi_chu_noi_bo.docx", "docx", 20 * 1024, None, data, "qtdl.gd2", "2026-03-31",
        access="PRIVATE")
    return rows


class SampleDocuments:
    """Chạy không cần WebDoc: cùng dữ liệu mẫu và cùng quy tắc xem với API /api/v1/documents/filter."""
    name = "sample"

    def __init__(self, org: str) -> None:
        self.rows = _sample_rows(org)

    def known_areas(self) -> list[str]:
        return sorted({r["area"] for r in self.rows if r["area"]})

    @staticmethod
    def visible(s: Subject, r: dict) -> bool:
        if r["_org"] != s.org and "cross_org" not in s.permissions:
            return False
        if r["createdBy"] == s.user_id:
            return True
        if s.areas and r["area"] not in s.areas:
            return False
        if r["accessLevel"] == "PRIVATE":
            return False
        if r["status"] == "DRAFT" and s.role not in ("admin", "org_manager"):
            return False
        return True

    def search(self, s: Subject, f: DocFilter, token: str | None = None) -> list[dict]:
        out = []
        for r in self.rows:
            if not self.visible(s, r):
                continue
            if f.q and _n(f.q) not in _n(r["originalFilename"]) + " " + _n(r["title"]):
                continue
            if f.type and r["type"] != f.type:
                continue
            if f.area and r["area"] != f.area:
                continue
            if f.minSizeKb is not None and r["sizeBytes"] < f.minSizeKb * 1024:
                continue
            if f.maxSizeKb is not None and r["sizeBytes"] >= f.maxSizeKb * 1024:
                continue
            day = r["createdAt"][:10]
            if (f.date_from and day < f.date_from) or (f.date_to and day > f.date_to):
                continue
            out.append({k: r[k] for k in FIELDS})
        return sorted(out, key=lambda r: (r["createdAt"], -r["id"]), reverse=True)


def make_documents(domain) -> SampleDocuments | WebDocDocuments:
    cfg = (getattr(domain, "raw", {}) or {}).get("documents", {})
    kind = os.getenv("GAA_DOCS", "webdoc" if os.getenv("GAA_BACKEND") == "webdoc" else "sample")
    if kind == "webdoc":
        return WebDocDocuments(areas=cfg.get("areas", []), path=cfg.get("webdoc_path", "/api/v1/documents/filter"))
    if kind == "sample":
        return SampleDocuments(getattr(domain, "org", "CTN"))
    raise ValueError(f"GAA_DOCS không hợp lệ: {kind} (sample|webdoc)")
