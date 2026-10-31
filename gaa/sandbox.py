"""Sandbox chạy mã Python do agent sinh ra.

Ba lớp bảo vệ:
  1. Kiểm tra tĩnh (AST): chỉ cho import thư viện tính toán trong danh sách,
     cấm eval/exec/open/__import__, cấm truy cập thuộc tính dunder.
  2. Cô lập tiến trình: tiến trình con `python -I`, thư mục tạm riêng, biến môi
     trường tối thiểu, giới hạn CPU/bộ nhớ/kích thước tệp/số tệp, hết giờ thì giết;
     cắt mạng bằng `unshare -rn` khi hệ điều hành cho phép.
  3. Triển khai thật: DockerSandbox (--network none, --read-only, --cap-drop ALL,
     người dùng không phải root, giới hạn pids/bộ nhớ/CPU; khuyến nghị runtime gVisor
     cho môi trường Internet).

Dữ liệu vào: các DataFrame đã qua Data Gateway, ghi ra CSV chỉ-đọc trong thư mục
tạm; mã người dùng nhận sẵn biến `data` (dict tên -> DataFrame), `pd`, `np`, `plt`,
hàm `save_chart(fig)`, và gán kết quả vào biến `RESULT`.
"""
from __future__ import annotations

import ast
import base64
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

import pandas as pd

ALLOWED_IMPORTS = {
    "math", "cmath", "statistics", "fractions", "decimal", "itertools", "functools", "collections",
    "datetime", "json", "re", "random", "heapq", "bisect", "string", "textwrap",
    "numpy", "pandas", "matplotlib", "matplotlib.pyplot",
    "shapely", "shapely.geometry", "shapely.ops", "shapely.wkt",
    "pyproj", "geopandas", "osgeo", "osgeo.ogr", "osgeo.osr", "osgeo.gdal",
}
ALLOWED_PREFIXES = {"numpy", "pandas", "matplotlib", "shapely", "pyproj", "geopandas", "osgeo"}
FORBIDDEN_CALLS = {"eval", "exec", "compile", "open", "__import__", "input", "breakpoint",
                   "globals", "locals", "vars", "getattr", "setattr", "delattr", "memoryview"}
FORBIDDEN_ATTRS = {"read_csv", "read_excel", "read_sql", "read_json", "read_html", "read_parquet",
                   "read_pickle", "read_file", "to_csv", "to_excel", "to_pickle", "to_sql",
                   "to_file", "savefig", "system", "popen"}


@dataclass
class StaticCheck:
    ok: bool
    problems: list[str] = field(default_factory=list)


def static_check(code: str) -> StaticCheck:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return StaticCheck(False, [f"Lỗi cú pháp dòng {e.lineno}: {e.msg}"])
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name not in ALLOWED_IMPORTS and a.name.split(".")[0] not in ALLOWED_PREFIXES:
                    problems.append(f"Cấm import '{a.name}'")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod not in ALLOWED_IMPORTS and mod.split(".")[0] not in ALLOWED_PREFIXES:
                problems.append(f"Cấm import từ '{mod}'")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            problems.append(f"Cấm gọi '{node.func.id}()'")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__"):
                problems.append(f"Cấm truy cập thuộc tính '{node.attr}'")
            elif node.attr in FORBIDDEN_ATTRS:
                problems.append(f"Cấm dùng '.{node.attr}' (đọc/ghi tệp ngoài sandbox)")
        elif isinstance(node, ast.Name) and node.id.startswith("__"):
            problems.append(f"Cấm dùng tên '{node.id}'")
    return StaticCheck(not problems, sorted(set(problems)))


@dataclass
class ExecResult:
    ok: bool
    result: object = None
    result_kind: str = "none"            # table | spatial_geometry | value | none
    stdout: str = ""
    error: str = ""
    charts: list[str] = field(default_factory=list)   # PNG base64
    blocked: list[str] = field(default_factory=list)  # vi phạm kiểm tra tĩnh
    network_isolated: bool = False


