import asyncio
import os
import sys
import json
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.abspath("."))

from memory_store import memory_store
from ai_agent import CustomerData, ChatResponse
from main import process_omnichannel_logic, handle_fb_flow

async def run_tests():
    print("🚀 Starting Test: Auto Sending Vietcombank OneQR Code to Customers")

    session_id = "fb_38413034085009192"
    cust_data = CustomerData(
        ho_ten="Dmitry",
        nam_sinh="1995",
        quoc_tich="Russia",
        ngay_khoi_hanh="13/09",
        loai_visa="90D Laos",
        diem_don="40 Hon Chong",
        ghe_chon="B1"
    )
    memory_store[f"{session_id}_data"] = cust_data
    memory_store[f"{session_id}_name"] = "Dmitry"
    memory_store[session_id] = []

    # 1. Test customer asking "Как оплатить?"
    mock_ai_resp = ChatResponse(
        reply_message="Пожалуйста, выберите способ оплаты. Реквизиты Vietcombank: 1068582577, EASY TRIP & VISA CO. LTD",
        extracted_data=cust_data,
        current_phase="PAYMENT",
        is_complete=False
    )
    
    with patch("ai_agent.process_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_ai_resp
        
        reply, img = await process_omnichannel_logic(
            user_id="38413034085009192",
            platform="Facebook (Fanpage Tích Xanh)",
            user_text="Как оплатить?",
            session_id=session_id,
            customer_name="Dmitry"
        )
        
        assert img is not None, "image_to_send must NOT be None when customer asks to pay!"
        assert "qr_code.jpg" in img, f"Expected qr_code.jpg in image URL, got: {img}"
        print(f"✅ process_omnichannel_logic returned QR code URL: {img}")

    # 2. Test customer sending "QR"
    with patch("ai_agent.process_chat", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = mock_ai_resp
        
        reply, img = await process_omnichannel_logic(
            user_id="38413034085009192",
            platform="Facebook (Fanpage Tích Xanh)",
            user_text="QR",
            session_id=session_id,
            customer_name="Dmitry"
        )
        
        assert img is not None, "image_to_send must NOT be None when user sends 'QR'!"
        assert "qr_code.jpg" in img, f"Expected qr_code.jpg in image URL, got: {img}"
        print(f"✅ 'QR' trigger successfully returned: {img}")

    # 3. Test handle_fb_flow dispatch
    with patch("main.process_omnichannel_logic", new_callable=AsyncMock) as mock_omni, \
         patch("main.send_facebook_message", new_callable=AsyncMock) as mock_fb_msg, \
         patch("main.send_facebook_image", new_callable=AsyncMock) as mock_fb_img, \
         patch("main.notify_admin_incoming_message", new_callable=AsyncMock):
        
        mock_omni.return_value = ("Payment info...", "https://chatbot-easytrip.onrender.com/static/qr_code.jpg?v=2")
        mock_fb_msg.return_value = (True, "OK")
        mock_fb_img.return_value = (True, "OK")
        
        await handle_fb_flow("38413034085009192", "QR", page_id="1244422022092408")
        
        assert mock_fb_msg.called, "send_facebook_message must be called!"
        assert mock_fb_img.called, "send_facebook_image must be called!"
        
        call_kwargs = mock_fb_img.call_args[1]
        assert call_kwargs.get("local_file_path") is not None, "local_file_path must be passed to send_facebook_image!"
        print(f"✅ handle_fb_flow dispatched QR image with local_file_path: {call_kwargs.get('local_file_path')}")

    print("🎉 ALL QR CODE SENDING TESTS PASSED 100%!")

if __name__ == "__main__":
    asyncio.run(run_tests())
