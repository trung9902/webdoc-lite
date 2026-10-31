"""Kiểm thử tính toàn vẹn 3 lớp bảo vệ (Defense-in-Depth Verification).

Kịch bản:
- Tầng 1: AST Static Check (chặn reflection, dunder methods, getattr, to_csv, eval...)
- Tầng 2: Subprocess & Resource Limits (chặn CPU runaway, Memory Exhaustion, dọn sạch tempdir)
- Tầng 3 & Fault Injection: Bơm lỗi giả lập vượt qua Tầng 1 để kiểm chứng Tầng 2 & 3 vẫn giữ chốt an toàn.
"""
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gaa.sandbox import ExecResult, StaticCheck, SubprocessSandbox, static_check


class TestDefenseInDepth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sb = SubprocessSandbox(timeout_s=10, mem_mb=1024)

    # =========================================================================
    # TẦNG 1: AST STATIC ANALYSIS (Kiểm thử các kỹ thuật né tránh cú pháp)
    # =========================================================================

    def test_layer1_dunder_reflection_blocked(self):
        """Tầng 1: Chặn truy cập dunder attribute (__class__, __subclasses__)"""
        code = "RESULT = ().__class__.__bases__[0]"
        chk = static_check(code)
        self.assertFalse(chk.ok)
        self.assertTrue(any("__class__" in p for p in chk.problems), chk.problems)

    def test_layer1_getattr_introspection_blocked(self):
        """Tầng 1: Chặn hàm introspection động (getattr, setattr)"""
        code = "import math\nf = getattr(math, 'sin')\nRESULT = f(0)"
        chk = static_check(code)
        self.assertFalse(chk.ok)
        self.assertTrue(any("getattr()" in p for p in chk.problems), chk.problems)

    def test_layer1_eval_exec_blocked(self):
        """Tầng 1: Chặn hàm thực thi chuỗi (eval, exec, compile)"""
        code = "RESULT = eval('1 + 1')"
        chk = static_check(code)
        self.assertFalse(chk.ok)
        self.assertTrue(any("eval()" in p for p in chk.problems), chk.problems)

    def test_layer1_file_export_pandas_blocked(self):
        """Tầng 1: Chặn các phương thức trích xuất tệp của pandas (.to_csv)"""
        code = "data['tbl'].to_csv('/tmp/leak.csv')"
        chk = static_check(code)
        self.assertFalse(chk.ok)
        self.assertTrue(any(".to_csv" in p for p in chk.problems), chk.problems)

    def test_layer1_double_underscore_names_blocked(self):
        """Tầng 1: Chặn biến bắt đầu bằng __ (như __builtins__)"""
        code = "RESULT = __builtins__"
        chk = static_check(code)
        self.assertFalse(chk.ok)
        self.assertTrue(any("__builtins__" in p for p in chk.problems), chk.problems)

    # =========================================================================
    # TẦNG 2: PROCESS & RESOURCE LIMITS (Kiểm thử giới hạn phần cứng)
    # =========================================================================

    def test_layer2_cpu_exhaustion_stopped(self):
        """Tầng 2: Mã hợp lệ cú pháp nhưng đốt CPU bị dừng sau 10 giây"""
        code = "total = 0\nwhile True:\n    total += 1"
        t0 = time.time()
        res = self.sb.run(code)
        elapsed = time.time() - t0
        self.assertFalse(res.ok)
        self.assertIn("Quá thời gian", res.error)
        self.assertGreaterEqual(elapsed, 9.8)
        self.assertLess(elapsed, 13.0)

    def test_layer2_memory_exhaustion_handled(self):
        """Tầng 2: Mã hợp lệ cú pháp nhưng xin cấp phát bộ nhớ khổng lồ"""
        # Cố tình cấp phát danh sách ~3 GB RAM
        code = "RESULT = [0] * (400 * 1024 * 1024)"
        res = self.sb.run(code)
        self.assertFalse(res.ok)
        # Sẽ bị bắt bởi MemoryError hoặc Timeout của hệ điều hành
        self.assertTrue(res.error != "", "Phải ghi nhận lỗi khi tràn RAM")

    def test_layer2_tempdir_cleanup_integrity(self):
        """Tầng 2: Xác nhận thư mục tạm luôn được dọn dẹp sạch sẽ 100%"""
        temp_dir = tempfile.gettempdir()
        initial_dirs = {d for d in os.listdir(temp_dir) if d.startswith("gaa_sbx_")}

        # Chạy 3 bài test liên tiếp (1 bài thành công, 1 bài lỗi cú pháp, 1 bài ngoại lệ)
        self.sb.run("RESULT = 12345")
        self.sb.run("import os\nRESULT = 1")
        self.sb.run("RESULT = 1 / 0")

        current_dirs = {d for d in os.listdir(temp_dir) if d.startswith("gaa_sbx_")}
        new_leftovers = current_dirs - initial_dirs
        self.assertEqual(len(new_leftovers), 0, f"Có thư mục tạm bị rò rỉ: {new_leftovers}")

    # =========================================================================
    # TẦNG 3 & FAULT INJECTION (Bơm lỗi: Giả lập vượt Tầng 1 để thử Tầng 2 & 3)
    # =========================================================================

    def test_fault_injection_bypass_ast_caught_by_process_isolation(self):
        """Fault Injection: Nếu Tầng 1 (AST) bị bypass, Tầng 2 (Subprocess) vẫn cô lập lỗi"""
        # Giả lập bypass Tầng 1 bằng cách mock static_check luôn trả về True
        with patch("gaa.sandbox.static_check", return_value=StaticCheck(True, [])):
            # Mã cố tình truy cập sys để thoát tiến trình hoặc sửa đổi interpreter
            dangerous_code = "import sys\nsys.exit(42)"
            res = self.sb.run(dangerous_code)
            # Tiến trình con thoát với mã lỗi, nhưng tiến trình máy chủ (parent) hoàn toàn an toàn
            self.assertFalse(res.ok)
            # Xác nhận hệ thống vẫn hoạt động bình thường ở lệnh tiếp theo
            subsequent = self.sb.run("RESULT = 'SYSTEM ALIVE'")
            self.assertTrue(subsequent.ok)
            self.assertEqual(subsequent.result, "SYSTEM ALIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
