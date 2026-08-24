import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")

async def get_tenant_access_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    data = {"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=data)
        r.raise_for_status()
        return r.json().get("tenant_access_token")

async def sync_qa_files_to_lark():
    token = await get_tenant_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    files_to_sync = [
        "extracted_qa_zalo_docx.json",
        "extracted_qa_meta.json"
    ]
    
    total_pushed = 0
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records/batch_create"
    
    for filename in files_to_sync:
        if not os.path.exists(filename):
            print(f"Skipping {filename} (not found)")
            continue
            
        with open(filename, "r", encoding="utf-8") as f:
            qa_list = json.load(f)
            
        print(f"\n🚀 Đang đồng bộ {len(qa_list)} cặp Q&A từ {filename} lên Lark Base...")
        
        batch_size = 100
        async with httpx.AsyncClient(timeout=30) as client:
            for i in range(0, len(qa_list), batch_size):
                batch = qa_list[i:i+batch_size]
                payload = {
                    "records": [
                        {
                            "fields": {
                                "Question": qa.get("question", ""),
                                "Answer": qa.get("answer", "")
                            }
                        }
                        for qa in batch
                    ]
                }
                res = await client.post(url, json=payload, headers=headers)
                if res.status_code == 200:
                    print(f"  ✅ Batch {i//batch_size + 1} ({len(batch)} records): Thành công")
                    total_pushed += len(batch)
                else:
                    print(f"  ❌ Batch {i//batch_size + 1}: Lỗi {res.text[:120]}")
                    
    print(f"\n🎉 HOÀN THÀNH: Đã đồng bộ tổng cộng {total_pushed} cặp Q&A mới lên Lark Base!")

if __name__ == "__main__":
    asyncio.run(sync_qa_files_to_lark())
