# -*- coding: utf-8 -*-
"""Dựng file BOM ERP / BOM SNPL tối thiểu giống Excel lưu (sharedStrings, công thức có cache)."""
import zipfile
from pathlib import Path

NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
NSR = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'


def _xlsx(path: Path, sheets: dict[str, dict]) -> None:
    """sheets = {tên: {ref: giá trị | ('=công thức', cache)}}"""
    sst: list[str] = []

    def s_idx(t):
        if t not in sst:
            sst.append(t)
        return sst.index(t)

    parts = {}
    for i, (ten, o) in enumerate(sheets.items(), start=1):
        rows: dict[int, list[str]] = {}
        for ref, v in o.items():
            n = int("".join(ch for ch in ref if ch.isdigit()))
            if isinstance(v, tuple):
                f, c = v
                cv = f"<v>{c}</v>" if not isinstance(c, str) else f"<v>{s_idx(c)}</v>"
                t = ' t="s"' if isinstance(c, str) else ""
                cell = f'<c r="{ref}"{t}><f>{f.lstrip("=")}</f>{cv}</c>'
            elif isinstance(v, str):
                cell = f'<c r="{ref}" t="s"><v>{s_idx(v)}</v></c>'
            else:
                cell = f'<c r="{ref}"><v>{v}</v></c>'
            rows.setdefault(n, []).append(cell)
        data = "".join(f'<row r="{n}">{"".join(c)}</row>' for n, c in sorted(rows.items()))
        parts[f"xl/worksheets/sheet{i}.xml"] = f"<worksheet {NS}><sheetData>{data}</sheetData></worksheet>"
    wb = "".join(f'<sheet name="{t}" sheetId="{i}" r:id="rId{i}"/>' for i, t in enumerate(sheets, start=1))
    rels = "".join(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(sheets) + 1))
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f"<workbook {NS} {NSR}><sheets>{wb}</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels",
                   f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}</Relationships>')
        for k, v in parts.items():
            z.writestr(k, v)
        z.writestr("xl/sharedStrings.xml", f"<sst {NS}>" + "".join(f"<si><t>{t}</t></si>" for t in sst) + "</sst>")


def bom_erp(path: Path, qty: float = 2.0, hq: str = "HQ01", lech: bool = False) -> None:
    _xlsx(path, {"Sheet1": {
        "A1": "FG Code", "L1": "MA HQ",
        "A2": path.stem, "F2": "NL01", "I2": qty, "J2": ("=IF(H2=\"\",I2,I2*H2)", qty),
        "L2": ("=XLOOKUP(F2,[1]M!$A:$A,[1]M!$C:$C,\"KHÔNG CÓ MÃ\")", hq),
    }})


def bom_snpl(path: Path, qty: float = 2.0, hq: str = "HQ01", e: float | None = None, d14="Đơn vị tính sp: Cái ") -> None:
    ten = path.stem[:31]
    _xlsx(path, {
        ten: {"D14": d14, "A18": ("=ROW(A1)", 1), "B18": ("=XLOOKUP(C18,x,y)", "Vải"), "C18": hq,
              "D18": ("=XLOOKUP(C18,a,b)", "MET"), "E18": qty if e is None else e,
              "F18": ("=XLOOKUP(C18,a,c)", 0), "G18": ("=E18+E18*F18/100", qty), "H18": ("=G18*$E$15", qty)},
        "Sheet1": {"A1": "FG Code", "L1": "MA HQ", "A2": ten, "J2": ("=I2", qty), "L2": ("=XLOOKUP(F2)", hq)},
        "Sheet2": {"A3": "Row Labels", "B3": "Sum of Quantity", "A4": hq, "B4": qty, "A5": "Grand Total", "B5": qty},
    })
