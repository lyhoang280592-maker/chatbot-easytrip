"""
test_wizard_flow.py - Bộ công cụ kiểm thử toàn diện quy trình Wizard Telegram Bot
Đồng bộ theo yêu cầu chuẩn:
1. Quốc gia (Country Names) + Nhận diện khi khách gõ tên nước
2. Vị trí/Thành phố (Abroad, Nha Trang, Mũi Né, Đà Nẵng, TP.HCM xe riêng, Hà Nội, Khác)
3. Lịch tháng tương tác chuẩn quốc tế (Calendar Picker)
4. Dịch vụ cụ thể:
   - Tách riêng: Nha Trang - Lào Bờ Y 45 ngày & Nha Trang - Lào Bờ Y 90 ngày
   - Gửi thông tin hành trình chi tiết và cách thức đăng ký từng bước
   - Mũi Né đi Campuchia, TP.HCM xe riêng, link thanh toán https://t.me/visaEASYTRIP/118
5. 4 nút tư vấn chuyên viên tách riêng (Overstay, TRC, Work Visa, Family Visa)
6. Phương thức thanh toán chuẩn hóa:
   - 🏦 Vietcombank (VCB)
   - 🏦 VRB Bank (Ngân hàng Liên doanh Việt - Nga)
   - 🏢 Tiền mặt tại văn phòng ở Nha Trang
   - 🔙 Nút trở về thao tác trước đó (Back to services/city/nationality)
7. Booking final + Nhắc xe trước 2 tiếng + Chính sách hủy/hoàn
"""

import sys
from datetime import datetime
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

load_dotenv()

from wizard_flows import (
    CITY_OPTIONS,
    ROUTE_SERVICES,
    get_nationality_keyboard,
    get_city_keyboard,
    get_calendar_keyboard,
    get_smart_advisory_keyboard,
    get_routes_keyboard,
    get_itinerary_message,
    get_payment_methods_keyboard,
    get_payment_detail_keyboard,
    get_payment_detail_message,
    get_payment_instruction_text,
    generate_booking_final_message,
    identify_country,
    analyze_customer_incoming_message,
    calculate_evisa_smart_schedule,
    get_evisa_main_keyboard,
    get_evisa_flight_keyboard,
    generate_evisa_consultation_message,
)
from ai_agent import CustomerData

def print_separator(title=""):
    print("\n" + "=" * 65)
    if title:
        print(f"📌 {title}")
        print("=" * 65)

def display_keyboard(kb, label="BÀN PHÍM NÚT BẤM TELEGRAM"):
    print(f"\n📱 [{label}]:")
    idx = 1
    for row in kb.inline_keyboard:
        row_str = []
        for btn in row:
            target = f"data: {btn.callback_data}" if btn.callback_data else f"url: {btn.url}"
            row_str.append(f"[{btn.text}] ({target})")
            idx += 1
        print("   " + "  |  ".join(row_str))

