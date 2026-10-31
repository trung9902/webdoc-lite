"""Lớp kết nối mô hình AI dùng chung cho mọi agent.

Nội bộ (Ollama, vLLM) và OpenRouter đều có API tương thích OpenAI
(/chat/completions), nên một client phục vụ cả hai; chỉ khác base_url, khóa và
tên mô hình. Đổi nhà cung cấp = đổi cấu hình, không đổi mã agent.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

from .config import Profile


class LLMError(RuntimeError):
    pass


class LLMClient:
    def complete_json(self, agent: str, system: str, user: dict) -> dict:  # pragma: no cover
        raise NotImplementedError


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise LLMError(f"LLM không trả JSON: {text[:200]}")
    return json.loads(text[start:end + 1])


class OpenAICompatClient(LLMClient):
    def __init__(self, profile: Profile) -> None:
        self.p = profile
        self.base = profile.llm_base_url.rstrip("/")
        if profile.llm_provider == "openrouter":
            self.key = os.getenv("OPENROUTER_API_KEY", "")
            if not self.key:
                raise LLMError("Thiếu OPENROUTER_API_KEY")
        else:
            self.key = os.getenv("GAA_LLM_API_KEY", "local")

    def complete_json(self, agent: str, system: str, user: dict) -> dict:
        body = {
            "model": self.p.model_for(agent),
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system + "\nChỉ trả về MỘT đối tượng JSON hợp lệ."},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.key}"}
        if self.p.llm_provider == "openrouter":
            headers["X-Title"] = "Genadata Analyst Agents"
            if self.p.openrouter_no_data_collection:
                body["provider"] = {"data_collection": "deny"}
        req = urllib.request.Request(f"{self.base}/chat/completions", data=json.dumps(body).encode(),
                                     headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"Gọi LLM thất bại ({agent}, {body['model']}): {e}") from e
        return _extract_json(resp["choices"][0]["message"]["content"])


def make_llm(profile: Profile) -> LLMClient:
    if profile.llm_provider == "mock":
        from .mock_llm import MockLLM
        return MockLLM()
    if profile.llm_provider in ("local", "openrouter"):
        return OpenAICompatClient(profile)
    raise ValueError(f"Nhà cung cấp LLM không hỗ trợ: {profile.llm_provider}")
