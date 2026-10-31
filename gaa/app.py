"""Lắp ráp hệ thống và người dùng mẫu.

Khi tích hợp thật, Subject được dựng từ token Genadata (JWT do Genadata cấp):
vai trò, tổ chức, phòng ban, dự án, quyền bổ sung, cờ MFA — không tin dữ liệu
do trình duyệt gửi lên.
"""
from __future__ import annotations

from .config import Profile, load_profile
from .gateway import DataGateway, MockGenadata
from .graph import Orchestrator
from .llm import make_llm
from .policy import Environment, Subject
from .sandbox import make_sandbox

DEMO_USERS: dict[str, Subject] = {
    "u_lan": Subject("u_lan", "Lan — Thành viên XN1 (được cấp quyền phân tích)", "member", "CTN", "XN1",
                     extra_permissions=frozenset({"analytics"})),
    "u_hoa": Subject("u_hoa", "Hòa — Thành viên XN2 (chưa có quyền phân tích)", "member", "CTN", "XN2"),
    "u_minh": Subject("u_minh", "Minh — Quản lý tổ chức, quyền dữ liệu hạn chế, có MFA", "org_manager", "CTN", "PKT",
                      clearances=frozenset({"han_che"}), mfa=True),
    "u_minh_nomfa": Subject("u_minh_nomfa", "Minh (phiên không MFA)", "org_manager", "CTN", "PKT",
                            clearances=frozenset({"han_che"}), mfa=False),
    "u_khac": Subject("u_khac", "Khách — Quản lý tổ chức khác", "org_manager", "CTN-KHAC", "XN-K"),
    "u_admin": Subject("u_admin", "Quản trị viên hệ thống", "admin", "CTN", "IT", mfa=True),
}


def build(profile: Profile | None = None, domain=None) -> Orchestrator:
    """profile: môi trường triển khai (local/internet); domain: hồ sơ nghiệp vụ (cap_nuoc/thoat_nuoc_gd2)."""
    from .backends import make_backend
    from .documents import make_documents
    from .domain import load_domain
    p = profile or load_profile()
    d = domain if domain is not None and not isinstance(domain, str) else load_domain(domain)
    env = Environment(p.name, p.channel, p.allow_restricted_data, p.require_mfa_for_restricted)
    return Orchestrator(p, DataGateway(make_backend(d), env), make_llm(p), make_sandbox(p), domain=d,
                        documents=make_documents(d))
