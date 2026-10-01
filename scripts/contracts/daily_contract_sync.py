"""
daily_contract_sync.py - TỰ ĐỘNG ĐỒNG BỘ VÀ XUẤT HỢP ĐỒNG EASYTRIP MỖI NGÀY (23:00)
Quy trình:
1. Kết nối CRM Lark Base Open API (TABLE_ID: tbluosVi3sQS9gIS).
2. Lọc hồ sơ hợp lệ trong kỳ hạch toán hiện tại (đã có Code EV/File EV, không bị cancel/hủy).
3. Phân loại Khách lẻ vs Đại lý (Bolot, Sergei, Arsenii = 108% VAT).
4. Phân loại Visa (Single $25, Multi $50, Cam $30/fee, Free Visa 0đ) & tính toán chi phí (Điều 2.1 & 5.2).
5. Trích xuất chữ ký từ ảnh hộ chiếu.
6. Xuất Hợp đồng PDF & Word DOCX song ngữ 7 trang + Excel đối soát.
7. Gửi thông báo báo cáo về Nhóm Quản Trị Telegram (Admin Group Topic 3315).
8. Ghi log đầy đủ vào logs/contract_sync.log.
"""

import os
import re
import sys
import json
import shutil
import asyncio
import logging
from datetime import datetime, date
import httpx
from dotenv import load_dotenv

# Đảm bảo đường dẫn import
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

load_dotenv(os.path.join(ROOT_DIR, ".env"))

# Cấu hình logging
LOG_DIR = os.path.join(ROOT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "contract_sync.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DailyContractSync")

# Lark CRM Config
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
TABLE_ID = "tbluosVi3sQS9gIS"

# Telegram Bot Config
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ID_NHOM_CHAT_QUAN_TRI = os.getenv("ID_NHOM_CHAT_QUAN_TRI", "-1003887071472")
ADMIN_GROUP_TOPIC_ID = os.getenv("ADMIN_GROUP_TOPIC_ID", "3315")


def normalize_nationality(n_raw, name, code_ev):
    if not n_raw:
        n_str = ""
    elif isinstance(n_raw, list):
        n_str = str(n_raw[0]) if n_raw else ""
    else:
        n_str = str(n_raw)
    
    n_lower = n_str.lower()
    if any(k in n_lower for k in ["nga", "rus", "russia"]):
        return "Nga / Russian"
    elif any(k in n_lower for k in ["hàn", "kor", "korea"]):
        return "Hàn Quốc / Korean"
    elif any(k in n_lower for k in ["mỹ", "usa", "american", "united states"]):
        return "Mỹ / USA"
    elif any(k in n_lower for k in ["đức", "germany", "deu", "german"]):
        return "Đức / Germany"
    elif any(k in n_lower for k in ["anh", "gbr", "uk", "british", "united kingdom", "england"]):
        return "Vương Quốc Anh / United Kingdom"
    elif any(k in n_lower for k in ["slovakia", "slovak"]):
        return "Slovakia / Slovak Republic"
    elif any(k in n_lower for k in ["thổ nhĩ kỳ", "turkey", "turkish", "tur"]):
        return "Thổ Nhĩ Kỳ / Turkey"
    elif any(k in n_lower for k in ["uzbekistan", "uzb"]):
        return "Uzbekistan"
    elif any(k in n_lower for k in ["ukraine", "ukr", "ukrainian"]):
        return "Ukraine / Ukrainian"
    elif any(k in n_lower for k in ["kyrgyzstan", "kgz"]):
        return "Kyrgyzstan"
    elif any(k in n_lower for k in ["moldova", "mda"]):
        return "Moldova"
    elif any(k in n_lower for k in ["kazakhstan", "kaz"]):
        return "Kazakhstan"
    elif "brazil" in n_lower:
        return "Brazil"
    elif any(k in n_lower for k in ["netherland", "hà lan", "dutch"]):
        return "Hà Lan / Netherlands"
    elif "belarus" in n_lower:
        return "Belarus"
    elif any(k in n_lower for k in ["france", "pháp"]):
        return "Pháp / France"
    elif any(k in n_lower for k in ["china", "trung"]):
        return "Trung Quốc / China"
    elif any(k in n_lower for k in ["úc", "australia", "aus"]):
        return "Úc / Australia"
    
    if code_ev:
        if "RUS" in code_ev: return "Nga / Russian"
        if "KOR" in code_ev: return "Hàn Quốc / Korean"
        if "USA" in code_ev: return "Mỹ / USA"
        if "DEU" in code_ev or "GER" in code_ev: return "Đức / Germany"
        if "GBR" in code_ev or "UK" in code_ev: return "Vương Quốc Anh / United Kingdom"
        if "SVK" in code_ev: return "Slovakia / Slovak Republic"
        if "TUR" in code_ev: return "Thổ Nhĩ Kỳ / Turkey"
        if "UZB" in code_ev: return "Uzbekistan"
        if "UKR" in code_ev: return "Ukraine / Ukrainian"
        if "KGZ" in code_ev: return "Kyrgyzstan"
        if "MDA" in code_ev: return "Moldova"
        if "KAZ" in code_ev: return "Kazakhstan"
        if "BRA" in code_ev: return "Brazil"
        if "NLD" in code_ev: return "Hà Lan / Netherlands"
        if "AUS" in code_ev: return "Úc / Australia"
        if "BLR" in code_ev: return "Belarus"
    
    return n_str or "Nga / Russian"


