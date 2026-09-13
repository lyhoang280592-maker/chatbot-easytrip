import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.abspath("."))
from unittest.mock import AsyncMock, patch, MagicMock

# Setup mock environment
os.environ["BUS_GROUP_CHAT_ID"] = "-1002646043809"
os.environ["ADMIN_GROUP_CHAT_ID"] = "-1003887071472"
os.environ["RENDER_EXTERNAL_URL"] = "https://chatbot-easytrip.onrender.com"

from memory_store import memory_store
from ai_agent import CustomerData
import telegram_router
from telegram_router import handle_photo, send_to_bus_group, recent_scheme_requests, date_to_topic_id_map, latest_seat_maps

async def run_tests():
    print("🚀 Starting Test: Auto Forwarding Bus Seat Map Photo to Omnichannel Customers")

    # 1. Setup simulated waiting Facebook customer
    fb_session_id = "fb_38413034085009192"
    cust_data = CustomerData(
        ho_ten="Dmitry",
        nam_sinh="1995",
        quoc_tich="Russia",
        ngay_khoi_hanh="14/09",  # Customer specified 14/09 or 15/09 expiry
        ngay_het_han_visa="15/09",
        loai_visa="90D Laos",
        diem_don="40 Hon Chong"
    )
    memory_store[f"{fb_session_id}_data"] = cust_data
    memory_store[f"{fb_session_id}_fb_page_id"] = "1244422022092408"
    memory_store[f"{fb_session_id}_name"] = "Dmitry"
    memory_store[fb_session_id] = [
        {"role": "user", "content": "Россия - 15/09 - Нячанг - визаран 90 дней\nДмитрий / 1995\n40 Hon Chong"}
    ]

    # 2. Simulate Bot issuing Scheme command
    mock_sent_msg = MagicMock()
    mock_sent_msg.message_id = 998877
    
    mock_bot = AsyncMock()
    mock_bot.send_message = AsyncMock(return_value=mock_sent_msg)
    
    mock_ctx = MagicMock()
    mock_ctx.bot = mock_bot
    
    await send_to_bus_group(mock_ctx, "Scheme 13/09 - 90D laos", date="13/09", service="90D")
    
    assert "latest" in recent_scheme_requests, "recent_scheme_requests['latest'] must exist"
    assert recent_scheme_requests["latest"]["date"] == "13/09"
    assert recent_scheme_requests["latest"]["service"] == "90D"
    print("✅ send_to_bus_group properly registered recent_scheme_requests!")

    # 3. Simulate Admin uploading photo in Telegram (Reply to Scheme without caption)
    mock_photo_file = AsyncMock()
    mock_photo_file.download_to_drive = AsyncMock(return_value=None)
    
    mock_photo_obj = MagicMock()
    mock_photo_obj.file_id = "AgACAgUAAxkBAAM_test_photo"
    mock_photo_obj.get_file = AsyncMock(return_value=mock_photo_file)
    
    mock_reply_msg = MagicMock()
    mock_reply_msg.text = "Scheme 13/09 - 90D laos"
    mock_reply_msg.message_id = 998877
    mock_reply_msg.forum_topic_created = None
    
    mock_tg_msg = MagicMock()
    mock_tg_msg.photo = [mock_photo_obj]
    mock_tg_msg.caption = None  # Admin sent photo without caption
    mock_tg_msg.message_thread_id = 1234
    mock_tg_msg.reply_to_message = mock_reply_msg
    mock_tg_msg.reply_text = AsyncMock()
    
    mock_update = MagicMock()
    mock_update.effective_chat = MagicMock()
    mock_update.effective_chat.id = -1002646043809
    mock_update.effective_chat.type = "supergroup"
    mock_update.effective_message = mock_tg_msg
    mock_update.message = mock_tg_msg
    mock_update.business_message = None
    
    with patch("main.send_facebook_message", new_callable=AsyncMock) as mock_send_fb_msg, \
         patch("main.send_facebook_image", new_callable=AsyncMock) as mock_send_fb_img:
        
        mock_send_fb_msg.return_value = (True, "OK")
        mock_send_fb_img.return_value = (True, "OK")
        
        await handle_photo(mock_update, mock_ctx)
        
        # Verify Facebook dispatch
        assert mock_send_fb_msg.called, "send_facebook_message must be called for customer!"
        assert mock_send_fb_img.called, "send_facebook_image must be called for customer!"
        
        called_uid = mock_send_fb_img.call_args[0][0]
        called_img_url = mock_send_fb_img.call_args[0][1]
        called_page_id = mock_send_fb_img.call_args[1].get("page_id")
        
        assert called_uid == "38413034085009192", f"Expected UID 38413034085009192, got {called_uid}"
        assert "map_13_09_90D.jpg" in called_img_url, f"Expected map_13_09_90D.jpg in URL, got {called_img_url}"
        assert called_page_id == "1244422022092408", f"Expected page_id 1244422022092408, got {called_page_id}"
        
        print("✅ SUCCESS: Telegram handle_photo automatically detected Scheme reply, extracted 13/09 90D, and forwarded seat map photo to Facebook customer!")

if __name__ == "__main__":
    asyncio.run(run_tests())
