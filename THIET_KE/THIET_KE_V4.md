# Thiết kế lại quy trình BOM v4: chốt chặn, bảo toàn dữ liệu, chạy theo đội

## 1. Bản v4 khác bản danh sách trước ở đâu

| Vấn đề của bản trước | Cách v4 xử lý |
|---|---|
| Chốt kiểm chỉ là cột ghi chú, phụ thuộc vào việc người chạy có nhớ dừng hay không | Mỗi chốt có **mã**, **mức** (CỨNG hoặc MỀM) và **cách đo**. Chốt CỨNG được viết thành `raise ChotDung` trong `chot_kiem.py`, nên script tự dừng mà không cần ai nhớ |
| "Không đạt thì dừng" xung đột với quy tắc CHỜ XỬ LÝ (lỗi lẻ thì chạy tiếp) | Tách hai mức: lỗi của **một đơn hoặc một mã** là MỀM, đưa vào chờ; lỗi **của cả lô hoặc của dữ liệu** là CỨNG, dừng phiên. Nếu > 20 % mục bị đưa vào chờ thì nâng lên CỨNG |
| Người làm tự chấm bước của mình | Có vai **Gác cổng** độc lập, chỉ đọc, đếm lại từ file (chốt K.6) |
| Ghi thẳng vào đích nên dễ ghi đè | Mọi kết quả ghi vào `_TMP\<run_id>` trước, Gác cổng chấm đạt rồi mới chuyển sang đích bằng `ghi_khong_de()`, có O_EXCL và kiểm md5 |
| MAPPING có thể đổi giữa chừng | Khoá md5 ở nhịp 1, kiểm lại ở đầu và cuối mỗi bước (K.1) |
| Script có thể bị phiên khác ghi đè (đã xảy ra) | Ghim md5 script trong `PHIEN_BAN_SCRIPT.tsv` (K.2) |
| 6.2 "không mất phần đã sửa" chỉ là lời dặn | `so_sanh_o()` so từng ô trước và sau: chỉ ô mã HQ được đổi, ô khác đổi thì dừng |
| 5.2 báo lỗi giả vì [1]/[2] đảo chỗ | `chuan_hoa_cong_thuc()` thay [n] bằng tên file thật trước khi so |
| Chạy như một agent, tuần tự hết | Có 7 vai. Việc đọc và chạy thử được làm song song; việc ghi do một người làm, tuần tự |

## 2. Sơ đồ một bước

```
 Trưởng nhóm ──phiếu giao việc──▶ Vai bước n ──dry-run──▶ phiếu kết quả
      │                                                         │
      │◀───────────────────────────────────────────────────────┘
      ├─ hỏi anh Thiên ── "chạy" ──▶ chạy thật vào _TMP\<run_id>
      │                                     │
      │                         Gác cổng chấm CHOT_KIEM bước n
      │                     ┌───────────────┼────────────────┐
      │                 CỨNG ✘           MỀM ✘             ✔
      │              DỪNG, giữ _TMP    vào CHỜ XỬ LÝ    ghi_khong_de → đích
      │              chờ lệnh          (mục đó)         BAN_GIAO_n.tsv
      └────────────────────────────── báo cáo ──────────▶ bước n+1
```

Song song (chỉ đọc): Thu thập 2025 ‖ Thu thập 2026 · chạy thử BOM theo lô khách hàng · Kiểm toán theo lô.
Tuần tự (có ghi): mọi bước bàn giao, bước 2b (Excel chạy phiên riêng), bước 6.

## 3. Bảo toàn dữ liệu: 6 lớp

1. **Nguồn chỉ đọc (K.3).** Chụp md5 các file nguồn đã đọc trước khi chạy, so lại sau khi chạy.
2. **Ghi vào chỗ tạm trước (nhịp 5).** Nếu hỏng giữa chừng thì đích không bị đụng tới.
3. **Không ghi đè (K.4).** `ghi_khong_de()` mở file bằng O_EXCL, nên kể cả khi hai tiến trình cùng ghi một đích cũng chỉ một bên ghi được. Ghi xong so md5.
4. **Sao lưu có kiểm tra (6.1).** `sao_luu()` chép vào `_CHO_XOA\<tên>_<run_id>`, đối chiếu từng md5, rồi ghi `_MD5_SAO_LUU.tsv`.
5. **Sửa có hàng rào (6.2, 4.2, 4.4).** So ô và so entry zip giữa bản trước và bản sau. Đổi ngoài vùng cho phép thì dừng. Cách này bắt được lỗi openpyxl load-rồi-save làm hỏng Pivot, Table, externalLink.
6. **Vùng ghi theo bước (K.5).** Bước nào chỉ được ghi vào thư mục của bước đó.

## 4. Bảo toàn nguyên tắc script đã chốt

- **Sổ quy tắc có mã** (R-NGAY, R-LOAI, R-SL, R-HQ, R-KKHQ, R-MX, nằm trong `CHOT_KIEM.md`). Script và skill dẫn mã quy tắc, không chép lại nội dung, để tránh mỗi nơi một phiên bản.
- **Ghim phiên bản script (K.2).** Khi sửa script phải đi đủ các bước: anh duyệt, thử trên 2–3 file mẫu và một bản cố tình làm hỏng (theo luật cũ), cập nhật md5 trong `PHIEN_BAN_SCRIPT.tsv`, ghi ngày.
- **Bộ ca thử hồi quy.** Mỗi lỗi đã gặp thành một ca thử cố định: lấy MAPPING cũ, ghi đè mất phần đã sửa, báo lỗi công thức giả, bỏ sót bước so tổng theo HQ. Trước mỗi lần đổi script phải chạy lại toàn bộ bộ ca thử. `tests/test_chot_kiem.py` hiện có 14 ca, chạy đạt trên cloud.

