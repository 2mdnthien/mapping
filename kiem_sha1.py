# -*- coding: utf-8 -*-
"""Đối chiếu SHA1 file ĐÃ CHÉP lên máy với SHA1SUMS.txt. Chỉ đọc.

  python -X utf8 -B kiem_sha1.py <thư mục bộ công cụ BCC> <thư mục AGENTIC\\.claude\\agents>
In ≤ 15 dòng. Mã thoát 0 = khớp hết, 2 = có file thiếu/lệch.
"""
import hashlib
import sys
from pathlib import Path

goc = Path(__file__).resolve().parent
bcc, agents = Path(sys.argv[1]), Path(sys.argv[2])
loi = []
n = 0
for dong in (goc / "SHA1SUMS.txt").read_text(encoding="utf-8").splitlines():
    sha, rel = dong.split("  ", 1)
    dich = agents / Path(rel).name if rel.startswith("AGENTS/") else bcc / Path(rel)
    n += 1
    if not dich.exists():
        loi.append(f"  ✘ THIẾU {dich}")
    elif hashlib.sha1(dich.read_bytes()).hexdigest() != sha:
        loi.append(f"  ✘ LỆCH  {dich}")
print(f"{'✔' if not loi else '✘'} SHA1: {n - len(loi)}/{n} file khớp")
print("\n".join(loi[:14]))
sys.exit(2 if loi else 0)
