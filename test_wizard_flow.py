"""
test_wizard_flow.py - Bộ công cụ kiểm thử toàn diện quy trình Wizard Telegram Bot
Đồng bộ theo yêu cầu chuẩn:
1. Quốc gia (Country Names) + Nhận diện khi khách gõ tên nước
2. Vị trí/Thành phố (Abroad, Nha Trang, Mũi Né, Đà Nẵng, TP.HCM xe riêng, Hà Nội, Khác)
3. Lịch tháng tương tác chuẩn quốc tế (Calendar Picker)
4. Dịch vụ cụ thể (Mũi Né đi Campuchia, TP.HCM xe riêng 2.300.000đ, link thanh toán https://t.me/visaEASYTRIP/118)
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
    get_routes_keyboard,
    get_payment_methods_keyboard,
    get_payment_detail_keyboard,
    get_payment_detail_message,
    get_payment_instruction_text,
    generate_booking_final_message,
    identify_country,
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
    print_separator("TEST LUỒNG MỚI: 2 NGÂN HÀNG VCB & VRB + TIỀN MẶT VP + NÚT TRỞ VỀ")
    
    # 1. BƯỚC 1: Lời chào & Chọn Quốc gia
    print("\n[BƯỚC 1]: Chọn Quốc Gia (Country Names)")
    kb1 = get_nationality_keyboard()
    display_keyboard(kb1, "Bước 1 - Danh mục Quốc gia")
    
    # Test thử khách gõ tên quốc gia (Kazakhstan / Germany / France)
    print("\n👉 Giả lập: Khách chọn [🇰🇿 🇰🇬 Kazakhstan / Kyrgyzstan / CIS] hoặc gõ 'Germany'")
    test_country_input = "Germany"
    detected = identify_country(test_country_input)
    print(f"🔍 Kết quả nhận diện khi khách nhắn '{test_country_input}': {detected}")
    
    # Chọn Kazakhstan
    cust_data = CustomerData(quoc_tich="Kazakhstan")
    lang = "ru"
    
    # 2. BƯỚC 2: Chọn Thành phố (Abroad lên đầu, có Mũi Né)
    print("\n[BƯỚC 2]: Chọn Vị trí / Thành phố (Abroad mục 1, Nha Trang, Mũi Né, TP.HCM xe riêng...)")
    kb2 = get_city_keyboard(lang)
    display_keyboard(kb2, "Bước 2 - Vị trí lưu trú")
    
    # Khách chọn Mũi Né
    print("\n👉 Giả lập: Khách bấm chọn [🏖️ Mũi Né (Phan Thiết)]")
    cust_data.thanh_pho = "muine"
    
    # 3. BƯỚC 3: Lịch tháng chuẩn quốc tế
    print("\n[BƯỚC 3]: Lịch tháng tương tác chuẩn quốc tế (Calendar Picker)")
    now = datetime.now()
    kb3 = get_calendar_keyboard(now.year, now.month, lang)
    display_keyboard(kb3, f"Bước 3 - Lịch Tháng {now.month}/{now.year} (Tiêu chuẩn Quốc Tế)")
    
    # Khách chọn ngày 15 trong tháng
    chosen_date = f"15/{now.month:02d}"
    print(f"\n👉 Giả lập: Khách chạm chọn ngày: [📅 {chosen_date}]")
    cust_data.ngay_het_han_visa = chosen_date
    cust_data.ngay_khoi_hanh = chosen_date
    
    # 4. BƯỚC 4: Bảng dịch vụ Mũi Né (Có đầy đủ 4 nút chuyên viên + 2 nút trở về đổi thành phố/quốc gia)
    print("\n[BƯỚC 4]: Dịch vụ Mũi Né (Đón 01:00-02:00 sáng đi Campuchia + Nút Trở Về)")
    kb4 = get_routes_keyboard("muine", lang, country="Kazakhstan")
    display_keyboard(kb4, "Bước 4 - Bảng đề xuất thông minh (Tiếng Nga)")
    
    # 5. BƯỚC 5: Danh mục chọn Phương thức thanh toán (VCB, VRB, Tiền mặt tại VP)
    print_separator("DANH MỤC PHƯƠNG THỨC THANH TOÁN (VCB, VRB, TIỀN MẶT TẠI VP + NÚT TRỞ VỀ)")
    kb_pay_menu = get_payment_methods_keyboard(lang)
    display_keyboard(kb_pay_menu, "Bàn phím lựa chọn phương thức thanh toán")
    
    # 6. BƯỚC 6: Chi tiết cách thức chuyển khoản từng ngân hàng
    print_separator("CHI TIẾT CHUYỂN KHOẢN: VIETCOMBANK (VCB)")
    print(get_payment_detail_message("vcb", lang))
    kb_detail = get_payment_detail_keyboard(lang)
    display_keyboard(kb_detail, "Bàn phím sau khi xem VCB")
    
    print_separator("CHI TIẾT CHUYỂN KHOẢN: VRB BANK (VIỆT - NGA)")
    print(get_payment_detail_message("vrb", lang))
    display_keyboard(kb_detail, "Bàn phím sau khi xem VRB")
    
    print_separator("CHI TIẾT THANH TOÁN: TIỀN MẶT TẠI VĂN PHÒNG NHA TRANG")
    print(get_payment_detail_message("cash", lang))
    display_keyboard(kb_detail, "Bàn phím sau khi xem Tiền mặt tại VP")
    
    # Kiểm tra giao diện Tiếng Việt
    print_separator("KIỂM TRA GIAO DIỆN PHƯƠNG THỨC THANH TOÁN TIẾNG VIỆT")
    kb_pay_vi = get_payment_methods_keyboard("vi")
    display_keyboard(kb_pay_vi, "Bàn phím thanh toán Tiếng Việt")
    print("\n[Chi tiết VCB Tiếng Việt]:")
    print(get_payment_detail_message("vcb", "vi"))
    print("\n[Chi tiết VRB Tiếng Việt]:")
    print(get_payment_detail_message("vrb", "vi"))
    
    # 7. Booking Final + Nhắc trước 2 tiếng + Chính sách hủy/hoàn
    print_separator("VÉ BOOKING FINAL TIẾNG NGA (KÈM NHẮC XE TRƯỚC 2 TIẾNG & CHÍNH SÁCH)")
    cust_data.ho_ten = "AZAMAT NURGALIYEV"
    cust_data.ghe_chon = "A04 (Tầng 1)"
    cust_data.loai_visa = "🚌 Муйне ⇄ Мокбай (Камбоджа) Слипбас"
    cust_data.diem_don = "04 Trần Phú, Mũi Né (https://maps.app.goo.gl/vysXaB9b4BeauGgV9)"
    receipt = generate_booking_final_message(cust_data, lang=lang)
    print(receipt)

if __name__ == "__main__":
    test_full_flow()
