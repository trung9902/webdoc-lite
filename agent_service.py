"""
Dịch vụ Agent Python – FastAPI.

Chạy: pip install -r requirements.txt && uvicorn agent_service:app --reload --port 8000
Sandbox cần Linux (rlimit, unshare); trên Windows chạy bằng Docker, xem Dockerfile.
"""

import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

from gaa.sandbox import SubprocessSandbox

app = FastAPI(title="WebDoc Agent Service")

# Giới hạn của POST /api/sandbox/run: 10 giây CPU, 1 GB bộ nhớ
SANDBOX_CPU_S = 10
SANDBOX_MEM_MB = 1024


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


class SandboxRunRequest(BaseModel):
    code: str
    # tên bảng -> danh sách dòng; tên bảng thành tên tệp CSV nên chỉ cho chữ, số, gạch dưới
    data: dict[str, list[dict]] = Field(default_factory=dict)


class SandboxRunResponse(BaseModel):
    ok: bool
    result: object = None
    result_kind: str = "none"
    stdout: str = ""
    error: str = ""
    charts: list[str] = []
    blocked: list[str] = []
    network_isolated: bool = False


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/api/v1/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    return AskResponse(answer="Đã nhận: " + req.question)


@app.post("/api/sandbox/run", response_model=SandboxRunResponse)
def sandbox_run(req: SandboxRunRequest):
    bad = [name for name in req.data if not name.isidentifier() or not name.isascii()]
    if bad:
        return SandboxRunResponse(ok=False, error="Tên bảng không hợp lệ", blocked=[f"Tên bảng '{n}'" for n in bad])
    frames = {name: pd.DataFrame(rows) for name, rows in req.data.items()}
    r = SubprocessSandbox(timeout_s=SANDBOX_CPU_S, mem_mb=SANDBOX_MEM_MB).run(req.code, frames)
    return SandboxRunResponse(ok=r.ok, result=r.result, result_kind=r.result_kind, stdout=r.stdout, error=r.error,
                              charts=r.charts, blocked=r.blocked, network_isolated=bool(r.network_isolated))
