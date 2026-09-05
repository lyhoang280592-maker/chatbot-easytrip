"""
sync_knowledge_crm.py - Đồng bộ 2 chiều giữa Máy tính và CRM Lark Base
- Chạy: python sync_knowledge_crm.py push  (Đẩy toàn bộ Q&A từ máy lên CRM)
- Chạy: python sync_knowledge_crm.py pull  (Tải toàn bộ Q&A từ CRM về máy khác)
"""

import os
import sys
import json
import asyncio
import httpx
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

load_dotenv()

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")

LOCAL_QA_FILES = [
    "extracted_qa_telegram.json",
    "extracted_qa_meta.json",
    "extracted_qa_zalo_docx.json",
    "extracted_qa_excel.json",
    "manual_qa.json",
]

CRM_DOWNLOADED_FILE = "extracted_qa_from_crm.json"

async def get_tenant_access_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    data = {"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(url, json=data)
        r.raise_for_status()
        return r.json().get("tenant_access_token")

# =====================================================================
# 1. ĐẨY TOÀN BỘ DỮ LIỆU TỪ MÁY LÊN CRM LARK BASE
# =====================================================================
async def push_all_to_crm():
    print("=" * 60)
    print("🚀 BẮT ĐẦU ĐẨY TOÀN BỘ TRI THỨC TỪ MÁY LÊN CRM LARK BASE")
    print("=" * 60)

    # 1. Gom tất cả Q&A từ các file local
    all_qa = []
    seen = set()
    for fname in LOCAL_QA_FILES:
        if os.path.exists(fname):
            try:
                with open(fname, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        q = (item.get("question") or item.get("Question") or "").strip()
                        a = (item.get("answer") or item.get("Answer") or "").strip()
                        if len(q) > 5 and len(a) > 5:
                            q_key = q.lower()[:100]
                            if q_key not in seen:
                                seen.add(q_key)
                                all_qa.append({"Question": q, "Answer": a})
                    print(f"  -> Đọc file '{fname}': tìm thấy {len(data)} cặp Q&A")
            except Exception as e:
                print(f"  Lỗi khi đọc file {fname}: {e}")

    print(f"\n📊 Tổng cộng có {len(all_qa)} cặp Q&A độc nhất chuẩn bị đồng bộ lên Lark Base...")

    token = await get_tenant_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records/batch_create"

    batch_size = 100
    total_pushed = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for i in range(0, len(all_qa), batch_size):
            batch = all_qa[i:i+batch_size]
            payload = {
                "records": [
                    {"fields": {"Question": item["Question"], "Answer": item["Answer"]}}
                    for item in batch
                ]
            }
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code == 200:
                print(f"  ✅ Đã tải lên Lô {i//batch_size + 1} ({len(batch)} câu Q&A)")
                total_pushed += len(batch)
            else:
                print(f"  ⚠️ Lỗi khi tải lô {i//batch_size + 1}: {res.text[:100]}")

    print(f"\n🎉 HOÀN THÀNH: Đã đồng bộ thành công {total_pushed} cặp Q&A lên bảng 'Kho_tri_thức' CRM!")

# =====================================================================
# 2. TẢI TOÀN BỘ TRI THỨC TỪ CRM LARK BASE VỀ MÁY TÍNH KHÁC
# =====================================================================
async def pull_from_crm():
    print("=" * 60)
    print("📥 BẮT ĐẦU TẢI TOÀN BỘ TRI THỨC TỪ CRM LARK BASE VỀ MÁY TÍNH NÀY")
    print("=" * 60)

    token = await get_tenant_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    base_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records"

    all_downloaded = []
    page_token = None
    page_num = 1

    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            params = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token

            res = await client.get(base_url, headers=headers, params=params)
            if res.status_code != 200:
                print(f"❌ Lỗi từ Lark API: {res.status_code} - {res.text[:200]}")
                break

            data = res.json().get("data", {})
            items = data.get("items", [])
            if not items:
                break

            valid_count = 0
            for item in items:
                fields = item.get("fields", {})
                q = fields.get("Question") or fields.get("question") or ""
                a = fields.get("Answer") or fields.get("answer") or ""
                if isinstance(q, str) and isinstance(a, str) and len(q.strip()) > 3 and len(a.strip()) > 3:
                    all_downloaded.append({
                        "question": q.strip(),
                        "answer": a.strip()
                    })
                    valid_count += 1

            print(f"  -> Tải Trang {page_num}: Lấy được {valid_count} cặp Q&A (Tổng cộng hiện tại: {len(all_downloaded)})")

            has_more = data.get("has_more", False)
            if not has_more:
                break
            page_token = data.get("page_token")
            page_num += 1

    # Lưu vào file JSON local
    with open(CRM_DOWNLOADED_FILE, "w", encoding="utf-8") as f:
        json.dump(all_downloaded, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 HOÀN THÀNH XUẤT SẮC!")
    print(f"💾 Đã lưu toàn bộ {len(all_downloaded)} cặp Q&A từ CRM vào file: {CRM_DOWNLOADED_FILE}")
    print(f"🤖 RAG Engine trên máy này sẽ tự động nạp toàn bộ tri thức này vào Chatbot.")

if __name__ == "__main__":
    action = "pull"
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["push", "up", "upload"]:
        action = "push"
    
    if action == "push":
        asyncio.run(push_all_to_crm())
    else:
        asyncio.run(pull_from_crm())
