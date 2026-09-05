# 📚 HỆ THỐNG CHATBOT EASY TRIP & VISA (TÀI LIỆU CẤU TRÚC & VẬN HÀNH)

Chào mừng bạn đến với tài liệu kỹ thuật và cấu trúc thư mục của dự án **Chatbot Easy Trip & Visa Omnichannel**.

---

## 🗂️ SƠ ĐỒ CẤU TRÚC THƯ MỤC KHOA HỌC

```text
chatbot-easytrip/
├── 🚀 CORE SERVER APPLICATION (Mã nguồn chạy chính)
│   ├── main.py                     # Entry point FastAPI Webhook & API Server
│   ├── ai_agent.py                 # Bộ não AI xử lý hội thoại, trích xuất & RAG
│   ├── customer_memory.py          # Quản lý SQLite DB, bộ nhớ dài hạn & định danh
│   ├── visa_reminder.py            # Hệ thống tự động nhắc nhở hết hạn Visa trước 10 ngày
│   ├── memory_store.py             # Bộ nhớ đệm RAM kết hợp khôi phục DB
│   ├── knowledge_rag.py            # RAG TF-IDF Engine tìm kiếm Q&A thực tế
│   ├── telegram_router.py          # Router xử lý sự kiện Telegram Bot
│   ├── telegram_poller.py          # Long-polling dự phòng cho Telegram Bot
│   ├── lark_api.py                 # Tích hợp Lark Base CRM (Order & Q&A)
│   ├── google_sheet_sync.py        # Tích hợp Google Sheets đối soát
│   ├── seat_map_generator.py       # Tự động vẽ và tạo sơ đồ ghế xe
│   ├── i18n.py                     # Đa ngôn ngữ (Nga, Hàn, Trung, Việt, Anh, Pháp)
│   └── easytrip_chat.db            # Cơ sở dữ liệu SQLite sản xuất (WAL mode)
│
├── 📊 DATA (Dữ liệu huấn luyện, tri thức & hợp đồng)
│   ├── training_knowledge/         # Tri thức Q&A đã qua xử lý nạp vào RAG
│   │   ├── easytrip_qa_master.xlsx # File Excel Master Hỏi-Đáp chuẩn
│   │   ├── extracted_qa_excel.json # Q&A trích xuất từ Excel
│   │   ├── extracted_qa_telegram.json # Q&A trích xuất từ 150 chat Telegram
│   │   ├── extracted_qa_meta.json  # Q&A trích xuất từ Facebook Messenger
│   │   ├── extracted_qa_zalo_docx.json # Q&A trích xuất từ Zalo
│   │   ├── manual_qa.json          # Q&A quản trị viên dạy trực tiếp
│   │   └── knowledge.txt           # Kiến thức tĩnh bổ trợ
│   │
│   ├── raw_chat_history/           # Dữ liệu chat nguyên bản từ các kênh
│   │   ├── telegram_chat.json      # Toàn bộ lịch sử chat Telegram
│   │   ├── meta_chat.json          # Toàn bộ lịch sử chat Meta/Facebook
│   │   ├── zalo_chat.docx          # Lịch sử chat Zalo
│   │   └── zalo_images/            # Hình ảnh trích xuất từ Zalo
│   │
│   └── contracts_and_crm/          # Hồ sơ khách hàng & hợp đồng đã ký
│       ├── contract_snapshot.json  # 114 hợp đồng đã xử lý
│       ├── danh_sach_hop_dong_01_08_den_24_08.xlsx
│       ├── danh_sach_khach_hang_co_evisa_01_08_den_19_08.xlsx
│       ├── danh_sach_khach_hang_theo_accounting_date_01_08_den_19_08.xlsx
│       ├── output_contracts/       # Hợp đồng PDF đã tạo
│       ├── output_docx_contracts/  # Hợp đồng DOCX đã tạo
│       └── extracted_signatures/   # Chữ ký khách hàng đã tách nền
│
├── 🛠️ SCRIPTS (Công cụ huấn luyện, cào dữ liệu & hợp đồng)
│   ├── contracts/                  # Scripts tạo và xử lý hợp đồng khách hàng
│   │   ├── contract_generator_master.py # 🌟 Menu 1 chạm tạo hợp đồng (Lẻ & Hàng loạt)
│   │   ├── generate_docx_contracts.py   # Engine sinh file DOCX có dấu & chữ ký
│   │   ├── batch_process_contracts.py   # Tạo hàng loạt từ Excel
│   │   ├── convert_passports_to_bw.py   # Xử lý ảnh hộ chiếu trắng đen
│   │   └── update_contracts_retail_vs_agency.py
│   │
│   ├── training/                   # Scripts đồng bộ tri thức & CRM
│   │   ├── train_chatbot_master.py # 🌟 Menu 1 chạm huấn luyện & quản trị dữ liệu
│   │   ├── import_legacy_data.py   # Nạp dữ liệu cũ vào SQLite DB
│   │   ├── sync_knowledge_crm.py   # Đồng bộ 2 chiều với Lark CRM
│   │   ├── sync_excel_kb.py        # Đồng bộ Excel Master vào RAG
│   │   └── populate_lark_kb.py     # Nạp dữ liệu vào bảng KB Lark
│   │
│   └── scrapers/                   # Scripts trích xuất dữ liệu chat
│       ├── export_telegram_dialogs.py
│       ├── run_meta_export.py
│       └── telethon_scraper.py
│
├── 🧪 TESTS (Toàn bộ bài kiểm thử tự động)
│   ├── test_returning_customer.py  # Test nhận diện khách cũ & ngữ điệu
│   ├── test_visa_reminder.py       # Test tự động nhắc nhở visa 10 ngày
│   ├── test_compound_logic.py      # Test tính ngày xe & chọn ghế
│   ├── test_i18n.py                # Test đa ngôn ngữ
│   └── test_exact_call.py          # Test gọi mô hình AI
│
└── 📖 DOCS (Tài liệu kỹ thuật & Hướng dẫn sử dụng)
    ├── README_HE_THONG.md          # Sơ đồ kiến trúc & tổng quan
    ├── HUONG_DAN_TAO_HOP_DONG.md   # 📄 Hướng dẫn tạo hợp đồng khách hàng
    ├── HUONG_DAN_HUAN_LUYEN_CHATBOT.md # 🧠 Hướng dẫn huấn luyện & quản lý dữ liệu
    └── QUY_TRINH_TOI_UU_VA_HUAN_LUYEN_CHATBOT.md # Quy trình tối ưu chi tiết
```

---

## ⚡ HƯỚNG DẪN CÁC LỆNH VẬN HÀNH THƯỜNG DÙNG

### 1. Chạy Server Local / Development:
```bash
./venv/bin/python main.py
```

### 2. Chạy Kiểm Thử Toàn Bộ Tính Năng:
```bash
# Kiểm thử Bộ nhớ dài hạn & Nhận diện khách cũ:
./venv/bin/python tests/test_returning_customer.py

# Kiểm thử Tự động nhắc nhở hết hạn Visa trước 10 ngày:
./venv/bin/python tests/test_visa_reminder.py

# Kiểm thử Logic nghiệp vụ & Đa ngôn ngữ:
./venv/bin/python tests/test_compound_logic.py
./venv/bin/python tests/test_i18n.py
```

### 3. Đồng Bộ Lại Tri Thức Khi Chỉnh Sửa Excel Master:
```bash
./venv/bin/python scripts/training/sync_excel_kb.py
```

### 4. Nạp Dữ Liệu Lịch Sử Hợp Đồng Mới Vào Database:
```bash
./venv/bin/python scripts/training/import_legacy_data.py
```
