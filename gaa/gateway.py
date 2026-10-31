"""Data Gateway — điểm thực thi chính sách (PEP) giữa các agent và CSDL nghiệp vụ / Genadata.

Hỗ trợ cả 2 chế độ:
  1) SqlConnector: kết nối CSDL trực tiếp (SQLite/PostgreSQL), phân quyền bảng authorize_table,
     lọc hàng, che cột, LIMIT 5000 và timeout 5s.
  2) Backend / MockGenadata / WebdocClient: phân quyền tập dữ liệu authorize_dataset,
     lọc trên pandas DataFrame in-memory, kiểm tra vòng đời bản ghi, kiểm tra masking.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import audit
from .policy import DatasetMeta, Decision, Environment, Subject, authorize_dataset, authorize_table
from .sql_connector import QueryRejected, QuerySpec, QueryTimeout, SqlConnector

__all__ = ["DataGateway", "FetchResult", "QuerySpec", "MockGenadata", "DataSourceError", "ALLOWED_OPS", "_mock_datasets"]

ALLOWED_OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "contains", "between"}


class DataSourceError(RuntimeError):
    """Nguồn dữ liệu từ chối hoặc không trả được (VD WebDoc 401/403/404)."""


@dataclass
class FetchResult:
    dataset: str
    df: pd.DataFrame | None
    decision: Decision
    notes: list[str] = field(default_factory=list)


def _who(s: Subject) -> dict:
    return {"user": s.user_id, "org": s.org, "dept": s.dept, "roles": sorted(s.roles)}


# ---------------------------------------------------------------------------
def _mock_datasets(seed: int = 69) -> dict[str, DatasetMeta]:
    rng = np.random.default_rng(seed)
    days = pd.date_range("2026-01-01", "2026-09-30", freq="D")

    # 1) Kết quả nội kiểm chất lượng nước sạch (CN-E-61) — dùng chung trong tổ chức
    rows = []
    for nmn, base in (("NMN số 1", 0.45), ("NMN số 2", 0.40)):
        for d in days:
            rows.append({
                "ngay": d.date().isoformat(), "nha_may": nmn, "vi_tri": "Bể chứa sau xử lý",
                "ph": round(rng.normal(7.2, 0.15), 2),
                "do_duc_ntu": round(abs(rng.normal(0.8, 0.25)), 2),
                "clo_du_mgl": round(float(np.clip(rng.normal(base, 0.07), 0.15, 0.9)), 2),
                "coliform": int(rng.random() < 0.01),
                "_org": "CTN", "_dept": "PTN", "_scope": "cong_khai", "_che_do": "dung_chung",
            })
    nk = pd.DataFrame(rows)
    nk["ket_luan"] = np.where((nk.clo_du_mgl.between(0.2, 1.0)) & (nk.do_duc_ntu <= 2) & (nk.coliform == 0), "Đạt", "Không đạt")

    # 2) Sự cố mạng lưới (DM11) — theo phòng ban; chi phí và toạ độ là dữ liệu hạn chế
    loai = ["Vỡ, rò rỉ đường ống", "Mất áp", "Gián đoạn cấp nước", "Sự cố thiết bị", "Tắc nghẽn, ngập"]
    rows = []
    for i in range(240):
        xn = "XN1" if rng.random() < 0.55 else "XN2"
        d = days[rng.integers(0, len(days))]
        rows.append({
            "ma_su_co": f"SC-2026-{i + 1:04d}", "ngay": d.date().isoformat(),
            "xi_nghiep": xn, "loai": loai[rng.integers(0, len(loai))],
            "muc_do": ["Thấp", "Trung bình", "Cao"][rng.integers(0, 3)],
            "thoi_gian_khac_phuc_gio": round(float(rng.gamma(2.0, 3.0)), 1),
            "chi_phi_khac_phuc_vnd": int(rng.integers(5, 400) * 100_000),
            "toa_do": f"{10.75 + rng.random() / 10:.5f},{106.65 + rng.random() / 10:.5f}",
            "nguoi_bao_cao_sdt": f"09{rng.integers(10_000_000, 99_999_999)}",
            "_org": "CTN", "_dept": xn, "_scope": "phong_ban",
            "_che_do": "han_che" if rng.random() < 0.05 else "theo_phan_quyen",
        })
    # vài bản ghi của tổ chức khác để kiểm tra cô lập tổ chức
    for i in range(20):
        d = days[rng.integers(0, len(days))]
        rows.append({
            "ma_su_co": f"SC-K-{i + 1:04d}", "ngay": d.date().isoformat(), "xi_nghiep": "XN-K",
            "loai": loai[0], "muc_do": "Cao", "thoi_gian_khac_phuc_gio": 5.0,
            "chi_phi_khac_phuc_vnd": 10_000_000, "toa_do": "0,0", "nguoi_bao_cao_sdt": "0900000000",
            "_org": "CTN-KHAC", "_dept": "XN-K", "_scope": "phong_ban", "_che_do": "theo_phan_quyen",
        })
    sc = pd.DataFrame(rows)

    # 3) Danh mục tài liệu căn cứ — có phạm vi Riêng tư / Phòng ban / Công khai (Genadata 3.9.4)
    tl = pd.DataFrame([
        {"ma": "GP-KTNM-01", "ten": "Giấy phép khai thác nước mặt NMN số 1", "loai": "Giấy phép",
         "hieu_luc_den": "2026-12-15", "doi_tuong": "NMN số 1", "trang_thai": "Đáp ứng yêu cầu chất lượng",
         "_org": "CTN", "_dept": "PKT", "_scope": "cong_khai", "_owner": "u_minh", "_che_do": "dung_chung"},
        {"ma": "HD-XLNT-A", "ten": "Hợp đồng QLVH Trạm XLNT khu A", "loai": "Hợp đồng",
         "hieu_luc_den": "2026-12-31", "doi_tuong": "Trạm XLNT khu A", "trang_thai": "Đáp ứng yêu cầu chất lượng",
         "_org": "CTN", "_dept": "PKD", "_scope": "phong_ban", "_owner": "u_minh", "_che_do": "theo_phan_quyen"},
        {"ma": "BB-HC-07", "ten": "Biên bản hiệu chuẩn đồng hồ tổng TBTA số 3", "loai": "Biên bản hiệu chuẩn",
         "hieu_luc_den": "2026-10-24", "doi_tuong": "TBTA số 3", "trang_thai": "Chờ rà soát",
         "_org": "CTN", "_dept": "XN1", "_scope": "phong_ban", "_owner": "u_lan", "_che_do": "theo_phan_quyen"},
        {"ma": "NHAP-LAN-1", "ten": "Ghi chú hiện trường (nháp)", "loai": "Khác",
         "hieu_luc_den": "2027-06-30", "doi_tuong": "Mạng lưới XN1", "trang_thai": "Khởi tạo",
         "_org": "CTN", "_dept": "XN1", "_scope": "rieng_tu", "_owner": "u_lan", "_che_do": "theo_phan_quyen"},
        {"ma": "PA-BV-01", "ten": "Phương án bảo vệ trạm bơm đầu mối", "loai": "Phương án",
         "hieu_luc_den": "2027-12-31", "doi_tuong": "Trạm bơm nước thô", "trang_thai": "Đáp ứng yêu cầu chất lượng",
         "_org": "CTN", "_dept": "PKT", "_scope": "cong_khai", "_owner": "u_minh", "_che_do": "han_che"},
    ])

    return {
        "noi_kiem_cln": DatasetMeta(
            "noi_kiem_cln", "Kết quả nội kiểm chất lượng nước sạch",
            "Một dòng/ngày/nhà máy, tại bể chứa sau xử lý (CN-E-61).",
            {"ngay": "ngày lấy mẫu (YYYY-MM-DD)", "nha_may": "tên nhà máy", "vi_tri": "vị trí lấy mẫu",
             "ph": "pH", "do_duc_ntu": "độ đục (NTU)", "clo_du_mgl": "clo dư tự do (mg/L)",
             "coliform": "coliform (CFU/100 mL)", "ket_luan": "Đạt/Không đạt"},
            {}, nk),
        "su_co": DatasetMeta(
            "su_co", "Sự cố cấp nước",
            "Mỗi dòng một sự cố (danh mục DM11), theo xí nghiệp quản lý.",
            {"ma_su_co": "mã sự cố", "ngay": "ngày phát sinh", "xi_nghiep": "xí nghiệp",
             "loai": "loại sự cố", "muc_do": "mức độ", "thoi_gian_khac_phuc_gio": "thời gian khắc phục (giờ)",
             "chi_phi_khac_phuc_vnd": "chi phí khắc phục (đồng)", "toa_do": "toạ độ vị trí",
             "nguoi_bao_cao_sdt": "số điện thoại người báo"},
            {"chi_phi_khac_phuc_vnd": "han_che", "toa_do": "han_che", "nguoi_bao_cao_sdt": "ca_nhan"}, sc),
        "tai_lieu": DatasetMeta(
            "tai_lieu", "Danh mục tài liệu căn cứ",
            "Siêu dữ liệu tài liệu căn cứ, có hạn hiệu lực.",
            {"ma": "mã tài liệu", "ten": "tên", "loai": "loại", "hieu_luc_den": "hiệu lực đến",
             "doi_tuong": "đối tượng liên kết", "trang_thai": "trạng thái chất lượng (DM14)"},
            {}, tl),
    }


class MockGenadata:
    def __init__(self) -> None:
        self.datasets = _mock_datasets()


class DataGateway:
    def __init__(self, backend_or_connector, env: Environment) -> None:
        self.backend = backend_or_connector
        self.connector = backend_or_connector
        self.env = env

    def for_token(self, token: str | None) -> "DataGateway":
        """Backend WebDoc: mỗi yêu cầu dùng token của chính người dùng (on-behalf-of)."""
        if token and hasattr(self.backend, "with_token"):
            return DataGateway(self.backend.with_token(token), self.env)
        return self

    def _is_sql(self) -> bool:
        return hasattr(self.connector, "list_tables")

    def catalog(self, s: Subject, action: str = "analytics") -> list[dict]:
        """Danh mục dữ liệu NGƯỜI DÙNG NÀY thấy được — chỉ phần này được đưa cho LLM."""
        if self._is_sql():
            out = []
            for name in self.connector.list_tables():
                t = self.connector.tables[name]
                dec = authorize_table(s, action, t, self.env, self.connector.org)
                if not dec.allow:
                    continue
                visible_cols = {c: d for c, d in t.columns.items() if c not in dec.masked_columns}
                out.append({"dataset": name, "title": t.title, "description": t.description,
                            "columns": visible_cols, "masked_columns": dec.masked_columns})
            return out

        out = []
        for meta in self.backend.datasets.values():
            if meta.search_only and action == "analytics":
                continue
            dec = authorize_dataset(s, action, meta, self.env)
            if not dec.allow:
                continue
            visible_cols = {c: d for c, d in meta.columns.items() if c not in dec.masked_columns}
            out.append({"dataset": meta.name, "title": meta.title, "description": meta.description,
                        "columns": visible_cols, "masked_columns": dec.masked_columns})
        return out

    def _deny(self, s: Subject, spec: QuerySpec, event: str, reasons: list[str], question: str) -> FetchResult:
        audit.log(event, **_who(s), dataset=spec.dataset, reasons=reasons, question=question)
        return FetchResult(str(spec.dataset), None, Decision(False, reasons), [])

    def fetch(self, s: Subject, spec: QuerySpec, action: str = "analytics", question: str = "") -> FetchResult:
        if self._is_sql():
            return self._fetch_sql(s, spec, action, question)
        return self._fetch_dataset(s, spec, action, question)

    def _fetch_sql(self, s: Subject, spec: QuerySpec, action: str = "analytics", question: str = "") -> FetchResult:
        try:
            t = self.connector.table(spec.dataset)
        except QueryRejected as e:
            return self._deny(s, spec, "fetch_rejected", [str(e)], question)
        dec = authorize_table(s, action, t, self.env, self.connector.org)
        if not dec.allow:
            return self._deny(s, spec, "fetch_denied", dec.reasons, question)

        # Lọc trên cột bị che cũng làm lộ giá trị, nên chặn như khi xin cột đó
        touched = set(spec.columns or []) | {f.get("col") for f in spec.filters if isinstance(f, dict)}
        asked = sorted(c for c in touched if c in dec.masked_columns)
        if asked:
            why = [r for r in dec.reasons if "che cột" in r]
            return self._deny(s, spec, "fetch_denied",
                              [f"Từ chối: yêu cầu cột dữ liệu hạn chế {', '.join(asked)}"] + why, question)

        enforced, notes = list(dec.enforced), []
        columns = spec.columns or [c for c in t.columns if c not in dec.masked_columns]
        try:
            # Vòng đời bản ghi: người có view_proposed mặc định vẫn chỉ dùng bản ghi chính thức,
            # trừ khi agent lọc rõ theo cột trạng thái
            if t.status_col and dec.view_proposed:
                if any(isinstance(f, dict) and f.get("col") == t.status_col for f in spec.filters):
                    notes.append("Kết quả có thể gồm dữ liệu chưa duyệt: gắn nhãn TẠM TÍNH")
                else:
                    other = {"col": t.status_col, "op": "!=", "value": t.official_status}
                    left_out = self.connector.count_by(spec, enforced + [other], t.status_col)
                    enforced.append({"col": t.status_col, "op": "==", "value": t.official_status})
                    if left_out:
                        notes.append(f"Chỉ dùng dữ liệu {t.official_status}: bỏ "
                                     + ", ".join(f"{n} bản ghi {st}" for st, n in sorted(left_out.items(), key=str)))
            df = self.connector.query(spec, enforced, columns)
        except QueryRejected as e:
            return self._deny(s, spec, "fetch_rejected", [str(e)], question)
        except QueryTimeout as e:
            audit.log("fetch_timeout", **_who(s), dataset=spec.dataset, filters=spec.filters, question=question)
            return FetchResult(spec.dataset, None, Decision(False, dec.reasons + [str(e)]), notes)

        if len(df) >= self.connector.max_rows:
            notes.append(f"Kết quả bị cắt ở {self.connector.max_rows} dòng")
        audit.log("fetch", **_who(s), dataset=spec.dataset, rows=len(df), masked=dec.masked_columns,
                  filters=spec.filters, reasons=dec.reasons, notes=notes, question=question)
        return FetchResult(spec.dataset, df, dec, notes)

    def _fetch_dataset(self, s: Subject, spec: QuerySpec, action: str = "analytics", question: str = "") -> FetchResult:
        peek = getattr(self.backend, "schema", None)
        meta = peek(spec.dataset) if peek else self.backend.datasets.get(spec.dataset)
        if meta is None:   # tên lạ không bao giờ tới CSDL
            dec0 = Decision(False, [f"Không có tập dữ liệu {spec.dataset}"])
            audit.log("fetch_denied", user=s.user_id, dataset=spec.dataset, reasons=dec0.reasons, question=question)
            return FetchResult(spec.dataset, None, dec0, [])
        dec = authorize_dataset(s, action, meta, self.env)
        if not dec.allow:
            audit.log("fetch_denied", user=s.user_id, dataset=spec.dataset, reasons=dec.reasons, question=question)
            return FetchResult(spec.dataset, None, dec, [])

        asked = [c for c in (spec.columns or []) if c in dec.masked_columns]
        if asked:
            why = [r for r in dec.reasons if "che cột" in r]
            dec2 = Decision(False, [f"Từ chối: yêu cầu cột dữ liệu hạn chế {', '.join(asked)}"] + why)
            audit.log("fetch_denied", user=s.user_id, dataset=spec.dataset, reasons=dec2.reasons, question=question)
            return FetchResult(spec.dataset, None, dec2, [])

        source = getattr(self.backend, "source_of", lambda _n: "local")(spec.dataset)
        if peek:
            try:
                meta = self.backend.datasets.get(spec.dataset)
            except DataSourceError as e:
                dec3 = Decision(False, [str(e)])
                audit.log("fetch_denied", user=s.user_id, dataset=spec.dataset, source=source, reasons=dec3.reasons,
                          question=question)
                return FetchResult(spec.dataset, None, dec3, [])
        source_rows = int(len(meta.df))
        df = dec.row_filter(meta.df)
        notes = []
        # Vòng đời bản ghi
        if meta.status_col and meta.default_status and not any(f.get("col") == meta.status_col for f in spec.filters):
            keep_m = df["_status"].isin(list(meta.default_status)) if "_status" in df.columns else pd.Series(True, index=df.index)
            n_out = int((~keep_m).sum())
            df = df[keep_m]
            if n_out:
                notes.append(f"Chỉ dùng dữ liệu {', '.join(meta.default_status)}: bỏ {n_out} bản ghi chưa duyệt")
        elif meta.status_col and any(f.get("col") == meta.status_col for f in spec.filters):
            notes.append("Kết quả có thể gồm dữ liệu chưa duyệt: gắn nhãn TẠM TÍNH")
        for f in spec.filters:
            col, op, val = f.get("col"), f.get("op"), f.get("value")
            if col not in meta.columns or col in dec.masked_columns or op not in ALLOWED_OPS:
                notes.append(f"Bỏ điều kiện lọc không hợp lệ hoặc trên cột bị che: {f}")
                continue
            s_ = df[col]
            if op == "==": df = df[s_ == val]
            elif op == "!=": df = df[s_ != val]
            elif op == ">": df = df[s_ > val]
            elif op == ">=": df = df[s_ >= val]
            elif op == "<": df = df[s_ < val]
            elif op == "<=": df = df[s_ <= val]
            elif op == "in": df = df[s_.isin(list(val))]
            elif op == "contains": df = df[s_.astype(str).str.contains(str(val), case=False, regex=False)]
            elif op == "between": df = df[s_.between(val[0], val[1])]

        keep = [c for c in (spec.columns or list(meta.columns))
                if c in meta.columns and c not in dec.masked_columns and c in df.columns]
        df = df[keep].reset_index(drop=True)
        audit.log("fetch", user=s.user_id, dataset=spec.dataset, source=source, source_rows=source_rows, rows=len(df),
                  masked=dec.masked_columns, filters=spec.filters, reasons=dec.reasons, question=question)
        return FetchResult(spec.dataset, df, dec, notes)
