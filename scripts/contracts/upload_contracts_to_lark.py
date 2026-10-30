"""
scripts/upload_contracts_to_lark.py - TỰ ĐỘNG UPLOAD FILE HỢP ĐỒNG LÊN CỘT 'HỢP ĐỒNG' LARK BASE CRM
"""

import os
import sys
import re
import json
import asyncio
import httpx
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
TABLE_ID = "tbluosVi3sQS9gIS"
# Real Bitable app_token for Data KH
REAL_APP_TOKEN = "QIdAbCjeuaa6oxs9fyGjrHNapsh"


async def get_tenant_access_token() -> str | None:
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET})
        return r.json().get("tenant_access_token")


async def upload_pdf_to_lark(client: httpx.AsyncClient, headers: dict, pdf_path: str) -> str | None:
    """Upload PDF lên Lark Drive Media và trả về file_token"""
    if not os.path.exists(pdf_path):
        return None
    file_size = os.path.getsize(pdf_path)
    file_name = os.path.basename(pdf_path)
    upload_url = "https://open.larksuite.com/open-apis/drive/v1/medias/upload_all"

    try:
        with open(pdf_path, "rb") as f:
            files = {"file": (file_name, f, "application/pdf")}
            data = {
                "file_name": file_name,
                "parent_type": "bitable_file",
                "parent_node": REAL_APP_TOKEN,
                "size": str(file_size)
            }
            res = await client.post(upload_url, headers=headers, data=data, files=files)
            res_json = res.json()
            if res_json.get("code") == 0:
                return res_json.get("data", {}).get("file_token")
            else:
                print(f"⚠️ Lỗi upload {file_name}: {res_json.get('msg')}")
                return None
    except Exception as e:
        print(f"⚠️ Ngoại lệ upload {file_name}: {e}")
        return None


async def sync_contracts_to_lark_base():
    token = await get_tenant_access_token()
    if not token:
        print("❌ Không lấy được Lark Token!")
        return

    headers = {"Authorization": f"Bearer {token}"}
    headers_json = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    print("🔄 Đang tải danh sách toàn bộ khách hàng từ CRM Lark Base...")
    all_records = []
    page_token = None
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            p_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{TABLE_ID}/records?page_size=500"
            if page_token:
                p_url += f"&page_token={page_token}"
            r_rec = await client.get(p_url, headers=headers)
            data_res = r_rec.json().get("data", {})
            items = data_res.get("items", [])
            all_records.extend(items)
            if not data_res.get("has_more"):
                break
            page_token = data_res.get("page_token")

    print(f"📊 Tổng số bản ghi trên CRM: {len(all_records)}")

    # Đọc snapshot hợp đồng hiện tại
    snapshot_path = os.path.join(ROOT_DIR, "contract_snapshot.json")
    if not os.path.exists(snapshot_path):
        snapshot_path = os.path.join(ROOT_DIR, "data", "contracts_and_crm", "contract_snapshot.json")
    if not os.path.exists(snapshot_path):
        print("❌ Không tìm thấy contract_snapshot.json! Hãy chạy tạo hợp đồng trước.")
        return

    with open(snapshot_path, "r", encoding="utf-8") as f_snap:
        snapshot = json.load(f_snap)

    print(f"📂 Snapshot chứa {len(snapshot)} hợp đồng cần kiểm tra upload.")

    # Tạo map từ clean_name -> record_id và thông tin record
    crm_map = {}
    for it in all_records:
        rec_id = it.get("record_id")
        fields = it.get("fields", {})
        name_val = str(fields.get("Tên khách (Name)", "") or "").strip()
        if name_val:
            clean_key = re.sub(r'[^a-zA-Z0-9]', '', name_val.upper())
            crm_map[clean_key] = {
                "record_id": rec_id,
                "name": name_val,
                "existing_contract": fields.get("Hợp đồng")
            }

    contracts_dir = os.path.join(ROOT_DIR, "output_contracts")
    sem = asyncio.Semaphore(5)

    success_count = 0
    skipped_count = 0
    error_count = 0

    async def process_customer(customer_name, c_data, idx, total):
        nonlocal success_count, skipped_count, error_count
        clean_key = re.sub(r'[^a-zA-Z0-9]', '', customer_name.upper())
        rec_info = crm_map.get(clean_key)
        if not rec_info:
            error_count += 1
            return

        rec_id = rec_info["record_id"]
        existing_contract = rec_info.get("existing_contract")

        pdf_filename = c_data.get("pdf_filename")
        pdf_path = os.path.join(contracts_dir, pdf_filename)
        if not os.path.exists(pdf_path):
            pdf_path = os.path.join(ROOT_DIR, "data", "contracts_and_crm", "output_contracts", pdf_filename)
        if not os.path.exists(pdf_path):
            error_count += 1
            return

        # Kiểm tra nếu đã có file hợp đồng đính kèm trên CRM
        if existing_contract and isinstance(existing_contract, list) and len(existing_contract) > 0:
            skipped_count += 1
            return

        async with sem:
            async with httpx.AsyncClient(timeout=45) as c_client:
                # 1. Upload PDF
                file_token = await upload_pdf_to_lark(c_client, headers, pdf_path)
                if not file_token:
                    print(f"[{idx}/{total}] ❌ Lỗi upload file lên Lark: {customer_name}")
                    error_count += 1
                    return

                # 2. Update record (có retry khi Lark báo 1254607 Data not ready)
                update_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{TABLE_ID}/records/{rec_id}"
                payload = {
                    "fields": {
                        "Hợp đồng": [
                            {"file_token": file_token}
                        ]
                    }
                }
                updated_ok = False
                for attempt in range(4):
                    res_up = await c_client.put(update_url, headers=headers_json, json=payload)
                    if res_up.status_code == 200 and res_up.json().get("code") == 0:
                        print(f"[{idx}/{total}] ✅ Đã đính kèm HĐ lên Lark CRM: {customer_name} ({pdf_filename})")
                        success_count += 1
                        updated_ok = True
                        break
                    await asyncio.sleep(1.5 * (attempt + 1))
                if not updated_ok:
                    print(f"[{idx}/{total}] ❌ Lỗi update bản ghi {customer_name}: {res_up.text}")
                    error_count += 1

                await asyncio.sleep(0.15)

    tasks = []
    total_items = len(snapshot)
    for idx, (cust_name, cust_data) in enumerate(snapshot.items(), 1):
        tasks.append(process_customer(cust_name, cust_data, idx, total_items))

    await asyncio.gather(*tasks)

    print("\n" + "=" * 65)
    print("🎉 HOÀN TẤT ĐỒNG BỘ HỢP ĐỒNG LÊN LARK BASE CRM!")
    print(f"  ✅ Đã tải lên mới: {success_count} hợp đồng")
    print(f"  ⏭️ Đã có sẵn (bỏ qua): {skipped_count} hợp đồng")
    print(f"  ⚠️ Lỗi / Không tìm thấy: {error_count} hồ sơ")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(sync_contracts_to_lark_base())
