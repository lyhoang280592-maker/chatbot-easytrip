# 📘 QUY TRÌNH HOẠT ĐỘNG TOÀN DIỆN VẬN HÀNH AI CHATBOT EASY TRIP & VISA

> **Phiên bản**: 4.2 (Cập nhật Co-Pilot Studio Live Control, Đồng Bộ SQLite 8.900+ Tin Nhắn, Nút Tải Lại Real-time, Tự Động Bắn Vietcombank OneQR & Chuẩn Hóa Đối Tác Xe)  
> **Áp dụng cho**: Toàn bộ hệ thống AI Chatbot, Nhân viên Điều hành, CSKH & Quản trị viên Easy Trip & Visa.

---

## 📑 MỤC LỤC
1. [Kiến Trúc Đa Kênh Toàn Diện & Luồng Xử Lý (Omnichannel Flow)](#1-kiến-trúc-đa-kênh-toàn-diện--luồng-xử-lý-omnichannel-flow)
2. [Cơ Chế Báo Đơn Tức Thì & Giám Sát Admin Real-time (Telegram Alert & Delivery Status)](#2-cơ-chế-báo-đơn-tức-thì--giám-sát-admin-real-time-telegram-alert--delivery-status)
3. [Ba Chế Độ Vận Hành & Co-Pilot Studio Live Control (Auto, Co-Pilot, Manual)](#3-ba-chế-độ-vận-hành--co-pilot-studio-live-control-auto-copilot-manual)
4. [Quy Trình 5 Giai Đoạn Phục Vụ Khách Hàng Khép Kín](#4-quy-trình-5-giai-đoạn-phục-vụ-khách-hàng-khép-kín)
5. [Tự Động Hóa Thanh Toán Bằng Vietcombank OneQR Code](#5-tự-động-hóa-thanh-toán-bằng-vietcombank-oneqr-code)
6. [Phân Định Khách Hàng: Mới (New), Cũ (Returning), VIP & Đại Lý](#6-phân-định-khách-hàng-mới-new-cũ-returning-vip--đại-lý)
7. [Bảng Giá Bán Lẻ & Bảng Giá Ưu Đãi Khách Cũ (Chuẩn Telegram & Các Kênh)](#7-bảng-giá-bán-lẻ--bảng-giá-ưu-đãi-khách-cũ-chuẩn-telegram--các-kênh)
8. [Thuật Toán Lịch Xe Tránh Quá Hạn Visa & Điểm Đón Chuẩn (Anti-Overstay Scheduling)](#8-thuật-toán-lịch-xe-tránh-quá-hạn-visa--điểm-đón-chuẩn-anti-overstay-scheduling)
9. [Quy Trình Lấy Sơ Đồ Xe (Scheme), Tự Động Chuyển Tiếp & Chuẩn Hóa Đối Tác Xe](#9-quy-trình-lấy-sơ-đồ-xe-scheme-tự-động-chuyển-tiếp--chuẩn-hóa-đối-tác-xe)
10. [Hệ Thống Tự Động Quét & Nhắc Hết Hạn Visa Trước 10 Ngày](#10-hệ-thống-tự-động-quét--nhắc-hết-hạn-visa-trước-10-ngày)
11. [Tự Động Hóa Tạo Hợp Đồng Song Ngữ (7 Trang) & Kế Toán CRM](#11-tự-động-hóa-tạo-hợp-đồng-song-ngữ-7-trang--kế-toán-crm)
12. [Hướng Dẫn Triển Khai, Khởi Chạy & Bảo Mật Webhook](#12-hướng-dẫn-triển-khai-khởi-chạy--bảo-mật-webhook)

---

## 🏗️ 1. KIẾN TRÚC ĐA KÊNH TOÀN DIỆN & LUỒNG XỬ LÝ (OMNICHANNEL FLOW)

Hệ thống kết nối đa nền tảng qua Backend FastAPI tập trung, tích hợp bộ nhớ bền vững SQLite (WAL Mode với hơn 8.900+ tin nhắn và 936+ hồ sơ khách), RAG TF-IDF (1.800+ cặp Q&A chuẩn nghiệp vụ), cùng **Bộ Ba Lớp AI Fallback** (`DeepSeek-Chat` ➔ `Groq Mixtral / Llama 3` ➔ `Google Gemini`) đảm bảo bot vận hành liên tục 24/7 và không bao giờ im lặng.

```mermaid
flowchart TD
    subgraph INCOMING [Kênh Khách Hàng Đến 24/7]
        TG[Telegram: @Easy_Trip_Visa_bot / Business]
        FB[Facebook: Fanpage Tích Xanh & Phụ]
        IG[Instagram: Direct Messages]
        WA[WhatsApp: Business Cloud API]
        WEB[Website Chatbox: Đa Ngôn Ngữ]
        ZL[Zalo: Zalo OA OpenAPI v3 + OAuth 2.0]
    end

    subgraph BACKEND [FastAPI Core Gateway - main.py]
        INCOMING --> GW[Router Tiếp Nhận & Phân Luồng Webhook]
        GW --> RES[Tự Động Tra Cứu: Tên Khách + Năm Sinh + Nguồn + Loại Dịch Vụ]
        GW --> MEM[(SQLite WAL Database: 936+ Hồ Sơ & 8.900+ Tin Nhắn)]
        GW --> RAG[Bộ Não Tri Thức RAG TF-IDF: 1.800+ Cặp Q&A Chuẩn]
        GW --> CAL[Bộ Tính Lịch Chạy Xe Thông Minh: T3, T5, CN Tránh Overstay]
        GW --> LLM[3-Layer AI: DeepSeek-Chat -> Groq Mixtral -> Google Gemini]
    end

    subgraph OPERATION [Hệ Thống Vận Hành & Điều Phối]
        LLM --> OUT_CUST[Phản Hồi Trực Tiếp Cho Khách Đa Ngôn Ngữ]
        LLM --> NOTIF[Bắn Alert Telegram Báo Đơn Tức Thì Tới Admin]
        LLM --> QR_PAY[Tự Động Gửi Ảnh Vietcombank OneQR Code Lúc Thanh Toán]
        LLM --> SCHEME_ADMIN[Gửi Lệnh Scheme Đến Admin https://t.me/easytripvisa_co_ltd Lấy Sơ Đồ]
        SCHEME_ADMIN --> SEAT_FORWARD[Admin Gửi Sơ Đồ -> Bot Tự Động Forward Khách Đa Kênh]
        LLM --> BUS_GRP[Gửi Lệnh Lock Ghế / Chốt Đơn Chuẩn Hóa Vào Đúng Topic Bus]
        LLM --> COPILOT_HUB[Đồng Bộ Co-Pilot Studio Live Control 24/7]
        LLM --> CRM_SYNC[Đồng Bộ Lark Base / Google Sheets / Bảng Kê Kế Toán]
        LLM --> CONTR[Tự Động Sinh Hợp Đồng 7 Trang Song Ngữ + Ký Tên]
    end
```

---

## 🔔 2. CƠ CHẾ BÁO ĐƠN TỨC THÌ & GIÁM SÁT ADMIN REAL-TIME (TELEGRAM ALERT & DELIVERY STATUS)

Mỗi khi có khách hàng gửi tin nhắn từ bất kỳ kênh nào, hàm `notify_admin_incoming_message` lập tức gửi thông báo đẩy trực tiếp tới Telegram Admin (`ADMIN_TELEGRAM_ID`) hoặc Nhóm Quản Trị (`ADMIN_GROUP_CHAT_ID`).

### 2.1. Cấu Trúc Thông Báo Admin:
* **Tiêu đề cảm xúc, thân thiện**:
  - `🚀 Nổ đơn kìa sếp ơi!`
  - `💃 Khách iu ghé thăm!`
  - `🔥 Có khách cần chốt visa kìa sếp!`
  - `✨ Khách quen quay lại!`
* **Thông tin định danh khách (Tra cứu tức thì từ SQLite Database)**:
  - Tên hiển thị / Họ tên thật.
  - Năm sinh & Quốc tịch.
  - Kênh tiếp nhận / Nguồn (Telegram / Facebook / WhatsApp / Zalo / Web).
  - Loại dịch vụ khách đã/đang quan tâm (Visarun Lào 90D/45D, Mộc Bài...).
* **Nội dung cuộc hội thoại & Giám sát**:
  - 💬 **Khách nhắn**: Trích xuất chính xác câu hỏi/yêu cầu của khách.
  - 🤖 **Bot đã phản hồi**: Hiển thị câu trả lời mà Bot đã gửi cho khách (Auto Mode) hoặc câu trả lời nháp (Co-Pilot Mode).

### 2.2. Kiểm Tra Trạng Thái Gửi Tin Thực Tế (Real API Delivery Status):
* Khi Bot gửi tin nhắn qua Facebook Messenger, Zalo OA hoặc WhatsApp Cloud API, hệ thống tự động bắt phản hồi từ API thực tế.
* Báo cáo ngay về Telegram Admin nếu tin nhắn được gửi thành công (`✅ Đã chuyển tới người nhận`) hoặc thất bại (`⚠️ Lỗi gửi tin Zalo/FB: Token hết hạn/khách chặn`) để nhân viên kịp thời hỗ trợ thủ công.

---

## ⚙️ 3. BA CHẾ ĐỘ VẬN HÀNH & CO-PILOT STUDIO LIVE CONTROL (AUTO, COPILOT, MANUAL)

Hệ thống cho phép linh hoạt chuyển đổi giữa 3 chế độ ở cấp độ **Toàn hệ thống (Global)** hoặc cho **Từng phiên chat riêng lẻ (Per-session)**:

| Đặc Điểm | 🤖 TỰ ĐỘNG (AUTO MODE - Mặc Định) | 🟡 BÁN TỰ ĐỘNG (CO-PILOT / NHÁP) | 🔴 THỦ CÔNG (MANUAL / TIẾP QUẢN) |
| :--- | :--- | :--- | :--- |
| **Mục đích** | Phản hồi siêu tốc 24/7, không để khách chờ dù chỉ 1 giây. | Áp dụng khi đào tạo nhân viên, duyệt kịch bản giá đặc thù hoặc kiểm soát 100% nội dung. | Tạm dừng bot để nhân viên tư vấn chat tay trực tiếp khi có tình huống phức tạp. |
| **Hành vi Bot** | AI tự động phân tích và gửi ngay câu trả lời cho khách. | AI soạn bản nháp (Draft Reply) kèm độ tự tin (Confidence %). | Bot hoàn toàn im lặng, chỉ ghi nhận tin nhắn khách gửi vào hệ thống. |
| **Thao tác Admin** | Nhận thông báo giám sát qua Telegram; can thiệp khi cần. | Bấm **`✅ Duyệt & Gửi`** hoặc **`✍️ Sửa & Dạy`** trên Co-Pilot Studio. | Gõ tin nhắn và đính kèm ảnh/file gửi trực tiếp từ Co-Pilot đến điện thoại khách. |
| **Tự học (Active Learning)**| Ghi nhận lịch sử hội thoại để cải thiện RAG. | Khi Admin sửa câu trả lời, Bot lập tức nạp tri thức mới vào bộ nhớ tức thì. | Lưu nhật ký chat tay vào cơ sở dữ liệu để huấn luyện dữ liệu mẫu sau này. |

### 3.1. Tính Năng Mới Trên Co-Pilot Studio (`/copilot/index.html`):
1. **Mặc định Tab Live Channels Control**: Khởi động trang sẽ tự động đưa quản trị viên vào tab **🌐 Live Channels Control** để theo dõi khách thật, thay vì màn hình Sandbox giả lập.
2. **Ghi nhớ Tab Thông Minh**: Tự động lưu tab đang sử dụng vào `localStorage`, không bị mất trạng thái khi tải lại trang hoặc F5.
3. **Đồng bộ tự động từ Database SQLite (8.900+ tin nhắn)**: API `/api/sessions` kết hợp cả bộ nhớ RAM và Database SQLite, luôn đảm bảo hiển thị đầy đủ danh sách khách hàng mới nhất kể cả khi server vừa khởi động lại (restart).
4. **Nút `🔄 Tải lại` Danh Sách Phiên Chat**: Đặt ngay tại tiêu đề cột *Khách Hàng Đang Chat*, nhấp để ép quét lại toàn bộ dữ liệu mới nhất từ máy chủ.
5. **Nút `🔄 Làm mới` Khung Hội Thoại**: Đặt ngay tại header chi tiết chat, nhấp để cập nhật các tin nhắn mới nhất của khách hàng đang chọn mà không cần tải lại toàn bộ trang.

---

## 🔄 4. QUY TRÌNH 5 GIAI ĐOẠN PHỤC VỤ KHÁCH HÀNG KHÉP KÍN

```mermaid
sequenceDiagram
    autonumber
    actor C as Khách Hàng (Telegram / Đa Kênh)
    participant B as AI Chatbot Core
    participant DB as SQLite CRM (936+ Khách)
    participant AD as Admin (https://t.me/easytripvisa_co_ltd)
    participant BUS as Nhóm Telegram Điều Hành Xe

    C->>B: Nhắn tin: Hết hạn 15/09, muốn đi Lào 90D
    B->>DB: Tra cứu: Tên Khách + Năm Sinh + Nguồn + Dịch Vụ
    alt Tìm thấy trong CRM (Khách Cũ)
        DB-->>B: Trả về Profile: Khách Cũ (Tên, Năm sinh, Ghế quen)
        B->>C: Chào đúng tên + Báo giá Khách Cũ Telegram (3.000.000đ - Chỉ nhận tiền mặt)
    else Chưa có trong CRM (Khách Mới)
        DB-->>B: Trả về: Khách Mới
        B->>C: Chào lịch sự + Báo giá Khách Mới Telegram (3.400.000đ)
    end

    B->>B: Tính ngày xe: 15/09 -> Lùi về Tối Chủ Nhật 13/09 (Đón 21:30 tại map)
    B->>C: Thông báo ngày đi 13/09, giờ đón 21:30 tại link Google Maps

    opt Khách yêu cầu xem sơ đồ xe
        B->>AD: Phát lệnh Scheme: "Scheme 13/09 - 90D Laos"
        AD-->>B: Admin gửi ảnh sơ đồ xe thực tế
        B->>C: Tự động chuyển tiếp ảnh sơ đồ cho khách kèm nhãn: "[13/09 - 90D Laos]" (chống cache ảnh)
    end

    C->>B: Chọn số ghế (ví dụ: A1)
    B->>BUS: Gửi lệnh khóa ghế tạm: "Lock A1 Telegram" (vào Topic 13/09 - 90D)
    B->>C: Hướng dẫn nộp ảnh Hộ chiếu + Tự động gửi ảnh Vietcombank OneQR
    C->>B: Gửi ảnh Hộ chiếu + Xác nhận đã thanh toán (hoặc chọn nộp tiền mặt)
    B->>BUS: Báo chốt khách chuẩn format: [HỌ TÊN]/[NĂM SINH] A1 TELEGRAM [ĐIỂM ĐÓN] Đã tt
    B->>DB: Lưu hồ sơ, cập nhật chuyến đi vào SQLite và đồng bộ CRM
```

---

## 💳 5. TỰ ĐỘNG HÓA THANH TOÁN BẰNG VIETCOMBANK ONEQR CODE

Hệ thống tích hợp quy trình thanh toán tự động không chạm:
1. **Kích hoạt tự động**: Khi khách hàng hoàn tất bước chọn ghế hoặc xác nhận đặt dịch vụ, AI Agent chuyển sang giai đoạn `PAYMENT`.
2. **Bắn ảnh mã QR OneQR Vietcombank**: Chatbot tự động gửi ảnh **Vietcombank OneQR Code** (`static/qr_code.jpg`) tới khách hàng trên mọi kênh (Telegram, Facebook Messenger, Zalo, WhatsApp).
3. **Cú pháp thanh toán chuẩn**:
   ```text
   Ngân hàng: Vietcombank (VCB)
   Số tài khoản: 0071000688888 (hoặc STK công ty)
   Chủ tài khoản: EASY TRIP & VISA CO LTD
   Nội dung: [Họ Tên] [SĐT/Kênh] Visarun [Ngày đi]
   ```
4. **Quy định đối với Khách Cũ Telegram**:
   - Áp dụng chính sách đặc thù: **Chỉ nhận tiền mặt** khi đón xe đối với giá ưu đãi khách cũ Telegram (được AI thông báo rõ ràng trong báo giá).

---

## 👥 6. PHÂN ĐỊNH KHÁCH HÀNG: MỚI (NEW), CŨ (RETURNING), VIP & ĐẠI LÝ

```mermaid
graph TD
    A[Tiếp Nhận Khách Hàng] --> B{Tra Cứu SQLite CRM 936+ Khách}
    B -->|Tên + Năm Sinh + Nguồn + Dịch Vụ Chưa Có| C[👤 Khách Hàng Mới - NEW]
    B -->|Đã Từng Sử Dụng Dịch Vụ| D[🌟 Khách Hàng Cũ - RETURNING]
    B -->|Đã Đi >= 5 Chuyến| E[💎 Khách VIP]
    B -->|Thuộc Đối Tác| F[🤝 Đại Lý: Sergei / Bolot / Arcenii]

    C --> C1[Báo Giá Khách Mới: 45D = 1.400k | 90D = 3.400k]
    D --> D1[Báo Giá Khách Cũ: 45D = 1.150k | 90D = 3.000k - CHỈ NHẬN TIỀN MẶT]
    E --> E1[Ưu tiên giữ ghế đẹp nhất A1/A2 + Chăm sóc VIP]
    F --> F1[Áp dụng Bảng Giá Chiết Khấu Đại Lý]
```

---

## 💰 7. BẢNG GIÁ BÁN LẺ & BẢNG GIÁ ƯU ĐÃI KHÁCH CŨ (CHUẨN TELEGRAM & CÁC KÊNH)

### 7.1. Tuyến Visarun Nha Trang - Lào (Chuẩn Kênh Telegram)

| DỊCH VỤ VISARUN LÀO | 👤 KHÁCH MỚI (NEW) | 🌟 KHÁCH CŨ (RETURNING) | HÌNH THỨC THANH TOÁN |
| :--- | :---: | :---: | :---: |
| **Nha Trang - Lào 45 Ngày (Free Visa)** | **1.400.000 VNĐ** | **1.150.000 VNĐ** | **Khách cũ: Chỉ nhận tiền mặt** |
| **Nha Trang - Lào 90 Ngày (E-visa Single)** | **3.400.000 VNĐ** | **3.000.000 VNĐ** | **Khách cũ: Chỉ nhận tiền mặt** |
| **Nha Trang - Lào 90 Ngày (E-visa Multi)** | **4.400.000 VNĐ** | **4.000.000 VNĐ** | **Khách cũ: Chỉ nhận tiền mặt** |

---

### 7.2. Tuyến Campuchia (Cửa Khẩu Mộc Bài) & Đại Lý

| DỊCH VỤ | KHÁCH MỚI | KHÁCH CŨ | ĐẠI LÝ SERGEI | ĐẠI LÝ BOLOT | ĐẠI LÝ ARCENII |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Free Visa Mộc Bài (Cam 45D)** | **1.400.000đ** | **1.300.000đ** | 1.100.000đ | 1.150.000đ | 1.200.000đ |
| **Visarun 90D Cam (< 2 ngày)** | **4.000.000đ** | **3.550.000đ** | 2.520.000đ | 2.650.000đ | 2.800.000đ |
| **Visarun 90D Lào (Đại lý)** | - | - | **2.520.000đ** | **2.650.000đ** | **2.800.000đ** |

---

### 7.3. Dịch Vụ Làm E-Visa Lẻ (Single Entry)

| GÓI THỜI GIAN | GIÁ BÁN LẺ (Khách Mới) | GIÁ ƯU ĐÃI (Khách Cũ) | ĐẠI LÝ SERGEI | ĐẠI LÝ BOLOT | ĐẠI LÝ ARCENII |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Siêu khẩn 1 giờ** | **4.600.000đ** | **3.300.000đ** | 3.300.000đ | 3.300.000đ | 3.300.000đ |
| **Khẩn 2 giờ** | **3.400.000đ** | **2.900.000đ** | 2.700.000đ | 2.700.000đ | 2.900.000đ |
| **Khẩn 4 giờ (< 2 ngày)** | **2.600.000đ** | **1.600.000đ** | 1.420.000đ | 1.500.000đ | 1.600.000đ |
| **Khẩn 4 giờ (> 3 ngày)** | **2.600.000đ** | **1.600.000đ** | 1.350.000đ | 1.500.000đ | 1.600.000đ |
| **Gấp 8 giờ** | **2.900.000đ** | **1.900.000đ** | 1.650.000đ | 1.800.000đ | 1.900.000đ |
| **Gấp 1 ngày** | **2.200.000đ** | **1.500.000đ** | 1.350.000đ | 1.350.000đ | 1.500.000đ |
| **Gấp 2 ngày** | **2.150.000đ** | **1.450.000đ** | 1.300.000đ | 1.300.000đ | 1.450.000đ |
| **Tiêu chuẩn 3 - 5 ngày** | **1.810.000đ** | **1.110.000đ** | 1.050.000đ | 1.050.000đ | 1.110.000đ |
| **E-visa Multi-entry** | **+ 1.000.000đ** vào gói Single tương ứng |

---

## 📅 8. THUẬT TOÁN LỊCH XE TRÁNH QUÁ HẠN VISA & ĐIỂM ĐÓN CHUẨN (ANTI-OVERSTAY SCHEDULING)

### 8.1. Thuật Toán Lùi Lịch Tránh Overstay:
1. **Nguyên tắc an toàn tuyệt đối**: Xe xuất bến chậm nhất trước ngày hết hạn visa 1 ngày: $T_{depart} \le T_{expiry} - 1 \text{ ngày}$.
2. **Lịch chạy xe thực tế phân định theo tuyến**:
   - **Tuyến 45D Lào**: Chạy **HÀNG NGÀY** (mỗi tối).
   - **Tuyến 90D Lào**: Chạy cố định các tối **Thứ 3, Thứ 5, Chủ Nhật**.
   - **Tuyến Mộc Bài (45D Mộc Bài & 90D Mộc Bài)**: Chạy cố định các tối **Thứ 3, Thứ 5, Chủ Nhật**.
3. **Cơ chế tự động lùi ngày của Chatbot**:
   - Bot nhận diện ngày hết hạn visa ($T_{expiry}$) và tuyến khách đi (Lào hay Mộc Bài, 45D hay 90D).
   - Xác định ngày muộn nhất có thể đi là $T_{expiry} - 1$.
   - Nếu ngày đó trùng ngày có xe chạy của tuyến tương ứng, bot chọn ngay ngày đó.
   - Nếu ngày đó không có chuyến xe (ví dụ Thứ 2, Thứ 4, Thứ 6, Thứ 7 đối với tuyến 90D/Mộc Bài/Lào), bot sẽ tự động lùi dần về chuyến xe chạy gần nhất trước đó (tối Thứ 3, Thứ 5 hoặc Chủ Nhật).
4. **Ví dụ Khách hết hạn visa 15/09**:
   - **Đối với tuyến 90D Lào, 45D Mộc Bài hoặc 90D Mộc Bài**:
     + Ngày muộn nhất được phép đi: 14/09 (Thứ 2 - không có xe chạy).
     + Bot tự động lùi về chuyến xe gần nhất: **Tối Chủ Nhật ngày 13/09**.
   - **Đối với tuyến 45D Lào**:
     + Do xe chạy hàng ngày nên ngày đi an toàn muộn nhất là **Tối Thứ 2 ngày 14/09**.

### 8.2. Thời Gian Khởi Hành & Điểm Đón Chính Thức Tại Nha Trang:
* ⏰ **Thời gian đón khách**: **21:30**
* 📍 **Điểm đón Google Maps chính thức**: [https://maps.app.goo.gl/PAxvxTsxxjvqqBpG9](https://maps.app.goo.gl/PAxvxTsxxjvqqBpG9)

---

## 🚌 9. QUY TRÌNH LẤY SƠ ĐỒ XE (SCHEME), TỰ ĐỘNG CHUYỂN TIẾP & CHUẨN HÓA ĐỐI TÁC XE

### 9.1. Quy Trình Lấy & Chuyển Tiếp Sơ Đồ Xe Đa Kênh:
1. Khi khách hỏi sơ đồ xe hoặc muốn chọn vị trí ghế:
   * Bot tự động tạo câu lệnh `Scheme` gửi đến kênh Admin: [https://t.me/easytripvisa_co_ltd](https://t.me/easytripvisa_co_ltd)
   * *Ví dụ câu lệnh Bot gửi Admin*:
     ```text
     Scheme 13/09 - 90D Laos
     ```
2. **Admin gửi lại sơ đồ xe**:
   * Khi Admin gửi ảnh sơ đồ xe vào Telegram, Bot lập tức bắt ảnh và **tự động chuyển tiếp (forward)** đến khách hàng trên **Telegram, Facebook Messenger, Zalo OA hoặc WhatsApp**.
   * Ảnh được đính kèm timestamp để tránh bị trình duyệt/ứng dụng lưu cache ảnh cũ.
   * Tin nhắn đi kèm ảnh theo định dạng chuẩn:
     ```text
     [13/09 - 90D Laos]
     ```

### 9.2. Cấu Trúc Topic Trong Nhóm Điều Hành `EasyTrip booking BUS`:
* `# General`: Kênh điều phối chung.
* Topic `[Ngày/Tháng] - 45D`: Chuyến xe 45 ngày Lào *(Ví dụ: `11/10 - 45D`)*.
* Topic `[Ngày/Tháng] - 90D`: Chuyến xe 90 ngày Lào *(Ví dụ: `13/09 - 90D`, `10/09 - 90D`)*.
* Topic `[Ngày/Tháng] - mộc bài` *(hoặc `mbi`)*: Chuyến Campuchia.

### 9.3. Cú Pháp Khóa Ghế & Chuẩn Hóa Thông Báo Chốt Đơn:
* **Khóa ghế tạm thời (chờ thanh toán)**:
  ```text
  Lock A1 Telegram
  ```
* **Báo khách chính thức & Đã thanh toán (hoặc thu tiền mặt)**:
  ```text
  [HỌ TÊN]/[NĂM SINH] [SỐ GHẾ] [KÊNH] [ĐIỂM ĐÓN] [TÌNH TRẠNG TT]
  ```
  *Ví dụ chuẩn hóa cho đối tác vận tải:*
  ```text
  IVANOV SERGEI/1990 A1 TELEGRAM Điểm đón Maps Đã tt
  ```
  *(hoặc `Chưa tt` nếu thanh toán tiền mặt lúc lên xe)*.

---

## ⏰ 10. HỆ THỐNG TỰ ĐỘNG QUÉT & NHẮC HẾT HẠN VISA TRƯỚC 10 NGÀY

1. **Lịch trình tự động**: Cronjob nội bộ kích hoạt lúc **09:00 sáng hàng ngày** (`visa_reminder.py`).
2. **Tiêu chí lọc hồ sơ**:
   - Khách hàng có `visa_expiry_date` cách ngày hiện tại từ **9 đến 11 ngày**.
   - Trạng thái `reminder_status` chưa gửi hoặc đã qua hơn 7 ngày (Cơ chế chống spam nghiêm ngặt).
3. **Mẫu tin nhắn cá nhân hóa theo ngôn ngữ mẹ đẻ**:
   - 🇷🇺 **Tiếng Nga (`ru`)**: Chào thân mật theo tên, nhắc visa sắp hết hạn, chủ động đề xuất giữ lại ghế quen `A1` và áp dụng giá tri ân khách cũ **3.000.000 VNĐ (tiền mặt)**.
   - 🇰🇷 **Tiếng Hàn (`ko`)**: Sử dụng kính ngữ trang trọng, đề xuất giữ chỗ quen `B2`.
   - 🇬🇧 **Tiếng Anh (`en`)**: Lịch sự, chuyên nghiệp, thông báo lịch xe chạy gần nhất.
   - 🇻🇳 **Tiếng Việt (`vi`)** & 🇫🇷 **Tiếng Pháp (`fr`)**.
4. **Xử lý phản hồi**: Khi khách trả lời, Bot tự động nối tiếp ngữ cảnh để chốt chuyến nhanh chóng.

---

## 📑 11. TỰ ĐỘNG HÓA TẠO HỢP ĐỒNG SONG NGỮ (7 TRANG) & KẾ TOÁN CRM

1. **Quy chuẩn hợp đồng**: Hợp đồng dịch vụ tư vấn visa song ngữ Việt - Anh chuẩn 7 trang (`generate_contracts.py`).
2. **Bóc tách chữ ký tự động**: Tự động nhận diện vùng chữ ký trên ảnh Hộ chiếu, tách nền trong suốt và chèn vào đúng vị trí chữ ký của Khách Hàng (Bên B).
3. **Phân loại hạch toán Khách Lẻ vs Đại Lý**:
   - **Khách lẻ**: Chi phí = 0đ (không chi trả trung gian), Doanh thu = Giá thu khách.
   - **Đại lý**: Tự động trích xuất hoa hồng/chi phí trung gian theo biểu phí đại lý (Sergei, Bolot, Arcenii).
4. **Đối soát kế toán**: Xuất file Excel bảng kê 17 cột chuẩn mực, phục vụ công tác kế toán và kiểm toán thuế.

---

## 🚀 12. HƯỚNG DẪN TRIỂN KHAI, KHỞI CHẠY & BẢO MẬT WEBHOOK

### 12.1. Lệnh Khởi Chạy Hệ Thống

```bash
# 1. Kích hoạt môi trường ảo Python
source venv/bin/activate  # Trên Linux/macOS
# hoặc venv\Scripts\activate trên Windows

# 2. Khởi chạy Server FastAPI Gateway (Cổng 8000)
python main.py

# 3. Khởi chạy Telegram Bot Poller dự phòng
python telegram_poller.py
```

### 11.2. Cơ Chế Webhook Guardian Tự Động Phục Hồi
Backend tích hợp tiến trình nền `webhook_guardian()` chạy ngầm mỗi 60 giây. Nếu Webhook URL của Telegram bị sai lệch hoặc mất kết nối với Render Server (`RENDER_EXTERNAL_URL`), hệ thống sẽ tự động khôi phục Webhook ngay lập tức.

---

*Tài liệu quy trình vận hành chính thức thuộc bản quyền Easy Trip & Visa Co. Ltd. Mọi cập nhật được đồng bộ trực tiếp lên hệ thống GitHub và CSDL trung tâm.*