HARNESS = r'''
import io, json, sys, os, contextlib, traceback, base64
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
os.environ["MPLBACKEND"] = "Agg"
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Công cụ GIS (GDAL / PROJ / Shapely / GeoPandas) trong sandbox
try:
    import shapely
    from shapely.geometry import Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon
    import shapely.wkt as wkt
except ImportError:
    shapely = None
    Point = LineString = Polygon = None

try:
    import pyproj
    # VN-2000 nội tỉnh Thanh Hóa: KTT 105°00', múi 3°
    _crs_vn2000 = pyproj.CRS.from_proj4("+proj=tmerc +lat_0=0 +lon_0=105 +k=0.9999 +x_0=500000 +y_0=0 +ellps=WGS84 +units=m +no_defs")
    _crs_wgs84 = pyproj.CRS.from_epsg(4326)
    _t_to_wgs = pyproj.Transformer.from_crs(_crs_vn2000, _crs_wgs84, always_xy=True)
    _t_to_vn = pyproj.Transformer.from_crs(_crs_wgs84, _crs_vn2000, always_xy=True)

    def vn2000_to_wgs84(x_north, y_east):
        lon, lat = _t_to_wgs.transform(y_east, x_north)
        return lat, lon

    def wgs84_to_vn2000(lat, lon):
        y_east, x_north = _t_to_vn.transform(lon, lat)
        return x_north, y_east
except ImportError:
    pyproj = None
    vn2000_to_wgs84 = wgs84_to_vn2000 = None

try:
    import geopandas as gpd
except ImportError:
    gpd = None

W = os.getcwd()
meta = json.load(open(os.path.join(W, "inputs.json"), encoding="utf-8"))
data = {k: pd.read_csv(os.path.join(W, v), encoding="utf-8") for k, v in meta["files"].items()}
_charts = []
def save_chart(fig):
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=110, bbox_inches="tight"); plt.close(fig)
    _charts.append(base64.b64encode(b.getvalue()).decode())
code = open(os.path.join(W, "user_code.py"), encoding="utf-8").read()
g = {
    "data": data, "pd": pd, "np": np, "plt": plt, "save_chart": save_chart,
    "shapely": shapely, "Point": Point, "LineString": LineString, "Polygon": Polygon,
    "pyproj": pyproj, "gpd": gpd,
    "vn2000_to_wgs84": vn2000_to_wgs84, "wgs84_to_vn2000": wgs84_to_vn2000,
    "RESULT": None
}
out = io.StringIO(); err = ""
try:
    with contextlib.redirect_stdout(out):
        exec(compile(code, "user_code.py", "exec"), g)
except Exception:
    err = traceback.format_exc(limit=3)
r = g.get("RESULT"); kind = "none"
if isinstance(r, pd.Series): r = r.reset_index()

if gpd and isinstance(r, gpd.GeoDataFrame):
    kind = "table"
    df_copy = pd.DataFrame(r.copy())
    if "geometry" in df_copy.columns:
        df_copy["geometry"] = df_copy["geometry"].apply(lambda gm: gm.wkt if gm else None)
    r = {"columns": [str(c) for c in df_copy.columns], "rows": json.loads(df_copy.head(500).to_json(orient="values", force_ascii=False)), "n_rows": int(len(df_copy))}
elif isinstance(r, pd.DataFrame):
    kind = "table"; r = {"columns": [str(c) for c in r.columns], "rows": json.loads(r.head(500).to_json(orient="values", force_ascii=False)), "n_rows": int(len(r))}
elif shapely and hasattr(r, "geom_type"):
    kind = "spatial_geometry"
    r = {"wkt": r.wkt, "geom_type": r.geom_type, "bounds": list(r.bounds)}
elif r is not None:
    kind = "value"
    try: json.dumps(r)
    except Exception: r = repr(r)
print("\n@@GAA_RESULT@@" + json.dumps({"result": r, "kind": kind, "stdout": out.getvalue()[-4000:], "error": err, "charts": _charts}, ensure_ascii=False, default=str))
'''