## 5. ✘ Mâu thuẫn giữa bảng anh gửi và skill hiện hành, cần anh chốt

Em **chưa** tự chọn bên nào. Mỗi mục dưới đây cần một quyết định.

1. **2.3 "Loại COVER".** Skill `xu-ly-bom` **giữ** COVER và chỉ chia hệ số divisor cho COVER, không loại COVER. Anh muốn loại COVER ở đâu: ở Sheet1, hay chỉ khi so với Custom?
2. **2.3 và 3.4 "Loại dòng KHÔNG KHAI HQ, còn lại phải bằng 0".** Bản hiện hành **giữ** dòng đó ở Sheet1, ẩn ở Pivot và trừ khỏi tổng (kiểm toán tiêu chí 3, mục 13). Nếu loại hẳn thì mục 13 và tiêu chí 3 phải sửa theo. → R-KKHQ
3. **2.2 "Đơn mới nhất theo mtime, rồi mã đơn".** Hiện đang có 3 quy tắc khác nhau:
   - `xu-ly-pi` dùng Amend Date → Date Issued → mã lớn nhất.
   - Mục 26 dùng ô M3 → mtime.
   - Bảng của anh dùng mtime → mã đơn.

   Đề xuất thống nhất **R-NGAY** = ngày trong ruột file → mtime → mã đơn lớn hơn. Lý do: mtime thay đổi khi chép file, nên không đáng tin bằng ngày trong ruột file.
4. **4.1 "Lập Pivot".** Theo luật hiện hành, Pivot phải là **Pivot thật do Excel tính** (bước 2b), không được tự cộng. V4 giữ luật này (chốt 4.1).
5. **0.4 Thư mục đích.** `xu-ly-pi` và `xu-ly-bom` dùng đường dẫn phẳng `NGUON CUSTOM MATERIAL\<mã>.xls`. Mục 26 và bảng của anh dùng `<năm>\<KH>\`. Nếu đổi sang dạng có thư mục con thì script 02 phải đọc theo đường dẫn mới, nghĩa là phải sửa script.
6. **Bước 0 bảng mới chỉ nhắc MATERIALCUST.** Luật cũ yêu cầu **đủ cặp** PDF PI và Custom. V4 giữ yêu cầu đủ cặp (chốt 0.2).
7. **Script 04 và thư mục CAP NHAT** chưa có trong `run_all.py` và chưa có trong skill nào. Em cần anh cho biết: tên script, đường dẫn CAP NHAT, và thư mục đích mà 04 sửa.
8. **Sổ `SO_CHOT_KIEM.tsv` và `BAN_GIAO_*.tsv`.** Luật hiện hành có câu "không tạo file báo cáo". Hai file này là nhật ký để Gác cổng kiểm lại, đặt trong `NHAT KY\<run_id>\`. Cần anh duyệt đây là ngoại lệ, giống như `chi_muc_custom_material.json` đã được duyệt ngày 09/10.

## 6. Ba lỗi ✘ còn mở từ bản trước, kèm đề xuất

| Lỗi | Đề xuất | Trạng thái |
|---|---|---|
| 0.3: file XDOC không có mã đơn | Đọc ruột file (M-Globar ID, nếu trống thì PI No.). Vẫn không có mã → CHỜ B0 với lý do "XDOC không có mã đơn trong ruột". Tên thư mục chỉ ghi kèm làm **gợi ý**, không dùng để gán. Đây là chốt MỀM | Chờ anh duyệt |
| 3.1: khoá MAPPING | Đã viết sẵn `Phien.khoa()` và `kiem_khoa()` | Code xong, có test. Chờ anh duyệt để gắn vào 02 và 03 |
| 4.3: chặn ghi đè | Đã viết sẵn `ghi_khong_de()` | Code xong, có test. Chờ anh duyệt để gắn vào 00, 01, 02, 04 |

## 7. Triển khai theo thứ tự, mỗi bước chờ anh duyệt

1. Anh chốt 8 mâu thuẫn ở mục 5.
2. Chép `SCRIPTS\chot_kiem.py` lên máy vào `BO_CONG_CU_TU_DONG_HOA_BOM\SCRIPTS\`. Đây là file **mới**, không sửa script nào. Kiểm SHA1 sau khi chép.
3. Viết `gac_cong.py` (chỉ đọc) để chấm `CHOT_KIEM.md` theo từng bước. Thử trên cloud trước.
4. Gắn chốt vào từng script, mỗi lần một script, theo thứ tự 02 → 04 → 00 → 01. Với mỗi script: thử trên 2–3 file mẫu và một bản cố tình làm hỏng, rồi ghim md5.
5. Thay skill `quy-trinh-bom-toan-trinh` bằng bản v4 (`SKILLS\quy-trinh-bom-toan-trinh\`). Skill `xu-ly-pi` và `xu-ly-bom` chỉ thêm một dòng: "chốt kiểm theo CHOT_KIEM.md của skill toàn trình".
