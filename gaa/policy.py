"""Điểm quyết định chính sách (PDP): RBAC + ABAC theo claims của token WebDoc và vai trò GAA.

Nguyên tắc: LLM KHÔNG BAO GIỜ quyết định quyền. Mọi quyết định ở đây là
mã tất định, được áp tại Data Gateway (PEP) trước khi dữ liệu tới sandbox.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable

import jwt
import pandas as pd

from .sql_connector import TableSpec

TOKEN_AUDIENCE = "gaa"
TOKEN_MAX_TTL_S = 300

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({"search", "analytics", "run_code", "export", "cross_org"}),
    "org_manager": frozenset({"search", "analytics", "run_code", "export"}),
    "member": frozenset({"search", "run_code"}),
}

ROLE_LABEL = {"admin": "Quản trị viên", "org_manager": "Quản lý tổ chức", "member": "Thành viên"}


@dataclass(frozen=True)
class Subject:
    user_id: str                                # claim sub (tên đăng nhập WebDoc)
    name: str = ""
    role: str = ""
    org: str = ""
    dept: str = ""
    roles: frozenset[str] = frozenset()
    perms: frozenset[str] = frozenset()         # chỉ giữ quyền gaa.*
    extra_permissions: frozenset[str] = frozenset()
    clearances: frozenset[str] = frozenset()   # VD {"han_che"}
    projects: frozenset[str] = frozenset()
    mfa: bool = False
    areas: frozenset[str] = frozenset()        # VD {"Hạc Thành"}; rỗng = không giới hạn phường
    biz_role: str = ""
    granted: frozenset[str] | None = None

    @property
    def permissions(self) -> frozenset[str]:
        if self.granted is not None:
            return self.granted
        base = ROLE_PERMISSIONS.get(self.role, frozenset()) | self.extra_permissions
        if self.perms:
            cleaned = frozenset(p[4:] if p.startswith("gaa.") else p for p in self.perms)
            return base | self.perms | cleaned
        return base


class InvalidToken(ValueError):
    pass


def subject_from_claims(claims: dict) -> Subject:
    def str_list(key: str) -> frozenset[str]:
        v = claims.get(key, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            raise InvalidToken(f"claim '{key}' phải là danh sách chuỗi")
        return frozenset(v)

    sub, org, dept, mfa = claims.get("sub"), claims.get("org"), claims.get("dept", ""), claims.get("mfa", False)
    if not isinstance(sub, str) or not sub or not isinstance(org, str) or not org:
        raise InvalidToken("thiếu claim 'sub' hoặc 'org'")
    if not isinstance(dept, str) or not isinstance(mfa, bool):
        raise InvalidToken("claim 'dept' phải là chuỗi, 'mfa' phải là true/false")
    perms = frozenset(p for p in str_list("perms") if p.startswith("gaa."))
    roles = str_list("roles")
    role_cand = "admin" if "ADMIN" in roles else ("org_manager" if "ORG_MANAGER" in roles else "member")
    return Subject(user_id=sub, org=org, dept=dept, roles=roles, role=role_cand, perms=perms,
                   areas=str_list("areas"), mfa=mfa)


def subject_from_token(token: str, secret: str | None = None) -> Subject:
    """Kiểm chữ ký, aud=gaa, hạn dùng (≤ 5 phút) rồi dựng Subject từ claims."""
    secret = secret or os.environ.get("GAA_JWT_SECRET", "")
    if len(secret) < 32:
        raise InvalidToken("GAA_JWT_SECRET phải từ 32 ký tự")
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], audience=TOKEN_AUDIENCE,
                            options={"require": ["sub", "aud", "iat", "exp"]})
    except jwt.InvalidTokenError as e:
        raise InvalidToken(f"token không hợp lệ: {e}") from e
    if claims["exp"] - claims["iat"] > TOKEN_MAX_TTL_S:
        raise InvalidToken(f"token có hạn dài hơn {TOKEN_MAX_TTL_S} giây")
    return subject_from_claims(claims)


@dataclass(frozen=True)
class Environment:
    profile: str
    channel: str                  # "lan" | "internet"
    allow_restricted_data: bool
    require_mfa_for_restricted: bool


@dataclass
class DatasetMeta:
    name: str
    title: str
    description: str
    columns: dict[str, str]               # cột nghiệp vụ -> mô tả
    column_class: dict[str, str]          # cột -> "han_che" | "ca_nhan"
    df: pd.DataFrame                      # gồm cả cột thuộc tính hàng bắt đầu bằng "_"
    status_col: str = ""                  # cột vòng đời bản ghi (VD trang_thai)
    default_status: tuple = ()            # trạng thái dùng mặc định khi phân tích (VD Chính thức)
    search_only: bool = False             # chỉ dùng cho tìm kiếm, không đưa vào phân tích
    required_permission: str = ""         # quyền cấp bảng (VD table.khach_hang = gaa.table.khach_hang)


@dataclass
class Decision:
    allow: bool
    reasons: list[str] = field(default_factory=list)
    enforced: list[dict] = field(default_factory=list)   # điều kiện lọc bắt buộc {"col","op","value"}
    masked_columns: list[str] = field(default_factory=list)
    view_proposed: bool = False
    row_filter: Callable[[pd.DataFrame], pd.DataFrame] | None = None


def can_use_restricted(s: Subject, env: Environment) -> tuple[bool, str]:
    if not env.allow_restricted_data:
        return False, f"môi trường '{env.profile}' không cho khai thác dữ liệu hạn chế"
    has_res = ("han_che" in s.clearances or "gaa.restricted" in s.perms or "restricted" in s.permissions
               or s.role == "admin" or "ADMIN" in s.roles)
    if not has_res:
        return False, "tài khoản chưa có quyền gaa.restricted"
    if env.require_mfa_for_restricted and not s.mfa:
        return False, "cần xác thực đa yếu tố (MFA) để khai thác dữ liệu hạn chế"
    return True, "đủ điều kiện khai thác dữ liệu hạn chế"


def check_action(s: Subject, action: str) -> Decision:
    perm = f"gaa.{action}"
    if perm in s.perms or action in s.permissions or perm in s.permissions:
        return Decision(True, [f"RBAC: có quyền {perm}"])
    return Decision(False, [f"RBAC: chưa được cấp quyền {perm}"])


def authorize_table(s: Subject, action: str, table: TableSpec, env: Environment, data_org: str) -> Decision:
    """Quyết định quyền trên một bảng: cho/không, điều kiện lọc bắt buộc, cột bị che."""
    if s.org != data_org:
        return Decision(False, [f"ABAC: dữ liệu thuộc tổ chức {data_org}, tài khoản thuộc {s.org}"])
    d = check_action(s, action)
    if not d.allow:
        return d
    reasons = list(d.reasons)
    if table.required_perm:
        if table.required_perm not in s.perms and table.required_perm not in s.permissions:
            return Decision(False, reasons + [f"RBAC: bảng {table.name} cần quyền {table.required_perm}"])
        reasons.append(f"RBAC: có quyền {table.required_perm}")

    # ---- Che cột (column-level ABAC)
    restricted_ok, why = can_use_restricted(s, env)
    masked = [c for c, cls in table.column_class.items() if cls == "han_che" and not restricted_ok]
    if masked:
        reasons.append(f"ABAC: che cột {', '.join(masked)} ({why})")

    # ---- Lọc hàng (row-level ABAC), dịch thành điều kiện WHERE
    enforced = []
    if s.areas and table.area_col:
        enforced.append({"col": table.area_col, "op": "in", "value": sorted(s.areas)})
        reasons.append(f"ABAC: lọc phường = {', '.join(sorted(s.areas))}")
    view_proposed = "gaa.view_proposed" in s.perms or "view_proposed" in s.permissions
    if table.status_col and not view_proposed:
        enforced.append({"col": table.status_col, "op": "==", "value": table.official_status})
        reasons.append(f"ABAC: chỉ bản ghi {table.official_status} (chưa có quyền gaa.view_proposed)")
    return Decision(True, reasons, enforced, masked, view_proposed)


def authorize_dataset(s: Subject, action: str, meta: DatasetMeta, env: Environment) -> Decision:
    """Quyết định quyền trên một tập dữ liệu (dataset/DataFrame)."""
    d = check_action(s, action)
    if not d.allow:
        return d
    req = meta.required_permission
    if req:
        perm_name = req if req.startswith("gaa.") else f"gaa.{req}"
        raw_name = req[4:] if req.startswith("gaa.") else req
        if perm_name not in s.perms and raw_name not in s.permissions and perm_name not in s.permissions:
            return Decision(False, [f"RBAC: thiếu quyền cấp bảng {perm_name} để đọc {meta.name}"])
    reasons = list(d.reasons)
    restricted_ok, why = can_use_restricted(s, env)

    # ---- Che cột (column-level ABAC)
    masked = []
    for col, cls in meta.column_class.items():
        if cls == "han_che" and not restricted_ok:
            masked.append(col)
        elif cls == "ca_nhan" and s.role != "admin" and "ADMIN" not in s.roles:
            masked.append(col)
    if masked:
        reasons.append(f"ABAC: che cột {', '.join(masked)} ({why})" if not restricted_ok
                       else f"ABAC: che cột dữ liệu cá nhân {', '.join(masked)}")

    # ---- Lọc hàng (row-level ABAC)
    def row_filter(df: pd.DataFrame) -> pd.DataFrame:
        if "cross_org" in s.permissions:
            m = pd.Series(True, index=df.index)
        else:
            same_org = df["_org"] == s.org
            if "_scope" not in df.columns:
                m = same_org
            elif s.role == "org_manager" or "ORG_MANAGER" in s.roles:
                owner = df["_owner"] if "_owner" in df.columns else pd.Series("", index=df.index)
                m = same_org & ~((df["_scope"] == "rieng_tu") & (owner != s.user_id))
            else:
                owner = df["_owner"] if "_owner" in df.columns else pd.Series("", index=df.index)
                visible = (
                    (df["_scope"] == "cong_khai")
                    | ((df["_scope"] == "phong_ban") & (df["_dept"] == s.dept))
                    | ((df["_scope"] == "rieng_tu") & (owner == s.user_id))
                )
                if "_project" in df.columns and s.projects:
                    visible |= df["_project"].isin(list(s.projects))
                m = same_org & visible
        if not restricted_ok and "_che_do" in df.columns:
            m &= df["_che_do"] != "han_che"
        # ABAC theo địa bàn
        if s.areas and "_area" in df.columns and "cross_org" not in s.permissions:
            m &= df["_area"].isin(list(s.areas))
        # Vòng đời bản ghi
        has_vp = "view_proposed" in s.permissions or "gaa.view_proposed" in s.perms
        if "_status" in df.columns and not has_vp and "cross_org" not in s.permissions:
            m &= df["_status_official"]
        return df[m]

    if "cross_org" in s.permissions:
        reasons.append("ABAC: Quản trị viên xem dữ liệu mọi tổ chức")
    elif s.role == "org_manager" or "ORG_MANAGER" in s.roles:
        reasons.append(f"ABAC: phạm vi toàn tổ chức {s.org}")
    elif "_scope" not in meta.df.columns:
        reasons.append(f"ABAC: dữ liệu tổ chức {s.org}")
    else:
        reasons.append(f"ABAC: chỉ dữ liệu công khai trong tổ chức {s.org}, dữ liệu phòng ban {s.dept}"
                       + (f", dự án {', '.join(sorted(s.projects))}" if s.projects else "")
                       + " và dữ liệu riêng của bạn")
    if s.areas and "_area" in meta.df.columns and "cross_org" not in s.permissions:
        reasons.append(f"ABAC: lọc phường = {', '.join(sorted(s.areas))}")
    if not restricted_ok and "_che_do" in meta.df.columns and (meta.df["_che_do"] == "han_che").any():
        reasons.append("ABAC: bỏ các bản ghi có chế độ khai thác 'hạn chế'")
    return Decision(True, reasons, row_filter=row_filter, masked_columns=masked)
