"""
sync_lark_storage_and_passports.py - ĐỒNG BỘ & LƯU TRỮ HỢP ĐỒNG (PDF) VÀ HỘ CHIẾU LÊN LARK CLOUD
Chức năng:
1. Tạo thư mục hộ chiếu khách hàng cục bộ tương ứng 1-1 với hợp đồng (output_passports_01_08_den_06_09 & output_passports).
2. Upload toàn bộ 154 file PDF hợp đồng lên bảng lưu trữ "Kho Lưu Trữ Hợp Đồng (PDF)" trên Lark Base (Song song siêu tốc).
3. Upload toàn bộ 154 file ảnh Hộ chiếu lên bảng lưu trữ "Kho Lưu Trữ Hộ Chiếu (Passports)" trên Lark Base (Song song siêu tốc).
"""

import os
import sys
import re
import json
import shutil
import asyncio
import httpx
from datetime import datetime
from dotenv import load_dotenv

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN", "JIUZwOYhjicckYknQ2ajuCFUpsb")
REAL_APP_TOKEN = "QIdAbCjeuaa6oxs9fyGjrHNapsh"

TABLE_MASTER_CRM = "tbluosVi3sQS9gIS"        # Data KH 2026
TABLE_CONTRACTS_STORAGE = "tblyIA25aQWxSVGD" # Kho Lưu Trữ Hợp Đồng (PDF)
TABLE_PASSPORTS_STORAGE = "tblQv1exYfJvnUPS"  # Kho Lưu Trữ Hộ Chiếu (Passports)


def clean_name(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '', str(name).upper())


async def get_tenant_access_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET})
        return r.json().get("tenant_access_token")


def organize_local_passports():
    """Tổ chức thư mục Hộ Chiếu khách hàng tương ứng 1-1 với Hợp đồng"""
    print("\n" + "=" * 65)
    print(" 📂 [BƯỚC 1/3] TỔ CHỨC THƯ MỤC HỘ CHIẾU TƯƠNG ỨNG VỚI HỢP ĐỒNG")
    print("=" * 65)

    now_dt = datetime.now()
    end_tag = now_dt.strftime("%d_%m")
    
    target_dir_dated = os.path.join(ROOT_DIR, f"output_passports_01_08_den_{end_tag}")
    target_dir_root = os.path.join(ROOT_DIR, "output_passports")
    
    # Xóa sạch thư mục cũ để không còn file rác từ lần chạy trước
    if os.path.exists(target_dir_dated):
        shutil.rmtree(target_dir_dated, ignore_errors=True)
    if os.path.exists(target_dir_root):
        shutil.rmtree(target_dir_root, ignore_errors=True)
    
    dir_kl_dated = os.path.join(target_dir_dated, "Khach_Le")
    dir_dl_dated = os.path.join(target_dir_dated, "Dai_Ly")
    dir_kl_root = os.path.join(target_dir_root, "Khach_Le")
    dir_dl_root = os.path.join(target_dir_root, "Dai_Ly")

    for d in [dir_kl_dated, dir_dl_dated, dir_kl_root, dir_dl_root]:
        os.makedirs(d, exist_ok=True)

    snapshot_file = os.path.join(ROOT_DIR, "contract_snapshot.json")
    if not os.path.exists(snapshot_file):
        snapshot_file = os.path.join(ROOT_DIR, "data", "contracts_and_crm", "contract_snapshot.json")

    if not os.path.exists(snapshot_file):
        print("❌ Không tìm thấy contract_snapshot.json!")
        return {}

    with open(snapshot_file, "r", encoding="utf-8") as f:
        contracts = json.load(f)

    pass_src_dir = os.path.join(ROOT_DIR, "downloads", "passports")
    pass_files = os.listdir(pass_src_dir) if os.path.exists(pass_src_dir) else []

    mapped_passports = {}
    copied_count = 0

    for name, c in contracts.items():
        stt = int(c.get("stt", 0))
        stt_str = f"{stt:03d}"
        passport_no = str(c.get("passport_no", "") or "").strip()
        channel_type = c.get("channel_type", "Khach_Le")
        prefix_type = "Khach_Le" if channel_type == "Khách lẻ" else "Dai_Ly"
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())

        # Tìm ảnh hộ chiếu
        found_pass_file = None
        if passport_no and len(passport_no) >= 5 and passport_no != "Chưa có":
            for pf in pass_files:
                if passport_no in pf:
                    found_pass_file = pf
                    break
        if not found_pass_file:
            name_c = clean_name(name)
            for pf in pass_files:
                if name_c in clean_name(pf):
                    found_pass_file = pf
                    break

        if found_pass_file:
            ext = os.path.splitext(found_pass_file)[1] or ".jpg"
            new_pass_filename = f"{stt_str}_Ho_Chieu_{prefix_type}_{safe_name}_{passport_no}{ext}"
            src_path = os.path.join(pass_src_dir, found_pass_file)
            
            if prefix_type == "Khach_Le":
                dst_dated = os.path.join(dir_kl_dated, new_pass_filename)
                dst_root = os.path.join(dir_kl_root, new_pass_filename)
            else:
                dst_dated = os.path.join(dir_dl_dated, new_pass_filename)
                dst_root = os.path.join(dir_dl_root, new_pass_filename)

            shutil.copyfile(src_path, dst_dated)
            shutil.copyfile(src_path, dst_root)
            mapped_passports[name] = dst_root
            copied_count += 1

    print(f"✅ Đã tổ chức và sao chép {copied_count}/{len(contracts)} file Hộ chiếu vào:")
    print(f"   👉 '{target_dir_dated}'")
    print(f"   👉 '{target_dir_root}'")
    return mapped_passports