def _limits(mem_mb: int, cpu_s: int):
    if sys.platform == "win32":
        return None
    def apply():
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
        # hard > soft: hết soft nhận SIGXCPU (nhận ra là hết giờ CPU); soft == hard thì kernel gửi thẳng SIGKILL
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (20 * 1024 * 1024, 20 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        os.setsid()
    return apply


def _can_unshare() -> bool:
    if not shutil.which("unshare"):
        return False
    try:
        return subprocess.run(["unshare", "-rn", "true"], capture_output=True, timeout=5).returncode == 0
    except Exception:
        return False


_UNSHARE = None


class SubprocessSandbox:
    def __init__(self, timeout_s: int = 20, mem_mb: int = 2048) -> None:
        self.timeout_s, self.mem_mb = timeout_s, mem_mb

    def command(self, work: str) -> list[str]:
        cmd = [sys.executable, "-I", "harness.py"]
        return (["unshare", "-rn"] + cmd) if _UNSHARE else cmd

    def run(self, code: str, frames: dict[str, pd.DataFrame] | None = None) -> ExecResult:
        global _UNSHARE
        chk = static_check(code)
        if not chk.ok:
            return ExecResult(False, error="Mã bị chặn bởi kiểm tra tĩnh", blocked=chk.problems)
        if _UNSHARE is None:
            _UNSHARE = _can_unshare()
        work = tempfile.mkdtemp(prefix="gaa_sbx_")
        try:
            files = {}
            for name, df in (frames or {}).items():
                fn = f"{name}.csv"
                df.to_csv(os.path.join(work, fn), index=False, encoding="utf-8")
                os.chmod(os.path.join(work, fn), 0o444)
                files[name] = fn
            with open(os.path.join(work, "inputs.json"), "w", encoding="utf-8") as f:
                json.dump({"files": files}, f)
            with open(os.path.join(work, "user_code.py"), "w", encoding="utf-8") as f:
                f.write(code)
            with open(os.path.join(work, "harness.py"), "w", encoding="utf-8") as f:
                f.write(HARNESS)
            cmd = self.command(work)
            if sys.platform == "win32":
                env = os.environ.copy()
                env.update({"MPLCONFIGDIR": work, "MPLBACKEND": "Agg",
                            "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
                            "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
            else:
                env = {"PATH": "/usr/bin:/bin", "HOME": work, "MPLCONFIGDIR": work, "MPLBACKEND": "Agg",
                       "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "PYTHONIOENCODING": "utf-8"}
            try:
                p = subprocess.run(cmd, cwd=work, env=env, capture_output=True, text=True, encoding="utf-8",
                                   timeout=self.timeout_s, preexec_fn=_limits(self.mem_mb, self.timeout_s))
            except subprocess.TimeoutExpired:
                return ExecResult(False, error=f"Quá thời gian {self.timeout_s} giây", network_isolated=_UNSHARE)
            marker = "@@GAA_RESULT@@"
            if hasattr(signal, "SIGXCPU") and p.returncode == -signal.SIGXCPU:
                return ExecResult(False, error=f"Quá thời gian {self.timeout_s} giây CPU", network_isolated=_UNSHARE)
            if marker not in p.stdout:
                return ExecResult(False, error=(p.stderr or "Sandbox không trả kết quả")[-2000:], network_isolated=_UNSHARE)
            payload = json.loads(p.stdout.split(marker, 1)[1])
            return ExecResult(ok=not payload["error"], result=payload["result"], result_kind=payload["kind"],
                              stdout=payload["stdout"], error=payload["error"], charts=payload["charts"],
                              network_isolated=_UNSHARE)
        finally:
            shutil.rmtree(work, ignore_errors=True)


class DockerSandbox(SubprocessSandbox):
    """Dùng khi triển khai: image `gaa-sandbox` (python + numpy/pandas/matplotlib, không có công cụ mạng)."""

    IMAGE = os.getenv("GAA_SANDBOX_IMAGE", "gaa-sandbox:latest")
    RUNTIME = os.getenv("GAA_SANDBOX_RUNTIME", "")  # "runsc" (gVisor) cho môi trường Internet

    def command(self, work: str) -> list[str]:
        cmd = ["docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
               "--security-opt", "no-new-privileges", "--pids-limit", "64", "--memory", f"{self.mem_mb}m",
               "--cpus", "1", "--user", "65534:65534", "--tmpfs", "/tmp:size=64m",
               "-v", f"{work}:/work:rw", "-w", "/work"]
        if self.RUNTIME:
            cmd += ["--runtime", self.RUNTIME]
        return cmd + [self.IMAGE, "python", "-I", "harness.py"]


def make_sandbox(profile) -> SubprocessSandbox:
    cls = DockerSandbox if profile.sandbox_backend == "docker" else SubprocessSandbox
    return cls(timeout_s=profile.sandbox_timeout_s, mem_mb=profile.sandbox_mem_mb)


def chart_preview_b64(png_b64: str) -> str:
    return "data:image/png;base64," + png_b64


def decode_chart(png_b64: str) -> bytes:
    return base64.b64decode(png_b64)
