# -*- coding: utf-8 -*-
"""gac_cong.py — Gác cổng: chấm chốt kiểm nghiệp vụ trên FILE KẾT QUẢ, không tin số người làm báo.

Chỉ đọc. Mỗi hàm chấm trả về danh sách Chot(ma, ten, muc, dat, chi_tiet, doi_tuong).
dat = None nghĩa là KHÔNG KIỂM ĐƯỢC (thiếu cache…) — không bao giờ coi là đạt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import chot_kiem as ck

CUNG, MEM = ck.CUNG, ck.MEM
LOI_EXCEL = ("#N/A", "#REF!", "#VALUE!", "#NAME?", "#DIV/0!")
KHONG_KHAI = {"KHÔNG KHAI HQ", "KHONG KHAI HQ", "Không khai HQ"}
_REF = re.compile(r"([A-Z]+)(\d+)")


@dataclass
class Chot:
    ma: str
    ten: str
    muc: str
    dat: bool | None
    chi_tiet: str = ""
    doi_tuong: str = ""


def tach(ref: str) -> tuple[str, int]:
    m = _REF.fullmatch(ref)
    return m.group(1), int(m.group(2))


def so(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def sheet_mau07(o: dict) -> str | None:
    ten = {s for s, _ in o} - {"Sheet1", "Sheet2"}
    return next(iter(ten)) if len(ten) == 1 else None


# ------------------------------------------------------------------ từng loại file

def cham_bom_erp(f: Path) -> list[Chot]:
    o = ck.doc_o(f, chi_sheet=["Sheet1"])
    d = f.stem
    out = []
    hdr_ok = o.get(("Sheet1", "A1"), (None, None))[1] == "FG Code" and \
        o.get(("Sheet1", "L1"), (None, None))[1] == "MA HQ"
    out.append(Chot("2.0", "Tiêu đề Sheet1 A1=FG Code, L1=MA HQ", CUNG, hdr_ok, "", d))
    dong = sorted({tach(r)[1] for (_, r) in o if tach(r)[1] >= 2 and tach(r)[0] == "A"
                   and o[("Sheet1", r)][1] not in (None, "")})
    thieu_j = [n for n in dong if o.get(("Sheet1", f"J{n}"), (None, None))[0] is None]
    thieu_l = [n for n in dong if o.get(("Sheet1", f"L{n}"), (None, None))[0] is None]
    out.append(Chot("2.4", "Cột J là công thức", CUNG, not thieu_j,
                    f"dòng {thieu_j[:5]}" if thieu_j else f"{len(dong)} dòng", d))
    out.append(Chot("3.2", "Cột L là công thức XLOOKUP theo Material Code", CUNG, not thieu_l,
                    f"dòng {thieu_l[:5]}" if thieu_l else "", d))
    l_val = [o.get(("Sheet1", f"L{n}"), (None, None))[1] for n in dong]
    if all(v is None for v in l_val):
        out.append(Chot("3.3", "Không có KHÔNG CÓ MÃ", MEM, None, "[--] cột L chưa có giá trị cache", d))
    else:
        km = [n for n, v in zip(dong, l_val) if v == "KHÔNG CÓ MÃ"]
        nl = sorted({o.get(("Sheet1", f"F{n}"), (None, ""))[1] or "" for n in km})
        out.append(Chot("3.3", "Không có KHÔNG CÓ MÃ", MEM, not km, f"NL thiếu mapping: {nl[:10]}", d))
    loi = sorted({v for (_, _), (_, v) in o.items() if v in LOI_EXCEL})
    out.append(Chot("5.0", "Không có mã lỗi Excel", MEM, not loi, ",".join(loi), d))
    return out


def tong_doi_chieu(o: dict) -> tuple[float | None, float | None, float | None]:
    """(tổng Sheet1 J trừ KHÔNG KHAI HQ, tổng Pivot Sheet2, tổng cột E Mẫu07 trừ MX)."""
    s1 = p = m7 = 0.0
    co1 = cop = com = False
    for (sh, r), (_, v) in o.items():
        c, n = tach(r)
        if sh == "Sheet1" and c == "J" and n >= 2:
            hq = o.get(("Sheet1", f"L{n}"), (None, None))[1]
            if hq in KHONG_KHAI or so(v) is None:
                continue
            s1 += so(v); co1 = True
        elif sh == "Sheet2" and c == "B" and n >= 4:
            nhan = (o.get(("Sheet2", f"A{n}"), (None, None))[1] or "").strip()
            if nhan in ("", "Grand Total", "(blank)", "Row Labels") or nhan in KHONG_KHAI or so(v) is None:
                continue
            p += so(v); cop = True
    t = sheet_mau07(o)
    if t:
        for (sh, r), (_, v) in o.items():
            c, n = tach(r)
            if sh == t and c == "E" and n >= 18 and so(v) is not None:
                if (o.get((t, f"C{n}"), (None, None))[1] or "").strip() == "MX":
                    continue
                m7 += so(v); com = True
    return (round(s1, 6) if co1 else None, round(p, 6) if cop else None, round(m7, 6) if com else None)


def cham_bom_snpl(f: Path) -> list[Chot]:
    o = ck.doc_o(f)
    d = f.stem
    t = sheet_mau07(o)
    out = [Chot("4.0", "Đủ 3 sheet: Mẫu07 + Sheet1 + Sheet2", CUNG, t is not None and t == d[:31],
                f"sheet Mẫu07 = {t!r}", d)]
    if t is None:
        return out
    out.append(Chot("4.5", "D14 = 'Đơn vị tính sp: Cái '", CUNG,
                    o.get((t, "D14"), (None, None))[1] == "Đơn vị tính sp: Cái ", "", d))
    thieu = [r for (sh, r), (fm, v) in o.items()
             if sh == t and tach(r)[1] >= 18 and tach(r)[0] in "ABDFGH" and fm is None
             and o.get((t, f"C{tach(r)[1]}"), (None, None))[1]]
    out.append(Chot("4.2", "Mẫu07 A,B,D,F,G,H là công thức", CUNG, not thieu, f"ô {thieu[:5]}", d))
    s1, p, m7 = tong_doi_chieu(o)
    if None in (s1, p, m7):
        out.append(Chot("4.1", "Tổng Sheet1 = Pivot = Mẫu07", MEM, None,
                        f"[--] thiếu cache: Sheet1={s1} Pivot={p} Mẫu07={m7}", d))
    else:
        out.append(Chot("4.1", "Tổng Sheet1 = Pivot = Mẫu07", MEM, s1 == p == m7,
                        f"Sheet1={s1} Pivot={p} Mẫu07={m7}", d))
    return out


def cham_master_pi(f: Path) -> list[Chot]:
    o = ck.doc_o(f)
    sh = next(iter({s for s, _ in o}), None)
    tieu_de = [o.get((sh, f"{c}1"), (None, None))[1] for c in "ABCDEFGH"]
    so_cot = sum(1 for v in tieu_de if v not in (None, ""))
    dong = {tach(r)[1] for (s, r), (_, v) in o.items() if s == sh and tach(r)[0] == "B"
            and tach(r)[1] >= 2 and v not in (None, "")}
    return [Chot("1.2", "Master PI đúng 7 cột", CUNG, so_cot == 7, f"{so_cot} cột", f.name),
            Chot("1.3", "Master PI có dữ liệu", CUNG, len(dong) > 0, f"{len(dong)} mã TP", f.name)]


# ------------------------------------------------------------------ chấm theo bước

def cham(buoc: str, moi: list[Path], doi: list[Path], duong: dict) -> list[Chot]:
    """Chỉ chấm file MỚI hoặc ĐỔI trong lần chạy này (đỡ tốn thời gian và token)."""
    out: list[Chot] = []
    files = moi + doi
    erp = [f for f in files if f.suffix == ".xlsx" and Path(duong["BOM_ERP"]) in f.parents]
    snpl = [f for f in files if f.suffix == ".xlsx" and Path(duong["BOM_SNPL"]) in f.parents]
    if buoc == "B1":
        mp = Path(duong["MASTER_PI"])
        out += cham_master_pi(mp) if mp.exists() else [Chot("1.2", "Có Master PI", CUNG, False, str(mp))]
    if buoc == "B2":
        out.append(Chot("K.6", "Số file BOM ERP mới = số file BOM SNPL mới", CUNG,
                        {f.stem for f in erp} == {f.stem for f in snpl},
                        f"ERP {len(erp)}, SNPL {len(snpl)}; lệch "
                        f"{sorted({f.stem for f in erp} ^ {f.stem for f in snpl})[:5]}"))
        for f in erp:
            out += cham_bom_erp(f)
    if buoc in ("B2", "B2b", "B6"):
        for f in snpl:
            out += cham_bom_snpl(f)
    return out


def vung_duoc_doi(buoc: str) -> Callable[[str, str], bool]:
    """Ô nào được phép đổi trên FILE ĐÃ CÓ TỪ TRƯỚC khi chạy bước đó."""
    def b2b(sheet: str, ref: str) -> bool:
        c, n = tach(ref)
        return sheet == "Sheet2" or (sheet not in ("Sheet1",) and n >= 18 and c in "EGH")

    def b6(sheet: str, ref: str) -> bool:
        c, n = tach(ref)
        if sheet == "Sheet1":
            return c == "L" and n >= 2
        return sheet == "Sheet2" or (n >= 18 and c in "ABCDEFGH")

    return {"B2b": b2b, "B6": b6}.get(buoc, lambda s, r: False)
