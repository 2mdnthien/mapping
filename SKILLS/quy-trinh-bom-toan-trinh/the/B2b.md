# Thẻ B2b: Pivot do Excel tính, điền cột E (`02b_pivot_excel.py`). Chỉ đọc.

**Bước này làm gì:** mở Excel ở phiên riêng (UpdateLinks=0, tắt macro, tính thủ công), làm mới Pivot, điền E = giá trị Pivot (bỏ dòng MX), rồi chỉ tính lại G và H.

**Ô được phép đổi ở file đã có:** Mẫu 07 cột E, G, H từ dòng 18, và Sheet2. Đổi bất kỳ ô nào khác là vi phạm chốt 4.2.

**Lý do DỪNG thường gặp:**
- 4.2: cột B, D hoặc F bị đổi. Nguyên nhân thường là Excel cập nhật link `O:\`, hoặc file bị load-rồi-save bằng openpyxl.
- 4.1 / K.8: Sheet1 ≠ Pivot ≠ Mẫu 07. Nguyên nhân thường là Pivot chưa refresh, hoặc dòng KHÔNG KHAI HQ chưa được trừ.
- K.7: Excel đang bận hoặc treo. **Không được đóng Excel anh Thiên đang mở.**

**Trả về (tối đa 8 dòng):** nguyên nhân – bằng chứng – đề xuất.
