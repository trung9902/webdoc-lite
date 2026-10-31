"""Nhật ký kiểm toán dạng JSON-lines: mỗi dòng một sự kiện, chỉ ghi thêm.

Đường dẫn lấy từ biến môi trường GAA_AUDIT_LOG (mặc định logs/gaa_audit.jsonl).
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone

_lock = threading.Lock()


def path() -> str:
    return os.environ.get("GAA_AUDIT_LOG", os.path.join("logs", "gaa_audit.jsonl"))


def log(event: str, **fields) -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "event": event, **fields}
    line = json.dumps(rec, ensure_ascii=False, default=str)
    p = path()
    with _lock:
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")
