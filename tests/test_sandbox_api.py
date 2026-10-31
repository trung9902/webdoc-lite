"""Kiểm thử POST /api/sandbox/run, ca S1–S7.

Chạy (cần Linux; trên Windows dùng Docker, xem Dockerfile):
    python -m unittest discover -s tests -v
"""
import base64
import json
import os
import unittest

import pandas as pd
from fastapi.testclient import TestClient

from agent_service import app

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XLSX = os.path.join(ROOT, "data", "Bo_du_lieu_mau_GD2.xlsx")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def doan_cong_rows() -> list[dict]:
    df = pd.read_excel(XLSX, sheet_name="doan_cong")
    return json.loads(df.to_json(orient="records", force_ascii=False))  # NaN -> null


class SandboxApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def run_code(self, code: str, data: dict | None = None) -> dict:
        resp = self.client.post("/api/sandbox/run", json={"code": code, "data": data or {}})
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def assert_blocked(self, body: dict, fragment: str):
        self.assertFalse(body["ok"])
        self.assertTrue(any(fragment in p for p in body["blocked"]), body["blocked"])

    def test_s1_sum_range(self):
        body = self.run_code("RESULT = sum(range(10))")
        self.assertTrue(body["ok"], body["error"])
        print(f"\n  network_isolated={body['network_isolated']}", end=" ")
        self.assertEqual(body["result_kind"], "value")
        self.assertEqual(body["result"], 45)

    def test_s2_import_os_blocked(self):
        self.assert_blocked(self.run_code("import os\nRESULT = os.listdir('/')"), "import 'os'")

    def test_s3_infinite_loop_times_out(self):
        body = self.run_code("while True:\n    pass")
        self.assertFalse(body["ok"])
        self.assertEqual(body["blocked"], [])
        self.assertIn("Quá thời gian", body["error"])

    def test_s4_read_csv_url_blocked(self):
        body = self.run_code("RESULT = pd.read_csv('https://example.com/data.csv')")
        self.assert_blocked(body, ".read_csv")

    def test_s5_open_etc_passwd_blocked(self):
        body = self.run_code("RESULT = open('/etc/passwd').read()")
        self.assert_blocked(body, "open()")

    def test_s6_dong_son_official_sewer_length(self):
        code = (
            "df = data['doan_cong']\n"
            "ds = df[(df['Phường'] == 'Đông Sơn') & (df['Trạng thái'] == 'Chính thức')]\n"
            "RESULT = round(float(ds['Chiều dài khai báo (m)'].sum()), 1)\n"
        )
        body = self.run_code(code, {"doan_cong": doan_cong_rows()})
        self.assertTrue(body["ok"], body["error"])
        self.assertEqual(body["result"], 1204.9)

    def test_s7_bar_chart_returns_one_png(self):
        code = (
            "fig, ax = plt.subplots()\n"
            "ax.bar(['BTCT', 'HDPE', 'Gạch xây'], [796.2, 101.5, 111.1])\n"
            "save_chart(fig)\n"
        )
        body = self.run_code(code)
        self.assertTrue(body["ok"], body["error"])
        self.assertEqual(len(body["charts"]), 1)
        self.assertTrue(base64.b64decode(body["charts"][0]).startswith(PNG_SIGNATURE))


if __name__ == "__main__":
    unittest.main()
