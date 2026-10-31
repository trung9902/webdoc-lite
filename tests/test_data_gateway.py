"""Kiểm thử Data Gateway + SqlConnector (SQLite nạp từ Bo_du_lieu_mau_GD2.xlsx), ca G1–G7.

Chủ thể dựng từ token HS256 aud=gaa mang claims như WebDoc cấp cho 5 tài khoản demo.

Chạy:
    python -m unittest tests.test_data_gateway -v
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

import jwt
import pandas as pd
import sqlalchemy as sa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gaa.gateway import DataGateway, QuerySpec
from gaa.gd2 import ORG, TABLES, load_xlsx
from gaa.policy import Environment, subject_from_token
from gaa.sql_connector import QueryRejected, SqlConnector

XLSX = os.path.join(ROOT, "data", "Bo_du_lieu_mau_GD2.xlsx")
SECRET = "test-secret-gaa-0123456789abcdefghijkl"
BASE = ["gaa.search", "gaa.analytics", "gaa.run_code"]

# Claims như WebDoc cấp (xem README: bảng tài khoản demo)
CLAIMS = {
    "qtkt.gd2": {"dept": "Phòng Quản lý dữ liệu", "roles": ["ADMIN"], "mfa": True, "areas": [],
                 "perms": BASE + ["gaa.export", "gaa.view_proposed", "gaa.restricted", "gaa.table.khach_hang"]},
    "qtdl.gd2": {"dept": "Phòng Quản lý dữ liệu", "roles": ["ORG_MANAGER"], "mfa": True, "areas": [],
                 "perms": BASE + ["gaa.export", "gaa.view_proposed", "gaa.restricted"]},
    "capnhat.ht": {"dept": "Phòng Hạ tầng", "roles": ["MEMBER"], "mfa": False, "areas": ["Hạc Thành"],
                   "perms": BASE + ["gaa.view_proposed"]},
    "doichieu.ds": {"dept": "Phòng Thoát nước", "roles": ["MEMBER"], "mfa": False, "areas": ["Đông Sơn"],
                    "perms": BASE},
    "khaithac.so": {"dept": "Phòng Hạ tầng", "roles": ["MEMBER"], "mfa": False, "areas": [], "perms": BASE},
}


def token_for(user: str) -> str:
    now = int(time.time())
    claims = {"sub": user, "org": ORG, "aud": "gaa", "iat": now, "exp": now + 300, **CLAIMS[user]}
    return jwt.encode(claims, SECRET, algorithm="HS256")


class DataGatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="gaa_gw_")
        db = os.path.join(cls.tmp, "gd2.sqlite")
        writer = sa.create_engine(f"sqlite:///{db}")
        load_xlsx(XLSX, writer)
        # bảng khách hàng không có trong tệp mẫu: vài dòng giả lập chỉ để thử quyền cấp bảng
        pd.DataFrame([
            {"ma_khach_hang": "KH-0001", "phuong": "Hạc Thành", "loai_khach_hang": "Hộ gia đình", "tieu_thu_m3_thang": 14.0},
            {"ma_khach_hang": "KH-0002", "phuong": "Đông Sơn", "loai_khach_hang": "Cơ quan", "tieu_thu_m3_thang": 120.5},
            {"ma_khach_hang": "KH-0003", "phuong": "Hàm Rồng", "loai_khach_hang": "Hộ gia đình", "tieu_thu_m3_thang": 9.2},
        ]).to_sql("khach_hang", writer, index=False)
        writer.dispose()

        cls.audit_path = os.path.join(cls.tmp, "audit.jsonl")
        cls._env_backup = {k: os.environ.get(k) for k in ("GAA_AUDIT_LOG", "GAA_JWT_SECRET")}
        os.environ["GAA_AUDIT_LOG"] = cls.audit_path
        os.environ["GAA_JWT_SECRET"] = SECRET
        cls.connector = SqlConnector(f"sqlite:///{db}", TABLES, ORG)
        cls.gw = DataGateway(cls.connector, Environment("lan", "lan", True, True))

    @classmethod
    def tearDownClass(cls):
        cls.connector.engine.dispose()
        for k, v in cls._env_backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def fetch(self, user: str, spec: QuerySpec):
        return self.gw.fetch(subject_from_token(token_for(user)), spec)

    def last_audit(self) -> dict:
        with open(self.audit_path, encoding="utf-8") as f:
            return json.loads(f.readlines()[-1])

    def test_g1_qtdl_doan_cong_110_official_with_proposed_note(self):
        r = self.fetch("qtdl.gd2", QuerySpec("doan_cong"))
        self.assertTrue(r.decision.allow, r.decision.reasons)
        self.assertEqual(len(r.df), 110)
        self.assertEqual(set(r.df["trang_thai"]), {"Chính thức"})
        self.assertTrue(any("14 bản ghi Đề xuất" in n for n in r.notes), r.notes)
        self.assertEqual(self.last_audit()["event"], "fetch")

    def test_g2_capnhat_ht_16_rows(self):
        r = self.fetch("capnhat.ht", QuerySpec("doan_cong"))
        self.assertTrue(r.decision.allow, r.decision.reasons)
        self.assertEqual(len(r.df), 16)
        self.assertEqual(set(r.df["phuong"]), {"Hạc Thành"})

    def test_g3_doichieu_ds_12_rows(self):
        r = self.fetch("doichieu.ds", QuerySpec("doan_cong"))
        self.assertTrue(r.decision.allow, r.decision.reasons)
        self.assertEqual(len(r.df), 12)
        self.assertEqual(set(r.df["phuong"]), {"Đông Sơn"})

    def test_g4_doichieu_ds_filtered_to_hac_thanh_0_rows(self):
        r = self.fetch("doichieu.ds", QuerySpec("doan_cong", filters=[{"col": "phuong", "op": "==", "value": "Hạc Thành"}]))
        self.assertTrue(r.decision.allow, r.decision.reasons)
        self.assertEqual(len(r.df), 0)

    def test_g5_khaithac_so_coordinates_denied(self):
        spec = QuerySpec("ho_ga_cua_xa", columns=["ma_nut", "x_vn2000_m", "y_vn2000_m"])
        r = self.fetch("khaithac.so", spec)
        self.assertFalse(r.decision.allow)
        self.assertIsNone(r.df)
        self.assertTrue(any("gaa.restricted" in x for x in r.decision.reasons), r.decision.reasons)
        rec = self.last_audit()
        self.assertEqual((rec["event"], rec["user"]), ("fetch_denied", "khaithac.so"))
        # đối chứng: qtdl.gd2 có gaa.restricted và MFA thì lấy được
        self.assertTrue(self.fetch("qtdl.gd2", spec).decision.allow)

    def test_g6_khaithac_so_khach_hang_denied(self):
        r = self.fetch("khaithac.so", QuerySpec("khach_hang"))
        self.assertFalse(r.decision.allow)
        self.assertTrue(any("gaa.table.khach_hang" in x for x in r.decision.reasons), r.decision.reasons)
        self.assertEqual(self.last_audit()["event"], "fetch_denied")
        # đối chứng: bảng có thật, qtkt.gd2 có quyền cấp bảng thì đọc được
        ok = self.fetch("qtkt.gd2", QuerySpec("khach_hang"))
        self.assertTrue(ok.decision.allow, ok.decision.reasons)
        self.assertEqual(len(ok.df), 3)

    def test_g7_injection_in_dataset_rejected(self):
        r = self.fetch("qtdl.gd2", QuerySpec("doan_cong; DROP TABLE phuong"))
        self.assertFalse(r.decision.allow)
        self.assertTrue(any("danh sách cho phép" in x for x in r.decision.reasons), r.decision.reasons)
        self.assertEqual(self.last_audit()["event"], "fetch_rejected")
        with self.assertRaises(QueryRejected):
            self.connector.query(QuerySpec("doan_cong; DROP TABLE phuong"))
        self.assertIn("phuong", self.connector.list_tables())
        # giá trị lọc đi qua tham số ràng buộc, không thành SQL
        r2 = self.fetch("qtdl.gd2", QuerySpec("doan_cong", filters=[{"col": "ma_doan", "op": "==", "value": "x' OR '1'='1"}]))
        self.assertTrue(r2.decision.allow, r2.decision.reasons)
        self.assertEqual(len(r2.df), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