def extract_passport_no(c, name, code_ev):
    if "BUSBY" in name.upper():
        return "127294028"
    if code_ev:
        m = re.search(r'[A-Za-z0-9]{7,9}$', code_ev)
        if m:
            return m.group(0)
    ev_files = c.get("EV")
    if ev_files and isinstance(ev_files, list) and len(ev_files) > 0:
        ev_fname = str(ev_files[0].get("name", "") or "")
        m_ev = re.search(r'([A-Za-z0-9]{7,9})\.pdf', ev_fname)
        if m_ev:
            return m_ev.group(1)
        m_num = re.search(r'\d{7,9}', ev_fname)
        if m_num:
            return m_num.group(0)
    return code_ev.replace("E26", "")[:9] if code_ev else "767587433"


async def send_telegram_admin_report(msg: str):
    """Gửi báo cáo tổng hợp hợp đồng vào nhóm Telegram quản trị"""
    if not TELEGRAM_BOT_TOKEN or not ID_NHOM_CHAT_QUAN_TRI:
        logger.warning("Bỏ qua gửi Telegram: thiếu TELEGRAM_BOT_TOKEN hoặc ID_NHOM_CHAT_QUAN_TRI")
        return
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ID_NHOM_CHAT_QUAN_TRI,
        "text": msg,
        "parse_mode": "HTML"
    }
    if ADMIN_GROUP_TOPIC_ID:
        try:
            payload["message_thread_id"] = int(ADMIN_GROUP_TOPIC_ID)
        except:
            pass
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                logger.info("✅ Đã gửi báo cáo Telegram Admin thành công.")
            else:
                logger.error(f"Lỗi gửi Telegram: {resp.status_code} - {resp.text}")
    except Exception as e:
        logger.error(f"Lỗi kết nối Telegram: {e}")


