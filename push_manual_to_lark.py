import os, httpx, asyncio
from dotenv import load_dotenv

load_dotenv()

async def push_manual_to_lark():
    LARK_APP_ID = os.getenv("LARK_APP_ID")
    LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
    LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
    TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")
    
    knowledge_file = "knowledge.txt"
    if not os.path.exists(knowledge_file):
        print(f"Khong tim thay file {knowledge_file}")
        return
        
    with open(knowledge_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Chia nho theo cac tieu de gach ngang
    sections = content.split("-------------------------------------------------------------------")
    qa_list = []
    
    for section in sections:
        lines = section.strip().split("\n")
        if not lines or len(lines) < 2:
            continue
            
        # Lay tieu de lam cau hoi, phan con lai lam cau tra loi
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        
        if title and body:
            qa_list.append({"question": f"Thông tin về: {title}", "answer": body})

    print(f"Dang day {len(qa_list)} vung kien thuc tu knowledge.txt len Lark...")

    async with httpx.AsyncClient(timeout=30) as http:
        auth = await http.post(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
        )
        token = auth.json().get("tenant_access_token")
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records/batch_create"
        
        payload = {"records": [{"fields": {"Question": qa["question"], "Answer": qa["answer"]}} for qa in qa_list]}
        r = await http.post(url, json=payload, headers=headers)
        
        if r.status_code == 200:
            print(f"=== THANH CONG ===\nToan bo quy tac nghiep vu da duoc day len Lark Base.")
        else:
            print(f"LOI - {r.text}")

if __name__ == "__main__":
    asyncio.run(push_manual_to_lark())