def test_full_flow():
    print_separator("TEST LUỒNG: TÁCH RIÊNG NHA TRANG LÀO BỜ Y 45D & 90D + HƯỚNG DẪN ĐĂNG KÝ")
    
    # 1. BƯỚC 1: Lời chào & Chọn Quốc gia
    print("\n[BƯỚC 1]: Chọn Quốc Gia (Country Names)")
    kb1 = get_nationality_keyboard()
    display_keyboard(kb1, "Bước 1 - Danh mục Quốc gia")
    
    # Test thử khách gõ tên quốc gia (Kazakhstan / Germany / France)
    print("\n👉 Giả lập: Khách chọn [🇰🇿 🇰🇬 Kazakhstan / Kyrgyzstan / CIS] hoặc gõ 'Germany'")
    test_country_input = "Germany"
    detected = identify_country(test_country_input)
    print(f"🔍 Kết quả nhận diện khi khách nhắn '{test_country_input}': {detected}")
    
    # Chọn Nga / Kazakhstan
    cust_data = CustomerData(quoc_tich="Russia")
    lang = "ru"
    
    # 2. BƯỚC 2: Chọn Thành phố (Abroad lên đầu, Nha Trang, Mũi Né...)
    print("\n[BƯỚC 2]: Chọn Vị trí / Thành phố (Abroad mục 1, Nha Trang, Mũi Né, TP.HCM xe riêng...)")
    kb2 = get_city_keyboard(lang)
    display_keyboard(kb2, "Bước 2 - Vị trí lưu trú")
    
    # Khách chọn Nha Trang
    print("\n👉 Giả lập: Khách bấm chọn [🏖️ Nha Trang]")
    cust_data.thanh_pho = "nhatrang"
    
    # 3. BƯỚC 3: Lịch tháng chuẩn quốc tế
    print("\n[BƯỚC 3]: Lịch tháng tương tác chuẩn quốc tế (Calendar Picker)")
    now = datetime.now()
    kb3 = get_calendar_keyboard(now.year, now.month, lang)
    display_keyboard(kb3, f"Bước 3 - Lịch Tháng {now.month}/{now.year} (Tiêu chuẩn Quốc Tế)")
    
    # 4. BƯỚC 4: Bảng dịch vụ Nha Trang (ĐÃ TÁCH RIÊNG 45D & 90D)
    print_separator("BƯỚC 4: BẢNG DỊCH VỤ NHA TRANG (ĐÃ TÁCH RIÊNG 45D & 90D)")
    kb4 = get_smart_advisory_keyboard("nhatrang", "Russia", lang="ru")
    display_keyboard(kb4, "Bước 4 - Bảng đề xuất thông minh Nha Trang (Tiếng Nga)")

    kb4_vi = get_smart_advisory_keyboard("nhatrang", "Vietnam", lang="vi")
    display_keyboard(kb4_vi, "Bước 4 - Bảng đề xuất thông minh Nha Trang (Tiếng Việt)")
    
    # 5. TEST CHI TIẾT HÀNH TRÌNH & CÁCH THỨC ĐĂNG KÝ
    print_separator("CHI TIẾT HÀNH TRÌNH & CÁCH THỨC ĐĂNG KÝ: LÀO BỜ Y 45 NGÀY (TIẾNG VIỆT)")
    print(get_itinerary_message("laos_boy_45d", "vi"))

    print_separator("CHI TIẾT HÀNH TRÌNH & CÁCH THỨC ĐĂNG KÝ: LÀO BỜ Y 90 NGÀY (TIẾNG VIỆT)")
    print(get_itinerary_message("laos_boy_90d", "vi"))

    print_separator("CHI TIẾT HÀNH TRÌNH & CÁCH THỨC ĐĂNG KÝ: LÀO BỜ Y 45 NGÀY (TIẾNG NGA)")
    print(get_itinerary_message("laos_boy_45d", "ru"))

    print_separator("CHI TIẾT HÀNH TRÌNH & CÁCH THỨC ĐĂNG KÝ: LÀO BỜ Y 90 NGÀY (TIẾNG NGA)")
    print(get_itinerary_message("laos_boy_90d", "ru"))
    
    # 6. BƯỚC 5: Danh mục chọn Phương thức thanh toán (VCB, VRB, Tiền mặt tại VP)
    print_separator("DANH MỤC PHƯƠNG THỨC THANH TOÁN (VCB, VRB, TIỀN MẶT TẠI VP + NÚT TRỞ VỀ)")
    kb_pay_menu = get_payment_methods_keyboard(lang)
    display_keyboard(kb_pay_menu, "Bàn phím lựa chọn phương thức thanh toán")
    
    # 7. BƯỚC 6: Chi tiết cách thức chuyển khoản từng ngân hàng
    print_separator("CHI TIẾT CHUYỂN KHOẢN: VIETCOMBANK (VCB)")
    print(get_payment_detail_message("vcb", lang))
    kb_detail = get_payment_detail_keyboard(lang)
    display_keyboard(kb_detail, "Bàn phím sau khi xem VCB")
    
    print_separator("CHI TIẾT CHUYỂN KHOẢN: VRB BANK (VIỆT - NGA)")
    print(get_payment_detail_message("vrb", lang))
    display_keyboard(kb_detail, "Bàn phím sau khi xem VRB")
    
    # 8. Booking Final + Nhắc trước 2 tiếng + Chính sách hủy/hoàn
    print_separator("VÉ BOOKING FINAL TIẾNG NGA (KÈM NHẮC XE TRƯỚC 2 TIẾNG & CHÍNH SÁCH)")
    cust_data.ho_ten = "IVANOV SERGEI"
    cust_data.ghe_chon = "A04 (Tầng 1)"
    cust_data.loai_visa = "🚌 Nha Trang ⇄ Lào Bờ Y (90 Ngày E-Visa)"
    cust_data.diem_don = "40 Hòn Chồng = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8)"
    receipt = generate_booking_final_message(cust_data, lang=lang)
    print(receipt)

    # 9. KIỂM THỬ BẮT ĐOẠN CHAT THÔNG MINH TỪ WEB & LỜI CHÀO TELEGRAM BUSINESS
    print_separator("KIỂM THỬ BẮT Ý ĐỊNH ĐOẠN CHAT TỰ ĐỘNG (WEB LEAD, GREETING, OVERSTAY, FAST TRACK)")
    test_cases = [
        ("hi easytrip", "Chào hỏi đầu phiên"),
        ("/start", "Lệnh khởi động Bot"),
        ("Здравствуйте! Хочу заказать визаран из Нячанга в Лаос", "Web Lead: Nha Trang -> Lào"),
        ("Tư vấn xe buýt Đà Nẵng đi Lào Lao Bảo", "Web Lead: Đà Nẵng -> Lào"),
        ("Tôi bị quá hạn visa 5 ngày (visa overstay)", "Dịch vụ chuyên biệt: Overstay"),
        ("Cần thẻ tạm trú TRC cho gia đình", "Dịch vụ chuyên biệt: TRC"),
        ("Airport VIP Fast Track tại sân bay Cam Ranh", "Dịch vụ: Fast Track"),
        ("Kazakhstan", "Khách tự gõ tên quốc tịch"),
        ("Здравствуйте, Easy Trip & Visa! Я хочу забронировать визаран из Нячанга в Камбоджу (Мокбай): Автобус + однократная E-visa во Вьетнам на 90 дней + виза в Камбоджу (4.400.000 VND - оформление за 24 часа). Пожалуйста, проконсультируйте меня!", "Web Lead: Nha Trang -> Campuchia Mộc Bài 90D"),
    ]
    
    for text_in, desc in test_cases:
        res = analyze_customer_incoming_message(text_in)
        print(f"👉 [{desc}]: '{text_in}' => {res}")

    print_separator("KIỂM THỬ BỘ ĐẾM E-VISA THÔNG MINH (4H, 1 NGÀY, 2 NGÀY, TRỪ T7 & CN)")
    # Case 1: Khách ở 1 đêm (gói 4h)
    tue = datetime(2026, 11, 4, 11, 0)
    sched_1 = calculate_evisa_smart_schedule(stay_type="1night", now=tue, lang="vi")
    print(f"👉 [Trường hợp 1 - Ở 1 đêm]: {sched_1['package_name']['vi']}")
    print(f"   Nộp: {sched_1['submit_time']} | Trả: {sched_1['delivery_time']} | Kích hoạt: {sched_1['activation_date']}")

    # Case 2: Khách ở 2 đêm (gói 1 ngày nộp Thứ Sáu -> Trả Thứ Hai)
    fri = datetime(2026, 11, 6, 11, 0)
    sched_2 = calculate_evisa_smart_schedule(stay_type="2nights", now=fri, lang="vi")
    print(f"👉 [Trường hợp 2 - Nộp Thứ 6 vướng T7/CN]: {sched_2['package_name']['vi']}")
    print(f"   Nộp: {sched_2['submit_time']} | Trả: {sched_2['delivery_time']} | Kích hoạt: {sched_2['activation_date']}")

    # Case 3: Bàn phím phân luồng & Thẻ tư vấn khoa học
    display_keyboard(get_evisa_main_keyboard("ru"), "Bàn phím lựa chọn E-visa chính (Tiếng Nga)")
    display_keyboard(get_evisa_flight_keyboard("vi"), "Bàn phím chọn số đêm lưu trú (Tiếng Việt)")
    print("\n📄 [Thẻ tư vấn khoa học mẫu]:")
    print(generate_evisa_consultation_message(sched_2, "vi"))

if __name__ == "__main__":
    test_full_flow()
