import os
import sys
import json
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.tl.types import User, Channel, Chat
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
OUTPUT_FILE = "telegram_chat.json"

async def export_chats(limit_per_chat: int = 300, max_chats: int = 150):
    client = TelegramClient('scraper_v2', int(API_ID), API_HASH)
    await client.connect()

    if not await client.is_user_authorized():
        print("❌ Lỗi: Chưa đăng nhập tài khoản. Vui lòng đăng nhập trước.")
        return

    me = await client.get_me()
    print(f"🚀 Bắt đầu quét và tải dữ liệu chat từ tài khoản: {me.first_name} (@{me.username or 'NoUsername'})")
    
    chats_data = []
    dialog_count = 0

    print("⏳ Đang tải danh sách các cuộc hội thoại...")
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        name = dialog.name or "Unknown"
        
        # Bỏ qua các bot hệ thống chính thức của Telegram nếu cần
        if isinstance(entity, User) and entity.bot:
            continue

        ctype = "personal_chat"
        if isinstance(entity, Channel):
            if entity.megagroup:
                ctype = "private_supergroup"
            else:
                ctype = "public_channel"
        elif isinstance(entity, Chat):
            ctype = "private_group"

        print(f"  [{dialog_count + 1}] Đang tải chat: {name} ({ctype})...", end="\r")

        messages_list = []
        try:
            async for msg in client.iter_messages(entity, limit=limit_per_chat):
                if not msg.text:
                    continue
                
                sender_name = "Khách hàng"
                if msg.sender:
                    if isinstance(msg.sender, User):
                        sender_name = f"{msg.sender.first_name or ''} {msg.sender.last_name or ''}".strip() or msg.sender.username or "User"
                    else:
                        sender_name = getattr(msg.sender, 'title', 'Group')
                elif msg.out:
                    sender_name = me.first_name or "Easy Trip"

                msg_obj = {
                    "id": msg.id,
                    "type": "message",
                    "date": msg.date.strftime("%Y-%m-%dT%H:%M:%S") if msg.date else "",
                    "from": sender_name,
                    "text": msg.text.strip()
                }
                messages_list.append(msg_obj)
        except Exception as e:
            # Bỏ qua nếu không có quyền đọc (ví dụ channel cấm đọc)
            pass

        # Đảo ngược lại thứ tự thời gian tăng dần
        messages_list.reverse()

        if len(messages_list) >= 3:
            chats_data.append({
                "id": dialog.id,
                "name": name,
                "type": ctype,
                "messages": messages_list
            })
            dialog_count += 1

        if dialog_count >= max_chats:
            break

    print(f"\n✅ Đã tải thành công {len(chats_data)} cuộc hội thoại có nội dung tương tác!")

    output_payload = {
        "about": "Exported automatically via Telethon for Easy Trip & Visa Training",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chats": {
            "list": chats_data
        }
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, ensure_ascii=False, indent=2)

    print(f"💾 Dữ liệu thô đã được lưu vào file: {OUTPUT_FILE}")
    await client.disconnect()

if __name__ == "__main__":
    limit = 300
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])
    asyncio.run(export_chats(limit_per_chat=limit))
