# Easy Trip & Visa - Co-Pilot Chat Studio 🚀

Chào mừng bạn đến với **Co-Pilot Chat Studio**! Đây là một giao diện lập trình đặc biệt được thiết kế đồng bộ với phong cách thiết kế và nghiệp vụ thực tế của Chatbot **Easy Trip & Visa** mà bạn đang thực hiện. 

Ứng dụng này giúp bạn mô phỏng thực tế cách **Con người tham gia giám sát (Human-in-the-Loop)**, chỉnh sửa câu trả lời nháp của Bot và dạy Bot học hỏi trực tiếp trong thời gian thực.

---

## ✨ Các Tính Năng Nổi Bật

1. **Giao diện Split-Screen (Chia đôi màn hình):**
   * **Cột Trái (Khách Hàng):** Mô phỏng ứng dụng di động của khách hàng. Bạn có thể tự đóng vai khách hàng để gõ câu hỏi hoặc bấm vào các câu hỏi gợi ý nhanh liên quan đến Visarun đi Lào, Campuchia, làm E-visa Việt Nam hoặc thuê xe máy.
   * **Cột Phải (Bàn Làm Việc của Bạn):** Màn hình giám sát live-chat, trạm nháp Co-Pilot của Bot và bộ não chứa các bài học.

2. **Quy Trình Duyệt Tin Nhắn Co-Pilot:**
   * Khi khách hỏi, Bot phân tích từ khóa và soạn trước câu trả lời kèm mức độ tự tin (Confidence %).
   * **Duyệt & Gửi (Approve):** Gửi câu trả lời gốc của Bot nếu đã chuẩn xác.
   * **Sửa & Dạy Bot (Edit & Teach):** Chỉnh sửa câu trả lời của Bot trực tiếp trong ô nhập liệu và gửi đi. **Bot sẽ lập tức học câu trả lời mới này!**
   * **Trực Tiếp Chat (Agent Takeover):** Nhập câu trả lời hoàn toàn mới từ con người để tư vấn cho khách. Bot cũng sẽ ghi nhớ bài học này.

3. **Bộ Não Học Tập Tự Động (AI Learning Hub):**
   * Hiển thị danh sách tri thức của Bot bao gồm **Tri thức gốc** và **Tri thức được bạn dạy**.
   * Khi học được bài học mới từ bạn, thẻ tri thức đó sẽ xuất hiện trên đầu kèm theo **hiệu ứng nhấp nháy phát sáng neuron (glowing pulse)** vô cùng đẹp mắt!
   * Lưu trữ trực tiếp trong trình duyệt (`localStorage`), giúp Bot không bị mất trí nhớ ngay cả khi bạn tải lại trang (Reload)!

---

## 🛠️ Hướng Dẫn Cách Chạy Thử và Dạy Bot Học

Bạn có thể chạy thử trực tiếp bằng cách mở file `index.html` trên trình duyệt:

### Kịch bản thử nghiệm khả năng tự học của Bot:

1. **Thử nghiệm Tri thức Gốc:**
   * Tại cột Khách hàng, nhấn nút gợi ý nhanh: **"Đi Visa Run Lào (Người Nga)"**.
   * Bên bàn làm việc Admin, bạn sẽ thấy tin nhắn hiện lên, Bot tự động soạn thảo bản nháp gợi ý với **Độ tự tin rất cao (khoảng 98%)** vì đã khớp với Tri thức gốc.
   * Nhấn nút **Duyệt & Gửi** để phản hồi lại khách hàng.

2. **Dạy Bot học bài mới (Chưa có trong tri thức gốc):**
   * Ở cột Khách hàng, gõ câu hỏi chưa được cấu hình sẵn, ví dụ: *"Có cần mang hộ chiếu gốc không bạn?"*
   * Bên Admin, Bot phân tích thấy độ tự tin thấp vì đây là câu hỏi mới.
   * Bạn chọn nút **Sửa & Dạy Bot** (hoặc gõ vào ô nháp): *"Dạ bắt buộc phải mang hộ chiếu gốc còn hạn trên 6 tháng và không bị rách hỏng bạn nhé! 📘"* rồi nhấn gửi.
   * Quan sát bên **Bộ Não Tri Thức (AI Learning Hub)**: Một thẻ bài học mới vừa được nạp vào bộ não với hiệu ứng viền phát sáng màu xanh cyan rực rỡ!

3. **Kiểm tra khả năng ghi nhớ:**
   * Quay lại cột Khách hàng, gõ lại câu hỏi tương tự: *"Cho hỏi đi visarun cần mang hộ chiếu gốc không?"*
   * Hãy quan sát! Trạm nháp Co-Pilot lập tức gợi ý câu trả lời bạn vừa dạy với **Độ tự tin 100% (Màu Xanh Lá)**!
   * Nhấn **Duyệt & Gửi**! Bot đã hoàn toàn làm chủ tri thức mà bạn vừa truyền dạy chỉ sau duy nhất 1 lần!

---

## 🎨 Ngôn Ngữ Thiết Kế Đồng Bộ
Giao diện được xây dựng bằng CSS thuần chất lượng cao, đồng bộ hoàn toàn với các biến giao diện chatbot cũ của bạn:
* Nền tối huyền ảo (Deep Obsidian) `#060913`
* Các khối kính mờ (Glassmorphism) kết hợp đổ bóng sâu premium.
* Các hiệu ứng chuyển động vi mô (Micro-animations), hiệu ứng sóng xung mạch (Avatar pulse) đem lại cảm giác sống động, chuyên nghiệp vượt bậc!

---

## 📑 Hệ Thống Tạo Hợp Đồng Tự Động (Contract Automation)
Dự án bao gồm bộ công cụ tự động hóa toàn bộ quy trình tạo Hợp đồng dịch vụ tư vấn visa song ngữ Việt - Anh (7 trang chuẩn), tự động tách chữ ký từ Hộ chiếu và phân loại Khách Lẻ vs Đại Lý.

👉 **Xem hướng dẫn chi tiết tại**: [HUONG_DAN_TAO_HOP_DONG.md](HUONG_DAN_TAO_HOP_DONG.md)

### Các lệnh nhanh:
```bash
# 1. Tạo hợp đồng hàng loạt theo mốc ngày kế toán (PDF + DOCX + Excel)
python batch_generate_by_accounting_date.py

# 2. Tạo hợp đồng định dạng Word (.docx)
python generate_docx_contracts.py

# 3. Tạo hợp đồng định dạng PDF (.pdf)
python batch_process_contracts.py
```

