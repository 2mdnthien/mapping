# -*- coding: utf-8 -*-
"""dieu_phoi.py — Trưởng nhóm bằng code: chạy tuần tự từng bước nhỏ, Gác cổng chấm, mới cho bước sau.

Agent chỉ gọi 1 lệnh và đọc ≤ 12 dòng in ra. Chi tiết nằm trong NHAT KY, chỉ mở khi DỪNG.

  dieu_phoi.py bat-dau [--ds FILE] [--tu-dong]   tạo phiên, khoá MAPPING/NK/BOM mẫu/script
  dieu_phoi.py tiep [--den-het]                  làm nhịp kế tiếp (hoặc chạy tới khi phải dừng)
  dieu_phoi.py duyet                             anh Thiên cho chạy thật bước đang chờ
  dieu_phoi.py trang-thai                        mỗi bước 1 dòng
  dieu_phoi.py chi-tiet <mã chốt|bước> [--so-dong N]   trích sổ/nhật ký, có giới hạn dòng
  dieu_phoi.py khoi-phuc                         đưa bước đang DỪNG về trước bước, để chạy lại riêng bước đó

Điểm khôi phục: trước MỖI bước chạy thật -> _CHO_XOA/KHOI_PHUC_<run_id>/<bước>/. Chỉ xoá khi CẢ CHUỖI ĐẠT
(kiểm toán cuối xong); bước sau phát hiện bước trước sai vẫn quay lại được.

Mã thoát: 0 = bước xong, đi tiếp được · 2 = DỪNG (chốt CỨNG) · 3 = CHỜ DUYỆT · 4 = HOÀN TẤT.
--tu-dong: anh duyệt trước cả chuỗi → không hỏi lại từng bước, CHỈ dừng khi chốt CỨNG không đạt.
           Bước B6 (sửa file đã có) luôn phải duyệt riêng.
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chot_kiem as ck  # noqa: E402
import gac_cong as gc  # noqa: E402

TOI_DA_DONG = 12
TY_LE_NANG_CUNG = 0.20

THOAT_OK, THOAT_DUNG, THOAT_CHO, THOAT_HET = 0, 2, 3, 4


# ----------------------------------------------------------------------- cấu hình

def duong_dan(goc: Path) -> dict[str, Path]:
    """Mọi đường dẫn ở MỘT chỗ. Đối chiếu với máy trước khi chạy lần đầu."""
    cw = goc / "COWORK"
    out = cw / "Claude outputs" / "BOM"
    dc = goc / "DATA C"
    return {
        "GOC": goc,
        "SCRIPTS": cw / "BO_CONG_CU_TU_DONG_HOA_BOM" / "SCRIPTS",
        "OUT": out,
        "NHAT_KY": out / "NHAT KY" / "DIEU_PHOI",
        "TMP": out / "_TMP",
        "CHO_XOA": out / "_CHO_XOA",
        "CHO_XU_LY": out / "CHỜ XỬ LÝ",
        "NGUON_PI": dc / "NGUON PI",
        "NGUON_CUSTOM": dc / "NGUON CUSTOM MATERIAL",
        "MAPPING": dc / "NGUON MAPPING" / "MAPPING HQ+NVL.xlsx",
        "NK2025": dc / "NGUON MAPPING" / "BẢNG CHI TIẾT NHẬP KHẨU 2025.xlsx",
        "BOM_MAU": dc / "BOM MAU" / "3082-PUK-2S30-V.xlsx",
        "PI_DA_XU_LY": out / "PI ĐÃ XỬ LÝ",
        "MASTER_PI": out / "TỔNG HỢP MÃ THÀNH PHẨM PI.xlsx",
        "BOM_ERP": out / "BOM ERP",
        "BOM_SNPL": out / "BOM SNPL",
        "CAP_NHAT": out / "CAP NHAT",
    }


@dataclass
class Buoc:
    ma: str
    ten: str
    script: str
    tham_so: list[str]
    vung_ghi: list[str]                 # khoá trong duong_dan()
    sua_file_cu: list[str] = field(default_factory=list)  # vùng được sửa file đã có (sao lưu trước)
    duyet_rieng: bool = False           # luôn hỏi kể cả --tu-dong
    nhan_ds: bool = True                # có chuyển --ds xuống script không


CHUOI: list[Buoc] = [
    Buoc("B0", "Lọc nguồn", "00_loc_nguon.py", ["2025", "2026"], ["NGUON_PI", "NGUON_CUSTOM", "CHO_XU_LY"]),
    Buoc("B1", "Bóc PDF → Master PI", "01_boc_pdf.py", [], ["PI_DA_XU_LY", "MASTER_PI", "CHO_XU_LY"], nhan_ds=False),
    Buoc("B2", "BOM ERP + mapping HQ + Mẫu 07", "02_tao_bom_mau07.py", [], ["BOM_ERP", "BOM_SNPL", "CHO_XU_LY"]),
    Buoc("B2b", "Pivot Excel → cột E", "02b_pivot_excel.py", [], ["BOM_SNPL", "BOM_ERP", "CHO_XU_LY"],
         sua_file_cu=["BOM_SNPL"]),
    Buoc("B3", "Kiểm toán (chỉ đọc)", "03_kiem_toan.py", [], []),
]
BUOC_CAP_NHAT = Buoc("B6", "Cập nhật mã HQ", "04_cap_nhat.py", [], ["BOM_SNPL", "BOM_ERP", "CHO_XU_LY"],
                     sua_file_cu=["BOM_SNPL", "BOM_ERP"], duyet_rieng=True)

TRANG_THAI = ("CHUA", "CHO_DUYET", "DA_DUYET", "XONG", "DUNG")


# ------------------------------------------------------------------------ phiên

class PhienChay:
    """Trạng thái phiên lưu trong NHAT KY/<run_id>/ — mở lại ở hội thoại mới vẫn chạy tiếp được."""

    def __init__(self, goc: Path, run_id: str | None = None):
        self.d = duong_dan(goc)
        nk = self.d["NHAT_KY"]
        if run_id is None:
            ds = sorted(p.name for p in nk.iterdir() if p.is_dir()) if nk.exists() else []
            if not ds:
                raise SystemExit("Chưa có phiên. Chạy: dieu_phoi.py bat-dau")
            run_id = ds[-1]
        self.run_id = run_id
        self.thu_muc = nk / run_id
        self.f_tt = self.thu_muc / "TRANG_THAI.tsv"
        self.f_ch = self.thu_muc / "CAU_HINH.tsv"
        self.f_khoa = self.thu_muc / "KHOA.tsv"
        self.f_so = self.thu_muc / "SO_CHOT_KIEM.tsv"
        self.cau_hinh = dict(l.split("\t", 1) for l in self.f_ch.read_text(encoding="utf-8").splitlines() if l)

    # -- chuỗi bước của phiên này
    def chuoi(self) -> list[Buoc]:
        return [BUOC_CAP_NHAT] if self.cau_hinh.get("che_do") == "cap-nhat" else CHUOI

    def trang_thai(self) -> dict[str, tuple[str, str]]:
        tt = {b.ma: ("CHUA", "") for b in self.chuoi()}
        if self.f_tt.exists():
            for l in self.f_tt.read_text(encoding="utf-8").splitlines():
                p = l.split("\t")
                if len(p) >= 3 and p[1] in tt:
                    tt[p[1]] = (p[2], p[3] if len(p) > 3 else "")
        return tt

    def dat_trang_thai(self, ma: str, tt: str, ghi_chu: str = "") -> None:
        with open(self.f_tt, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}\t{ma}\t{tt}\t{ghi_chu}\n")

    def ghi_so(self, ma_buoc: str, c: gc.Chot | ck.KetQuaChot) -> None:
        kq = "DAT" if c.dat else ("KHONG KIEM DUOC" if c.dat is None else "KHONG DAT")
        with open(self.f_so, "a", encoding="utf-8", newline="\n") as f:
            f.write("\t".join([time.strftime("%H:%M:%S"), ma_buoc, c.ma, c.ten, c.muc, kq,
                               c.doi_tuong, (c.chi_tiet or "").replace("\n", " | ")]) + "\n")

    # -- khoá
    def kiem_khoa(self) -> list[str]:
        doi = []
        for l in self.f_khoa.read_text(encoding="utf-8").splitlines():
            p, md5 = l.split("\t")[0], l.split("\t")[3]
            if not Path(p).exists():
                doi.append(f"{Path(p).name}: MẤT FILE")
            elif ck.md5_file(Path(p)) != md5:
                doi.append(f"{Path(p).name}: đã đổi sau khi khoá")
        return doi


def file_khoa(d: dict[str, Path]) -> list[Path]:
    fs = [d["MAPPING"], d["NK2025"], d["BOM_MAU"]]
    if d["SCRIPTS"].exists():
        fs += sorted(p for p in d["SCRIPTS"].iterdir() if p.suffix in (".py", ".ps1"))
    return fs


def bat_dau(goc: Path, ds: str | None, tu_dong: bool, cap_nhat: bool) -> int:
    d = duong_dan(goc)
    thieu = [str(p) for p in (d["MAPPING"], d["NK2025"], d["BOM_MAU"], d["SCRIPTS"]) if not p.exists()]
    if thieu:
        return in_gon(["✘ DỪNG [K.0] thiếu đầu vào:"] + thieu, THOAT_DUNG)
    run_id = time.strftime("%Y%m%d-%H%M%S")
    td = d["NHAT_KY"] / run_id
    td.mkdir(parents=True, exist_ok=False)
    with open(td / "CAU_HINH.tsv", "w", encoding="utf-8", newline="\n") as f:
        f.write(f"ds\t{ds or ''}\ntu_dong\t{int(tu_dong)}\nche_do\t{'cap-nhat' if cap_nhat else 'toan-trinh'}\n")
    dong = []
    with open(td / "KHOA.tsv", "w", encoding="utf-8", newline="\n") as f:
        for p in file_khoa(d):
            dv = ck.DauVet.cua(p)
            f.write(dv.dong() + "\n")
            if p.name in (d["MAPPING"].name, d["NK2025"].name, d["BOM_MAU"].name):
                dong.append(f"  khoá {p.name}: md5 {dv.md5[:8]}, sửa {dv.dong().split(chr(9))[2]}")
    # K.2: script đúng phiên bản đã ghim (nếu đã có bảng ghim)
    ghim = d["SCRIPTS"].parent / "HUONG_DAN" / "PHIEN_BAN_SCRIPT.tsv"
    if ghim.exists():
        lech = []
        for l in ghim.read_text(encoding="utf-8").splitlines():
            if "\t" not in l:
                continue
            ten, md5 = l.split("\t")[:2]
            p = d["SCRIPTS"] / ten
            if not p.exists() or ck.md5_file(p) != md5.strip():
                lech.append(ten)
        if lech:
            return in_gon([f"✘ DỪNG [K.2] script khác phiên bản đã duyệt: {', '.join(lech)}"], THOAT_DUNG)
    return in_gon([f"PHIÊN {run_id} · {'TỰ ĐỘNG (đã duyệt trước)' if tu_dong else 'HỎI TỪNG BƯỚC'}"
                   f" · phạm vi: {ds or 'toàn bộ'}"] + dong + ["Tiếp: dieu_phoi.py tiep --den-het"], THOAT_OK)


# ------------------------------------------------------------------ chụp vùng ghi

def chup(goc_vung: list[Path]) -> dict[str, tuple[int, int]]:
    out = {}
    for v in goc_vung:
        if v.is_file():
            st = v.stat(); out[str(v)] = (st.st_size, st.st_mtime_ns)
        elif v.is_dir():
            for p in v.rglob("*"):
                if p.is_file() and not p.name.startswith("~$"):
                    st = p.stat(); out[str(p)] = (st.st_size, st.st_mtime_ns)
    return out


def chup_toan_vung(d: dict[str, Path]) -> dict[str, tuple[int, int]]:
    """Mọi chỗ có thể bị ghi nhầm (trừ NHAT KY, _TMP, _CHO_XOA của chính hệ thống)."""
    bo = {d["NHAT_KY"], d["TMP"], d["CHO_XOA"]}
    vung = [d["OUT"], d["NGUON_PI"], d["NGUON_CUSTOM"], d["MAPPING"].parent, d["BOM_MAU"].parent, d["SCRIPTS"]]
    snap = chup(vung)
    return {k: v for k, v in snap.items() if not any(Path(k).is_relative_to(b) for b in bo)}


# ------------------------------------------------------------------- chạy script

def chay_script(ph: PhienChay, b: Buoc, thu: bool) -> tuple[int, Path]:
    lenh = [sys.executable, "-X", "utf8", "-B", str(ph.d["SCRIPTS"] / b.script), *b.tham_so]
    ds = ph.cau_hinh.get("ds")
    if ds and b.nhan_ds:
        lenh += ["--ds", ds]
    if thu:
        lenh.append("--dry-run")
    log = ph.thu_muc / f"{b.ma}_{'THU' if thu else 'THAT'}.log"
    with open(log, "w", encoding="utf-8") as f:
        f.write("LỆNH: " + " ".join(lenh) + "\n")
        f.flush()
        rc = subprocess.run(lenh, cwd=ph.d["SCRIPTS"].parent, stdout=f, stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8"}).returncode
    return rc, log


def log_co_loi(log: Path) -> str:
    t = log.read_text(encoding="utf-8", errors="replace")
    return "Traceback" if "Traceback (most recent call last)" in t else ""


def duoi_log(log: Path, n: int = 4) -> list[str]:
    ls = [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    return ["  │ " + l[:160] for l in ls[-n:]]


# ------------------------------------------------------------------ một nhịp

def nhip(ph: PhienChay) -> int:
    tt = ph.trang_thai()
    b = next((b for b in ph.chuoi() if tt[b.ma][0] != "XONG"), None)
    if b is None:
        return in_gon([f"HOÀN TẤT phiên {ph.run_id}: mọi bước XONG."] + don_diem_khoi_phuc(ph)
                      + tom_tat_mem(ph), THOAT_HET)
    trang = tt[b.ma][0]
    if trang == "DUNG":
        return in_gon([f"✘ {b.ma} đang DỪNG: {tt[b.ma][1]}",
                       f"Xem: dieu_phoi.py chi-tiet {b.ma} · Khôi phục + chạy lại riêng bước: dieu_phoi.py khoi-phuc",
                       "Chờ anh ra lệnh."], THOAT_DUNG)
    if trang == "CHO_DUYET":
        return in_gon([f"⏸ {b.ma} {b.ten}: chạy thử ĐẠT, CHỜ DUYỆT chạy thật.", f"  {tt[b.ma][1]}",
                       "Anh cho chạy: dieu_phoi.py duyet"], THOAT_CHO)

    def dung(ma_chot: str, ly_do: str, them: list[str] = ()) -> int:
        ph.ghi_so(b.ma, ck.KetQuaChot(ma_chot, ly_do, ck.CUNG, False, ""))
        ph.dat_trang_thai(b.ma, "DUNG", f"[{ma_chot}] {ly_do}")
        return in_gon([f"✘ DỪNG {b.ma} {b.ten} [{ma_chot}] {ly_do}", *them, "Đang dừng, chờ anh ra lệnh."],
                      THOAT_DUNG)

    # K.1 trước mọi việc
    doi = ph.kiem_khoa()
    if doi:
        return dung("K.1", "đầu vào đã khoá bị đổi: " + "; ".join(doi[:3]))

    if trang == "CHUA":
        truoc = chup_toan_vung(ph.d)
        rc, log = chay_script(ph, b, thu=True)
        sau = chup_toan_vung(ph.d)
        if rc != 0 or log_co_loi(log):
            return dung("K.7", f"chạy thử lỗi (mã {rc})", duoi_log(log))
        ghi_nham = sorted(k for k in sau.keys() | truoc.keys() if sau.get(k) != truoc.get(k))
        if ghi_nham:
            return dung("K.5", f"chạy thử mà vẫn ghi {len(ghi_nham)} file", [f"  {Path(x).name}" for x in ghi_nham[:3]])
        tom = duoi_log(log, 3)
        tu_dong = ph.cau_hinh.get("tu_dong") == "1" and not b.duyet_rieng
        if not tu_dong:
            ph.dat_trang_thai(b.ma, "CHO_DUYET", " / ".join(x.strip(" │") for x in tom)[:300])
            return in_gon([f"⏸ {b.ma} {b.ten}: chạy thử ĐẠT, CHỜ DUYỆT chạy thật.", *tom,
                           "Anh cho chạy: dieu_phoi.py duyet"], THOAT_CHO)
        ph.dat_trang_thai(b.ma, "DA_DUYET", "tự động (duyệt trước cả chuỗi)")

    # ---- chạy thật: tạo ĐIỂM KHÔI PHỤC trước, rồi mới chạy
    try:
        kp = tao_diem_khoi_phuc(ph, b)
    except ck.ChotDung as e:
        return dung("6.1", str(e))
    khoa_chi_doc = khoa_file_cu(ph, b)          # file cũ không được sửa -> đặt chỉ đọc trong lúc chạy
    try:
        truoc = chup_toan_vung(ph.d)
        rc, log = chay_script(ph, b, thu=False)
        sau = chup_toan_vung(ph.d)
    finally:
        mo_khoa(khoa_chi_doc)
    goi_y = [f"Khôi phục bước {b.ma} rồi chạy lại riêng bước này: dieu_phoi.py khoi-phuc"]
    if rc != 0 or log_co_loi(log):
        return dung("K.7", f"chạy thật lỗi (mã {rc})", duoi_log(log) + goi_y)

    moi = sorted(Path(k) for k in sau.keys() - truoc.keys())
    doi_ = sorted(Path(k) for k in sau.keys() & truoc.keys() if sau[k] != truoc[k])
    mat = sorted(Path(k) for k in truoc.keys() - sau.keys())
    vung = [ph.d[k] for k in b.vung_ghi]
    ngoai = [p for p in moi + doi_ + mat if not any(p == v or v in p.parents for v in vung)]
    if ngoai:
        return dung("K.5", f"ghi/xoá ngoài vùng của bước: {len(ngoai)} file",
                    [f"  {p}" for p in ngoai[:3]] + goi_y)
    sai_de = [p for p in doi_ if not duoc_sua(ph, b, p)]
    if sai_de:
        return dung("K.4", f"ghi đè {len(sai_de)} file đã có", [f"  {p.name}" for p in sai_de[:3]] + goi_y)

    # 4.2 / 6.2: file cũ bị sửa chỉ được đổi trong vùng ô cho phép (so với bản ở điểm khôi phục)
    cho_phep = gc.vung_duoc_doi(b.ma)
    for p in doi_:
        ban_cu = kp / "FILE" / ma_hoa(ph, p)
        if p.suffix == ".xlsx" and any(ph.d[k] in p.parents for k in b.sua_file_cu) and ban_cu.exists():
            vp = ck.so_sanh_o(ban_cu, p, cho_phep)
            if vp:
                return dung("6.2" if b.ma == "B6" else "4.2",
                            f"{p.name}: đổi ngoài vùng cho phép ({len(vp)} ô)",
                            [f"  {x[:150]}" for x in vp[:3]] + goi_y)

    # Gác cổng nghiệp vụ trên file mới/đổi
    chot = gc.cham(b.ma, moi, doi_, {k: str(v) for k, v in ph.d.items()})
    for c in chot:
        ph.ghi_so(b.ma, c)
    cung = [c for c in chot if c.muc == ck.CUNG and c.dat is not True]
    if cung:
        c = cung[0]
        return dung(c.ma, f"{c.ten} — {c.doi_tuong} {c.chi_tiet}",
                    ([f"  (+{len(cung) - 1} chốt CỨNG khác)"] if len(cung) > 1 else []) + goi_y)
    mem = [c for c in chot if c.muc == ck.MEM and c.dat is not True]
    doi_tuong = {c.doi_tuong for c in chot if c.doi_tuong}
    hong = {c.doi_tuong for c in mem}
    if doi_tuong and len(hong) / len(doi_tuong) > TY_LE_NANG_CUNG:
        return dung("K.8", f"{len(hong)}/{len(doi_tuong)} file không đạt chốt MỀM (> 20 %): lỗi hệ thống", goi_y)
    doi2 = ph.kiem_khoa()
    if doi2:
        return dung("K.1", "đầu vào bị đổi trong lúc chạy: " + "; ".join(doi2[:3]), goi_y)
    ph.dat_trang_thai(b.ma, "XONG", f"mới {len(moi)}, đổi {len(doi_)}, MỀM {len(mem)}")
    dong = [f"✔ {b.ma} {b.ten}: XONG · file mới {len(moi)} · đổi {len(doi_)} · chốt đạt "
            f"{sum(1 for c in chot if c.dat)}/{len(chot)} · điểm khôi phục giữ tới khi cả chuỗi đạt"]
    if mem:
        dong.append(f"  ⏸ MỀM {len(mem)} mục ({len(hong)} file) → xem: dieu_phoi.py chi-tiet {b.ma}")
    return in_gon(dong, THOAT_OK)


# ------------------------------------------------------------ điểm khôi phục

FILE_SUA_DUOC = {"TỔNG HỢP MÃ THÀNH PHẨM PI.xlsx", "DANH SÁCH CHỜ XỬ LÝ.xlsx"}


def thu_muc_kp(ph: PhienChay, b: Buoc) -> Path:
    return ph.d["CHO_XOA"] / f"KHOI_PHUC_{ph.run_id}" / b.ma


def ma_hoa(ph: PhienChay, p: Path) -> Path:
    """Đường dẫn tương đối so với GOC để lưu trong điểm khôi phục."""
    return Path(p).relative_to(ph.d["GOC"])


def duoc_sua(ph: PhienChay, b: Buoc, p: Path) -> bool:
    return p.name in FILE_SUA_DUOC or any(ph.d[k] in p.parents for k in b.sua_file_cu)


def file_trong_vung(ph: PhienChay, b: Buoc) -> list[Path]:
    return [Path(k) for k in chup([ph.d[k] for k in b.vung_ghi])]


def tao_diem_khoi_phuc(ph: PhienChay, b: Buoc) -> Path:
    """Chép mọi file có sẵn trong vùng ghi của bước + ghi danh sách kèm md5.

    Đủ để đưa vùng ghi về đúng trạng thái trước bước: file mới -> dời ra, file sửa -> chép lại.
    """
    kp = thu_muc_kp(ph, b)
    if kp.exists():                       # lần chạy lại sau khi khôi phục: tạo điểm mới, giữ điểm cũ
        kp.rename(kp.with_name(f"{b.ma}_cu_{time.strftime('%H%M%S')}"))
    (kp / "FILE").mkdir(parents=True)
    co_san = file_trong_vung(ph, b)
    with open(kp / "DANH_SACH_TRUOC.tsv", "w", encoding="utf-8", newline="\n") as f:
        for p in co_san:
            # sao lưu MỌI file có sẵn; riêng 2 kho NGUON (B0 chỉ thêm mới) được bảo vệ bằng chỉ đọc
            sao = not any(ph.d[k] in p.parents for k in ("NGUON_PI", "NGUON_CUSTOM"))
            md5 = ck.md5_file(p)
            if sao:
                d = kp / "FILE" / ma_hoa(ph, p)
                d.parent.mkdir(parents=True, exist_ok=True)
                ck.ghi_khong_de(p, d)
            f.write(f"{p}\t{md5}\t{int(sao)}\n")
    return kp


def khoa_file_cu(ph: PhienChay, b: Buoc) -> list[Path]:
    """Đặt chỉ đọc cho file cũ KHÔNG được sửa -> script lỡ ghi đè sẽ bị hệ điều hành chặn."""
    out = []
    for p in file_trong_vung(ph, b):
        if not duoc_sua(ph, b, p) and os.access(p, os.W_OK):
            os.chmod(p, stat.S_IREAD)
            out.append(p)
    return out


def mo_khoa(ds: list[Path]) -> None:
    for p in ds:
        if p.exists():
            os.chmod(p, stat.S_IREAD | stat.S_IWRITE)


def khoi_phuc(ph: PhienChay) -> int:
    """Đưa vùng ghi của bước đang DỪNG về trạng thái trước bước, đặt lại CHUA để chạy lại riêng bước đó."""
    tt = ph.trang_thai()
    b = next((b for b in ph.chuoi() if tt[b.ma][0] in ("DUNG", "DA_DUYET")), None)
    if b is None:
        return in_gon(["Không có bước nào cần khôi phục."], THOAT_OK)
    kp = thu_muc_kp(ph, b)
    ds = kp / "DANH_SACH_TRUOC.tsv"
    if not ds.exists():                        # dừng trước khi chạy thật -> không có gì để khôi phục
        ph.dat_trang_thai(b.ma, "CHUA", "đặt lại (chưa chạy thật)")
        return in_gon([f"{b.ma}: chưa chạy thật, chỉ đặt lại. Tiếp: dieu_phoi.py tiep"], THOAT_OK)
    truoc = {}
    for l in ds.read_text(encoding="utf-8").splitlines():
        p, md5, sao = l.split("\t")
        truoc[Path(p)] = (md5, sao == "1")
    hien = set(file_trong_vung(ph, b))
    moi = sorted(hien - truoc.keys())
    # 1) file mới sinh ra trong bước lỗi -> dời sang KHOI_PHUC_<run>/<bước>_LOI (không xoá vĩnh viễn)
    loi = kp.with_name(f"{b.ma}_LOI_{time.strftime('%H%M%S')}")
    da_doi = {}
    for p in moi:
        d = loi / ma_hoa(ph, p)
        d.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
        shutil.move(str(p), str(d))
        da_doi[(p.name, ck.md5_file(d))] = d
    # 2) file có sẵn mà mất/đổi -> lấy lại (từ điểm khôi phục, hoặc file vừa bị dời đi nơi khác)
    khong_lay_lai = []
    for p, (md5, sao) in truoc.items():
        if p.exists() and ck.md5_file(p) == md5:
            continue
        nguon = kp / "FILE" / ma_hoa(ph, p) if sao else da_doi.get((p.name, md5))
        if nguon is None or not nguon.exists() or ck.md5_file(nguon) != md5:
            khong_lay_lai.append(p)
            continue
        if p.exists():
            d = loi / (ma_hoa(ph, p).as_posix() + ".SAI")
            d.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
            shutil.move(str(p), str(d))
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(nguon, p)
    # 3) kiểm lại: vùng ghi phải đúng như trước bước
    sai = [p for p, (md5, _) in truoc.items() if not p.exists() or ck.md5_file(p) != md5]
    thua = sorted(set(file_trong_vung(ph, b)) - truoc.keys())
    if sai or thua or khong_lay_lai:
        ph.dat_trang_thai(b.ma, "DUNG", f"khôi phục KHÔNG trọn: sai {len(sai)}, thừa {len(thua)}")
        return in_gon([f"✘ Khôi phục {b.ma} KHÔNG trọn vẹn: sai {len(sai)} · thừa {len(thua)} · "
                       f"không lấy lại được {len(khong_lay_lai)}",
                       *[f"  {p.name}" for p in (sai + thua + khong_lay_lai)[:4]],
                       f"Điểm khôi phục còn nguyên: {kp}", "Đang dừng, chờ anh ra lệnh."], THOAT_DUNG)
    ph.dat_trang_thai(b.ma, "CHUA", f"đã khôi phục: dời {len(moi)} file lỗi sang {loi.name}")
    return in_gon([f"✔ Đã khôi phục {b.ma}: vùng ghi đúng như trước bước ({len(truoc)} file khớp md5).",
                   f"  file của lần lỗi để ở {loi.name} để đối chiếu",
                   f"Chạy lại riêng {b.ma}: dieu_phoi.py tiep"], THOAT_OK)


def don_diem_khoi_phuc(ph: PhienChay) -> list[str]:
    """Chỉ gọi khi CẢ CHUỖI XONG (kiểm toán cuối đã đạt). Xoá điểm khôi phục, giữ thư mục *_LOI."""
    goc = ph.d["CHO_XOA"] / f"KHOI_PHUC_{ph.run_id}"
    if not goc.exists():
        return []
    n = 0
    for p in list(goc.iterdir()):
        if "_LOI_" in p.name:
            continue
        n += sum(1 for x in p.rglob("*") if x.is_file())
        shutil.rmtree(p)
    if not any(goc.iterdir()):
        goc.rmdir()
    return [f"  đã xoá điểm khôi phục ({n} file) vì mọi bước đã ĐẠT"]


def tom_tat_mem(ph: PhienChay) -> list[str]:
    if not ph.f_so.exists():
        return []
    mem = [l.split("\t") for l in ph.f_so.read_text(encoding="utf-8").splitlines()
           if "\tMEM\t" in l and "\tDAT\t" not in l]
    by: dict[str, int] = {}
    for p in mem:
        by[f"{p[1]} [{p[2]}] {p[3]}"] = by.get(f"{p[1]} [{p[2]}] {p[3]}", 0) + 1
    return [f"  ⏸ {k}: {v} mục" for k, v in sorted(by.items())][:8]


# ------------------------------------------------------------------ in gọn

def in_gon(dong: list[str], ma: int) -> int:
    if len(dong) > TOI_DA_DONG:
        dong = dong[:TOI_DA_DONG - 1] + [f"  … (+{len(dong) - TOI_DA_DONG + 1} dòng, xem chi-tiet)"]
    print("\n".join(dong))
    return ma


def chi_tiet(ph: PhienChay, khoa: str, n: int) -> int:
    ls = []
    if ph.f_so.exists():
        ls = [l for l in ph.f_so.read_text(encoding="utf-8").splitlines()
              if f"\t{khoa}\t" in l and "\tDAT\t" not in l]
    if not ls:
        for log in sorted(ph.thu_muc.glob(f"{khoa}_*.log")):
            ls += [f"{log.name}: {l}" for l in log.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]]
    global TOI_DA_DONG
    TOI_DA_DONG = n
    return in_gon([l[:200] for l in ls] or [f"Không có dòng nào cho {khoa}."], THOAT_OK)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["bat-dau", "tiep", "duyet", "trang-thai", "chi-tiet", "khoi-phuc"])
    ap.add_argument("khoa", nargs="?")
    ap.add_argument("--goc", default=os.environ.get("AGENTIC_GOC", r"C:\Users\accountsf\Downloads\AGENTIC"))
    ap.add_argument("--run")
    ap.add_argument("--ds")
    ap.add_argument("--tu-dong", action="store_true")
    ap.add_argument("--cap-nhat", action="store_true", help="phiên chỉ chạy B6 (script 04)")
    ap.add_argument("--den-het", action="store_true")
    ap.add_argument("--so-dong", type=int, default=20)
    a = ap.parse_args(argv)
    goc = Path(a.goc)
    if a.lenh == "bat-dau":
        return bat_dau(goc, a.ds, a.tu_dong, a.cap_nhat)
    ph = PhienChay(goc, a.run)
    if a.lenh == "trang-thai":
        return in_gon([f"PHIÊN {ph.run_id}"] + [f"  {k}: {v[0]} {v[1][:90]}" for k, v in ph.trang_thai().items()],
                      THOAT_OK)
    if a.lenh == "duyet":
        tt = ph.trang_thai()
        b = next((b for b in ph.chuoi() if tt[b.ma][0] == "CHO_DUYET"), None)
        if b is None:
            return in_gon(["Không có bước nào đang chờ duyệt."], THOAT_OK)
        ph.dat_trang_thai(b.ma, "DA_DUYET", "anh Thiên duyệt")
        return in_gon([f"Đã ghi duyệt {b.ma}. Tiếp: dieu_phoi.py tiep --den-het"], THOAT_OK)
    if a.lenh == "khoi-phuc":
        return khoi_phuc(ph)
    if a.lenh == "chi-tiet":
        return chi_tiet(ph, a.khoa or "", a.so_dong)
    while True:
        rc = nhip(ph)
        if not a.den_het or rc != THOAT_OK:
            return rc


if __name__ == "__main__":
    sys.exit(main())
