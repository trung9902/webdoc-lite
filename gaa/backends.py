"""Nguồn dữ liệu cho Data Gateway.

  MockGenadata (gateway.py) : dữ liệu mẫu cấp nước của prototype.
  FileBackend               : đọc bộ dữ liệu mẫu xlsx theo hồ sơ nghiệp vụ (chạy độc lập, demo, kiểm thử).
  WebDocBackend             : gọi REST API của WebDoc bằng token của CHÍNH người dùng (on-behalf-of),
                              WebDoc tự áp RBAC/ABAC thêm một lần; GAA áp lại lần nữa tại Data Gateway.

Cả ba trả về dict tên -> DatasetMeta với các cột thuộc tính hàng:
  _org, _area (phường), _status (trạng thái), _status_official (bool).
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pandas as pd

from .domain import ROOT, DomainProfile
from .policy import DatasetMeta


def _meta_from_frame(domain: DomainProfile, name: str, spec: dict, df: pd.DataFrame) -> DatasetMeta:
    ra = domain.raw.get("row_attributes", {})
    area_col, status_col = ra.get("area"), ra.get("status")
    df = df.copy()
    df["_org"] = domain.org
    if area_col in df.columns:
        df["_area"] = df[area_col]
    if status_col in df.columns:
        df["_status"] = df[status_col]
        df["_status_official"] = df[status_col].isin(domain.default_status)
    cols = {f: c.get("desc", f) for f, c in spec["columns"].items()}
    cls = {f: c["class"] for f, c in spec["columns"].items() if c.get("class")}
    return DatasetMeta(name, spec.get("title", name), spec.get("description", ""), cols, cls, df,
                       status_col=status_col if status_col in df.columns else "",
                       default_status=tuple(domain.default_status), search_only=bool(spec.get("search_only")))


class FileBackend:
    def __init__(self, domain: DomainProfile, path: str | None = None) -> None:
        path = path or os.getenv("GAA_DATA_FILE") or os.path.join(ROOT, domain.raw["source"]["file"])
        self.path = path
        self.datasets: dict[str, DatasetMeta] = {}
        for name, spec in domain.datasets.items():
            raw = pd.read_excel(path, sheet_name=spec["sheet"])
            ren = {c["header"]: f for f, c in spec["columns"].items()}
            missing = [h for h in ren if h not in raw.columns]
            if missing:
                raise ValueError(f"Sheet {spec['sheet']} thiếu cột {missing} (kiểm tra profile.yaml)")
            df = raw[list(ren)].rename(columns=ren)
            self.datasets[name] = _meta_from_frame(domain, name, spec, df)


class WebDocBackend:
    """Đọc dữ liệu từ WebDoc mỗi lần hỏi, bằng token người dùng (không dùng tài khoản dịch vụ toàn quyền)."""

    def __init__(self, domain: DomainProfile, base_url: str | None = None) -> None:
        self.domain = domain
        self.base = (base_url or os.getenv("GAA_WEBDOC_URL", "http://127.0.0.1:8090")).rstrip("/")
        self.path_tpl = domain.raw["source"].get("webdoc_dataset_path", "/api/v1/gaa/datasets/{dataset}")
        self._token = ""
        self._cache: dict[str, DatasetMeta] = {}

    def with_token(self, token: str) -> "WebDocBackend":
        b = WebDocBackend(self.domain, self.base)
        b._token = token
        return b

    def _get(self, name: str) -> DatasetMeta:
        if name in self._cache:
            return self._cache[name]
        spec = self.domain.datasets[name]
        url = self.base + self.path_tpl.format(dataset=urllib.parse.quote(name))
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self._token}", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read())
        df = pd.DataFrame(payload["rows"], columns=payload["columns"])
        meta = _meta_from_frame(self.domain, name, spec, df)
        self._cache[name] = meta
        return meta

    def _schema(self, name: str) -> DatasetMeta:
        """Chỉ lược đồ (không gọi WebDoc) – dùng để lập danh mục cho Planner."""
        spec = self.domain.datasets[name]
        return _meta_from_frame(self.domain, name, spec, pd.DataFrame(columns=list(spec["columns"])))

    @property
    def datasets(self) -> dict[str, DatasetMeta]:
        return _LazyDatasets(self)


class _LazyDatasets(dict):
    def __init__(self, b: WebDocBackend) -> None:
        super().__init__({n: None for n in b.domain.datasets})
        self.b = b

    def get(self, k, default=None):
        return self.b._get(k) if k in self.b.domain.datasets else default

    def __getitem__(self, k):
        return self.b._get(k)

    def values(self):
        return [self.b._schema(k) for k in self.b.domain.datasets]


class CompositeBackend:
    """Nguồn chính (file/WebDoc) + CSDL nghiệp vụ. Tên tập dữ liệu không được trùng giữa hai nguồn."""

    def __init__(self, primary, extra: dict[str, DatasetMeta]) -> None:
        self.primary, self.extra = primary, extra
        clash = set(extra) & set(primary.datasets)
        if clash:
            raise ValueError(f"Tập dữ liệu trùng tên giữa nguồn chính và CSDL nghiệp vụ: {sorted(clash)}")

    def with_token(self, token: str) -> "CompositeBackend":
        if not hasattr(self.primary, "with_token"):
            return self
        return CompositeBackend(self.primary.with_token(token), self.extra)

    @property
    def datasets(self) -> "_MergedDatasets":
        return _MergedDatasets(self.primary.datasets, self.extra)


class _MergedDatasets(dict):
    def __init__(self, primary, extra: dict) -> None:
        super().__init__({**{k: None for k in primary}, **extra})
        self.primary, self.extra = primary, extra

    def get(self, k, default=None):
        return self.extra[k] if k in self.extra else self.primary.get(k, default)

    def __getitem__(self, k):
        return self.extra[k] if k in self.extra else self.primary[k]

    def values(self):
        return list(self.primary.values()) + list(self.extra.values())


def make_backend(domain: DomainProfile):
    kind = os.getenv("GAA_BACKEND", "file" if domain.name != "cap_nuoc" else "mock")
    if kind == "mock":
        from .gateway import MockGenadata
        primary = MockGenadata()
    elif kind == "file":
        primary = FileBackend(domain)
    elif kind == "webdoc":
        primary = WebDocBackend(domain)
    else:
        raise ValueError(f"GAA_BACKEND không hợp lệ: {kind} (mock|file|webdoc)")
    if domain.raw.get("business_db") and os.getenv("GAA_BUSINESS_DB", "") != "off":
        from .business_db import BusinessDbBackend
        return CompositeBackend(primary, BusinessDbBackend(domain).datasets)
    return primary
