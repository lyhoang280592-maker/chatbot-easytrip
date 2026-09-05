import asyncio
import os
import sys

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

import customer_memory
from ai_agent import process_chat

async def test_ocr_and_yob_matching():
    print("======================================================================")
    print("🧪 KIỂM THỬ RÀNG BUỘC TÊN VÀ NĂM SINH (KHÔNG CẦN SĐT)")
    print("======================================================================\n")

    # 1. Test Choi Hae Joon (Hàn Quốc - có trong CRM với năm sinh 1986)
    print("--- [TEST 1] KHÁCH CÓ TRONG CRM: CHOI HAE JOON (HÀN QUỐC - 1986) ---")
    text_choi = """
    EASY TRIP AND VISA CO. LTD
    BOOKING RECEIPT
    Customer Name: CHOI HAE JOON
    Year of Birth: 1986
    Departure Date: 10/05/2026
    Route: Laos Bo Y 45 Days
    Seat: A12
    Pickup: 40 Hon Chong
    """
    matched_choi = customer_memory.find_customer_by_booking_text(text_choi)
    assert matched_choi is not None, "Lỗi: Không tìm thấy khách Choi Hae Joon"
    print(f"✅ Đã tìm thấy: {matched_choi['full_name']} | Năm sinh: {matched_choi.get('birth_year')} | Ghế: {matched_choi.get('preferred_seat')}")
    assert "CHOI" in matched_choi['full_name'].upper(), "Lỗi tên không khớp"
    
    # Format prompt & kiểm tra AI
    prompt_dir = customer_memory.format_customer_profile_for_prompt(matched_choi)
    assert "KOREAN" in prompt_dir, "Lỗi: Ngôn ngữ bắt buộc phải là Tiếng Hàn"
    assert "1,300,000" in prompt_dir, "Lỗi: Giá ưu đãi khách cũ Lào 45 ngày phải là 1.300.000đ"
    print("✅ Prompt chỉ dẫn AI chuẩn tiếng Hàn và giá 1.300.000đ cho khách cũ Lào 45 ngày.")

    # 2. Test Melnikova Anastasia (Nga - có trong CRM với năm sinh 1995)
    print("\n--- [TEST 2] KHÁCH CÓ TRONG CRM: MELNIKOVA ANASTASIA (NGA - 1995) ---")
    text_anastasia = """
    RECEIPT
    Passenger: Melnikova Anastasia
    DOB: 1995
    Service: 90 Days E-visa Single
    Seat: B1
    Pickup: Hon Chong
    """
    matched_ana = customer_memory.find_customer_by_booking_text(text_anastasia)
    assert matched_ana is not None, "Lỗi: Không tìm thấy khách Melnikova Anastasia"
    print(f"✅ Đã tìm thấy: {matched_ana['full_name']} | Năm sinh: {matched_ana.get('birth_year')} | Ghế: {matched_ana.get('preferred_seat')}")
    assert "ANASTASIA" in matched_ana['full_name'].upper(), "Lỗi tên không khớp"
    
    prompt_dir_ana = customer_memory.format_customer_profile_for_prompt(matched_ana)
    assert "RUSSIAN" in prompt_dir_ana, "Lỗi: Ngôn ngữ bắt buộc phải là Tiếng Nga"
    assert "3,000,000" in prompt_dir_ana, "Lỗi: Giá ưu đãi khách cũ Nga 90D Single phải là 3.000.000đ"
    print("✅ Prompt chỉ dẫn AI chuẩn tiếng Nga và giá ưu đãi 3.000.000đ cho khách cũ Nga 90D Single.")

    # 3. Test Melnikova Anastasia KHÔNG CÓ NĂM SINH TRÊN VÉ (Vẫn tìm thấy theo Tên)
    print("\n--- [TEST 3] KHÁCH CÓ TRONG CRM: MELNIKOVA ANASTASIA (KHÔNG KÈM NĂM SINH) ---")
    text_ana_no_yob = """
    RECEIPT
    Passenger: Melnikova Anastasia
    Service: 90 Days E-visa Single
    """
    matched_ana_no_yob = customer_memory.find_customer_by_booking_text(text_ana_no_yob)
    assert matched_ana_no_yob is not None, "Lỗi: Phải tìm thấy theo tên ngay cả khi không có năm sinh"
    print(f"✅ Đã tìm thấy theo tên: {matched_ana_no_yob['full_name']}")

    # 4. Test Atalan Tyros (Tây / Hy Lạp - KHÔNG CÓ TRONG CRM)
    print("\n--- [TEST 4] KHÁCH KHÔNG CÓ TRONG CRM: ATALAN TYROS ---")
    text_atalan = """
    EASY TRIP AND VISA
    RECEIPT
    Name: Atalan Tyros
    Year of Birth: 1990
    Service: Cambodia 90 Days
    Seat: B1
    Pickup: Hon Chong
    """
    matched_atalan = customer_memory.find_customer_by_booking_text(text_atalan)
    assert matched_atalan is None, "Lỗi: Atalan Tyros không được phép khớp với ai trong CRM!"
    print("✅ Chuẩn xác: Atalan Tyros KHÔNG bị gán nhầm sang khách khác dù trùng ghế B1 hay điểm đón!")

    # Format prompt trường hợp không tìm thấy
    unverified_profile = {
        "full_name": "Atalan Tyros",
        "nationality": "Greece",
        "unverified_returning_attempt": True
    }
    prompt_unverified = customer_memory.format_customer_profile_for_prompt(unverified_profile)
    assert "NOT FOUND IN CRM DATABASE" in prompt_unverified, "Lỗi: Phải có cảnh báo NOT FOUND"
    assert "standard website" in prompt_unverified.lower(), "Lỗi: Phải chỉ dẫn áp dụng giá niêm yết website"
    print("✅ Prompt chỉ dẫn AI thông báo rõ không tìm thấy trên CSDL và áp dụng giá chuẩn website.")

    print("\n======================================================================")
    print("🎉 TẤT CẢ KIỂM THỬ RÀNG BUỘC TÊN VÀ NĂM SINH ĐỀU THÀNH CÔNG 100%!")
    print("======================================================================\n")

if __name__ == "__main__":
    asyncio.run(test_ocr_and_yob_matching())
