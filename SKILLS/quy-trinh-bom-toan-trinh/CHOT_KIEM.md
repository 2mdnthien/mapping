# Danh mục chốt kiểm v4

**Mức CỨNG**: không đạt thì dừng cả phiên, báo trong chat và chờ anh Thiên ra lệnh.
**Mức MỀM**: không đạt thì đơn hoặc mã đó vào CHỜ XỬ LÝ của đúng bước, các đơn khác chạy tiếp. Nếu tổng số mục MỀM bị đưa vào chờ trong một bước **> 20 %** thì nâng lên CỨNG, vì khi đó lỗi có hệ thống chứ không còn lẻ.

Cột **Ai chấm** là vai **khác** với vai làm bước đó. Người làm bước không tự chấm bước của mình.

## Chốt chung, áp dụng ở mọi bước

| Mã | Chốt | Mức | Cách đo | Ai chấm |
|---|---|---|---|---|
| K.1 | Đầu vào đã khoá không đổi (MAPPING, NK 2025, BOM mẫu, các script) | CỨNG | `Phien.kiem_khoa()` ở đầu và cuối bước, so md5 | Gác cổng |
| K.2 | Script đúng phiên bản đã duyệt | CỨNG | md5 script = md5 trong `HUONG_DAN\PHIEN_BAN_SCRIPT.tsv` | Gác cổng |
| K.3 | Nguồn chỉ đọc không bị chạm | CỨNG | Chụp md5 các file nguồn đã đọc trước khi chạy, so lại sau khi chạy | Gác cổng |
| K.4 | Không ghi đè | CỨNG | Mọi lệnh ghi đều qua `ghi_khong_de()`; đích đã tồn tại thì chặn | tự động |
| K.5 | Không ghi ra ngoài vùng cho phép | CỨNG | Liệt kê file mới hoặc đổi trong AGENTIC sau khi chạy; chỉ được nằm trong vùng ghi của bước | Gác cổng |
| K.6 | Số liệu tự đếm lại khớp số liệu người làm báo | CỨNG | Gác cổng đếm lại từ file, không dùng số do người làm báo | Gác cổng |

## Bước 0: Lọc nguồn (vai: Thu thập)

| Mã | Chốt | Mức | Cách đo |
|---|---|---|---|
| 0.1 | Quét Orders 2025 và 2026, bỏ thư mục CANCEL | CỨNG nếu quét được 0 đơn hoặc không truy cập được thư mục | Số thư mục quét, số thư mục CANCEL bị bỏ, liệt kê mục rời và file phụ |
| 0.2 | Đơn đủ cặp PDF PI và Custom | MỀM | Liệt kê đơn thiếu PDF, đơn thiếu Custom (chỉ có MATERIALREVIEW) |
| 0.3 | Mã đơn lấy trong ruột file (M-Globar, nếu trống thì PI No.) | MỀM | File XDOC hoặc file bất kỳ không đọc được mã → CHỜ B0, lý do "không có mã đơn trong ruột", **không tự gán** theo tên thư mục hay tên file |
| 0.4 | Chép vào NGUON | CỨNG | Số file nguồn được chọn = số file đích mới; không có 2 nguồn trỏ về cùng một đích; md5 đích = md5 nguồn |
| 0.5 | Một mã đơn, một file | MỀM | Nhiều bản thì lấy bản mới nhất theo quy tắc R-NGAY; các bản bị bỏ phải liệt kê |

## Bước 1: Master PI (vai: Bóc PI)

| Mã | Chốt | Mức | Cách đo |
|---|---|---|---|
| 1.1 | Mỗi đơn đủ cặp ở B0 đều có PI bóc được | MỀM | Liệt kê đơn thiếu PI, PI dạng ảnh, sai biểu mẫu |
| 1.2 | Master PI đủ 7 cột | CỨNG | Tiêu đề 7 cột đúng từng chữ |
| 1.3 | Master PI khớp PDF | CỨNG | Số dòng và tổng Usage trên Master PI = tổng từng `PI ĐÃ XỬ LÝ\<mã>.xlsx` (trừ đơn chờ) |
| 1.4 | Loại vỏ theo mã HQ | MỀM | Da phối Vải, PU/PC đứng riêng, trùng tên khác usage → chờ |

## Bước 2: BOM ERP (vai: BOM)

| Mã | Chốt | Mức | Cách đo |
|---|---|---|---|
| 2.1 | Đọc Custom (sheet Material Review by Seater, tiêu đề dòng 8) | CỨNG khi số lỗi đọc > 0 | Số file đọc lỗi phải = 0; liệt kê từng file lỗi |
| 2.2 | Mỗi FG lấy đúng một đơn theo R-NGAY | CỨNG | In bảng FG → mã đơn → ngày → nguồn ngày (ô trong ruột hay mtime) |
| 2.3 | Loại vật tư theo R-LOAI | MỀM | In từng dòng bị loại: FG, Material Code, lý do |
| 2.4 | J = `IF(H="",I,I*H)` là công thức | CỨNG | 100 % ô J là công thức đúng mẫu |
| 2.5 | Chipboard là số nguyên, làm tròn lên | MỀM | So với Custom theo từng mã |
| 2.6 | Sheet1 đúng và đủ NVL so với Custom | MỀM | Dùng cùng hàm với mục 26: thiếu/thừa theo Material Code |

