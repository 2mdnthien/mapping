# -*- coding: utf-8 -*-
"""Thử bộ điều phối trên một cây AGENTIC giả với script 00→04 giả lập (có cài lỗi theo biến FAKE)."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "SCRIPTS"))
import dieu_phoi as dp  # noqa: E402

GIA = r'''# -*- coding: utf-8 -*-
import os, sys
from pathlib import Path
sys.path.insert(0, os.environ["FIXTURE_DIR"])
import fixture_xlsx as fx
G = Path(os.environ["AGENTIC_GOC"]); OUT = G/"COWORK"/"Claude outputs"/"BOM"; DC = G/"DATA C"
FAKE = set(os.environ.get("FAKE", "").split(","))
TEN = Path(__file__).name
if "--dry-run" in sys.argv:
    print(TEN, "chạy thử: 2 mục dự kiến")
    if "thu_ghi" in FAKE and TEN.startswith("02_"):
        (OUT/"BOM ERP").mkdir(parents=True, exist_ok=True); (OUT/"BOM ERP"/"lo.txt").write_text("x")
    sys.exit(0)
if TEN.startswith("00_"):
    for d, ext in ((DC/"NGUON PI", ".pdf"), (DC/"NGUON CUSTOM MATERIAL", ".xls")):
        d.mkdir(parents=True, exist_ok=True)
        p = d/("0B000001"+ext)
        if not p.exists(): p.write_bytes(b"src")
elif TEN.startswith("01_"):
    fx._xlsx(OUT/"TỔNG HỢP MÃ THÀNH PHẨM PI.xlsx", {"Master": {
        **{f"{c}1": h for c, h in zip("ABCDEFG", ["STT","Tên TP","Loại vỏ","Mã Cover","Usage","Số đơn","DS mã đơn"])},
        "A2": 1, "B2": "TP-A", "A3": 2, "B3": "TP-B"}})
elif TEN.startswith("02_"):
    for t in ("TP-A", "TP-B"):
        fx.bom_erp(OUT/"BOM ERP"/f"{t}.xlsx")
        fx.bom_snpl(OUT/"BOM SNPL"/f"{t}.xlsx", e=(9 if "loi_tong" in FAKE else None))
    if "de" in FAKE:
        (OUT/"BOM SNPL"/"CU.xlsx").write_bytes(b"BI GHI DE")
    if "ngoai" in FAKE:
        (DC/"BOM MAU"/"rac.txt").write_text("x")
elif TEN.startswith("02b_"):
    for t in ("TP-A", "TP-B"):
        p = OUT/"BOM SNPL"/f"{t}.xlsx"
        if "pha_b" in FAKE:
            import zipfile
            data = {n: zipfile.ZipFile(p).read(n) for n in zipfile.ZipFile(p).namelist()}
            data["xl/worksheets/sheet1.xml"] = data["xl/worksheets/sheet1.xml"].replace(b"<f>XLOOKUP(C18,x,y)</f>", b"")
            with zipfile.ZipFile(p, "w") as z:
                for n, b in data.items(): z.writestr(n, b)
        else:
            fx.bom_snpl(p, qty=2.0)
elif TEN.startswith("04_"):
    fx.bom_snpl(OUT/"BOM SNPL"/"TP-A.xlsx", hq="HQ02")
print(TEN, "xong")
if "crash" in FAKE and TEN.startswith("02_"):
    raise RuntimeError("giả lập lỗi")
'''


class Cay(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.goc = Path(self._td.name) / "AGENTIC"
        self.d = dp.duong_dan(self.goc)
        for k in ("SCRIPTS", "OUT", "NGUON_PI", "NGUON_CUSTOM", "BOM_SNPL"):
            self.d[k].mkdir(parents=True, exist_ok=True)
        for k in ("MAPPING", "NK2025", "BOM_MAU"):
            self.d[k].parent.mkdir(parents=True, exist_ok=True)
            self.d[k].write_bytes(k.encode())
        for s in ("00_loc_nguon.py", "01_boc_pdf.py", "02_tao_bom_mau07.py", "02b_pivot_excel.py",
                  "03_kiem_toan.py", "04_cap_nhat.py"):
            (self.d["SCRIPTS"] / s).write_text(GIA, encoding="utf-8")
        # một file định mức CŨ đã làm tốt trước đây — không được mất
        self.cu = self.d["BOM_SNPL"] / "CU.xlsx"
        self.cu.write_bytes(b"DINH MUC CU DA SUA TAY")
        os.environ.update(AGENTIC_GOC=str(self.goc), FIXTURE_DIR=str(HERE), FAKE="")

    def tearDown(self):
        for p in self.goc.rglob("*"):
            with contextlib.suppress(OSError):
                os.chmod(p, 0o700)
        self._td.cleanup()

    def lenh(self, *a):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = dp.main([*a, "--goc", str(self.goc)])
        return rc, buf.getvalue()


class TestChuoi(Cay):
    def test_tu_dong_chay_tron_chuoi_va_don_diem_khoi_phuc(self):
        self.lenh("bat-dau", "--tu-dong")
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_HET, out)
        self.assertIn("đã xoá điểm khôi phục", out)
        self.assertEqual(self.cu.read_bytes(), b"DINH MUC CU DA SUA TAY")
        self.assertTrue((self.d["BOM_SNPL"] / "TP-A.xlsx").exists())
        self.assertLessEqual(len(out.splitlines()), dp.TOI_DA_DONG)

    def test_hoi_tung_buoc(self):
        self.lenh("bat-dau")
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_CHO, out)
        self.assertIn("B0", out)
        rc, _ = self.lenh("tiep")
        self.assertEqual(rc, dp.THOAT_CHO)               # chưa duyệt thì không chạy
        self.assertFalse((self.d["NGUON_PI"] / "0B000001.pdf").exists())
        self.lenh("duyet")
        rc, out = self.lenh("tiep")
        self.assertEqual(rc, dp.THOAT_OK, out)
        self.assertTrue((self.d["NGUON_PI"] / "0B000001.pdf").exists())


class TestChotChan(Cay):
    def test_ghi_de_bi_dung_khoi_phuc_roi_chay_lai_rieng_buoc(self):
        self.lenh("bat-dau", "--tu-dong")
        os.environ["FAKE"] = "de"
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_DUNG, out)
        self.assertIn("K.4", out)
        self.assertIn("B2 ", out)
        rc, out = self.lenh("khoi-phuc")
        self.assertEqual(rc, dp.THOAT_OK, out)
        self.assertEqual(self.cu.read_bytes(), b"DINH MUC CU DA SUA TAY")      # lấy lại bản cũ
        self.assertFalse((self.d["BOM_SNPL"] / "TP-A.xlsx").exists())          # file của lần lỗi đã dời đi
        tt = dp.PhienChay(self.goc).trang_thai()
        self.assertEqual(tt["B0"][0], "XONG")                                   # B0, B1 không phải làm lại
        self.assertEqual(tt["B1"][0], "XONG")
        os.environ["FAKE"] = ""
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_HET, out)
        self.assertEqual(self.cu.read_bytes(), b"DINH MUC CU DA SUA TAY")

    def test_mapping_doi_giua_chung(self):
        self.lenh("bat-dau", "--tu-dong")
        self.d["MAPPING"].write_bytes(b"MAPPING MOI")
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_DUNG)
        self.assertIn("K.1", out)

    def test_chay_thu_ma_ghi_file(self):
        self.lenh("bat-dau", "--tu-dong")
        os.environ["FAKE"] = "thu_ghi"
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_DUNG)
        self.assertIn("K.5", out)

    def test_ghi_ngoai_vung(self):
        self.lenh("bat-dau", "--tu-dong")
        os.environ["FAKE"] = "ngoai"
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_DUNG)
        self.assertIn("K.5", out)

    def test_script_loi_giua_chung_khoi_phuc_duoc(self):
        self.lenh("bat-dau", "--tu-dong")
        os.environ["FAKE"] = "crash"
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_DUNG)
        self.assertIn("K.7", out)
        rc, out = self.lenh("khoi-phuc")
        self.assertEqual(rc, dp.THOAT_OK, out)
        self.assertFalse((self.d["BOM_ERP"] / "TP-A.xlsx").exists())

    def test_tong_lech_qua_20_phan_tram_thanh_cung(self):
        self.lenh("bat-dau", "--tu-dong")
        os.environ["FAKE"] = "loi_tong"
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_DUNG, out)
        self.assertIn("K.8", out)

    def test_2b_lam_mat_cong_thuc_B(self):
        self.lenh("bat-dau", "--tu-dong")
        os.environ["FAKE"] = "pha_b"
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_DUNG, out)
        self.assertIn("4.2", out)
        self.assertIn("B2b", out)

    def test_b6_luon_hoi_rieng(self):
        self.lenh("bat-dau", "--tu-dong")
        self.lenh("tiep", "--den-het")
        self.lenh("bat-dau", "--tu-dong", "--cap-nhat")
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_CHO, out)
        self.lenh("duyet")
        rc, out = self.lenh("tiep", "--den-het")
        self.assertEqual(rc, dp.THOAT_HET, out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
