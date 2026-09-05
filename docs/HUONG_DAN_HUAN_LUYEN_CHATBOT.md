# 🧠 HƯỚNG DẪN HUẤN LUYỆN CHATBOT & QUẢN TRỊ DỮ LIỆU EASYTRIP

Tài liệu này hướng dẫn toàn diện quy trình nạp dữ liệu kiến thức, cập nhật cơ sở dữ liệu RAG, đồng bộ CRM và huấn luyện lại Chatbot AI của **EasyTrip & Visa**.

---

## 🚀 1. Cách Sử Dụng Nhanh (1 Lệnh Duy Nhất)

Chúng tôi đã xây dựng công cụ tổng chỉ huy **`train_chatbot_master.py`** trong thư mục `scripts/training/`:

```bash
# Mở menu điều khiển huấn luyện trực quan:
./venv/bin/python scripts/training/train_chatbot_master.py
```

### Các Tùy Chọn Dòng Lệnh Nhanh:
- **Huấn luyện toàn diện & Re-index RAG**: `./venv/bin/python scripts/training/train_chatbot_master.py --train`
- **Thêm nhanh câu hỏi - câu trả lời mới**: `./venv/bin/python scripts/training/train_chatbot_master.py --add-qa`
- **Đồng bộ kiến thức với Lark CRM Base**: `./venv/bin/python scripts/training/train_chatbot_master.py --sync-crm`
- **Chạy kiểm thử đánh giá chất lượng AI**: `./venv/bin/python scripts/training/train_chatbot_master.py --eval`

---

## 📚 2. Cấu Trúc Toàn Bộ Kho Dữ Liệu Huấn Luyện

Toàn bộ dữ liệu của Chatbot được quy hoạch khoa học trong thư mục **`data/`**:

```text
data/
├── training_knowledge/           # 705+ cặp Hỏi - Đáp (Q&A) đã tinh lọc
│   ├── knowledge.txt             # Kiến thức cốt lõi, bảng giá, quy định
│   ├── extracted_qa_telegram.json# 561 Q&A thực tế từ Telegram
│   ├── extracted_qa_meta.json    # 95 Q&A từ Facebook Messenger & Instagram
│   ├── extracted_qa_zalo_docx.json# 25 Q&A chuyên sâu từ tư vấn viên Zalo
│   ├── extracted_qa_excel.json   # 14 Q&A nghiệp vụ nâng cao
│   └── manual_qa.json            # Các Q&A đặc biệt do Admin bổ sung thủ công
│
├── raw_chat_history/             # Dữ liệu chat thô gốc
│   ├── telegram_chat.json        # 4.485 tin nhắn Telegram
│   ├── meta_chat.json            # Hội thoại Facebook/Meta
│   └── zalo_chat.docx            # Tài liệu chat tư vấn viên Zalo
│
└── contracts_and_crm/            # Dữ liệu khách hàng & hợp đồng cũ
    ├── contract_snapshot.json    # Dữ liệu snapshot 323 khách hàng
    ├── danh_sach_hop_dong_*.xlsx # Danh sách hợp đồng thực tế
    └── danh_sach_khach_hang_*.xlsx# Danh sách cấp E-visa
```

---

## 🔄 3. Quy Trình Huấn Luyện & Cập Nhật Dữ Liệu Từng Bước

### Bước 1: Thu Thập & Thêm Kiến Thức Mới
Khi có chính sách giá mới, thay đổi giờ khởi hành xe, hoặc phát sinh tình huống khách hỏi mới:
- **Cách 1 (Nhanh nhất)**: Chạy `./venv/bin/python scripts/training/train_chatbot_master.py --add-qa` và nhập câu hỏi + câu trả lời. Hệ thống sẽ tự động ghi vào `manual_qa.json` và cập nhật RAG ngay.
- **Cách 2**: Chỉnh sửa trực tiếp file `data/training_knowledge/knowledge.txt` hoặc cập nhật trên bảng **Lark Base CRM**.

### Bước 2: Chạy Tái Lập Chỉ Mục (Re-indexing)
Sau khi cập nhật file kiến thức:
```bash
./venv/bin/python scripts/training/train_chatbot_master.py --train
```
Hệ thống sẽ:
1. Nạp **323 khách hàng** và **201 chuyến đi cũ** vào SQLite `easytrip_chat.db`.
2. Xây dựng lại Ma trận TF-IDF Search Engine của RAG từ 705+ cặp Q&A.

### Bước 3: Đồng Bộ 2 Chiều Với Lark Base CRM
- **Đẩy Q&A mới từ máy tính lên CRM**:
  ```bash
  ./venv/bin/python scripts/training/sync_knowledge_crm.py push
  ```
- **Tải Q&A mới nhất mà nhân viên CSKH đã nhập trên CRM về máy tính**:
  ```bash
  ./venv/bin/python scripts/training/sync_knowledge_crm.py pull
  ```

### Bước 4: Kiểm Thử Đánh Giá Chất Lượng AI (Evaluation)
Chạy bộ test để đảm bảo Bot phản hồi đúng 100% ngữ cảnh:
```bash
./venv/bin/python scripts/training/train_chatbot_master.py --eval
```
Bộ test tự động kiểm tra:
- ✅ Nhận diện khách cũ & điều chỉnh ngữ điệu (Nga, Hàn, Anh, Việt).
- ✅ Tự động nhắc nhở hết hạn Visa trước 10 ngày.
- ✅ Tính toán ngày xe chạy (Thứ 3, 5, CN) và tránh Overstay.
- ✅ Gợi ý sơ đồ ghế và điểm đón quen.

---

## 🎯 4. Danh Sách Script Trong Thư Mục Training

```text
scripts/training/
├── train_chatbot_master.py       # Menu tổng chỉ huy huấn luyện & quản lý dữ liệu
├── import_legacy_data.py         # Nạp toàn bộ dữ liệu cũ vào SQLite DB
├── sync_knowledge_crm.py         # Đồng bộ 2 chiều Máy tính <-> Lark Base CRM
├── populate_lark_kb.py           # Đẩy kho Q&A lên Lark Knowledge Base
├── populate_website_lark.py      # Đẩy thông tin website lên CRM
├── push_incidents_to_lark.py     # Nạp các ca sự cố / khiếu nại thực tế lên CRM
└── sop_creation_lark.py          # Tạo quy trình vận hành chuẩn SOP
```
