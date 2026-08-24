import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
LARK_KNOWLEDGE_TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")

async def get_tenant_access_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "app_id": LARK_APP_ID,
        "app_secret": LARK_APP_SECRET
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("tenant_access_token")

async def update_lark_records():
    token = await get_tenant_access_token()
    
    # 1. Tải danh sách bản ghi hiện có
    get_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{LARK_KNOWLEDGE_TABLE_ID}/records"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(get_url, headers=headers)
        if response.status_code != 200:
            print("Lỗi khi đọc bảng Lark:", response.text)
            return
        
        records = response.json().get("data", {}).get("items", [])
        target_record_id = None
        current_answer = ""
        
        # Tìm bản ghi có câu hỏi về dàn xe buýt (bỏ qua các giá trị None)
        for r in records:
            fields = r.get("fields", {})
            q = fields.get("Question")
            if q and isinstance(q, str):
                if "xe buýt giường nằm cao cấp" in q or "dàn xe buýt" in q:
                    target_record_id = r.get("record_id")
                    current_answer = fields.get("Answer", "")
                    break
                
        # 2. Cập nhật hoặc thêm mới
        drive_link = "https://drive.google.com/file/d/1Q-1OH9gOIWyPNzLIlZ-1Wdd0zRZYxwO2/view?usp=sharing"
        new_text = f"\n🎥 Xem Video đoàn xe giường nằm Easy Trip lăn bánh trên đường (Google Drive): {drive_link}"
        
        if target_record_id:
            # Cập nhật bản ghi có sẵn
            update_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{LARK_KNOWLEDGE_TABLE_ID}/records/{target_record_id}"
            payload = {
                "fields": {
                    "Answer": (current_answer or "") + new_text
                }
            }
            res = await client.put(update_url, headers=headers, json=payload)
            if res.status_code == 200:
                print("🎉 Đã cập nhật thành công video Google Drive vào câu trả lời hiện có trên Lark Base!")
            else:
                print("Lỗi khi cập nhật:", res.text)
        else:
            # Thêm mới nếu không tìm thấy
            create_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{LARK_KNOWLEDGE_TABLE_ID}/records"
            payload = {
                "fields": {
                    "Question": "Video thực tế đoàn xe buýt giường nằm Easy Trip & Visa lăn bánh trên đường",
                    "Answer": f"Chào bạn! Dưới đây là video thực tế đoàn xe buýt giường nằm cao cấp của Easy Trip & Visa lăn bánh trên đường:\n🎥 Xem Video Google Drive: {drive_link}"
                }
            }
            res = await client.post(create_url, headers=headers, json=payload)
            if res.status_code == 200:
                print("🎉 Đã thêm mới thành công Câu hỏi đáp video Google Drive lên Lark Base!")
            else:
                print("Lỗi khi tạo mới:", res.text)

if __name__ == "__main__":
    asyncio.run(update_lark_records())
