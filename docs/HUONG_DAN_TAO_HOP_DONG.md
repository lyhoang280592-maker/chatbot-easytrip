# 📄 HƯỚNG DẪN TẠO HỢP ĐỒNG KHÁCH HÀNG EASYTRIP

Tài liệu này hướng dẫn chi tiết quy trình tạo hợp đồng dịch vụ du lịch & visa run cho khách hàng của **EasyTrip & Visa**, bao gồm tạo hợp đồng đơn lẻ, tạo hàng loạt từ Excel CRM, xử lý con dấu/chữ ký và ảnh hộ chiếu scan.

---

## 🚀 1. Cách Sử Dụng Nhanh (1 Lệnh Duy Nhất)

Chúng tôi đã xây dựng công cụ tổng chỉ huy **`contract_generator_master.py`** trong thư mục `scripts/contracts/`:

```bash
# Mở menu điều khiển tạo hợp đồng trực quan:
./venv/bin/python scripts/contracts/contract_generator_master.py
```

### Các Tùy Chọn Dòng Lệnh Nhanh:
- **Tạo hợp đồng lẻ nhanh**: `./venv/bin/python scripts/contracts/contract_generator_master.py --single`
- **Tạo hợp đồng hàng loạt từ Excel**: `./venv/bin/python scripts/contracts/contract_generator_master.py --batch`
- **Xử lý ảnh hộ chiếu đen trắng**: `./venv/bin/python scripts/contracts/contract_generator_master.py --bw-passports`

---

## 📑 2. Các Kịch Bản Tạo Hợp Đồng

### 2.1. Tạo Hợp Đồng Đơn Lẻ Nhanh (Single Contract)
Dành cho trường hợp khách chốt tour qua Chatbot (Zalo, Telegram, Facebook) hoặc qua Hotline/văn phòng:

1. Chạy lệnh `./venv/bin/python scripts/contracts/contract_generator_master.py --single`
2. Nhập các thông tin cơ bản:
   - **Họ và tên khách**: `ALEXEY SMIRNOV`
   - **Quốc tịch**: `Russian`
   - **Số hộ chiếu**: `75N1234567`
   - **Tuyến dịch vụ**: Chọn `1` (Lào 45 ngày Miễn thị thực) hoặc `2` (Campuchia 90 ngày E-visa)
   - **Ngày khởi hành**: `17/09/2026`
   - **Giá tiền**: `3,300,000 VNĐ`
   - **Loại khách**: `Khách lẻ (Retail)` hoặc `Đại lý (Agency)`
3. File Word DOCX chuẩn mẫu pháp lý song ngữ Việt - Anh có chèn dấu đỏ và chữ ký tự động được tạo ra tại thư mục:
   👉 `output_contracts/HopDong_ET_20260904_ALEXEY_SMIRNOV.docx`

---

### 2.2. Tạo Hợp Đồng Hàng Loạt Từ Excel CRM (Batch Generation)
Dành cho kế toán / điều hành tour khi cần xuất toàn bộ hợp đồng theo ngày khởi hành hoặc theo đợt cấp e-visa:

- **Dữ liệu nguồn**: 
  - `data/contracts_and_crm/danh_sach_hop_dong_01_08_den_24_08.xlsx`
  - `data/contracts_and_crm/danh_sach_khach_hang_co_evisa_01_08_den_19_08.xlsx`
- **Thực thi**:
  ```bash
  ./venv/bin/python scripts/contracts/batch_process_contracts.py
  ```
- **Kết quả**: Tự động duyệt qua từng dòng dữ liệu khách hàng trong Excel, tạo từng file hợp đồng riêng biệt và lưu vào thư mục `output_contracts/`.

---

## 🖼️ 3. Quy Trình Xử Lý Ảnh Hộ Chiếu & Chữ Ký / Con Dấu

1. **Chuyển đổi Hộ Chiếu sang Trắng Đen (B&W Processing)**:
   - Script: `scripts/contracts/convert_passports_to_bw.py`
   - Công dụng: Tự động cân bằng sáng, tăng độ tương phản và chuyển ảnh hộ chiếu sang màu xám/trắng đen sắc nét để in ấn rõ ràng, không bị lem mực.
2. **Con dấu & Chữ ký**:
   - Chữ ký và con dấu của EasyTrip được tự động tách nền trong suốt (`transparent PNG`) và tự động chèn vào trang cuối của hợp đồng ở mục **Đại Diện Bên A (Công Ty EasyTrip)**.

---

## 📊 4. Cấu Trúc Thư Mục Phần Hợp Đồng

```text
scripts/contracts/
├── contract_generator_master.py         # Menu tổng quản lý tạo hợp đồng
├── generate_docx_contracts.py           # Engine sinh file Word DOCX song ngữ
├── generate_contracts.py                # Helper đọc số thành chữ (Việt - Anh) & xử lý dấu
├── batch_process_contracts.py           # Tạo hợp đồng hàng loạt từ Excel
├── convert_passports_to_bw.py           # Tool xử lý ảnh hộ chiếu sang B&W
└── update_contracts_retail_vs_agency.py # Phân loại hợp đồng Bán lẻ vs Đại lý
```
