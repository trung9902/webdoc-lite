"""Xác thực token do WebDoc cấp (JWT HS256, chỉ dùng thư viện chuẩn).

WebDoc (Spring Boot) ký token cho mỗi lần gọi GAA bằng khóa bí mật dùng chung
GAA_JWT_SECRET (≥ 32 ký tự). Claim bắt buộc: sub, biz_role, exp, iss="webdoc", aud="gaa";
tùy chọn: name, org, dept, areas[], clearances[], extra[], mfa.
Triển khai thật nên chuyển sang RS256/JWKS của Keycloak; giao diện hàm giữ nguyên.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time


class AuthError(PermissionError):
    pass


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def secret() -> bytes:
    s = os.getenv("GAA_JWT_SECRET", "")
    if len(s) < 32:
        raise AuthError("GAA_JWT_SECRET chưa đặt hoặc ngắn hơn 32 ký tự")
    return s.encode()


def sign(claims: dict, key: bytes | None = None, ttl_s: int = 600) -> str:
    key = key or secret()
    now = int(time.time())
    body = {"iss": "webdoc", "aud": "gaa", "iat": now, "exp": now + ttl_s, **claims}
    h = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = _b64url(json.dumps(body, ensure_ascii=False).encode())
    sig = _b64url(hmac.new(key, f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{sig}"


def verify(token: str, key: bytes | None = None) -> dict:
    key = key or secret()
    try:
        h, p, sig = token.split(".")
    except ValueError:
        raise AuthError("Token sai định dạng")
    try:
        alg = json.loads(_unb64url(h)).get("alg")
    except Exception:
        raise AuthError("Token sai định dạng")
    if alg != "HS256":
        raise AuthError("Thuật toán ký không được chấp nhận")
    good = _b64url(hmac.new(key, f"{h}.{p}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(good, sig):
        raise AuthError("Chữ ký token không hợp lệ")
    try:
        c = json.loads(_unb64url(p))
    except Exception:
        raise AuthError("Token sai định dạng")
    aud = c.get("aud")
    if c.get("iss") != "webdoc" or not (aud == "gaa" or (isinstance(aud, list) and "gaa" in aud)):
        raise AuthError("Token không dành cho GAA")
    if int(c.get("exp", 0)) < time.time():
        raise AuthError("Token đã hết hạn")
    # biz_role: token kiểu cũ (vai trò nghiệp vụ trong hồ sơ); perms: token WebDoc mang quyền gaa.* hiệu lực
    if not c.get("sub") or not (c.get("biz_role") or isinstance(c.get("perms"), list)):
        raise AuthError("Token thiếu sub hoặc biz_role/perms")
    return c
