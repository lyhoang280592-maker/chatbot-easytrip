import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock
from wizard_flows import (
    calculate_party_pricing,
    get_party_counter_keyboard,
    handle_step_callback,
    memory_store,
)
from ai_agent import CustomerData

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

async def test_party_check_cabins_and_seat_choice():
    print("=" * 65)
    print("🧪 KIỂM THỬ QUY TRÌNH: ĐẶT ĐOÀN -> BÁO CHECK CABIN -> TỰ ĐỌNG CHỐT GHẾ & THANH TOÁN")
    print("=" * 65)

    # 1. Test tính tiền đoàn
    route_key = "laos_boy_90d"
    adults = 2
    kids_over9 = 1
    kids_under9 = 1
    date_val = "12/11"

    pricing = calculate_party_pricing(route_key, adults, kids_under9, kids_over9)
    print(f"\n1️⃣ Tính giá cho gia đình: 2 NL + 1 Trẻ >=9T + 1 Trẻ <9T:")
    print(f"   • Người lớn: {pricing['adult_unit']:,} x {adults} = {pricing['adult_unit'] * adults:,} ₫")
    print(f"   • Trẻ >= 9T: {pricing['adult_unit']:,} x {kids_over9} = {pricing['adult_unit'] * kids_over9:,} ₫")
    print(f"   • Trẻ < 9T: Vé xe 0 ₫ + E-Visa = {pricing['total_kids_under9_price']:,} ₫")
    print(f"   💰 Tổng cộng: {pricing['grand_total']:,} VND (Kỳ vọng: 13,480,000 VND)")
    assert pricing['grand_total'] == 13480000, "Sai tổng tiền!"

    # 2. Test bàn phím sau khi confirm party
    kb = get_party_counter_keyboard(route_key, date_val, adults, kids_under9, kids_over9, "vi")
    confirm_btn = kb.inline_keyboard[-2][0]
    print(f"\n2️⃣ Nút xác nhận: '{confirm_btn.text}' | callback: '{confirm_btn.callback_data}'")

    # 3. Giả lập bấm nút 'step|check_cabins'
    chat_id = 999999
    session_id = f"telegram_{chat_id}"
    cust_data = CustomerData()
    cust_data.loai_visa = "Nha Trang ⇄ Lào Bờ Y (90 Ngày)"
    memory_store[f"{session_id}_data"] = cust_data
    memory_store[f"{session_id}_lang"] = "vi"

    mock_update = MagicMock()
    mock_update.effective_chat.id = chat_id
    mock_update.effective_chat.type = "private"
    mock_update.effective_user.id = chat_id
    mock_update.effective_user.full_name = "Easy Trip Visa"
    mock_update.effective_user.username = "easytripvisa_co_ltd"
    mock_update.callback_query = MagicMock()
    mock_update.callback_query.message = MagicMock()
    mock_update.callback_query.message.reply_text = AsyncMock()
    mock_update.callback_query.message.edit_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()
    mock_context.bot.send_photo = AsyncMock()

    # Callback check_cabins
    parts = ["step", "check_cabins", route_key, date_val, str(adults), str(kids_under9), str(kids_over9)]
    print(f"\n3️⃣ Khách bấm nút báo nhân viên kiểm tra cabin:")
    await handle_step_callback(mock_update, mock_context, parts, None)

    # Kiểm tra pending_seats được lưu
    pending = memory_store.get(f"{session_id}_pending_seats")
    assert pending is not None, "Chưa lưu pending_seats!"
    print(f"   ✅ Đã ghi nhận pending booking: {pending['total_seats_needed']} giường, tổng tiền: {pending['grand_total']:,} VND")

    # 4. Giả lập nhân viên gửi sơ đồ ghế và khách nhắn: "A1, A2, B2"
    from telegram_router import process_customer_text_message
    mock_msg_update = MagicMock()
    mock_msg_update.effective_chat.id = chat_id
    mock_msg_update.effective_chat.type = "private"
    mock_msg_update.effective_user.id = chat_id
    mock_msg_update.effective_user.full_name = "Easy Trip Visa"
    mock_msg_update.effective_user.username = "easytripvisa_co_ltd"
    mock_msg_update.message = MagicMock()
    mock_msg_update.message.text = "Gia đình mình chọn A1, A2, B2 nhé"
    mock_msg_update.message.reply_text = AsyncMock()
    mock_msg_update.business_message = None
    mock_msg_update.edited_business_message = None
    mock_msg_update.callback_query = None  # Cực kỳ quan trọng để không rơi vào query.message

    # Đánh dấu đã gửi channel card để tập trung kiểm thử tin nhắn ghế
    memory_store[f"{session_id}_sent_official_channel"] = True

    print(f"\n4️⃣ Khách nhắn tin chọn ghế: '{mock_msg_update.message.text}'")
    await process_customer_text_message(mock_msg_update, mock_context, str(chat_id), mock_msg_update.message.text)

    # Kiểm tra ghế đã chốt trong cust_data
    saved_cust = memory_store.get(f"{session_id}_data")
    print(f"   ✅ Vị trí ghế đã chốt trong hệ thống: {saved_cust.ghe_chon}")
    assert "A1, A2, B2" in saved_cust.ghe_chon, f"Ghế chưa đúng: {saved_cust.ghe_chon}"

    # Kiểm tra bot đã gửi tin nhắn xác nhận
    sent_calls = mock_msg_update.message.reply_text.call_args_list
    assert len(sent_calls) > 0, "Bot chưa gửi tin nhắn phản hồi!"
    final_reply = sent_calls[-1][0][0]
    print(f"\n5️⃣ Nội dung Final Booking gửi khách:")
    print("-" * 50)
    print(final_reply)
    print("-" * 50)
    assert "XÁC NHẬN GIỮ CHỖ CHÍNH THỨC" in final_reply, "Thiếu tiêu đề Final Booking!"
    assert "13,480,000" in final_reply, "Thiếu số tiền 13,480,000 VND!"
    assert "A1, A2, B2" in final_reply, "Thiếu số ghế đã chọn!"

    print("\n🎉 TẤT CẢ CÁC BƯỚC KIỂM THỬ ĐỀU THÀNH CÔNG VƯỢT TRỘI!")

if __name__ == "__main__":
    asyncio.run(test_party_check_cabins_and_seat_choice())
