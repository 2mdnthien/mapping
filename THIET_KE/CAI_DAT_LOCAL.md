# Cài và chạy trên máy (Windows)

Gốc trên máy: `C:\Users\accountsf\Downloads\AGENTIC\`. Bộ công cụ nằm ở `COWORK\BO_CONG_CU_TU_DONG_HOA_BOM\` (gọi tắt là **BCC**).

## 1. Chép file (đều là file MỚI, không sửa script nào đang có)

| Từ repo | Đặt vào máy |
|---|---|
| `SCRIPTS\chot_kiem.py`, `gac_cong.py`, `dieu_phoi.py` | `BCC\SCRIPTS\` |
| `dieu_phoi.cmd` | `BCC\` |
| `tests\*.py` (3 file) | `BCC\tests\` |
| `SKILLS\quy-trinh-bom-toan-trinh\SKILL.md`, `the\*.md`, `CHOT_KIEM.md` | Thay skill `quy-trinh-bom-toan-trinh` (bản cũ chuyển vào `_CHO_XOA`) |

Chép xong, kiểm SHA1 từng file phải khớp bảng dưới (theo luật cũ: đã có lần file bị ghi lại bản cũ):

```
Get-FileHash -Algorithm SHA1 <file>
```

| File | SHA1 |
|---|---|
| `SCRIPTS/chot_kiem.py` | `e0ee6822344366513b83bfabe63b5c22e1509752` |
| `SCRIPTS/gac_cong.py` | `8baeef8a854265ff81a8aeca1eddd86367890a29` |
| `SCRIPTS/dieu_phoi.py` | `6cc8f04b211eb6d5f6b27118142f16fd956507cd` |
| `dieu_phoi.cmd` | `59c295e3d9e374259c579f821c826fced862abf0` |
| `tests/test_chot_kiem.py` | `4ad76d03ff00e7d4740e222c6250a67daeda1030` |
| `tests/test_dieu_phoi.py` | `50fd8c25b4927f4fdc71ad25da28e567645ee839` |
| `tests/fixture_xlsx.py` | `92ab026fe4cabf4bd9d863ba7e573af5e04dfbf8` |

**Lưu ý:** bước 6 bên dưới ghim md5 của **mọi** file `.py` và `.ps1` trong `SCRIPTS`. Phải chép đủ cả 3 file mới **trước** khi ghim, nếu không thì `bat-dau` sẽ dừng ở chốt K.2.

## 2. Chạy kiểm thử trên máy, trước khi đụng vào dữ liệu thật

Kiểm thử chạy trong thư mục tạm, không đụng tới AGENTIC.

```
cd C:\Users\accountsf\Downloads\AGENTIC\COWORK\BO_CONG_CU_TU_DONG_HOA_BOM
& 'C:\Users\accountsf\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 -B tests\test_chot_kiem.py
& 'C:\Users\accountsf\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 -B tests\test_dieu_phoi.py
```

Phải ra `OK` cả hai. Trên Windows, chế độ chỉ đọc có hiệu lực thật, nên ca "ghi đè" sẽ dừng ở K.7 (hệ điều hành chặn ngay lúc ghi) thay vì K.4. Cả hai đều là DỪNG đúng.

## 3. Kiểm đường dẫn

```
.\dieu_phoi.cmd kiem-duong-dan
```

- Thấy dòng ✘ thì sửa hàm `duong_dan()` trong `dieu_phoi.py`. Mọi đường dẫn đều nằm ở hàm này. Sửa xong chạy lại kiểm thử ở mục 2.
- Dòng "đường dẫn điểm khôi phục dài nhất" phải ≤ 250 ký tự. Nếu vượt, cần rút tên thư mục `_CHO_XOA`. **Không** bật LongPaths, vì việc đó phải sửa registry.

## 4. Chạy thử lần đầu: 1 đơn, hỏi từng bước

```
.\dieu_phoi.cmd bat-dau --ds "<file danh sách 1 đơn>"
.\dieu_phoi.cmd tiep --den-het          (dừng ở ⏸, xem số liệu chạy thử)
.\dieu_phoi.cmd duyet
.\dieu_phoi.cmd tiep --den-het
```

Lặp lại đến khi thấy HOÀN TẤT. Sau đó mở Excel kiểm 1 file BOM SNPL bằng mắt.

## 5. Chạy thường ngày

- **Anh nói với agent:** "chạy toàn trình đơn …, duyệt cả chuỗi". Agent sẽ gọi `bat-dau --ds … --tu-dong` rồi `tiep --den-het`.
- **Agent chỉ gọi anh khi:** DỪNG, hoặc tới B6.
- **Khi DỪNG:** `chi-tiet <bước>` → anh quyết → `khoi-phuc` → `tiep`. Chỉ chạy lại riêng bước lỗi.

## 6. Ghim phiên bản script (chốt K.2, nên làm sau lần chạy đầu đạt)

Tạo file `BCC\HUONG_DAN\PHIEN_BAN_SCRIPT.tsv`, mỗi dòng có dạng `tên_script<TAB>md5`, gồm **mọi** file `.py` và `.ps1` trong `BCC\SCRIPTS`. Từ đó, script nào bị đổi ngoài ý muốn thì `bat-dau` dừng. Muốn sửa script thì phải anh duyệt, cập nhật md5 trong file này, và ghi ngày.

```
Get-ChildItem SCRIPTS\*.py, SCRIPTS\*.ps1 | ForEach-Object { "{0}`t{1}" -f $_.Name, (Get-FileHash -Algorithm MD5 $_).Hash.ToLower() } | Set-Content -Encoding utf8 HUONG_DAN\PHIEN_BAN_SCRIPT.tsv
```

Lệnh này có biến `$`, nên **anh tự gõ trong PowerShell**, không gửi qua Desktop Commander.
