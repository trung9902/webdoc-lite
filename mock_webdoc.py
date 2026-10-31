"""WebDoc giả lập: API dữ liệu cho GAA (chỉ để kiểm thử tích hợp khi chưa có WebDoc thật).

WebDoc thật (Spring Boot) cần cung cấp đúng hợp đồng này:

  GET /api/v1/gaa/datasets/{dataset}?profile=thoat_nuoc_gd2
  Authorization: Bearer <JWT người dùng>          (cùng token WebDoc đã ký khi gọi GAA)
  200 {"dataset": "...", "columns": [...], "rows": [[...], ...]}
  401 token sai/hết hạn · 403 không có quyền · 404 không có tập dữ liệu

  GET /api/v1/documents/filter?type=png&maxSizeKb=100&area=...&from=YYYY-MM-DD&to=...&q=...&page=0&size=20
  200 {"list": [{id, title, originalFilename, type, sizeBytes, sizeKb, area, createdBy, createdAt, ...}],
       "total": N, "page": 0, "size": 20}       (như WebDoc Lite, dữ liệu mẫu DataSeeder)

WebDoc tự áp quyền (RLS theo phường, che cột hạn chế) TRƯỚC khi trả; GAA áp lại một lần nữa.
Chạy:  GAA_JWT_SECRET=... GAA_DOMAIN=thoat_nuoc_gd2 python mock_webdoc.py   (cổng 8090)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from gaa import auth
from gaa.backends import FileBackend
from gaa.documents import SampleDocuments, sanitize
from gaa.domain import load_domain
from gaa.policy import Environment, authorize_dataset

DOM = load_domain(os.getenv("GAA_DOMAIN", "thoat_nuoc_gd2"))
DATA = FileBackend(DOM)
DOCS = SampleDocuments(DOM.org)
DOCS_PATH = "/api/v1/documents/filter"
ENV = Environment("webdoc", "lan", True, True)


class H(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        pre = "/api/v1/gaa/datasets/"
        if not u.path.startswith(pre) and u.path != DOCS_PATH:
            return self._json(404, {"error": "not found"})
        h = self.headers.get("Authorization", "")
        try:
            subj = DOM.subject_from_claims(auth.verify(h[7:] if h.startswith("Bearer ") else ""))
        except PermissionError as e:
            return self._json(401, {"error": str(e)})
        if u.path == DOCS_PATH:
            return self._documents(subj, urllib.parse.parse_qs(u.query))
        name = urllib.parse.unquote(u.path[len(pre):])
        meta = DATA.datasets.get(name)
        if meta is None:
            return self._json(404, {"error": f"không có tập dữ liệu {name}"})
        action = "search" if meta.search_only else "analytics"
        dec = authorize_dataset(subj, action, meta, ENV)
        if not dec.allow:
            return self._json(403, {"error": "; ".join(dec.reasons)})
        df = dec.row_filter(meta.df)
        cols = [c for c in meta.columns if c not in dec.masked_columns]
        print(f"[webdoc] {subj.user_id} đọc {name}: {len(df)} dòng, che {dec.masked_columns}")
        self._json(200, {"dataset": name, "columns": cols, "rows": json.loads(df[cols].to_json(orient="values", force_ascii=False))})

    def _documents(self, subj, qs):
        raw = {k: v[0] for k, v in qs.items()}
        try:
            for k in ("minSizeKb", "maxSizeKb"):
                if k in raw:
                    raw[k] = float(raw[k])
            page, size = int(raw.pop("page", 0)), min(int(raw.pop("size", 20)), 200)
        except ValueError:
            return self._json(400, {"error": "tham số không hợp lệ"})
        f, _ = sanitize(raw)
        hits = DOCS.search(subj, f)
        print(f"[webdoc] {subj.user_id} lọc tài liệu {f.params()}: {len(hits)} tệp")
        self._json(200, {"list": hits[page * size:(page + 1) * size], "total": len(hits), "page": page, "size": size})

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    port = int(os.getenv("WEBDOC_PORT", "8090"))
    print(f"WebDoc giả lập [{DOM.name}] → http://127.0.0.1:{port}{'/api/v1/gaa/datasets/{dataset}'}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