## Bước 3: Mapping mã HQ (vai: BOM)

| Mã | Chốt | Mức | Cách đo |
|---|---|---|---|
| 3.1 | Khoá MAPPING: ghi giờ sửa và md5 **trước** bước 2 | CỨNG | `Phien.khoa(MAPPING)`; nếu đổi giữa chừng thì K.1 dừng |
| 3.2 | L = XLOOKUP **chỉ theo Material Code** (MAPPING A→C) | CỨNG | 100 % ô L là công thức đúng R-HQ, không tra Description |
| 3.3 | FG có "KHÔNG CÓ MÃ" | MỀM | FG đó vào CHỜ B2-3; liệt kê mã NL thiếu mapping (gộp theo NL, có danh sách FG bị ảnh hưởng) |
| 3.4 | Dòng KHÔNG KHAI HQ xử lý theo R-KKHQ | CỨNG | Xem quyết định số 2 trong THIET_KE_V4 |

## Bước 4: Pivot và Mẫu 07 (vai: Mẫu 07)

| Mã | Chốt | Mức | Cách đo |
|---|---|---|---|
| 4.1 | Sheet2 là Pivot thật do Excel tính (2b) | CỨNG | Có pivotTable; tổng Pivot = tổng Sheet1 (trừ R-KKHQ) |
| 4.2 | Mẫu 07: A, B, D, F, G, H là công thức đúng mẫu; E = Pivot | CỨNG | `so_sanh_o()` trước/sau 2b: chỉ cột E, G, H được đổi giá trị; B, D, F giữ nguyên |
| 4.3 | Không ghi đè | CỨNG | Ghi vào `_TMP\<run_id>`, sau đó `ghi_khong_de()` sang đích; số file ghi = số FG đạt |
| 4.4 | Pivot, Table, externalLink không bị viết lại ngoài ý muốn | CỨNG | `so_sanh_entry()` chỉ cho phép đổi các entry đã khai báo |

## Bước 5: Kiểm toán (vai: Kiểm toán, độc lập, chỉ đọc)

| Mã | Chốt | Mức | Cách đo |
|---|---|---|---|
| 5.1 | Sheet1 = Pivot = Mẫu 07 theo từng mã HQ | MỀM | Mục 13 |
| 5.2 | Công thức giống template sau khi chuẩn hoá link ngoài | MỀM | `chuan_hoa_cong_thuc()`: so theo **tên file**, không theo số [1]/[2] |
| 5.3 | Đối chiếu Custom: (a) khớp NVL với đơn mới nhất; (b) khớp tổng theo HQ; (c) lùi về đơn cũ hơn | MỀM | Bắt buộc chạy đủ (a) → (b) → (c) theo thứ tự. Chỉ kết luận ĐÚNG hoặc SAI |
| 5.4 | Mỗi file SAI được xếp vào **SAI THẬT** hoặc **ĐỔI DO CUSTOM CẬP NHẬT** | CỨNG | Không file nào chưa được xếp nhóm; nhóm ĐỔI phải có đơn và ngày bắt đầu có NL mới |

## Bước 6: Cập nhật bằng script 04 (vai: Cập nhật)

| Mã | Chốt | Mức | Cách đo |
|---|---|---|---|
| 6.1 | Sao lưu thư mục đích vào `_CHO_XOA` | CỨNG | `sao_luu()`: đủ số file và md5 từng file khớp |
| 6.2 | Chỉ sửa mã HQ, nguồn là CAP NHAT, không lấy từ SRC | CỨNG | `so_sanh_o()`: chỉ các ô mã HQ được đổi (Sheet1 cột L nếu là giá trị, Mẫu 07 cột C từ dòng 18); mọi ô khác giữ nguyên |
| 6.3 | Không làm mất phần đã sửa trước đó | CỨNG | Bản đầu vào của 04 là bản **đang nằm ở đích** (đã gồm các lần sửa trước), không phải bản SRC; md5 đầu vào = md5 bản sao lưu ở 6.1 |
| 6.4 | Chạy lại toàn bộ Bước 5 trên các file vừa sửa | CỨNG | Không file nào chuyển từ ĐÚNG sang SAI |

## Quy tắc được dẫn chiếu (không viết lại trong script, chỉ dẫn mã quy tắc)

| Mã | Nội dung | Chốt ngày |
|---|---|---|
| R-NGAY | Ngày đơn: ngày trong ruột (Amend Date → Date Issued; Custom: ô M3), không có thì lấy mtime, bằng nhau thì lấy mã đơn lớn hơn | **chờ anh chốt** |
| R-LOAI | Loại Rattan, P04-003, carton 5 lớp, M01-043A, Qty = 0; Polyform khác chỉ cảnh báo | đã chốt |
| R-SL | Leather Scrap 0.0278; chỉ may = số mét; Pair = 2; chipboard làm tròn lên; divisor chỉ áp cho COVER; Y CABLE âm → dương | đã chốt |
| R-HQ | Mã HQ chỉ tra theo Material Code, MAPPING A→C; không có thì "KHÔNG CÓ MÃ"; không đoán | 05/10/2026 |
| R-KKHQ | Dòng "KHÔNG KHAI HQ": giữ ở Sheet1 và trừ khỏi tổng, hay loại hẳn | **chờ anh chốt** |
| R-MX | MX = 1 hoặc 2 (bộ 2 kiện) ở Mẫu 07 | đã chốt |
