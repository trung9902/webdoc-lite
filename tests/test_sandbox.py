"""Kiểm thử Sandbox chạy mã Python an toàn (ca S1–S7).

Chạy:
    python -m unittest tests.test_sandbox -v
"""
import base64
import os
import sys
import unittest

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gaa.sandbox import SubprocessSandbox
XLSX = os.path.join(ROOT, "data", "Bo_du_lieu_mau_GD2.xlsx")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def load_dong_son_data() -> pd.DataFrame:
    return pd.read_excel(XLSX, sheet_name="doan_cong")


class CustomTextTestResult(unittest.TextTestResult):
    def getDescription(self, test):
        doc = test.shortDescription()
        return doc if doc else str(test)

    def addSuccess(self, test):
        super(unittest.TextTestResult, self).addSuccess(test)
        if self.showAll:
            extra = getattr(test, "_extra_info", "")
            self.stream.writeln(f"ok    {extra}")


class CustomRunner(unittest.TextTestRunner):
    resultclass = CustomTextTestResult


class TestSandbox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sb = SubprocessSandbox(timeout_s=10, mem_mb=1024)

    def test_s1(self):
        """S1 RESULT = sum(range(10))                               """
        res = self.sb.run("RESULT = sum(range(10))")
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.result, 45)
        self._extra_info = f"result={res.result}"

    def test_s2(self):
        """S2 import os                                              """
        res = self.sb.run("import os\nRESULT = 1")
        self.assertFalse(res.ok)
        self.assertTrue(any("import 'os'" in b for b in res.blocked))
        self._extra_info = "blocked[AST]   Cấm import 'os'"

    def test_s3(self):
        """S3 while True: pass                                       """
        res = self.sb.run("while True:\n    pass")
        self.assertFalse(res.ok)
        self.assertIn("Quá thời gian", res.error)
        self._extra_info = "timeout        dừng sau 10,0 s (giới hạn CPU)"

    def test_s4(self):
        """S4 pd.read_csv('http://example.com/a.csv')                """
        res = self.sb.run("RESULT = pd.read_csv('http://example.com/a.csv')")
        self.assertFalse(res.ok)
        self.assertTrue(any(".read_csv" in b for b in res.blocked))
        self._extra_info = "blocked[AST]   Cấm gọi .read_csv"

    def test_s5(self):
        """S5 open('/etc/passwd').read()                             """
        res = self.sb.run("RESULT = open('/etc/passwd').read()")
        self.assertFalse(res.ok)
        self.assertTrue(any("open()" in b for b in res.blocked))
        self._extra_info = "blocked[AST]   Cấm open()"

    def test_s6(self):
        """S6 Đông Sơn, Chính thức, sum(chieu_dai_m)                 """
        df = load_dong_son_data()
        code = (
            "df = data['doan_cong']\n"
            "ds = df[(df['Phường'] == 'Đông Sơn') & (df['Trạng thái'] == 'Chính thức')]\n"
            "s = round(float(ds['Chiều dài khai báo (m)'].sum()), 1)\n"
            "n = len(ds)\n"
            "RESULT = f'{str(s).replace(\".\", \",\")} m · {n} đoạn'\n"
        )
        res = self.sb.run(code, {"doan_cong": df})
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.result, "1204,9 m · 12 đoạn")
        self._extra_info = f"result={res.result}"

    def test_s7(self):
        """S7 plt.bar(...); save_chart(fig)                          """
        code = (
            "fig, ax = plt.subplots()\n"
            "ax.bar(['A', 'B'], [1, 2])\n"
            "save_chart(fig)\n"
        )
        res = self.sb.run(code)
        self.assertTrue(res.ok, res.error)
        self.assertEqual(len(res.charts), 1)
        raw_png = base64.b64decode(res.charts[0])
        self.assertTrue(raw_png.startswith(PNG_SIGNATURE))
        kb = round(len(raw_png) / 1024)
        self._extra_info = f"charts=1 (PNG {kb} KB)"


if __name__ == "__main__":
    unittest.main(testRunner=CustomRunner(verbosity=2))
