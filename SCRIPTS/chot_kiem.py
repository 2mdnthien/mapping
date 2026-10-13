# -*- coding: utf-8 -*-
"""chot_kiem.py — Bộ chốt kiểm dùng chung cho bộ công cụ BOM (v4).

Chỉ dùng thư viện chuẩn của Python. Mọi script 00→04 import module này để:
  - khoá phiên bản đầu vào (MAPPING, BOM mẫu, chính các script) bằng md5 + giờ sửa;
  - ghi file an toàn: không bao giờ ghi đè, ghi xong đối chiếu md5;
  - sao lưu vào _CHO_XOA kèm bảng md5 và tự kiểm tra bản sao;
  - so 2 file .xlsx ở mức ô, chỉ cho phép đổi ở những ô được phép;
  - chuẩn hoá chỉ số liên kết ngoài [1]/[2] trước khi so công thức;
  - ghi sổ chốt kiểm (chỉ ghi thêm, không sửa) và bàn giao giữa các bước.

Quy ước mức chốt:
  CUNG -> không đạt thì DỪNG CẢ PHIÊN (raise ChotDung), chờ người dùng ra lệnh.
  MEM  -> không đạt thì đơn/mã đó vào CHỜ XỬ LÝ của đúng bước, phiên chạy tiếp.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import time
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

CUNG = "CUNG"
MEM = "MEM"

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


class ChotDung(Exception):
    """Chốt kiểm cứng không đạt: dừng toàn bộ phiên, báo trong chat, chờ lệnh."""


# --------------------------------------------------------------------------- md5

def md5_file(path: Path, _buf: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_buf), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class DauVet:
    """Dấu vết một file: đủ để biết file có bị đổi hay không."""
    path: str
    size: int
    mtime: float
    md5: str

    @classmethod
    def cua(cls, path: Path) -> "DauVet":
        st = Path(path).stat()
        return cls(str(path), st.st_size, round(st.st_mtime, 3), md5_file(Path(path)))

    def dong(self) -> str:
        t = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.mtime))
        return f"{self.path}\t{self.size}\t{t}\t{self.md5}"


# ------------------------------------------------------------------- sổ chốt kiểm

@dataclass
class KetQuaChot:
    ma: str           # vd "3.1"
    ten: str          # vd "Khoá phiên bản MAPPING"
    muc: str          # CUNG / MEM
    dat: bool
    chi_tiet: str = ""
    doi_tuong: str = ""   # đơn / FG / file bị ảnh hưởng (với chốt MEM)


@dataclass
class Phien:
    """Một phiên chạy. Mọi chốt kiểm đi qua đây để có sổ ghi thống nhất."""
    thu_muc_nhat_ky: Path
    run_id: str = field(default_factory=lambda: time.strftime("%Y%m%d-%H%M%S"))
    ket_qua: list[KetQuaChot] = field(default_factory=list)
    _khoa: dict[str, DauVet] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.thu_muc = Path(self.thu_muc_nhat_ky) / self.run_id
        self.thu_muc.mkdir(parents=True, exist_ok=False)
        self.so = self.thu_muc / "SO_CHOT_KIEM.tsv"
        self._ghi_dong("thoi_gian\tma\tten\tmuc\tket_qua\tdoi_tuong\tchi_tiet")

    # -- sổ chỉ ghi thêm
    def _ghi_dong(self, s: str) -> None:
        with open(self.so, "a", encoding="utf-8", newline="\n") as f:
            f.write(s.replace("\n", " | ") + "\n")

    def chot(self, ma: str, ten: str, dat: bool, chi_tiet: str = "",
             muc: str = CUNG, doi_tuong: str = "") -> KetQuaChot:
        kq = KetQuaChot(ma, ten, muc, bool(dat), chi_tiet, doi_tuong)
        self.ket_qua.append(kq)
        self._ghi_dong("\t".join([time.strftime("%H:%M:%S"), ma, ten, muc,
                                  "DAT" if dat else "KHONG DAT", doi_tuong, chi_tiet]))
        if not dat and muc == CUNG:
            raise ChotDung(f"[{ma}] {ten}: {chi_tiet}")
        return kq

    # -- khoá phiên bản đầu vào (MAPPING, BOM mẫu, script)
    def khoa(self, *paths: Path) -> None:
        for p in paths:
            dv = DauVet.cua(Path(p))
            self._khoa[str(p)] = dv
            self._ghi_dong(f"{time.strftime('%H:%M:%S')}\tKHOA\t{dv.dong()}")

    def kiem_khoa(self, ma: str = "KHOA") -> None:
        """Gọi ở đầu và cuối MỖI bước. Đầu vào đổi giữa chừng -> dừng."""
        doi = []
        for p, cu in self._khoa.items():
            if not Path(p).exists():
                doi.append(f"{p}: MẤT FILE")
                continue
            moi = DauVet.cua(Path(p))
            if moi.md5 != cu.md5:
                doi.append(f"{p}: md5 {cu.md5[:8]}→{moi.md5[:8]}")
        self.chot(ma, "Đầu vào đã khoá không đổi", not doi, "; ".join(doi))

    # -- tổng kết
    def tong_ket(self) -> tuple[list[KetQuaChot], list[KetQuaChot]]:
        dat = [k for k in self.ket_qua if k.dat]
        khong = [k for k in self.ket_qua if not k.dat]
        return dat, khong


# ------------------------------------------------------------- ghi không ghi đè

def ghi_khong_de(nguon_tam: Path, dich: Path) -> DauVet:
    """Chép file tạm sang đích. Đích đã có -> ChotDung. Chép xong so md5.

    Dùng O_EXCL nên kể cả 2 tiến trình cùng ghi một đích cũng chỉ một bên thắng.
    """
    nguon_tam, dich = Path(nguon_tam), Path(dich)
    dich.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(dich, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
    except FileExistsError:
        raise ChotDung(f"Chặn ghi đè: {dich} đã tồn tại")
    try:
        with os.fdopen(fd, "wb") as out, open(nguon_tam, "rb") as src:
            shutil.copyfileobj(src, out)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        dich.unlink(missing_ok=True)
        raise
    if md5_file(dich) != md5_file(nguon_tam):
        dich.unlink(missing_ok=True)
        raise ChotDung(f"Ghi lỗi: md5 {dich} khác bản tạm")
    shutil.copystat(nguon_tam, dich)
    return DauVet.cua(dich)


def ten_khong_trung(dich: Path) -> Path:
    """`X.xlsx` đã có -> `X (2).xlsx`, `X (3).xlsx`… (chỉ dùng khi người dùng duyệt)."""
    dich = Path(dich)
    if not dich.exists():
        return dich
    i = 2
    while True:
        p = dich.with_name(f"{dich.stem} ({i}){dich.suffix}")
        if not p.exists():
            return p
        i += 1


# ------------------------------------------------------------------- sao lưu

def sao_luu(thu_muc: Path, cho_xoa: Path, run_id: str) -> tuple[Path, int]:
    """Sao lưu nguyên thư mục vào `_CHO_XOA/<tên>_<run_id>`, kiểm số file + md5 từng file."""
    thu_muc, cho_xoa = Path(thu_muc), Path(cho_xoa)
    dich = cho_xoa / f"{thu_muc.name}_{run_id}"
    if dich.exists():
        raise ChotDung(f"Bản sao lưu đã tồn tại: {dich}")
    goc = {p.relative_to(thu_muc): md5_file(p) for p in thu_muc.rglob("*") if p.is_file()}
    shutil.copytree(thu_muc, dich)
    sao = {p.relative_to(dich): md5_file(p) for p in dich.rglob("*") if p.is_file()}
    if goc != sao:
        thieu = sorted(str(k) for k in goc.keys() - sao.keys())
        lech = sorted(str(k) for k in goc.keys() & sao.keys() if goc[k] != sao[k])
        raise ChotDung(f"Sao lưu không khớp: thiếu {thieu[:5]}, lệch md5 {lech[:5]}")
    with open(dich / "_MD5_SAO_LUU.tsv", "w", encoding="utf-8", newline="\n") as f:
        for k in sorted(goc, key=str):
            f.write(f"{k}\t{goc[k]}\n")
    return dich, len(goc)


# ------------------------------------------------------------- đọc ô trong xlsx

def _sheet_paths(z: zipfile.ZipFile) -> dict[str, str]:
    """Tên sheet -> đường dẫn XML trong zip."""
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
    rid_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    out = {}
    for s in wb.iter(f"{_NS}sheet"):
        t = rid_to_target[s.get(rid_attr)].lstrip("/")
        out[s.get("name")] = t if t.startswith("xl/") else f"xl/{t}"
    return out


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(t.text or "" for t in si.iter(f"{_NS}t")) for si in root.iter(f"{_NS}si")]


def doc_o(xlsx: Path, chi_sheet: Iterable[str] | None = None
          ) -> dict[tuple[str, str], tuple[str | None, str | None]]:
    """{(sheet, 'C18'): (công thức, giá trị)} — đọc thẳng XML, không qua openpyxl.

    Chữ trong sharedStrings được giải ra chữ thật. Ô theo sau của công thức dùng chung
    (Excel lưu `<f t="shared" si="n"/>` rỗng) trả về công thức `=SHARED#n`.
    """
    out = {}
    with zipfile.ZipFile(xlsx) as z:
        sst = _shared_strings(z)
        for name, part in _sheet_paths(z).items():
            if chi_sheet is not None and name not in chi_sheet:
                continue
            root = ET.fromstring(z.read(part))
            for c in root.iter(f"{_NS}c"):
                f = c.find(f"{_NS}f")
                v = c.find(f"{_NS}v")
                isv = c.find(f"{_NS}is")
                if isv is not None:
                    val = "".join(t.text or "" for t in isv.iter(f"{_NS}t"))
                elif v is not None and c.get("t") == "s" and v.text is not None:
                    val = sst[int(v.text)]
                else:
                    val = v.text if v is not None else None
                if f is None:
                    ct = None
                elif f.text:
                    ct = f.text
                else:
                    ct = f"=SHARED#{f.get('si')}"
                out[(name, c.get("r"))] = (ct, val)
    return out


def so_sanh_o(truoc: Path, sau: Path,
              duoc_doi: Callable[[str, str], bool]) -> list[str]:
    """Liệt kê ô bị đổi NGOÀI vùng được phép. Rỗng = đạt.

    `duoc_doi(sheet, ref)` trả True cho ô được phép đổi (vd chỉ cột C Mẫu 07 từ dòng 18).
    """
    a, b = doc_o(truoc), doc_o(sau)
    vi_pham = []
    for k in sorted(a.keys() | b.keys()):
        if a.get(k) != b.get(k) and not duoc_doi(*k):
            vi_pham.append(f"{k[0]}!{k[1]}: {a.get(k)} → {b.get(k)}")
    return vi_pham


def so_sanh_entry(truoc: Path, sau: Path, cho_phep: Iterable[str]) -> list[str]:
    """So byte từng entry trong zip; entry ngoài `cho_phep` mà đổi -> vi phạm.

    Bắt được Pivot/Table/externalLink bị viết lại (lỗi hay gặp khi load-rồi-save).
    """
    cho_phep = set(cho_phep)
    with zipfile.ZipFile(truoc) as za, zipfile.ZipFile(sau) as zb:
        na, nb = set(za.namelist()), set(zb.namelist())
        vp = [f"thiếu entry {n}" for n in sorted(na - nb)]
        vp += [f"thừa entry {n}" for n in sorted(nb - na)]
        vp += [f"đổi entry {n}" for n in sorted(na & nb)
               if n not in cho_phep and za.read(n) != zb.read(n)]
    return vp


# --------------------------------------------------------- công thức & link ngoài

def link_ngoai(xlsx: Path) -> dict[str, str]:
    """{'1': 'MAPPING HQ+NVL.xlsb', '2': '...'} theo thứ tự externalReference."""
    out = {}
    with zipfile.ZipFile(xlsx) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
        rid_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for i, e in enumerate(wb.iter(f"{_NS}externalReference"), start=1):
            part = rid_to_target[e.get(rid_attr)].lstrip("/")
            part = part if part.startswith("xl/") else f"xl/{part}"
            rel_path = part.replace("externalLinks/", "externalLinks/_rels/") + ".rels"
            try:
                r = ET.fromstring(z.read(rel_path))
                target = next(iter(r)).get("Target")
            except KeyError:
                target = part
            out[str(i)] = re.split(r"[\\/]", target)[-1]
    return out


def chuan_hoa_cong_thuc(f: str | None, links: dict[str, str]) -> str | None:
    """`[2]MAPPING (thư)!$A:$A` -> `[MAPPING HQ+NVL.xlsb]MAPPING (thư)!$A:$A`.

    So công thức giữa 2 file sau khi chuẩn hoá -> không báo lỗi giả vì [1]/[2] đảo chỗ.
    """
    if f is None:
        return None
    f = re.sub(r"\[(\d+)\]", lambda m: f"[{links.get(m.group(1), m.group(0))}]", f)
    return f.lstrip("=").replace("_xlfn.", "").replace(" ", "")
