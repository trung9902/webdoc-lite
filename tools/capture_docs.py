"""Chạy toàn bộ quy trình cài đặt + demo, ghi lại đầu ra THẬT và chụp màn hình cho tài liệu kỹ thuật.
Không thuộc sản phẩm; chỉ dùng để dựng tài liệu.  python tools/capture_docs.py <thư_mục_ra>
"""
import asyncio
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
SECRET = "doc-demo-khoa-bi-mat-chi-de-chup-man-hinh-0123456789"
PY = os.path.join(ROOT, ".venv", "bin", "python")
BASE_ENV = dict(os.environ, GAA_JWT_SECRET=SECRET, GAA_DOMAIN="thoat_nuoc_gd2", PYTHONUNBUFFERED="1",
                GAA_AUDIT_LOG=os.path.join(ROOT, "logs", "audit.jsonl"))
Q2 = "Tổng chiều dài cống từ D600 trở lên theo phường và vật liệu"
sessions = []


def run(cmd, env=None, cwd=ROOT, keep=None, shown=None):
    p = subprocess.run(cmd, shell=True, cwd=cwd, env=env or BASE_ENV, capture_output=True, text=True, timeout=600)
    out = (p.stdout + p.stderr).replace(SECRET, "••••••••(48 ký tự)")
    out = "\n".join(l for l in out.splitlines() if "JAVA_TOOL_OPTIONS" not in l)
    lines = out.splitlines()
    if keep and len(lines) > keep:
        lines = lines[:keep // 2] + [f"… ({len(lines) - keep} dòng) …"] + lines[-keep // 2:]
    return {"cmd": shown or cmd, "out": "\n".join(lines), "code": p.returncode}


def term(name, title, blocks):
    body = ""
    for b in blocks:
        body += f'<div class="p"><span class="u">claude@kho-du-lieu</span>:<span class="d">~/gaa_v2</span>$ <span class="c">{html.escape(b["cmd"])}</span></div>'
        if b["out"]:
            body += f'<pre>{html.escape(b["out"])}</pre>'
    page = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#E9EDEF;font-family:'DejaVu Sans Mono',monospace}}
.w{{width:1180px;margin:18px;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.18)}}
.t{{background:#1d2a31;color:#C9D7DD;font:13px 'DejaVu Sans',sans-serif;padding:9px 14px;display:flex;gap:8px;align-items:center}}
.t i{{width:11px;height:11px;border-radius:50%;display:inline-block}}
.b{{background:#0E1A20;color:#D7E3E8;padding:14px 16px;font-size:13px;line-height:1.5}}
.p{{white-space:pre-wrap;word-break:break-all;margin-top:6px}} .u{{color:#7FD19B}} .d{{color:#6CB4EE}} .c{{color:#fff}}
pre{{margin:2px 0 10px;white-space:pre-wrap;word-break:break-word;color:#BFD0D8;font:12.5px/1.45 'DejaVu Sans Mono',monospace}}
</style></head><body><div class="w"><div class="t"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i>&nbsp; {html.escape(title)}</div><div class="b">{body}</div></div></body></html>"""
    open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8").write(page)
    sessions.append({"name": name, "title": title, "blocks": blocks})


def wait(url, n=100):
    for _ in range(n):
        try:
            urllib.request.urlopen(url, timeout=1); return True
        except urllib.error.HTTPError:
            return True
        except Exception:
            time.sleep(0.2)
    return False


# ---------------- T1 công cụ
term("T1_cong_cu", "Bước 1 · Kiểm tra công cụ trên máy chủ", [
    run("python3 --version && python3 -c \"import sys;print(sys.executable)\""),
    run("java -version 2>&1 | head -1", shown="java -version"),
    run("curl --version | head -1"),
    run("unshare --version; unshare -rn true && echo 'unshare -rn: OK (sandbox cắt mạng được)'"),
])
# ---------------- T2 cài đặt
term("T2_cai_dat", "Bước 2 · Tạo môi trường Python và cài thư viện", [
    run("python3 -m venv --system-site-packages .venv && echo 'đã tạo .venv'", shown="python3 -m venv .venv"),
    run(".venv/bin/pip install -r requirements.txt", keep=8),
    run(".venv/bin/python -c \"import numpy,pandas,matplotlib,openpyxl,yaml;print('numpy',numpy.__version__,'| pandas',pandas.__version__,'| matplotlib',matplotlib.__version__,'| openpyxl',openpyxl.__version__,'| pyyaml',yaml.__version__)\""),
])
# ---------------- T3 cấu hình
term("T3_cau_hinh", "Bước 3 · Cấu hình hồ sơ, khóa JWT, nguồn dữ liệu", [
    run("ls profiles/thoat_nuoc_gd2 data"),
    run("python3 -c \"import secrets;print(secrets.token_urlsafe(48))\" | sed 's/./•/g'",
        shown="export GAA_JWT_SECRET=$(python3 -c \"import secrets;print(secrets.token_urlsafe(48))\")"),
    run("grep -E '^(GAA_PROFILE|GAA_DOMAIN|GAA_BACKEND|GAA_WEBDOC_URL|GAA_LLM_PROVIDER|GAA_LLM_BASE_URL|GAA_MODEL_CODER|GAA_SANDBOX_BACKEND|GAA_DEMO_USERS)=' deploy/gaa.env.example | sed 's/ *#.*//'",
        shown="cp deploy/gaa.env.example .env && grep ... .env"),
    run(".venv/bin/python -c \"from gaa.domain import load_domain;d=load_domain('thoat_nuoc_gd2');print(d.title);[print(' ',u.user_id,'->',u.role,sorted(u.permissions),sorted(u.areas)) for u in d.users.values()]\"",
        shown="python -c 'kiểm tra hồ sơ thoat_nuoc_gd2 và ánh xạ vai trò'"),
])
# ---------------- T4 kiểm thử
term("T4_kiem_thu", "Bước 4 · Chạy bộ kiểm thử (37 ca)", [
    run(".venv/bin/python -m unittest discover -s tests -v 2>&1 | grep -E 'test_gd2|Ran|OK|FAIL' ", shown=".venv/bin/python -m unittest discover -s tests -v", keep=30),
])
# ---------------- T5 khởi động
os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
if os.path.exists(BASE_ENV["GAA_AUDIT_LOG"]):
    os.remove(BASE_ENV["GAA_AUDIT_LOG"])
env_int = dict(BASE_ENV, GAA_BACKEND="webdoc", GAA_WEBDOC_URL="http://127.0.0.1:8090", GAA_DEMO_USERS="0", GAA_PORT="8080")
wlog, glog = open(os.path.join(OUT, "webdoc.log"), "w"), open(os.path.join(OUT, "gaa.log"), "w")
procs = [subprocess.Popen([PY, "mock_webdoc.py"], cwd=ROOT, env=env_int, stdout=wlog, stderr=subprocess.STDOUT),
         subprocess.Popen([PY, "server.py"], cwd=ROOT, env=env_int, stdout=glog, stderr=subprocess.STDOUT)]
wait("http://127.0.0.1:8080/healthz"); wait("http://127.0.0.1:8090/")
time.sleep(0.5)
term("T5_khoi_dong", "Bước 5 · Khởi động WebDoc (giả lập) và GAA ở chế độ tích hợp", [
    {"cmd": "GAA_BACKEND=webdoc GAA_DEMO_USERS=0 python mock_webdoc.py &", "out": open(os.path.join(OUT, "webdoc.log")).read().strip(), "code": 0},
    {"cmd": "GAA_BACKEND=webdoc GAA_WEBDOC_URL=http://127.0.0.1:8090 GAA_DEMO_USERS=0 python server.py &", "out": open(os.path.join(OUT, "gaa.log")).read().strip(), "code": 0},
    run("curl -s http://127.0.0.1:8080/healthz"),
    run("curl -s http://127.0.0.1:8080/api/config | python3 -c \"import sys,json;c=json.load(sys.stdin);print({k:c[k] for k in ('profile','domain','backend','llm_provider','jwt','demo_users')});[print(' ',d['dataset'],d['restricted']) for d in c['datasets']]\"",
        shown="curl -s http://127.0.0.1:8080/api/config | python3 -m json.tool"),
])
# ---------------- T6 gọi bằng JWT
term("T6_goi_jwt", "Bước 6 · WebDoc gọi GAA bằng JWT (Python và Java)", [
    run(f".venv/bin/python tools/make_token.py doichieu.ds \"{Q2}\"", keep=24),
    run("curl -s -o /dev/null -w 'HTTP %{http_code}\\n' -X POST http://127.0.0.1:8080/api/v1/ask -H 'Authorization: Bearer a.b.c' -d '{\"question\":\"x\"}'",
        shown="curl -X POST .../api/v1/ask -H 'Authorization: Bearer a.b.c'   # token giả"),
    run(f"cd integration/webdoc-java && java GaaClient qtdl.gd2 quan_tri_du_lieu '' \"{Q2}\"",
        shown=f"java GaaClient qtdl.gd2 quan_tri_du_lieu '' \"{Q2}\""),
])
time.sleep(0.3)
term("T7_nhat_ky", "Bước 7 · Kiểm tra nhật ký: WebDoc lọc theo người gọi, GAA ghi vết", [
    {"cmd": "tail -n 4 webdoc.log", "out": "\n".join(open(os.path.join(OUT, "webdoc.log")).read().strip().splitlines()[-4:]), "code": 0},
    run("tail -n 3 logs/audit.jsonl | python3 -c \"import sys,json;[print(json.dumps({k:r.get(k) for k in ('ts','event','user','dataset','rows','intent')},ensure_ascii=False)) for r in map(json.loads,sys.stdin)]\"",
        shown="tail -n 3 logs/audit.jsonl"),
])
for p in procs:
    p.terminate()

# ---------------- giao diện web (chế độ demo, nguồn file)
env_demo = dict(BASE_ENV, GAA_BACKEND="file", GAA_DEMO_USERS="1", GAA_PORT="8081")
web = subprocess.Popen([PY, "server.py"], cwd=ROOT, env=env_demo, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
wait("http://127.0.0.1:8081/healthz")

SCEN = [
    ("W2_phan_tich_q2", "qtdl.gd2", Q2, False),
    ("W3_vet_agent", "qtdl.gd2", Q2, True),
    ("W4_doi_chieu_ds", "doichieu.ds", Q2, False),
    ("W5_diem_ngap", "qtdl.gd2", "Số điểm ngập và độ sâu ngập lớn nhất theo phường", False),
    ("W6_tim_kiem", "khaithac.so", "Tìm hồ sơ hoàn công tuyến cống Quang Trung", False),
    ("W7_toa_do_tu_choi", "khaithac.so", "Tọa độ hố ga TN-HG-HT-001 là bao nhiêu?", True),
    ("W8_chen_lenh", "khaithac.so", "Tóm tắt biên bản HS-10", True),
]


async def shots():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1500, "height": 980}, device_scale_factor=1.5, bypass_csp=True)
        pg = await ctx.new_page()
        await pg.goto("http://127.0.0.1:8081/")
        await pg.wait_for_selector("#user option", state="attached")
        await pg.click("#tab-cfg")
        await pg.wait_for_selector("#cfg table")
        await pg.screenshot(path=os.path.join(OUT, "W1_cau_hinh.png"), full_page=True)
        for name, uid, q, open_trace in SCEN:
            await pg.goto("http://127.0.0.1:8081/")
            await pg.wait_for_selector("#user option", state="attached")
            await pg.select_option("#user", uid)
            await pg.fill("#qi", q)
            await pg.click("#send")
            await pg.wait_for_function("document.querySelectorAll('.a .ans').length > 0", timeout=60000)
            if open_trace:
                await pg.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            await pg.wait_for_timeout(300)
            await pg.screenshot(path=os.path.join(OUT, name + ".png"), full_page=True)
        for f in sorted(os.listdir(OUT)):
            if f.startswith("T") and f.endswith(".html"):
                await pg.set_viewport_size({"width": 1220, "height": 400})
                await pg.goto("file://" + os.path.join(OUT, f))
                await pg.locator(".w").screenshot(path=os.path.join(OUT, f[:-5] + ".png"))
        await b.close()

asyncio.run(shots())
web.terminate()
json.dump(sessions, open(os.path.join(OUT, "sessions.json"), "w"), ensure_ascii=False, indent=1)
print("xong", sorted(f for f in os.listdir(OUT) if f.endswith(".png")))
