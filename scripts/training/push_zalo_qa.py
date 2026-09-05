import os, json, httpx, asyncio
from dotenv import load_dotenv

load_dotenv()

async def push_to_lark():
    LARK_APP_ID = os.getenv("LARK_APP_ID")
    LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
    LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
    TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")
    
    qa_file = "extracted_qa_zalo_docx.json"
    if not os.path.exists(qa_file):
        print(f"Khong tim thay file {qa_file}")
        return
        
    with open(qa_file, "r", encoding="utf-8") as f:
        qa_list = json.load(f)
    
    print(f"Dang day {len(qa_list)} cap Q&A tu Zalo docx len Lark...")

    async with httpx.AsyncClient(timeout=30) as http:
        auth = await http.post(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
        )
        token = auth.json().get("tenant_access_token")
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records/batch_create"
        
        batch_size = 100
        for i in range(0, len(qa_list), batch_size):
            batch = qa_list[i:i+batch_size]
            payload = {"records": [{"fields": {"Question": qa["question"], "Answer": qa["answer"]}} for qa in batch]}
            r = await http.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                print(f"  Batch {i//100+1}: OK")
            else:
                print(f"  Batch {i//100+1}: LOI - {r.text[:100]}")

if __name__ == "__main__":
    asyncio.run(push_to_lark())
