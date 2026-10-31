"""Ca kiểm thử nghiệm thu K1, K2, K3, K4, K7, K8, K14 (số liệu mong đợi theo đề bài).

  python -m unittest tests.test_acceptance_k -v
  GAA_LLM_PROVIDER=openrouter|local ... python -m unittest tests.test_acceptance_k -v   # chạy với mô hình thật
"""
import os
import unittest

os.environ.setdefault("GAA_JWT_SECRET", "kiem-thu-khoa-bi-mat-dai-hon-32-ky-tu-0123456789")

from gaa.app import build  # noqa: E402
from gaa.config import load_profile  # noqa: E402
from gaa.domain import load_domain  # noqa: E402

DOM = load_domain("thoat_nuoc_gd2")
ORCH = build(load_profile("local"), DOM)
USER = "qtdl.gd2"            # Quản trị dữ liệu: toàn bộ 7 phường

K1 = "Tìm hồ sơ hoàn công tuyến cống Quang Trung"
K2 = "Tìm file .png dưới 100 KB"
K3 = "Lượng nước tiêu thụ trung bình theo tháng năm 2025"
K4 = "So sánh sản lượng nước tiêu thụ các phường, vẽ biểu đồ"
K7 = "Lượng nước tiêu thụ năm 2025 theo phường, vẽ biểu đồ cột"
K14 = "Giải phương trình x^2 - 2y^2 = 1, tìm các nghiệm nguyên dương với x < 10000"


def ask(q, uid=USER, orch=ORCH):
    return orch.ask(DOM.users[uid], q)


def col(r, name):
    c = r["result"]["columns"].index(name)
    return [x[c] for x in r["result"]["rows"]]


def steps(r, agent):
    return [t for t in r["trace"] if t["agent"] == agent]


class Acceptance(unittest.TestCase):
    def test_K1_search_quang_trung(self):
        r = ask(K1)
        self.assertEqual(r["intent"], "genadata_search")
        self.assertEqual(r["result"]["rows"][0][0], "HS-01")
        self.assertEqual(r["citations"][0], {"ma": "HS-01", "trang": 2})
        self.assertIn("[HS-01, tr.2]", r["answer"])
        self.assertIn("HS-09 là bản trùng HS-01", r["answer"])

    def test_K2_png_under_100kb(self):
        r = ask(K2)
        self.assertEqual(r["intent"], "file_search")
        files = col(r, "Tệp")
        self.assertEqual(len(files), 9)
        self.assertNotIn("so_do_tong_the.png", files)

    def test_K3_average_monthly_2025(self):
        r = ask(K3)
        rows = r["result"]["rows"]
        self.assertEqual(rows[-1][0], "Trung bình/tháng")
        self.assertAlmostEqual(rows[-1][1], 2_087_518.8, places=1)
        top = max(rows[:-1], key=lambda x: x[1])
        self.assertEqual((top[0], top[1]), ("2025-07", 2_413_061))

    def test_K4_wards_compare_with_chart(self):
        r = ask(K4)
        wards = dict(zip(col(r, "Phường"), col(r, "Sản lượng (m³)")))
        self.assertEqual(len(wards), 7)
        self.assertEqual(max(wards, key=wards.get), "Đông Sơn")
        self.assertEqual(wards["Đông Sơn"], 4_911_241)
        self.assertEqual(min(wards, key=wards.get), "Quảng Phú")
        self.assertEqual(wards["Quảng Phú"], 2_504_408)
        self.assertEqual(len(r["charts"]), 1)

    def test_K7_critic_retry_on_wrong_column(self):
        r = ask(K7)
        verdicts = [t["status"] for t in steps(r, "critic")]
        self.assertLessEqual(len(steps(r, "coder")), 3)
        if verdicts[-1] == "ok":
            self.assertEqual(verdicts, ["retry", "ok"])          # sửa được ở lượt 2
        else:
            self.assertEqual(len(verdicts), 3)                    # hoặc dừng an toàn sau 3 lượt
            self.assertTrue(r["answer"].startswith("Yêu cầu bị dừng"))
        self.assertIn("san_luong_m3", steps(r, "critic")[0]["detail"]["feedback"])

    def test_K14_pell_equation_without_database(self):
        r = ask(K14)
        self.assertEqual(r["intent"], "general_compute")
        pairs = [tuple(x) for x in r["result"]["rows"]]
        self.assertEqual(pairs, [(3, 2), (17, 12), (99, 70), (577, 408), (3363, 2378)])
        self.assertFalse(steps(r, "gateway"), "không được truy cập CSDL")
        self.assertFalse(steps(r, "planner"))


if __name__ == "__main__":
    unittest.main()
