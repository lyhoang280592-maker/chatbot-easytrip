"""
Công cụ trích xuất dữ liệu chat từ Meta Business / Facebook Fanpage qua Graph API
Hỗ trợ cả 2 nguồn:
1. Kết nối trực tiếp qua Meta Graph API (Page Access Token).
2. Đọc thư mục xuất dữ liệu JSON từ Meta / Facebook (sửa lỗi mã hóa font tiếng Việt của Facebook).
"""

import os
import sys
import json
import re
import httpx
from datetime import datetime
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

OUTPUT_FILE = "meta_chat.json"

# Sửa lỗi mã hóa ký tự tiếng Việt đặc thù của Facebook JSON export
def fix_fb_encoding(text: str) -> str:
    if not isinstance(text, str):
        return ""
    try:
        return text.encode('latin1').decode('utf-8')
    except Exception:
        return text

# =====================================================================
# 1. KÉO DỮ LIỆU TỪ META GRAPH API (FANPAGE / META BUSINESS)
# =====================================================================

async def export_from_meta_api(page_access_token: str, page_id: str = "me", max_conversations: int = 150):
    print(f"📡 Đang kết nối tới Meta Graph API với Token...")
    base_url = f"https://graph.facebook.com/v20.0/{page_id}/conversations"
    params = {
        "access_token": page_access_token,
        "fields": "id,updated_time,participants,messages{id,message,from,created_time}",
        "limit": 50
    }

    all_chats = []
    total_messages = 0

    async with httpx.AsyncClient(timeout=30) as client:
        url = base_url
        current_params = params

        while url and len(all_chats) < max_conversations:
            r = await client.get(url, params=current_params)
            if r.status_code != 200:
                print(f"❌ Lỗi từ Meta API: {r.status_code} - {r.text[:300]}")
                break

            data = r.json()
            convs = data.get("data", [])
            if not convs:
                break

            for conv in convs:
                participants = conv.get("participants", {}).get("data", [])
                customer_name = "Khách hàng"
                for p in participants:
                    if p.get("id") != page_id:
                        customer_name = p.get("name", "Khách hàng")
                        break

                raw_msgs = conv.get("messages", {}).get("data", [])
                formatted_msgs = []
                for m in reversed(raw_msgs):
                    msg_text = m.get("message", "").strip()
                    if not msg_text:
                        continue
                    sender = m.get("from", {}).get("name", "User")
                    formatted_msgs.append({
                        "id": m.get("id"),
                        "from": sender,
                        "text": msg_text,
                        "date": m.get("created_time")
                    })

                if len(formatted_msgs) >= 2:
                    all_chats.append({
                        "id": conv.get("id"),
                        "name": customer_name,
                        "type": "meta_page_inbox",
                        "messages": formatted_msgs
                    })
                    total_messages += len(formatted_msgs)

            # Phân trang (Paging)
            paging = data.get("paging", {})
            url = paging.get("next")
            current_params = {} # params đã nằm trong next URL

    print(f"✅ Đã tải thành công {len(all_chats)} cuộc hội thoại ({total_messages} tin nhắn) từ Meta API!")
    
    payload = {
        "about": "Exported from Meta Business / Facebook Page API",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chats": {
            "list": all_chats
        }
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"💾 Đã lưu vào file: {OUTPUT_FILE}")
    return all_chats

# =====================================================================
# 2. QUÉT VÀ ĐỌC THƯ MỤC XUẤT JSON TỪ FACEBOOK / META BUSINESS
# =====================================================================

def export_from_local_folder(folder_path: str):
    print(f"📂 Đang quét các file tin nhắn Facebook trong thư mục: {folder_path} ...")
    all_chats = []
    total_messages = 0

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".json") and "message" in file.lower():
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)

                    title = fix_fb_encoding(data.get("title", "Khách hàng"))
                    messages_raw = data.get("messages", [])
                    formatted_msgs = []

                    # Đảo ngược lại theo thứ tự thời gian
                    for m in reversed(messages_raw):
                        content = fix_fb_encoding(m.get("content", "")).strip()
                        if not content:
                            continue
                        sender = fix_fb_encoding(m.get("sender_name", "User"))
                        formatted_msgs.append({
                            "from": sender,
                            "text": content,
                            "date": datetime.fromtimestamp(m.get("timestamp_ms", 0)/1000).strftime("%Y-%m-%d %H:%M:%S") if m.get("timestamp_ms") else ""
                        })

                    if len(formatted_msgs) >= 2:
                        all_chats.append({
                            "id": title,
                            "name": title,
                            "type": "facebook_inbox",
                            "messages": formatted_msgs
                        })
                        total_messages += len(formatted_msgs)
                except Exception as e:
                    print(f"  Lỗi khi đọc file {file}: {e}")

    print(f"✅ Đã quét được {len(all_chats)} cuộc hội thoại ({total_messages} tin nhắn) từ file xuất Facebook!")
    payload = {
        "about": "Exported from Facebook / Meta JSON export",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "chats": {
            "list": all_chats
        }
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"💾 Đã lưu dữ liệu vào: {OUTPUT_FILE}")
    return all_chats

if __name__ == "__main__":
    import asyncio
    token = os.getenv("FB_PAGE_ACCESS_TOKEN") or os.getenv("META_PAGE_ACCESS_TOKEN", "")
    page_id = os.getenv("META_PAGE_ID", "me")
    
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        export_from_local_folder(sys.argv[1])
    elif token:
        asyncio.run(export_from_meta_api(token, page_id))
    else:
        print("💡 Hướng dẫn sử dụng:")
        print("1. Nếu dùng Meta Graph API: Cung cấp PAGE_ACCESS_TOKEN hoặc thêm vào .env")
        print("2. Nếu dùng thư mục file JSON xuất từ Facebook: python export_meta_chats.py <duong_dan_thu_muc>")
