"""Tạo JWT thử (thay WebDoc ký) và gọi /api/v1/ask.

  export GAA_JWT_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
  python tools/make_token.py doichieu.ds                 # in token
  python tools/make_token.py doichieu.ds "Tổng chiều dài cống từ D600 trở lên theo phường và vật liệu"
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml  # noqa: E402

from gaa import auth  # noqa: E402
from gaa.domain import PROFILE_DIR  # noqa: E402

dom = os.getenv("GAA_DOMAIN", "thoat_nuoc_gd2")
users = {u["id"]: u for u in yaml.safe_load(open(os.path.join(PROFILE_DIR, dom, "profile.yaml"), encoding="utf-8"))["demo_users"]}
uid = sys.argv[1] if len(sys.argv) > 1 else "doichieu.ds"
u = users[uid]
tok = auth.sign({"sub": uid, "name": u.get("name", uid), "biz_role": u["role"], "areas": u.get("areas", []),
                 "mfa": u.get("mfa", False)})
if len(sys.argv) < 3:
    print(tok)
    sys.exit(0)
url = os.getenv("GAA_URL", "http://127.0.0.1:8080") + "/api/v1/ask"
req = urllib.request.Request(url, data=json.dumps({"question": sys.argv[2]}).encode(),
                             headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"})
r = json.loads(urllib.request.urlopen(req, timeout=120).read())
print(json.dumps({k: r.get(k) for k in ("intent", "answer", "policy_notes")}, ensure_ascii=False, indent=1))
if r.get("result_kind") == "table":
    print(" | ".join(r["result"]["columns"]))
    for row in r["result"]["rows"]:
        print(" | ".join(str(x) for x in row))
for t in r.get("trace", []):
    print(f"  {t['agent']:<8} {t['status']:<7} {t['title']}")