async def upload_single_file(client: httpx.AsyncClient, file_path: str, mime_type: str, headers: dict) -> str | None:
    if not os.path.exists(file_path):
        return None
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    data = {
        "file_name": file_name,
        "parent_type": "bitable_file",
        "parent_node": REAL_APP_TOKEN,
        "size": str(file_size)
    }
    for attempt in range(3):
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_name, f, mime_type)}
                r = await client.post("https://open.larksuite.com/open-apis/drive/v1/medias/upload_all", data=data, files=files, headers=headers)
                res_json = r.json()
                if r.status_code == 200 and res_json.get("code") == 0:
                    return res_json.get("data", {}).get("file_token")
        except Exception as e:
            if attempt == 2:
                print(f"⚠️ Lỗi upload {file_name}: {e}")
            await asyncio.sleep(1.0 * (attempt + 1))
    return None


async def ensure_field_formatting(client: httpx.AsyncClient, headers: dict):
    """Đảm bảo các trường STT và Tổng tiền HĐ hiển thị dạng số nguyên (không có .0 ở sau)"""
    for tid in [TABLE_CONTRACTS_STORAGE, TABLE_PASSPORTS_STORAGE]:
        try:
            rf = await client.get(f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{tid}/fields", headers=headers)
            for f in rf.json().get("data", {}).get("items", []):
                fname = f.get("field_name")
                fid = f.get("field_id")
                if fname in ["STT", "Tổng tiền HĐ"] and f.get("type") == 2:
                    current_prop = f.get("property") or {}
                    if current_prop.get("formatter") != "0":
                        up_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{tid}/fields/{fid}"
                        await client.put(up_url, json={"field_name": fname, "type": 2, "property": {"formatter": "0"}}, headers=headers)
        except Exception as e:
            pass


async def get_all_record_ids(client: httpx.AsyncClient, table_id: str, headers: dict) -> list[str]:
    """Lấy toàn bộ record_id trong bảng BitTable (có phân trang)"""
    all_ids = []
    page_token = None
    while True:
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{table_id}/records?page_size=500"
        if page_token:
            url += f"&page_token={page_token}"
        r = await client.get(url, headers=headers)
        data = r.json().get("data") or {}
        items = data.get("items") or []
        for it in items:
            all_ids.append(it["record_id"])
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
    return all_ids


async def sync_contracts_and_passports_to_lark(mapped_passports: dict = None):
    """Tải toàn bộ Hợp đồng PDF và Hộ chiếu lên 2 kho lưu trữ trên Lark Base (Xử lý đồng thời)"""
    token = await get_tenant_access_token()
    if not token:
        print("❌ Không lấy được token Lark!")
        return

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    headers_form = {"Authorization": f"Bearer {token}"}

    snapshot_file = os.path.join(ROOT_DIR, "contract_snapshot.json")
    if not os.path.exists(snapshot_file):
        snapshot_file = os.path.join(ROOT_DIR, "data", "contracts_and_crm", "contract_snapshot.json")

    with open(snapshot_file, "r", encoding="utf-8") as f:
        contracts = json.load(f)

    if mapped_passports is None:
        mapped_passports = organize_local_passports()

    sorted_contracts = sorted(contracts.items(), key=lambda x: int(x[1].get("stt", 0)))
    sem = asyncio.Semaphore(8)

    async with httpx.AsyncClient(timeout=60) as client:
        # 0. Đảm bảo định dạng trường số nguyên không có .0
        await ensure_field_formatting(client, headers)

        # -----------------------------------------------------------------
        # 1. ĐỒNG BỘ BẢNG HỢP ĐỒNG (PDF) THEO ĐÚNG THỨ TỰ 1..154
        # -----------------------------------------------------------------
        print("\n" + "=" * 65)
        print(" ☁️  [BƯỚC 2/3] UPLOAD TOÀN BỘ HỢP ĐỒNG (PDF) LÊN LARK CLOUD")
        print("=" * 65)

        pdf_dir = os.path.join(ROOT_DIR, "output_contracts")
        contract_records = []

        async def prepare_contract_record(name, c):
            async with sem:
                stt_int = int(c.get("stt", 0))
                pdf_fname = c.get("pdf_filename", "")
                pdf_path = os.path.join(pdf_dir, pdf_fname)
                if not os.path.exists(pdf_path):
                    for root, _, files in os.walk(ROOT_DIR):
                        if "output_contracts" in root and pdf_fname in files:
                            pdf_path = os.path.join(root, pdf_fname)
                            break

                file_token = await upload_single_file(client, pdf_path, "application/pdf", headers_form) if os.path.exists(pdf_path) else None
                fld = {
                    "STT": stt_int,
                    "Tên khách hàng": name.upper(),
                    "Số hộ chiếu": str(c.get("passport_no", "") or ""),
                    "Phân loại": str(c.get("channel_type", "") or ""),
                    "Loại Visa": str(c.get("visa_type", "") or ""),
                    "Ngày hạch toán": str(c.get("accounting_date", "") or ""),
                    "Tổng tiền HĐ": int(c.get("total_amount", 0) or 0)
                }
                if file_token:
                    fld["File Hợp Đồng (PDF)"] = [{"file_token": file_token, "name": pdf_fname}]
                return (stt_int, {"fields": fld})

        results_c = await asyncio.gather(*(prepare_contract_record(n, c) for n, c in sorted_contracts))
        results_c.sort(key=lambda x: x[0])
        contract_records = [x[1] for x in results_c]

        # Xóa các bản ghi cũ và chèn mới theo đúng thứ tự
        old_ids_c = await get_all_record_ids(client, TABLE_CONTRACTS_STORAGE, headers)
        if old_ids_c:
            for i in range(0, len(old_ids_c), 500):
                await client.post(f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{TABLE_CONTRACTS_STORAGE}/records/batch_delete", json={"records": old_ids_c[i:i+500]}, headers=headers)

        for i in range(0, len(contract_records), 50):
            await client.post(f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{TABLE_CONTRACTS_STORAGE}/records/batch_create", json={"records": contract_records[i:i+50]}, headers=headers)
            await asyncio.sleep(0.3)

        print(f"✅ Hoàn tất upload {len(contract_records)} Hợp đồng PDF theo thứ tự chuẩn 1..{len(contract_records)} lên bảng 'Kho Lưu Trữ Hợp Đồng (PDF)'!")

        # -----------------------------------------------------------------
        # 2. ĐỒNG BỘ BẢNG HỘ CHIẾU THEO ĐÚNG THỨ TỰ
        # -----------------------------------------------------------------
        print("\n" + "=" * 65)
        print(" 🛂 [BƯỚC 3/3] UPLOAD TOÀN BỘ HỘ CHIẾU KHÁCH HÀNG LÊN LARK CLOUD")
        print("=" * 65)

        async def prepare_passport_record(name, c):
            async with sem:
                stt_int = int(c.get("stt", 0))
                passport_no = str(c.get("passport_no", "") or "").strip()
                channel_type = c.get("channel_type", "Khách lẻ")
                nationality = str(c.get("nationality", "") or "")

                found_pass_file = mapped_passports.get(name)
                file_token = await upload_single_file(client, found_pass_file, "image/jpeg", headers_form) if found_pass_file and os.path.exists(found_pass_file) else None
                await asyncio.sleep(0.1)

                fld = {
                    "STT": stt_int,
                    "Tên khách hàng": name.upper(),
                    "Số hộ chiếu": passport_no,
                    "Quốc tịch": nationality,
                    "Phân loại": channel_type
                }
                if file_token:
                    fld["File Hộ Chiếu"] = [{"file_token": file_token, "name": os.path.basename(found_pass_file)}]
                return (stt_int, {"fields": fld})

        results_p = await asyncio.gather(*(prepare_passport_record(n, c) for n, c in sorted_contracts))
        results_p.sort(key=lambda x: x[0])
        passport_records = [x[1] for x in results_p]

        # Xóa các bản ghi cũ và chèn mới theo đúng thứ tự
        old_ids_p = await get_all_record_ids(client, TABLE_PASSPORTS_STORAGE, headers)
        if old_ids_p:
            for i in range(0, len(old_ids_p), 500):
                await client.post(f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{TABLE_PASSPORTS_STORAGE}/records/batch_delete", json={"records": old_ids_p[i:i+500]}, headers=headers)

        for i in range(0, len(passport_records), 50):
            await client.post(f"https://open.larksuite.com/open-apis/bitable/v1/apps/{REAL_APP_TOKEN}/tables/{TABLE_PASSPORTS_STORAGE}/records/batch_create", json={"records": passport_records[i:i+50]}, headers=headers)
            await asyncio.sleep(0.3)

        print(f"✅ Hoàn tất upload {len(passport_records)} Hộ chiếu theo thứ tự chuẩn 1..{len(passport_records)} lên bảng 'Kho Lưu Trữ Hộ Chiếu (Passports)'!")


async def main():
    mapped = organize_local_passports()
    await sync_contracts_and_passports_to_lark(mapped)
    print("\n" + "=" * 65)
    print(" 🎉 TOÀN BỘ HỢP ĐỒNG VÀ HỘ CHIẾU ĐÃ ĐƯỢC ĐỒNG BỘ 100% LÊN LARK CLOUD!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
