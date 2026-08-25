# 📑 HƯỚNG DẪN TẠO VÀ XỬ LÝ HỢP ĐỒNG EASY TRIP & VISA
> Tài liệu hướng dẫn chi tiết dành cho việc thiết lập, đồng bộ và chạy hệ thống tạo Hợp đồng dịch vụ tư vấn Visa tự động trên máy tính mới (Windows / macOS / Linux).

---

## 📌 1. Tổng quan hệ thống Hợp đồng
Hệ thống hỗ trợ tự động hóa toàn bộ quy trình làm hợp đồng:
* **Định dạng xuất**: Song ngữ Việt - Anh chuẩn 7 trang (cả file `.docx` Word và `.pdf` chuẩn in ấn).
* **Phân loại khách hàng**: Tự động phân tách **Khách Lẻ (Retail)** và **Đại Lý (Agency)**.
* **Tự động tính phí**:
  - **Visa Single (Lào/Việt Nam)**: Lệ phí Nhà nước $25 × 26.500 = **662.500 VNĐ**
  - **Visa Multi (Nhiều lần)**: Lệ phí Nhà nước $50 × 26.500 = **1.325.000 VNĐ**
  - **Visa Campuchia**: Lệ phí Nhà nước $30 × 26.500 = **795.000 VNĐ**
  - **Phí dịch vụ tư vấn**: `Tổng doanh thu - Lệ phí Nhà nước` (Tự động đọc số tiền thành chữ cả tiếng Việt và tiếng Anh).
* **Trích xuất chữ ký tự động**: Thuật toán Computer Vision (OpenCV + PIL) tự động tách nền, làm trong suốt và dán chữ ký từ ảnh Hộ chiếu vào trang 7 của hợp đồng.
* **Báo cáo đối soát**: Tự động xuất file Excel (`.xlsx`) tổng hợp danh sách khách hàng, số hộ chiếu, mã hồ sơ EV và số tiền.

---

## 💻 2. Hướng dẫn cài đặt trên máy tính mới

### Bước 1: Kéo code từ GitHub về máy
Mở Terminal (Mac/Linux) hoặc PowerShell/CMD (Windows):
```bash
git clone git@github.com:lyhoang280592-maker/chatbot-easytrip.git
cd chatbot-easytrip
```
*(Nếu đã có thư mục, chỉ cần gõ: `git pull origin main`)*

### Bước 2: Tạo môi trường ảo (Virtual Environment)
* **Trên macOS / Linux:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```
* **Trên Windows:**
  ```cmd
  python -m venv venv
  .\venv\Scripts\activate
  ```

### Bước 3: Cài đặt toàn bộ thư viện phụ thuộc
```bash
pip install -r requirements.txt
```

### Bước 4: Cấu hình file `.env`
Tạo file `.env` trong thư mục gốc `chatbot-easytrip/` với các biến cần thiết kết nối Lark Base:
```env
LARK_APP_ID=cli_xxxxxxxxxxxx
LARK_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
LARK_APP_TOKEN=bascnxxxxxxxxxxxxxxxxx
```

---

## 🚀 3. Hướng dẫn chạy các công cụ tạo Hợp đồng

### A. Tạo Hợp đồng hàng loạt theo Ngày Kế Toán (Khuyên dùng)
Kịch bản này quét toàn bộ khách hàng trên Lark Base theo **Accounting Date** (ví dụ 01/08 đến 24/08), tự động phân loại Khách Lẻ vs Đại Lý, tải ảnh hộ chiếu, tách chữ ký và xuất cả PDF + DOCX + Excel đối soát:
```bash
python batch_generate_by_accounting_date.py
```
* **Kết quả**:
  - Hợp đồng PDF lưu tại: `output_contracts_01_08_den_24_08/`
  - Bảng kê đối soát lưu tại: `danh_sach_hop_dong_01_08_den_24_08.xlsx`

---

### B. Tạo Hợp đồng định dạng Word (.docx) 7 trang
Chạy lệnh sau để tạo file Word `.docx` 7 trang song ngữ chuẩn cho danh sách khách hàng:
```bash
python generate_docx_contracts.py
```
* **Kết quả**: File `.docx` lưu tại thư mục `output_docx_contracts/`.

---

### C. Tạo Hợp đồng định dạng PDF (.pdf) chuẩn in ấn
Chạy lệnh sau để tạo hợp đồng PDF chuẩn ReportLab kèm chữ ký số:
```bash
python batch_process_contracts.py
```
* **Kết quả**: File `.pdf` lưu tại thư mục `output_contracts/` và bảng kê `danh_sach_doi_soat_khach_hang.xlsx`.

---

### D. Gom nhóm Hợp đồng và Hộ chiếu theo khách hàng
Sắp xếp file hợp đồng và ảnh hộ chiếu tương ứng theo từng thư mục hoặc tên chuẩn:
```bash
python organize_contracts_and_passports.py
```

---

## 📂 4. Sơ đồ các file mã nguồn liên quan

| Tên File | Vai trò / Chức năng |
| :--- | :--- |
| **`generate_contracts.py`** | Engine tạo PDF 7 trang (ReportLab), hàm đọc số tiền ra chữ Việt/Anh, thuật toán tách chữ ký. |
| **`generate_docx_contracts.py`** | Engine tạo file Word `.docx` 7 trang song ngữ, kẻ bảng biểu và định dạng font Arial chuẩn. |
| **`batch_generate_by_accounting_date.py`** | Quy trình tạo hợp đồng tự động theo mốc Accounting Date từ Lark Base. |
| **`batch_process_contracts.py`** | Quy trình lọc theo Event Date, xuất Excel đối soát và tạo PDF. |
| **`update_contracts_retail_vs_agency.py`** | Công cụ rà soát và cập nhật mẫu hợp đồng Đại lý vs Khách lẻ. |
| **`organize_contracts_and_passports.py`** | Công cụ tổ chức, sắp xếp file hợp đồng và ảnh hộ chiếu theo STT. |

---

## ❓ 5. Xử lý sự cố thường gặp (Troubleshooting)

1. **Lỗi `ModuleNotFoundError: No module named 'reportlab'` / `'docx'` / `'openpyxl'`**:
   - Hãy chắc chắn bạn đã kích hoạt môi trường ảo (`venv`) và chạy lệnh `pip install -r requirements.txt`.

2. **Lỗi `Không lấy được Lark Tenant Access Token`**:
   - Kiểm tra xem file `.env` đã có đúng `LARK_APP_ID` và `LARK_APP_SECRET` chưa.

3. **Chữ ký không hiển thị trong hợp đồng**:
   - Hệ thống sẽ kiểm tra xem khách hàng có trường `Ảnh hộ chiếu` trên Lark Base hay không. Nếu có, ảnh sẽ được tự động tải về thư mục `downloads/passports/` và trích xuất sang `extracted_signatures/`. Nếu khách chưa có ảnh hộ chiếu, hợp đồng vẫn tạo bình thường với ô chữ ký để trống.
