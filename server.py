"""Máy chủ GAA (chỉ dùng thư viện chuẩn Python).

  GAA_PROFILE=local GAA_DOMAIN=thoat_nuoc_gd2 python server.py        # web nội bộ, hồ sơ GĐ2
  GAA_PROFILE=internet GAA_DEMO_TOKEN=abc python server.py           # mô phỏng Internet

API
  GET  /api/meta          thông tin môi trường, hồ sơ, người dùng mẫu, câu hỏi mẫu
  GET  /api/config        cấu hình agent + danh mục dữ liệu + ánh xạ vai trò (chỉ đọc)
  POST /api/ask           chế độ demo: {"user_id", "question"} (tắt khi GAA_DEMO_USERS=0)
  POST /api/v1/ask        tích hợp WebDoc: Authorization: Bearer <JWT do WebDoc ký>, {"question"}
  GET  /healthz           kiểm tra sống

Triển khai thật: đặt sau Nginx (HTTPS), chỉ mở /api/v1/* cho WebDoc backend, tắt chế độ demo.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.platform == "win32":
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from gaa import auth
from gaa.app import build
from gaa.config import AGENTS
from gaa.policy import ROLE_LABEL

ORCH = build()
P, DOM = ORCH.p, ORCH.domain
WEB = os.path.join(os.path.dirname(__file__), "web", "index.html")
TOKEN = os.getenv("GAA_DEMO_TOKEN", "")
DEMO_ON = os.getenv("GAA_DEMO_USERS", "1") != "0"


def _user_row(u):
    return {"id": u.user_id, "name": u.name, "role": ROLE_LABEL.get(u.role, u.role),
            "biz_role": DOM.role_labels.get(u.biz_role, u.biz_role), "areas": sorted(u.areas)}


def config_view() -> dict:
    ds = []
    b = ORCH.gw.backend
    primary, extra = getattr(b, "primary", b), getattr(b, "extra", {})   # CompositeBackend: + CSDL nghiệp vụ
    if hasattr(primary, "with_token"):     # WebDoc: dữ liệu chỉ đọc được bằng token người dùng
        for name, sp in DOM.datasets.items():
            ds.append({"dataset": name, "title": sp.get("title", name), "rows": None,
                       "restricted": [f for f, c in sp["columns"].items() if c.get("class") == "han_che"],
                       "status_col": DOM.raw.get("row_attributes", {}).get("status", ""),
                       "search_only": bool(sp.get("search_only"))})
    for meta in (extra.values() if hasattr(primary, "with_token") else b.datasets.values()):
        ds.append({"dataset": meta.name, "title": meta.title, "rows": int(len(meta.df)),
                   "restricted": [c for c, k in meta.column_class.items() if k == "han_che"],
                   "status_col": meta.status_col, "search_only": meta.search_only})
    return {
        "profile": P.name, "channel": P.channel, "domain": DOM.name, "domain_title": DOM.title,
        "backend": os.getenv("GAA_BACKEND", "mock" if DOM.name == "cap_nuoc" else "file"),
        "llm_provider": P.llm_provider, "llm_base_url": P.llm_base_url,
        "models": {a: P.model_for(a) for a in AGENTS},
        "limits": {"max_code_retries": P.max_code_retries, "sandbox_timeout_s": P.sandbox_timeout_s,
                   "sandbox_mem_mb": P.sandbox_mem_mb, "sandbox_backend": P.sandbox_backend,
                   "rate_limit_per_min": P.rate_limit_per_min, "sample_rows_to_llm": P.sample_rows_to_llm},
        "allow_restricted_data": P.allow_restricted_data, "require_mfa_for_restricted": P.require_mfa_for_restricted,
        "datasets": ds,
        "roles": [{"biz_role": k, **v} for k, v in DOM.raw.get("roles", {}).items()],
        "jwt": bool(os.getenv("GAA_JWT_SECRET")), "demo_users": DEMO_ON,
    }


class H(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(b)

    def _body(self) -> dict:
        n = min(int(self.headers.get("Content-Length", 0)), 20_000)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            b = open(WEB, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'")
            self.end_headers()
            self.wfile.write(b)
        elif self.path == "/healthz":
            self._json(200, {"ok": True, "profile": P.name, "domain": DOM.name})
        elif self.path == "/api/meta":
            self._json(200, {
                "profile": P.name, "channel": P.channel, "llm_provider": P.llm_provider, "domain": DOM.name,
                "domain_title": DOM.title, "models": {a: P.model_for(a) for a in AGENTS},
                "allow_restricted_data": P.allow_restricted_data, "sandbox": P.sandbox_backend,
                "token_required": bool(TOKEN), "examples": DOM.examples,
                "users": [_user_row(u) for u in DOM.users.values()] if DEMO_ON else []})
        elif self.path == "/api/config":
            self._json(200, config_view())
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        try:
            if self.path == "/api/v1/ask":           # tích hợp WebDoc
                h = self.headers.get("Authorization", "")
                if not h.startswith("Bearer "):
                    return self._json(401, {"error": "Thiếu token WebDoc"})
                tok = h[7:]
                try:
                    claims = auth.verify(tok)
                    subj = DOM.subject_from_claims(claims)
                except PermissionError as e:
                    return self._json(401, {"error": str(e)})
                q = str(self._body().get("question", "")).strip()[:1000]
                if not q:
                    return self._json(400, {"error": "Thiếu câu hỏi"})
                return self._json(200, ORCH.ask(subj, q, token=tok))
            if self.path == "/api/ask":              # chế độ demo
                if not DEMO_ON:
                    return self._json(403, {"error": "Chế độ người dùng mẫu đã tắt"})
                if TOKEN and self.headers.get("Authorization", "") != f"Bearer {TOKEN}":
                    return self._json(401, {"error": "Thiếu hoặc sai token"})
                body = self._body()
                user = DOM.users.get(body.get("user_id", ""))
                q = str(body.get("question", "")).strip()[:1000]
                if not user or not q:
                    return self._json(400, {"error": "Thiếu người dùng hoặc câu hỏi"})
                return self._json(200, ORCH.ask(user, q))
            self._json(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    host = os.getenv("GAA_HOST", "127.0.0.1")
    port = int(os.getenv("GAA_PORT", "8080"))
    print(f"GAA [{P.name}] hồ sơ={DOM.name} LLM={P.llm_provider} nguồn={config_view()['backend']} → http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()
