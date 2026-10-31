"""Cấu hình 2 môi trường triển khai: web nội bộ (local) và Internet.

Cùng một bộ mã; khác nhau ở nguồn mô hình AI, mức cho phép với dữ liệu hạn chế
và giới hạn sandbox. Chọn bằng biến môi trường GAA_PROFILE=local|internet.

Mô hình AI (biến GAA_LLM_PROVIDER):
  mock        — luật cố định, chạy demo không cần mạng (mặc định)
  local       — mô hình chạy nội bộ qua API tương thích OpenAI (Ollama, vLLM, LM Studio)
  openrouter  — OpenRouter: DeepSeek, Meta Llama, Claude, OpenAI, Gemini… qua một khóa
Mỗi agent có thể dùng một mô hình riêng (GAA_MODEL_ROUTER, GAA_MODEL_CODER, …).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace

AGENTS = ("router", "planner", "file_planner", "coder", "critic", "writer")

PROVIDER_BASE_URL = {
    "local": "http://localhost:11434/v1",          # Ollama; vLLM thường là :8000/v1
    "openrouter": "https://openrouter.ai/api/v1",
}

# Gợi ý mô hình theo agent. Tên mô hình OpenRouter đổi theo thời gian:
# kiểm tra lại tại https://openrouter.ai/models trước khi dùng.
DEFAULT_MODELS = {
    "local": {"router": "qwen2.5:7b", "planner": "qwen2.5:14b", "file_planner": "qwen2.5:7b",
              "coder": "qwen2.5-coder:14b", "critic": "qwen2.5:14b", "writer": "qwen2.5:14b"},
    "openrouter": {"router": "openai/gpt-4o-mini", "planner": "deepseek/deepseek-chat",
                   "file_planner": "openai/gpt-4o-mini",
                   "coder": "anthropic/claude-sonnet-4", "critic": "google/gemini-2.5-flash",
                   "writer": "meta-llama/llama-3.3-70b-instruct"},
    "mock": {a: "mock" for a in AGENTS},
}


@dataclass(frozen=True)
class Profile:
    name: str
    channel: str                      # "lan" | "internet" — thuộc tính môi trường cho ABAC
    llm_provider: str                 # "mock" | "local" | "openrouter"
    llm_base_url: str
    agent_models: dict = field(default_factory=dict)
    openrouter_no_data_collection: bool = True   # chỉ định tuyến tới nhà cung cấp không lưu dữ liệu
    allow_restricted_data: bool = False          # dữ liệu hạn chế khai thác (TT 69, Điều 10 k4)
    require_mfa_for_restricted: bool = True      # TT 69, Điều 25 k2
    sample_rows_to_llm: int = 0                  # dòng mẫu (đã che) gửi cho LLM; 0 = chỉ lược đồ
    max_result_rows_to_llm: int = 50             # dòng kết quả TỔNG HỢP tối đa gửi cho LLM viết câu trả lời
    sandbox_backend: str = "subprocess"          # "subprocess" (prototype) | "docker" (triển khai)
    sandbox_timeout_s: int = 20
    sandbox_mem_mb: int = 2048
    max_code_retries: int = 2
    rate_limit_per_min: int = 60

    def model_for(self, agent: str) -> str:
        return self.agent_models.get(agent) or DEFAULT_MODELS.get(self.llm_provider, {}).get(agent, "")


PROFILES: dict[str, Profile] = {
    # Web nội bộ: chạy trong LAN cạnh Genadata; khuyến nghị mô hình chạy nội bộ
    # => dữ liệu không ra khỏi công ty, cho phép khai thác dữ liệu hạn chế khi đủ điều kiện.
    "local": Profile(name="local", channel="lan", llm_provider="mock", llm_base_url=PROVIDER_BASE_URL["local"],
                     allow_restricted_data=True, sample_rows_to_llm=3, max_result_rows_to_llm=200,
                     sandbox_timeout_s=20, sandbox_mem_mb=2048, rate_limit_per_min=60),
    # Internet: truy cập công khai qua HTTPS; khuyến nghị OpenRouter.
    # Không gửi dòng dữ liệu nào cho LLM, chặn hẳn dữ liệu hạn chế, sandbox chặt hơn.
    "internet": Profile(name="internet", channel="internet", llm_provider="mock",
                        llm_base_url=PROVIDER_BASE_URL["openrouter"], allow_restricted_data=False,
                        sample_rows_to_llm=0, max_result_rows_to_llm=50,
                        sandbox_timeout_s=10, sandbox_mem_mb=1536, rate_limit_per_min=20),
}


def load_profile(name: str | None = None) -> Profile:
    name = name or os.getenv("GAA_PROFILE", "local")
    if name not in PROFILES:
        raise ValueError(f"GAA_PROFILE không hợp lệ: {name} (local|internet)")
    p = PROFILES[name]
    ov: dict = {}
    prov = os.getenv("GAA_LLM_PROVIDER")
    if prov:
        ov["llm_provider"] = prov
        ov["llm_base_url"] = PROVIDER_BASE_URL.get(prov, p.llm_base_url)
    if os.getenv("GAA_LLM_BASE_URL"):
        ov["llm_base_url"] = os.environ["GAA_LLM_BASE_URL"]
    models = {a: os.environ[f"GAA_MODEL_{a.upper()}"] for a in AGENTS if os.getenv(f"GAA_MODEL_{a.upper()}")}
    if models:
        ov["agent_models"] = models
    if os.getenv("GAA_SANDBOX_BACKEND"):
        ov["sandbox_backend"] = os.environ["GAA_SANDBOX_BACKEND"]
    return replace(p, **ov) if ov else p
