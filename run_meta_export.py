import os
import sys
import json
import httpx
import asyncio
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PAGE_TOKEN = "EAAUeesZAub7ABSVfFdaZBwAaps6rkEUYAoqLTkTEerc06wfYDZCJjgZC0A5glicvLoY5YVwbaXUfmmlgnOfQEPckE7gf05CPeuQhq3mhQp7EOZBL11Rxiy1PBXsFunMryhTPbsfuoYwXXSB4AN15LMAos3cZBkfXMJGq8LZBZCHODgLhe9hnVcZCy1LP3HSfA3ZBwSUEMX449PA4IKT9gUj7Q1aNz9vtlRBpZB5PiUJRCIEQh1dINQ0HzhkFlJUCA8HJnPdDEc6QZAkzm8NrykGZCSmznWFKkPUFScypTCrSaBAZDZD"
OUTPUT_FILE = "meta_chat.json"

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        print("📡 Đang kết nối tới Meta Graph API với Page Token...")
        # 1. Xác thực Page
        r = await client.get("https://graph.facebook.com/v20.0/me", params={"access_token": PAGE_TOKEN})
        page_info = r.json()
        
        if "error" in page_info:
            print(f"❌ Lỗi xác thực Page Token: {page_info['error']}")
            return

        page_name = page_info.get("name", "Fanpage")
        page_id = page_info.get("id")
        print(f"✅ Đã kết nối thành công tới Fanpage: {page_name} (ID: {page_id})")

        # 2. Lấy danh sách hội thoại
        conv_url = f"https://graph.facebook.com/v20.0/{page_id}/conversations"
        params = {
            "access_token": PAGE_TOKEN,
            "fields": "id,updated_time,participants,messages{id,message,from,created_time}",
            "limit": 50
        }

        all_chats = []
        total_msgs = 0
        current_url = conv_url
        current_params = params

        print(f"🚀 Bắt đầu quét và tải dữ liệu chat từ hộp thư {page_name}...")

        while current_url and len(all_chats) < 250:
            r_conv = await client.get(current_url, params=current_params)
            if r_conv.status_code != 200:
                print(f"\n❌ Lỗi từ Meta API ({r_conv.status_code}): {r_conv.text}")
                break

            data = r_conv.json()
            conv_list = data.get("data", [])
            if not conv_list:
                break

            for conv in conv_list:
                participants = conv.get("participants", {}).get("data", [])
                customer_name = "Khách hàng"
                for pt in participants:
                    if str(pt.get("id")) != str(page_id):
                        customer_name = pt.get("name", "Khách hàng")
                        break

                raw_messages = conv.get("messages", {}).get("data", [])
                formatted_msgs = []
                for m in reversed(raw_messages):
                    text = m.get("message", "").strip()
                    if not text:
                        continue
                    sender = m.get("from", {}).get("name", "User")
                    formatted_msgs.append({
                        "id": m.get("id"),
                        "from": sender,
                        "text": text,
                        "date": m.get("created_time")
                    })

                if len(formatted_msgs) >= 2:
                    all_chats.append({
                        "id": conv.get("id"),
                        "name": customer_name,
                        "type": "meta_page_inbox",
                        "messages": formatted_msgs
                    })
                    total_msgs += len(formatted_msgs)
                    print(f"  [+] Đã tải: {customer_name[:30]:30s} ({len(formatted_msgs)} tin nhắn)", end="\r")

            paging = data.get("paging", {})
            current_url = paging.get("next")
            current_params = {}

        print(f"\n\n🎉 HOÀN THÀNH: Đã tải thành công {len(all_chats)} cuộc hội thoại ({total_msgs} tin nhắn) từ Fanpage {page_name}!")
        payload = {
            "about": f"Exported from Meta Page {page_name}",
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "chats": {
                "list": all_chats
            }
        }
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"💾 Đã lưu dữ liệu thô vào: {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