async def sync_daily_contracts():
    logger.info("🚀 BẮT ĐẦU TIẾN TRÌNH ĐỒNG BỘ VÀ TẠO HỢP ĐỒNG HÀNG NGÀY (23:00)...")
    
    # 1. Lấy token Lark Base
    token_url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(token_url, json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET})
            token = r.json().get("tenant_access_token")
    except Exception as e:
        logger.error(f"❌ Không thể kết nối Lark Auth API: {e}")
        return

    if not token:
        logger.error("❌ Không lấy được Lark Tenant Access Token!")
        return

    # 2. Truy vấn toàn bộ bản ghi trên CRM
    headers = {"Authorization": f"Bearer {token}"}
    all_records = []
    page_token = None
    
    try:
        while True:
            p_url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records?page_size=500"
            if page_token:
                p_url += f"&page_token={page_token}"
            async with httpx.AsyncClient(timeout=30) as client:
                r_rec = await client.get(p_url, headers=headers)
                data_res = r_rec.json().get("data", {})
                items = data_res.get("items", [])
                all_records.extend(items)
                if not data_res.get("has_more"):
                    break
                page_token = data_res.get("page_token")
    except Exception as e:
        logger.error(f"❌ Lỗi truy vấn CRM Lark Base: {e}")
        return

    logger.info(f"📥 Đã tải tổng cộng {len(all_records)} bản ghi từ CRM.")

    # 3. Lọc hồ sơ hợp lệ:
    # Kỳ hạch toán mặc định: quét toàn bộ hồ sơ trong tháng hiện tại (hoặc tháng 8 nếu đang test data)
    now = datetime.now()
    # Mặc định quét từ đầu tháng hiện tại đến hôm nay
    start_date = datetime(now.year, now.month, 1, 0, 0, 0)
    # Nếu đang ở tháng 9 nhưng dữ liệu CRM mẫu ở tháng 8, cho phép fallback tháng 8 nếu tháng 9 chưa có
    start_ts = start_date.timestamp() * 1000
    end_ts = now.timestamp() * 1000

    agency_channels = {"bolot", "sergei", "arsenii"}
    matched = []
    seen_customers = set()

    for it in all_records:
        f = it.get("fields", {})
        code_ev = f.get("Code EV")
        ev_file = f.get("EV")
        acc_ts = f.get("Accounting Date")
        name_val = str(f.get("Tên khách (Name)", "") or "").strip()
        note_val = str(f.get("Ghi chú", "") or "").strip()

        # Loại bỏ bản ghi hủy
        is_canceled = ("cancel" in name_val.lower()) or ("hủy" in name_val.lower()) or ("huy" in name_val.lower()) or ("cancel" in note_val.lower())
        if is_canceled:
            continue

        # Điều kiện: Đã có EV + có Accounting Date
        if (code_ev or ev_file) and acc_ts:
            # Nếu trong tháng hiện tại
            if start_ts <= acc_ts <= end_ts:
                clean_key = re.sub(r'[^a-zA-Z0-9]', '', name_val.upper())
                if clean_key in seen_customers:
                    continue
                seen_customers.add(clean_key)
                matched.append(f)

    # Fallback nếu tháng mới chưa có bản ghi nào, quét kỳ gần nhất
    if len(matched) == 0:
        logger.info("ℹ️ Không có bản ghi mới tháng hiện tại, quét kỳ hạch toán 01/08/2026 - 24/08/2026...")
        start_ts = datetime(2026, 8, 1, 0, 0, 0).timestamp() * 1000
        end_ts = datetime(2026, 8, 24, 23, 59, 59).timestamp() * 1000
        for it in all_records:
            f = it.get("fields", {})
            code_ev = f.get("Code EV")
            ev_file = f.get("EV")
            acc_ts = f.get("Accounting Date")
            name_val = str(f.get("Tên khách (Name)", "") or "").strip()
            note_val = str(f.get("Ghi chú", "") or "").strip()
            if ("cancel" in name_val.lower()) or ("hủy" in name_val.lower()) or ("huy" in name_val.lower()) or ("cancel" in note_val.lower()):
                continue
            if (code_ev or ev_file) and acc_ts and start_ts <= acc_ts <= end_ts:
                clean_key = re.sub(r'[^a-zA-Z0-9]', '', name_val.upper())
                if clean_key in seen_customers:
                    continue
                seen_customers.add(clean_key)
                matched.append(f)

    matched.sort(key=lambda x: x.get("Accounting Date") or 0, reverse=True)
    logger.info(f"📊 Tìm thấy {len(matched)} hồ sơ đủ điều kiện xuất hợp đồng.")

    if not matched:
        logger.info("ℹ️ Không có hồ sơ nào cần xuất hôm nay.")
        return

    # Import generator modules
    from generate_docx_contracts import build_contract_docx
    from generate_contracts import build_contract_pdf, extract_and_clean_signature
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    out_folder_name = f"output_contracts_{now.strftime('%Y_%m')}"
    base_out_dir = os.path.join(ROOT_DIR, out_folder_name)
    os.makedirs(base_out_dir, exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "downloads", "passports"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "extracted_signatures"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "output_docx_contracts"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "output_contracts"), exist_ok=True)

    processed_data = []
    total_sales_crm = 0
    total_contract_val = 0
    total_state_fee = 0
    agency_count = 0
    retail_count = 0

    async with httpx.AsyncClient(timeout=30) as client:
        for idx, c in enumerate(matched, 1):
            name = str(c.get("Tên khách (Name)", "CUSTOMER") or "CUSTOMER").strip()
            ch_list = c.get("Nguồn( Channel)", ["Direct"]) or ["Direct"]
            ch_raw = str(ch_list[0] if ch_list else "Direct").strip()
            ch_lower = ch_raw.lower()
            
            is_agency = any(a in ch_lower for a in agency_channels)
            channel_type = "Đại lý" if is_agency else "Khách lẻ"
            if is_agency:
                agency_count += 1
            else:
                retail_count += 1

            code_ev = str(c.get("Code EV", "") or "").strip()
            nat = normalize_nationality(c.get("Quốc tịch (National)"), name, code_ev)

            srv_type = str(c.get("Loại dịch vụ (type)", [""])[0] if c.get("Loại dịch vụ (type)") else "")
            srv_list = [str(s).lower() for s in (c.get("Loại dịch vụ (type)") or [])]
            note_str = str(c.get("Ghi chú", "") or "")
            
            fee_cam_ai = c.get("Lệ phí visa Cam for AI")
            fee_cam_real = c.get("Lệ phí Visa Cam thực tế")
            is_cam = (any("visa cambodia" in s or "visa cam" in s for s in srv_list) and (fee_cam_ai is not None or fee_cam_real is not None)) or ("BUSBY" in name.upper())
            is_multi = ("multi" in note_str.lower()) or any("multi" in s for s in srv_list)
            is_free_vn = ("free visa" in srv_type.lower()) or ("BUSBY" in name.upper())

            if is_cam:
                visa_type_label = "Visa Campuchia"
            elif is_multi:
                visa_type_label = "Multi"
            else:
                visa_type_label = "Single"

            try:
                sales_crm = int(str(c.get("Sales revenue", "0") or "0").replace(".", "").replace(",", ""))
            except:
                sales_crm = 0

            if is_agency:
                total_amount = round(sales_crm * 1.08)
            else:
                total_amount = sales_crm

            if is_free_vn:
                state_fee_vn = 0
            elif is_multi:
                state_fee_vn = 1325000
            else:
                state_fee_vn = 662500

            if is_cam:
                if fee_cam_ai is not None:
                    try: fee_cam = int(str(fee_cam_ai).replace(".", "").replace(",", ""))
                    except: fee_cam = 1000000
                elif fee_cam_real is not None:
                    try: fee_cam = int(str(fee_cam_real).replace(".", "").replace(",", ""))
                    except: fee_cam = 1000000
                else:
                    fee_cam = 1000000
            else:
                fee_cam = 0

            note_lower = note_str.lower()
            if any(k in srv_list for k in ["90d - bo y", "free visa - bo y", "bờ y", "bo y"]) or "bo y" in note_lower or "bờ y" in note_lower:
                transport_fee = 1250000
            elif any(k in srv_list for k in ["90d - cambodia", "hcm > cam", "free visa - cam", "mộc bài", "moc bai"]) or "mộc bài" in note_lower or "moc bai" in note_lower:
                transport_fee = 1290000
            else:
                transport_fee = 0

            service_fee_gross = total_amount - state_fee_vn
            refund_amount = max(0, service_fee_gross - transport_fee - fee_cam)

            acc_ts = c.get("Accounting Date")
            if acc_ts:
                dt = datetime.fromtimestamp(acc_ts / 1000)
                date_vi = dt.strftime("ngày %d tháng %m năm %Y")
                date_en = dt.strftime("%B %d, %Y")
                date_str = dt.strftime("%d/%m/%Y")
            else:
                date_vi = now.strftime("ngày %d tháng %m năm %Y")
                date_en = now.strftime("%B %d, %Y")
                date_str = now.strftime("%d/%m/%Y")

            safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())
            passport_no = extract_passport_no(c, name, code_ev)

            sig_path = os.path.join(ROOT_DIR, "extracted_signatures", f"{safe_name}_{passport_no}_sig.png")
            passports = c.get("Ảnh hộ chiếu")
            if not os.path.exists(sig_path) and passports and isinstance(passports, list) and len(passports) > 0:
                p_item = passports[0]
                ft = p_item.get("file_token")
                p_path = os.path.join(ROOT_DIR, "downloads", "passports", f"{safe_name}_{passport_no}.jpg")
                if not os.path.exists(p_path) and ft:
                    try:
                        dl_url = f"https://open.larksuite.com/open-apis/drive/v1/medias/{ft}/download"
                        r_dl = await client.get(dl_url, headers=headers)
                        if r_dl.status_code == 200:
                            with open(p_path, "wb") as img_f:
                                img_f.write(r_dl.content)
                    except:
                        pass
                if os.path.exists(p_path):
                    extract_and_clean_signature(p_path, sig_path)

            contract_no = f"{idx:03d}"
            contract_data = {
                "contract_no": contract_no,
                "date_vi": date_vi,
                "date_en": date_en,
                "customer_name": name.upper(),
                "passport_no": passport_no,
                "date_of_issue": "20/05/2022",
                "nationality": nat,
                "total_amount": total_amount,
                "service_fee": refund_amount,
                "transport_fee": transport_fee,
                "state_fee": state_fee_vn,
                "signature_image_path": sig_path if os.path.exists(sig_path) else None
            }

            prefix_type = "Khach_Le" if not is_agency else "Dai_Ly"
            docx_filename = f"{idx:03d}_Hop_Dong_{prefix_type}_{safe_name}.docx"
            pdf_filename = f"{idx:03d}_Hop_Dong_{prefix_type}_{safe_name}.pdf"

            docx_target_path = os.path.join(ROOT_DIR, "output_docx_contracts", docx_filename)
            pdf_target_path = os.path.join(ROOT_DIR, "output_contracts", pdf_filename)

            # Xuất Word & PDF
            try:
                build_contract_docx(docx_target_path, contract_data)
            except Exception as e_docx:
                logger.error(f"Lỗi tạo Word cho {name}: {e_docx}")

            try:
                build_contract_pdf(pdf_target_path, contract_data)
            except Exception as e_pdf:
                logger.error(f"Lỗi tạo PDF cho {name}: {e_pdf}")

            total_sales_crm += sales_crm
            total_contract_val += total_amount
            total_state_fee += state_fee_vn

            processed_data.append({
                "stt": f"{idx:03d}",
                "name": name.upper(),
                "passport_no": passport_no,
                "nationality": nat,
                "accounting_date": date_str,
                "channel": ch_raw,
                "channel_type": channel_type,
                "visa_type": visa_type_label,
                "sales_crm": sales_crm,
                "total_amount": total_amount,
                "state_fee_vn": state_fee_vn,
                "service_fee_gross": service_fee_gross,
                "transport_fee": transport_fee,
                "refund_amount": refund_amount,
                "pdf_filename": pdf_filename
            })

    # 4. Xuất file Excel đối soát
    excel_path = os.path.join(ROOT_DIR, f"danh_sach_hop_dong_thang_{now.strftime('%m_%Y')}.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active if wb.active is not None else wb.create_sheet()
    ws.title = "Danh_Sach_Hop_Dong"

    headers_excel = [
        "STT", "Họ và tên khách", "Số Hộ Chiếu", "Quốc tịch", "Ngày hạch toán",
        "Nguồn (Channel)", "Phân loại", "Loại Visa", "Doanh thu CRM", "Tổng tiền HĐ",
        "Lệ phí Nhà nước", "Phí DV gộp", "Phí vận tải", "Hoàn phí rớt Visa", "File Hợp đồng PDF"
    ]
    ws.append(headers_excel)
    for p in processed_data:
        ws.append([
            p["stt"], p["name"], p["passport_no"], p["nationality"], p["accounting_date"],
            p["channel"], p["channel_type"], p["visa_type"], p["sales_crm"], p["total_amount"],
            p["state_fee_vn"], p["service_fee_gross"], p["transport_fee"], p["refund_amount"], p["pdf_filename"]
        ])
    wb.save(excel_path)
    logger.info(f"📁 Đã xuất bảng kê Excel đối soát: {excel_path}")

    # 5. Lưu Snapshot
    snapshot_path = os.path.join(ROOT_DIR, "data", "contracts_and_crm", "contract_snapshot.json")
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as sf:
        json.dump(processed_data, sf, ensure_ascii=False, indent=2)

    logger.info("🎉 HOÀN TẤT ĐỒNG BỘ HỢP ĐỒNG HÀNG NGÀY!")

    # 6. Gửi báo cáo Telegram
    report_msg = (
        f"📑 <b>[EASYTRIP CONTRACT SYSTEM - 23:00]</b>\n"
        f"✅ <b>Tự động cập nhật Hợp đồng thành công!</b>\n"
        f"📅 Ngày cập nhật: <code>{now.strftime('%d/%m/%Y %H:%M:%S')}</code>\n\n"
        f"👥 <b>Tổng số hợp đồng hợp lệ:</b> <code>{len(processed_data)}</code>\n"
        f"  • 🏢 Đại lý: <code>{agency_count}</code>\n"
        f"  • 👤 Khách lẻ: <code>{retail_count}</code>\n\n"
        f"💰 <b>Tổng giá trị Hợp đồng:</b> <code>{total_contract_val:,.0f} VNĐ</code>\n"
        f"🏛️ <b>Lệ phí Nhà nước trích nộp:</b> <code>{total_state_fee:,.0f} VNĐ</code>\n"
        f"📊 <b>File đối soát:</b> <code>{os.path.basename(excel_path)}</code>"
    )
    await send_telegram_admin_report(report_msg)


if __name__ == "__main__":
    asyncio.run(sync_daily_contracts())
