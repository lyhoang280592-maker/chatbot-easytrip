import os
import asyncio
from unittest.mock import AsyncMock, patch
from dotenv import load_dotenv

load_dotenv()

async def run_tests():
    print("🚀 BẮT ĐẦU KIỂM THỬ TÍNH NĂNG THÔNG BÁO TELEGRAM ADMIN OMNICHANNEL\n" + "="*60)
    
    # 1. Kiểm tra import module
    from telegram_router import notify_admin_incoming_message, tg_app
    from main import process_omnichannel_logic, handle_fb_flow, handle_zalo_flow
    print("✅ 1. Import thành công telegram_router và main.py!")

    # 2. Test hàm notify_admin_incoming_message với Mock Telegram bot
    import telegram
    mock_send = AsyncMock()
    with patch.object(telegram.Bot, "send_message", mock_send):
        
        # Test 2.1: Website Chatbox
        print("\n--- Test 2.1: Khách nhắn qua Website ---")
        mock_send.reset_mock()
        await notify_admin_incoming_message(
            platform="Website",
            user_id="web_test_123",
            user_text="Mình muốn hỏi xe đi Mộc Bài ngày mai",
            session_id="web_test_123",
            user_name="Nguyễn Văn A",
            agent="Direct",
            mode="copilot",
            bot_reply="Dạ chào bạn, ngày mai chuyến Mộc Bài khởi hành lúc 7h sáng ạ."
        )
        assert mock_send.called, "Bot phải gọi send_message!"
        call_kwargs = mock_send.call_args.kwargs
        sent_text = call_kwargs["text"]
        print("Nội dung thông báo Website đã tạo:\n" + sent_text)
        assert "Website Chatbox" in sent_text
        assert "Nguyễn Văn A" in sent_text
        assert "Mộc Bài" in sent_text
        assert "Co-Pilot" in sent_text
        assert call_kwargs.get("parse_mode") == "HTML"
        print("✅ Test 2.1 thành công!")

        # Test 2.2: Facebook (Page Tích Xanh)
        print("\n--- Test 2.2: Khách nhắn qua Facebook (Page Tích Xanh) ---")
        mock_send.reset_mock()
        await notify_admin_incoming_message(
            platform="Facebook (Page Tích Xanh)",
            user_id="fb_user_456",
            user_text="Hello, how much is the Laos visarun?",
            session_id="fb_fb_user_456",
            user_name="John Doe",
            mode="auto",
            bot_reply="Hello John! Laos Visarun 45 days is 2,000,000 VND."
        )
        assert mock_send.called, "Bot phải gọi send_message!"
        sent_text = mock_send.call_args.kwargs["text"]
        print("\nNội dung thông báo Facebook đã tạo:\n" + sent_text)
        assert "Facebook (Fanpage Tích Xanh)" in sent_text
        assert "John Doe" in sent_text
        assert "Laos visarun" in sent_text
        assert "Tự động" in sent_text
        print("✅ Test 2.2 thành công!")

        # Test 2.3: Zalo (OA)
        print("\n--- Test 2.3: Khách nhắn qua Zalo ---")
        mock_send.reset_mock()
        await notify_admin_incoming_message(
            platform="Zalo",
            user_id="zalo_user_789",
            user_text="Tư vấn giúp mình visa 3 tháng",
            session_id="zalo_zalo_user_789",
            mode="manual"
        )
        assert mock_send.called, "Bot phải gọi send_message!"
        sent_text = mock_send.call_args.kwargs["text"]
        print("\nNội dung thông báo Zalo đã tạo:\n" + sent_text)
        assert "Zalo (OA)" in sent_text
        assert "visa 3 tháng" in sent_text
        assert "Thủ công" in sent_text
        print("✅ Test 2.3 thành công!")

        # Test 2.4: Bỏ qua khi chính Admin gửi tin
        print("\n--- Test 2.4: Tránh tự thông báo khi Admin nhắn tin ---")
        mock_send.reset_mock()
        admin_id = os.getenv("ADMIN_TELEGRAM_ID") or os.getenv("ID_TELEGRAM_QUAN_TRI")
        await notify_admin_incoming_message(
            platform="Telegram",
            user_id=str(admin_id),
            user_text="Kiểm tra đơn hàng",
            session_id=f"telegram_{admin_id}"
        )
        assert not mock_send.called, "Không được gửi thông báo nếu người gửi là chính Admin!"
        print("✅ Test 2.4 thành công: Bỏ qua tin nhắn của Admin chuẩn xác!")

    print("\n" + "="*60 + "\n🎉 TẤT CẢ CÁC BÀI KIỂM THỬ ĐÃ HOÀN TẤT THÀNH CÔNG RỰC RỠ!")

if __name__ == "__main__":
    asyncio.run(run_tests())
