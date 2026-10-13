# -*- coding: utf-8 -*-
"""Kiểm thử bộ chốt kiểm: mỗi chốt có 1 ca đạt + 1 ca cố tình làm hỏng."""
import os
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "SCRIPTS"))
import chot_kiem as ck  # noqa: E402

import openpyxl  # chỉ dùng để dựng file thử


def tao_xlsx(path: Path, o: dict) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Mau07"
    for ref, val in o.items():
        ws[ref] = val
    wb.save(path)
    return path


class Nen(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.td = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()


class TestKhoa(Nen):
    def test_mapping_khong_doi_thi_dat(self):
        m = self.td / "MAPPING.xlsx"
        m.write_bytes(b"v1")
        p = ck.Phien(self.td / "NHAT KY")
        p.khoa(m)
        p.kiem_khoa("3.1")
        self.assertTrue(p.ket_qua[-1].dat)

    def test_mapping_doi_giua_chung_thi_dung(self):
        m = self.td / "MAPPING.xlsx"
        m.write_bytes(b"v1")
        p = ck.Phien(self.td / "NHAT KY")
        p.khoa(m)
        m.write_bytes(b"v2")
        with self.assertRaises(ck.ChotDung):
            p.kiem_khoa("3.1")
        self.assertIn("KHONG DAT", p.so.read_text(encoding="utf-8"))

    def test_chot_mem_khong_dung(self):
        p = ck.Phien(self.td / "NHAT KY")
        kq = p.chot("3.3", "FG thiếu mapping", False, "NL X01", muc=ck.MEM, doi_tuong="FG-A")
        self.assertFalse(kq.dat)

    def test_phien_khong_trung_thu_muc(self):
        ck.Phien(self.td / "NK", run_id="R1")
        with self.assertRaises(FileExistsError):
            ck.Phien(self.td / "NK", run_id="R1")


class TestGhiKhongDe(Nen):
    def test_ghi_moi(self):
        t = self.td / "tam.bin"
        t.write_bytes(b"abc")
        dv = ck.ghi_khong_de(t, self.td / "out" / "A.xlsx")
        self.assertEqual(dv.md5, ck.md5_file(t))

    def test_chan_ghi_de_va_giu_nguyen_ban_cu(self):
        t = self.td / "tam.bin"
        t.write_bytes(b"moi")
        d = self.td / "A.xlsx"
        d.write_bytes(b"cu-da-sua-tay")
        with self.assertRaises(ck.ChotDung):
            ck.ghi_khong_de(t, d)
        self.assertEqual(d.read_bytes(), b"cu-da-sua-tay")

    def test_ten_khong_trung(self):
        d = self.td / "A.xlsx"
        d.write_bytes(b"1")
        self.assertEqual(ck.ten_khong_trung(d).name, "A (2).xlsx")


class TestSaoLuu(Nen):
    def test_sao_luu_du_file_dung_md5(self):
        src = self.td / "BOM SNPL"
        (src / "con").mkdir(parents=True)
        (src / "a.xlsx").write_bytes(b"a")
        (src / "con" / "b.xlsx").write_bytes(b"b")
        dich, n = ck.sao_luu(src, self.td / "_CHO_XOA", "R1")
        self.assertEqual(n, 2)
        self.assertTrue((dich / "_MD5_SAO_LUU.tsv").exists())

    def test_khong_sao_luu_de_len_ban_cu(self):
        src = self.td / "S"
        src.mkdir()
        (src / "a").write_bytes(b"a")
        ck.sao_luu(src, self.td / "_CHO_XOA", "R1")
        with self.assertRaises(ck.ChotDung):
            ck.sao_luu(src, self.td / "_CHO_XOA", "R1")


class TestSoSanhO(Nen):
    def test_chi_doi_cot_c_thi_dat(self):
        a = tao_xlsx(self.td / "a.xlsx", {"C18": "OLD-HQ", "D18": "=1+1"})
        b = tao_xlsx(self.td / "b.xlsx", {"C18": "NEW-HQ", "D18": "=1+1"})
        vp = ck.so_sanh_o(a, b, lambda s, r: r.startswith("C"))
        self.assertEqual(vp, [])

    def test_lam_mat_cong_thuc_thi_bat(self):
        a = tao_xlsx(self.td / "a.xlsx", {"C18": "OLD-HQ", "D18": "=1+1"})
        b = tao_xlsx(self.td / "b.xlsx", {"C18": "NEW-HQ", "D18": 2})
        vp = ck.so_sanh_o(a, b, lambda s, r: r.startswith("C"))
        self.assertEqual(len(vp), 1)
        self.assertIn("D18", vp[0])

    def test_so_sanh_entry_bat_entry_bi_viet_lai(self):
        a = tao_xlsx(self.td / "a.xlsx", {"A1": 1})
        b = tao_xlsx(self.td / "b.xlsx", {"A1": 2})
        vp = ck.so_sanh_entry(a, b, cho_phep=[])
        self.assertTrue(any("sheet1.xml" in x for x in vp))


class TestCongThuc(Nen):
    def _xlsx_co_link(self, path: Path, thu_tu: list[str]) -> Path:
        """Dựng xlsx tối thiểu có externalReference theo thứ tự cho trước."""
        refs = "".join(f'<externalReference r:id="rIdE{i}"/>' for i in range(1, len(thu_tu) + 1))
        wb = ('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
              f'<sheets/><externalReferences>{refs}</externalReferences></workbook>')
        rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                + "".join(f'<Relationship Id="rIdE{i}" Target="externalLinks/externalLink{i}.xml"/>'
                          for i in range(1, len(thu_tu) + 1)) + "</Relationships>")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("xl/workbook.xml", wb)
            z.writestr("xl/_rels/workbook.xml.rels", rels)
            for i, ten in enumerate(thu_tu, start=1):
                z.writestr(f"xl/externalLinks/externalLink{i}.xml", "<externalLink/>")
                z.writestr(f"xl/externalLinks/_rels/externalLink{i}.xml.rels",
                           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                           f'<Relationship Id="rId1" Target="file:///O:\\{ten}"/></Relationships>')
        return path

    def test_link_dao_cho_khong_bao_loi_gia(self):
        mau = self._xlsx_co_link(self.td / "mau.xlsx", ["BẢNG CHI TIẾT NHẬP KHẨU 2025.xlsx", "MAPPING HQ+NVL.xlsb"])
        moi = self._xlsx_co_link(self.td / "moi.xlsx", ["MAPPING HQ+NVL.xlsb", "BẢNG CHI TIẾT NHẬP KHẨU 2025.xlsx"])
        f_mau = "=_xlfn.XLOOKUP(F2,[2]'MAPPING (thư)'!$A:$A,[2]'MAPPING (thư)'!$C:$C,\"KHÔNG CÓ MÃ\")"
        f_moi = "=XLOOKUP(F2,[1]'MAPPING (thư)'!$A:$A,[1]'MAPPING (thư)'!$C:$C,\"KHÔNG CÓ MÃ\")"
        self.assertEqual(ck.chuan_hoa_cong_thuc(f_mau, ck.link_ngoai(mau)),
                         ck.chuan_hoa_cong_thuc(f_moi, ck.link_ngoai(moi)))

    def test_link_sai_file_van_bao(self):
        mau = self._xlsx_co_link(self.td / "mau.xlsx", ["MAPPING HQ+NVL.xlsb"])
        moi = self._xlsx_co_link(self.td / "moi.xlsx", ["MAPPING CU.xlsb"])
        f = "=XLOOKUP(F2,[1]'MAPPING (thư)'!$A:$A,[1]'MAPPING (thư)'!$C:$C,\"KHÔNG CÓ MÃ\")"
        self.assertNotEqual(ck.chuan_hoa_cong_thuc(f, ck.link_ngoai(mau)),
                            ck.chuan_hoa_cong_thuc(f, ck.link_ngoai(moi)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
