"""Điều phối luồng multi-agent (Orchestrator).

  câu hỏi ─► Router ─┬─ data_analysis ─► RBAC ─► Planner ─► Data Gateway (RBAC/ABAC, che cột, lọc hàng)
                     │                                          │
                     ├─ general_compute ─► RBAC(run_code) ──────┤
                     │                                          ▼
                     │                       Coder ─► Sandbox ─► DLP ─► Critic ─┐ (retry ≤ N)
                     │                         ▲─────────────────────────────────┘
                     ├─ genadata_search ─► Data Gateway (search)
                     ├─ file_search ─► RBAC(search) ─► File planner ─► API tài liệu WebDoc ─► kiểm lại phường
                     └─ out_of_scope

Nguồn dữ liệu phân tích = nguồn chính (file/WebDoc) + CSDL nghiệp vụ (backends.CompositeBackend).
Mỗi bước trong trace: agent, status, ms (thời gian chạy), at (thời điểm bắt đầu, UTC), model (None = bước tất định).
                                         ─► Writer ─► câu trả lời + nguồn + phạm vi quyền
"""
from __future__ import annotations

import re
import time
import unicodedata
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import audit, documents, guard
from .agents import CoderAgent, CriticAgent, FilePlannerAgent, PlannerAgent, RouterAgent, WriterAgent
from .config import Profile
from .gateway import DataGateway, QuerySpec
from .llm import LLMClient, LLMError
from .policy import ROLE_LABEL, Subject, check_action
from .sandbox import SubprocessSandbox


@dataclass
class Step:
    agent: str
    title: str
    status: str = "ok"            # ok | denied | blocked | error | retry | warn
    detail: dict = field(default_factory=dict)
    ms: int = 0
    at: str = ""                  # thời điểm bắt đầu bước (ISO 8601, UTC)
    model: str | None = None      # mô hình AI của agent; None = bước tất định (policy, gateway, sandbox...)


class RateLimiter:
    def __init__(self, per_min: int) -> None:
        self.per_min, self.hits = per_min, defaultdict(deque)

    def allow(self, uid: str) -> bool:
        now, q = time.time(), self.hits[uid]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_min:
            return False
        q.append(now)
        return True


class Orchestrator:
    def __init__(self, profile: Profile, gateway: DataGateway, llm: LLMClient, sandbox: SubprocessSandbox,
                 domain=None, documents=None) -> None:
        self.p, self.gw, self.sbx = profile, gateway, sandbox
        self.domain, self.docs = domain, documents
        self.router, self.planner, self.coder = RouterAgent(llm), PlannerAgent(llm), CoderAgent(llm)
        self.file_planner = FilePlannerAgent(llm)
        self.critic, self.writer = CriticAgent(llm), WriterAgent(llm)
        self.limiter = RateLimiter(profile.rate_limit_per_min)

    # ------------------------------------------------------------------
    def ask(self, s: Subject, question: str, token: str | None = None) -> dict:
        trace: list[Step] = []
        started = time.time()
        gw = self.gw.for_token(token)
        dom = getattr(self.domain, "name", "cap_nuoc")
        out = {"question": question, "intent": None, "answer": "", "policy_notes": [], "code": None,
               "result": None, "result_kind": "none", "charts": [], "trace": trace, "plan": None,
               "profile": self.p.name, "domain": dom, "llm_provider": self.p.llm_provider,
               "started_at": self._iso(started)}

        def step(agent, title, status="ok", t0=None, model=None, **detail):
            now = time.time()
            trace.append(Step(agent, title, status, detail, int((now - t0) * 1000) if t0 else 0,
                              self._iso(t0 or now), model))

        if not self.limiter.allow(s.user_id):
            out["answer"] = "Bạn đã hỏi quá số lần cho phép trong 1 phút. Vui lòng thử lại sau."
            step("gateway", "Giới hạn tần suất", "denied")
            return self._finish(s, out)

        try:
            t0 = time.time()
            route = self.router({"question": question, "role": ROLE_LABEL.get(s.role, s.role),
                                 "permissions": sorted(s.permissions), "domain": dom,
                                 "glossary": getattr(self.domain, "glossary", "")})
            intent = route.get("intent", "out_of_scope")
            out["intent"] = intent
            step("router", f"Phân loại: {intent}", t0=t0, reason=route.get("reason"), model=self.p.model_for("router"))

            if intent == "out_of_scope":
                out["answer"] = ("Câu hỏi nằm ngoài phạm vi trợ lý: không cần dữ liệu Genadata và cũng không giải "
                                 "được bằng tính toán. Bạn có thể hỏi về số liệu chất lượng nước, sự cố, tài liệu "
                                 "căn cứ, hoặc một bài toán cần tính.")
                return self._finish(s, out)

            if intent == "genadata_search":
                return self._search(s, question, out, step, gw)
            if intent == "file_search":
                return self._file_search(s, question, out, step, token)

            frames, notes, masked = {}, [], []
            if intent == "data_analysis":
                d = check_action(s, "analytics")
                if not d.allow:
                    step("policy", "RBAC từ chối phân tích dữ liệu", "denied", reasons=d.reasons)
                    out["policy_notes"] = d.reasons
                    out["answer"] = ("Tài khoản của bạn chưa được cấp quyền phân tích dữ liệu trong Genadata "
                                     "(Thành viên cần Quản lý tổ chức cấp thêm quyền). Bạn vẫn có thể tra cứu "
                                     "tài liệu, hoặc gửi yêu cầu cấp quyền.")
                    return self._finish(s, out)
                catalog = gw.catalog(s)
                step("policy", "Danh mục dữ liệu được phép", datasets=[c["dataset"] for c in catalog],
                     masked={c["dataset"]: c["masked_columns"] for c in catalog if c["masked_columns"]})
                t0 = time.time()
                plan = self.planner({"question": question, "catalog": catalog,
                                     "glossary": getattr(self.domain, "glossary", "")})
                out["plan"] = {"queries": plan.get("queries", []), "reason": plan.get("reason")}
                step("planner", "Lập truy vấn có cấu trúc", t0=t0, queries=plan.get("queries"),
                     reason=plan.get("reason"), model=self.p.model_for("planner"))
                denied = []
                for q in plan.get("queries", []):
                    t0 = time.time()
                    res = gw.fetch(s, QuerySpec(q.get("dataset", ""), q.get("columns"), q.get("filters") or []),
                                        question=question)
                    if res.df is None:
                        step("gateway", f"Từ chối truy cập {res.dataset}", "denied", t0=t0, reasons=res.decision.reasons)
                        notes += res.decision.reasons
                        denied += res.decision.reasons
                        continue
                    frames[res.dataset] = res.df
                    masked += res.decision.masked_columns
                    notes += [r for r in res.decision.reasons if r not in notes] + res.notes
                    step("gateway", f"Lấy {res.dataset}: {len(res.df)} dòng", t0=t0,
                         masked=res.decision.masked_columns, reasons=res.decision.reasons)
                out["policy_notes"] = notes
                if not frames:
                    out["answer"] = (("Yêu cầu bị từ chối. " + "; ".join(r.replace("ABAC: ", "") for r in denied) + ".")
                                     if denied else
                                     "Không có dữ liệu nào trong phạm vi bạn được phép khai thác để trả lời câu hỏi này.")
                    return self._finish(s, out)
            else:  # general_compute
                d = check_action(s, "run_code")
                if not d.allow:
                    step("policy", "RBAC từ chối chạy mã", "denied", reasons=d.reasons)
                    out["answer"] = "Tài khoản của bạn chưa được phép chạy phân tích bằng mã."
                    return self._finish(s, out)
                out["policy_notes"] = ["Câu hỏi tính toán chung: không truy cập dữ liệu Genadata"]

            # ---- vòng Coder -> Sandbox -> DLP -> Critic
            frame_desc = {
                n: {"columns": {c: str(t) for c, t in df.dtypes.items()}, "n_rows": int(len(df)),
                    **({"sample_rows": df.head(self.p.sample_rows_to_llm).to_dict("records")}
                       if self.p.sample_rows_to_llm else {})}
                for n, df in frames.items()}
            prev_err, prev_code, ex = None, None, None
            for attempt in range(self.p.max_code_retries + 1):
                t0 = time.time()
                gen = self.coder({"question": question, "frames": frame_desc, "masked_columns": sorted(set(masked)),
                                  "previous_code": prev_code, "previous_error": prev_err})
                code = gen.get("code", "")
                step("coder", f"Sinh mã Python (lần {attempt + 1})", t0=t0, code=code,
                     explanation=gen.get("explanation"), model=self.p.model_for("coder"))
                t0 = time.time()
                ex = self.sbx.run(code, frames)
                if ex.blocked:
                    step("sandbox", "Chặn mã vi phạm", "blocked", t0=t0, problems=ex.blocked)
                else:
                    step("sandbox", "Chạy mã" + (" (cô lập mạng)" if ex.network_isolated else ""),
                         "ok" if ex.ok else "error", t0=t0, error=ex.error[-800:] if ex.error else "",
                         stdout=ex.stdout[-800:])
                leak = self._dlp(ex, masked)
                if leak:
                    ex.ok, ex.error = False, leak
                    step("dlp", "Chặn kết quả chứa cột bị che", "blocked", detail=leak)
                t0 = time.time()
                verdict = self.critic({"question": question, "code": code, "attempt": attempt + 1,
                                       "max_attempts": self.p.max_code_retries + 1,
                                       "frames": {n: list(d["columns"]) for n, d in frame_desc.items()},
                                       "exec": {"ok": ex.ok, "error": ex.error[-1500:], "blocked": ex.blocked,
                                                "result_kind": ex.result_kind,
                                                "result_preview": self._preview(ex, 20)}})
                v = verdict.get("verdict", "fail")
                step("critic", f"Kiểm định: {v}", "ok" if v == "accept" else ("retry" if v == "retry" else "error"),
                     t0=t0, feedback=verdict.get("feedback"), model=self.p.model_for("critic"))
                out["code"] = code
                if v == "accept" and ex.ok:
                    break
                if v == "fail":
                    break
                prev_code, prev_err = code, verdict.get("feedback") or ex.error or "; ".join(ex.blocked)

            if ex and ex.ok:
                out["result"], out["result_kind"], out["charts"] = ex.result, ex.result_kind, ex.charts
                t0 = time.time()
                w = self.writer({"question": question, "intent": intent, "policy_notes": out["policy_notes"],
                                 "result_kind": ex.result_kind,
                                 "result": self._preview(ex, self.p.max_result_rows_to_llm),
                                 "stdout": ex.stdout[-1000:]})
                out["answer"] = w.get("answer", "")
                step("writer", "Tổng hợp câu trả lời", t0=t0, model=self.p.model_for("writer"))
            else:
                fb = verdict.get("feedback", "") if ex else ""
                out["answer"] = ("Yêu cầu bị dừng vì không an toàn. "
                                 + (f"{fb} Sandbox đã chặn: " + "; ".join(ex.blocked) + "." if ex and ex.blocked else
                                    f"Lỗi: {(ex.error if ex else '')[-300:]}"))
        except LLMError as e:
            step("llm", "Lỗi gọi mô hình AI", "error", error=str(e))
            out["answer"] = f"Không gọi được mô hình AI: {e}"
        return self._finish(s, out)

    # ------------------------------------------------------------------
    STOP = {"tim", "tra", "cuu", "tai", "lieu", "ve", "cac", "nhung", "cho", "toi", "ho", "so", "tuyen", "nao", "co",
            "la", "gi", "cua", "va", "trong", "tom", "tat", "hay", "xem", "ban"}

    @staticmethod
    def _norm(t: str) -> str:
        t = unicodedata.normalize("NFD", str(t).lower())
        return "".join(c for c in t if unicodedata.category(c) != "Mn").replace("đ", "d")

    def _search(self, s, question, out, step, gw):
        d = check_action(s, "search")
        if not d.allow:
            out["answer"] = "Bạn chưa có quyền tra cứu."
            return self._finish(s, out)
        cfg = getattr(self.domain, "search", {}) or {"dataset": "tai_lieu", "text_columns": ["ten"]}
        ds, cols = cfg.get("dataset", "tai_lieu"), cfg.get("text_columns", ["ten"])
        dup = cfg.get("duplicates", {})
        t0 = time.time()
        res = gw.fetch(s, QuerySpec(ds, None, []), action="search", question=question)
        out["policy_notes"] = res.decision.reasons
        if res.df is None:
            step("gateway", "Từ chối tìm kiếm", "denied", t0=t0, reasons=res.decision.reasons)
            out["answer"] = "Bạn không được tra cứu tập tài liệu này."
            return self._finish(s, out)
        df = res.df.copy()
        cols = [c for c in cols if c in df.columns]
        text = df[cols].astype(str).agg(" ".join, axis=1).map(self._norm)
        code = re.search(r"\bHS-\d+\b", question.upper())
        summary = bool(code) and self._norm(question).startswith(("tom tat", "noi dung"))
        if code:
            hits = df[df[cols[0]].astype(str).str.upper() == code.group(0)].assign(_diem=1.0)
            kws = [code.group(0).lower()]
        else:
            kws = [w for w in re.findall(r"[a-z0-9]+", self._norm(question)) if w not in self.STOP and len(w) > 1]
            score = text.map(lambda t: sum(1 for w in kws if re.search(r"\b" + re.escape(w) + r"\b", t)))
            hits = df[score > 0].assign(_diem=(score[score > 0] / max(len(kws), 1)).round(2))
            hits = hits.sort_values("_diem", ascending=False, kind="stable").head(5)
        step("gateway", f"Tìm trong {ds}: {len(hits)} kết quả", t0=t0, keywords=kws, reasons=res.decision.reasons)
        if hits.empty:
            out["answer"] = f"Không tìm thấy tài liệu phù hợp trong phạm vi bạn được xem (từ khóa: {', '.join(kws)})."
            return self._finish(s, out)
        # Lá chắn chỉ dẫn chèn: quét tất định văn bản tài liệu trước khi đưa cho LLM
        body_col = "noi_dung" if "noi_dung" in hits.columns else cols[-1]
        warn = {}
        for _, r in hits.iterrows():
            found = guard.scan(str(r[body_col]))
            if found:
                warn[str(r[cols[0]])] = found
        if warn:
            step("guard", "Phát hiện chỉ dẫn trong tài liệu – coi là dữ liệu", "warn",
                 documents=list(warn), patterns=sorted({p for v in warn.values() for p in v}))
        rows = []
        for _, r in hits.iterrows():
            ma = str(r[cols[0]])
            rows.append({"ma": ma, "loai": str(r.get("loai", "")), "so_hieu": str(r.get("so_hieu", "")),
                         "phuong": str(r.get("phuong", "")), "trang": r.get("trang_nguon", ""),
                         "ghi_chu": (f"bản trùng {dup[ma]}" if ma in dup else ("có chỉ dẫn lạ" if ma in warn else "")),
                         "diem": float(r["_diem"])})
        out["result"] = {"columns": ["Mã", "Loại", "Số hiệu", "Phường", "Trang nguồn", "Ghi chú", "Điểm"],
                         "rows": [list(x.values()) for x in rows], "n_rows": len(rows)}
        out["result_kind"] = "table"
        top = hits.iloc[0]
        t0 = time.time()
        w = self.writer({"question": question, "intent": "genadata_search", "mode": "summary" if summary else "search",
                         "document": guard.wrap(str(top[body_col])), "document_id": str(top[cols[0]]),
                         "source_page": top.get("trang_nguon", ""), "hits": rows, "injection_warnings": warn,
                         "policy_notes": out["policy_notes"]})
        out["answer"] = w.get("answer", "")
        out["citations"] = [{"ma": str(top[cols[0]]), "trang": top.get("trang_nguon", "")}]
        step("writer", "Tổng hợp câu trả lời có trích dẫn", t0=t0, model=self.p.model_for("writer"))
        return self._finish(s, out)

    def _file_search(self, s, question, out, step, token):
        """Câu hỏi siêu dữ liệu tệp: LLM chỉ đề xuất bộ lọc; gọi API tài liệu và kiểm quyền là mã tất định."""
        d = check_action(s, "search")
        if not d.allow:
            step("policy", "RBAC từ chối tra cứu tệp", "denied", reasons=d.reasons)
            out["answer"] = "Bạn chưa có quyền tra cứu tài liệu."
            return self._finish(s, out)
        if self.docs is None:
            out["answer"] = "Chưa cấu hình nguồn siêu dữ liệu tài liệu (API tài liệu WebDoc)."
            return self._finish(s, out)
        known = self.docs.known_areas()
        t0 = time.time()
        plan = self.file_planner({"question": question, "known_areas": known})
        f, dropped = documents.sanitize(plan.get("filters"), known)
        out["plan"] = {"filters": f.params(), "reason": plan.get("reason")}
        step("file_planner", "Lập bộ lọc siêu dữ liệu tệp", t0=t0, model=self.p.model_for("file_planner"),
             filters=f.params(), dropped=dropped, reason=plan.get("reason"))
        t0 = time.time()
        try:
            found = self.docs.search(s, f, token)
        except documents.DocumentSourceError as e:
            step("documents", "Lỗi gọi API tài liệu", "error", t0=t0, source=self.docs.name, error=str(e))
            out["answer"] = f"Không tra được siêu dữ liệu tài liệu: {e}"
            return self._finish(s, out)
        docs, hidden = documents.recheck(s, found)
        notes = ["Lọc lần 1: quy tắc xem tài liệu của WebDoc (tổ chức, phường, riêng tư, bản nháp)"]
        if s.areas:
            notes.append(f"ABAC: GAA kiểm lại phường = {', '.join(sorted(s.areas))}"
                         + (f", bỏ {hidden} tệp ngoài phạm vi" if hidden else ""))
        out["policy_notes"] = notes
        step("documents", f"Tra siêu dữ liệu tệp: {len(docs)} kết quả", t0=t0, source=self.docs.name,
             filters=f.params(), rechecked_out=hidden)
        audit.log("file_search", user=s.user_id, filters=f.params(), hits=len(docs), hidden=hidden, question=question)
        hits = [{"tep": x["originalFilename"], "tieu_de": x["title"], "dinh_dang": x["type"],
                 "dung_luong_kb": round((x.get("sizeBytes") or 0) / 1024, 1), "phuong": x.get("area") or "",
                 "ngay_tai_len": str(x.get("createdAt") or "")[:10], "nguoi_tai_len": x.get("createdBy") or ""}
                for x in docs]
        out["result"] = {"columns": ["Tệp", "Tiêu đề", "Định dạng", "Dung lượng (KB)", "Phường", "Ngày tải lên",
                                     "Người tải lên"],
                         "rows": [list(h.values()) for h in hits], "n_rows": len(hits)}
        out["result_kind"] = "table"
        t0 = time.time()
        w = self.writer({"question": question, "intent": "file_search", "filters": f.params(), "n_hits": len(hits),
                         "hits": hits[:self.p.max_result_rows_to_llm], "policy_notes": notes})
        out["answer"] = w.get("answer", "")
        step("writer", "Tổng hợp câu trả lời", t0=t0, model=self.p.model_for("writer"))
        return self._finish(s, out)

    @staticmethod
    def _iso(t: float) -> str:
        return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="milliseconds")

    @staticmethod
    def _dlp(ex, masked) -> str:
        """Kiểm tra tất định: kết quả không được chứa cột đã che."""
        if ex.result_kind == "table" and isinstance(ex.result, dict):
            bad = [c for c in ex.result.get("columns", []) if c in set(masked)]
            if bad:
                return f"Kết quả chứa cột bị che: {bad}"
        return ""

    @staticmethod
    def _preview(ex, n):
        if ex is None or not ex.ok:
            return None
        if ex.result_kind == "table" and isinstance(ex.result, dict):
            return {"columns": ex.result["columns"], "rows": ex.result["rows"][:n], "n_rows": ex.result["n_rows"]}
        return ex.result

    def _finish(self, s: Subject, out: dict) -> dict:
        audit.log("ask", user=s.user_id, role=s.role, profile=self.p.name, intent=out.get("intent"),
                  question=out["question"], steps=[f"{t.agent}:{t.status}" for t in out["trace"]])
        out["trace"] = [asdict(t) for t in out["trace"]]
        if out.get("started_at"):
            t = datetime.fromisoformat(out["started_at"]).timestamp()
            out["elapsed_ms"] = int((time.time() - t) * 1000)
        return out
