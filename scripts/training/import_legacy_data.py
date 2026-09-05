"""
Script import dữ liệu lịch sử khách hàng, hợp đồng và tin nhắn cũ vào SQLite Database (easytrip_chat.db)
Dữ liệu nguồn:
1. contract_snapshot.json & danh_sach_hop_dong_01_08_den_24_08.xlsx
2. danh_sach_khach_hang_co_evisa_01_08_den_19_08.xlsx
3. telegram_chat.json & meta_chat.json
"""

import json
import os
import sys
import re
import sqlite3
from typing import Any
import openpyxl
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from customer_memory import (
    get_db_connection,
    init_db,
    normalize_phone,
    get_or_create_customer,
    update_customer_profile,
    record_completed_trip,
    save_chat_message
)

def safe_int(val: Any) -> int:
    """Chuyển đổi an toàn giá trị bất kỳ sang int"""
    if val is None:
        return 0
    val_str = str(val).split('.')[0].strip()
    return int(val_str) if val_str.isdigit() else 0

def resolve_path(rel_path: str) -> str:
    """Tìm đường dẫn trong data/ hoặc root"""
    candidates = [
        os.path.join(ROOT_DIR, "data", "contracts_and_crm", rel_path),
        os.path.join(ROOT_DIR, "data", "raw_chat_history", rel_path),
        os.path.join(ROOT_DIR, "data", "training_knowledge", rel_path),
        os.path.join(ROOT_DIR, "data", rel_path),
        os.path.join(ROOT_DIR, rel_path),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]

def detect_language(nationality: str) -> str:
    """Tự động suy luận ngôn ngữ từ quốc tịch"""
    if not nationality:
        return "en"
    nat_lower = nationality.lower()
    if any(k in nat_lower for k in ["nga", "russia", "russian", "kazakhstan", "kyrgyzstan", "uzbekistan", "tajikistan", "belarus", "ukraine"]):
        return "ru"
    if any(k in nat_lower for k in ["hàn quốc", "korea", "korean"]):
        return "ko"
    if any(k in nat_lower for k in ["việt nam", "vietnam", "vietnamese"]):
        return "vi"
    if any(k in nat_lower for k in ["pháp", "france", "french"]):
        return "fr"
    return "en"

def import_contracts():
    """Nạp danh sách hợp đồng từ contract_snapshot.json và Excel"""
    print("\n--- 1. IMPORTING CONTRACTS & CUSTOMERS ---")
    conn = get_db_connection()
    count_cust = 0
    count_trips = 0
    
    # 1.1 Load contract_snapshot.json
    contract_file = resolve_path("contract_snapshot.json")
    if os.path.exists(contract_file):
        with open(contract_file, "r", encoding="utf-8") as f:
            contracts = json.load(f)
            print(f"Loaded {len(contracts)} contracts from {contract_file}")
            
            for name, c in contracts.items():
                full_name = c.get("name") or name
                passport = c.get("passport_no", "")
                nationality = c.get("nationality", "")
                channel = (c.get("channel") or "").strip()
                channel_type = c.get("channel_type", "")
                visa_type = c.get("visa_type", "")
                service = c.get("service", "")
                date_str = c.get("accounting_date", datetime.now().strftime("%d/%m/%Y"))
                price = int(c.get("total_amount") or 0)
                notes = f"Passport: {passport} | Channel: {channel} ({channel_type}) | HĐ: {c.get('pdf_filename', '')}"
                
                lang = detect_language(nationality)
                
                # Check if customer already exists by full_name
                cursor = conn.cursor()
                cursor.execute("SELECT customer_id FROM customers WHERE full_name = ?", (full_name,))
                row = cursor.fetchone()
                
                if row:
                    cust_id = row["customer_id"]
                    # Update fields
                    conn.execute("""
                        UPDATE customers 
                        SET nationality = COALESCE(NULLIF(nationality, ''), ?),
                            preferred_lang = ?,
                            customer_notes = COALESCE(customer_notes || ' | ' || ?, customer_notes, ?),
                            updated_at = CURRENT_TIMESTAMP
                        WHERE customer_id = ?
                    """, (nationality, lang, notes, notes, cust_id))
                else:
                    with conn:
                        cursor = conn.execute("""
                            INSERT INTO customers (full_name, nationality, preferred_lang, customer_tier, customer_notes)
                            VALUES (?, ?, ?, 'RETURNING', ?)
                        """, (full_name, nationality, lang, notes))
                        cust_id = cursor.lastrowid
                        count_cust += 1
                
                # Record trip in trip_history
                with conn:
                    conn.execute("""
                        INSERT INTO trip_history (customer_id, departure_date, route, visa_type, price_paid, order_status, order_id)
                        VALUES (?, ?, ?, ?, ?, 'COMPLETED', ?)
                    """, (cust_id, date_str, service, visa_type, price, f"HD_{c.get('stt', cust_id)}"))
                    
                    conn.execute("""
                        UPDATE customers 
                        SET total_trips = total_trips + 1,
                            customer_tier = CASE WHEN total_trips + 1 >= 3 THEN 'VIP' ELSE 'RETURNING' END,
                            preferred_route = COALESCE(?, preferred_route)
                        WHERE customer_id = ?
                    """, (service, cust_id))
                    count_trips += 1

    # 1.2 Load from Excel E-visa
    evisa_file = resolve_path("danh_sach_khach_hang_co_evisa_01_08_den_19_08.xlsx")
    if os.path.exists(evisa_file):
        try:
            wb = openpyxl.load_workbook(evisa_file)
            ws = wb.active
            if ws is not None:
                rows = list(ws.iter_rows(values_only=True))
                # Header is row 4 (0-indexed: 3)
                # ('STT', 'Ngày Event', 'Ngày nộp (Apply)', 'Tên khách hàng', 'Quốc tịch', 'Loại dịch vụ', 'Mã E-Visa (Code EV)', 'Tệp đính kèm EV', 'Doanh thu (VNĐ)', 'Trạng thái thanh toán')
                for r in rows[4:]:
                    if not r or not r[3]:
                        continue
                    c_name = str(r[3]).strip()
                    c_nat = str(r[4] or "").strip()
                    c_srv = str(r[5] or "").strip()
                    c_code = str(r[6] or "").strip()
                    c_price = safe_int(r[8])
                    c_date = str(r[1] or datetime.now().strftime("%d/%m/%Y"))
                    
                    lang = detect_language(c_nat)
                    
                    cursor = conn.cursor()
                    cursor.execute("SELECT customer_id FROM customers WHERE full_name = ?", (c_name,))
                    row = cursor.fetchone()
                    if row:
                        cust_id = row["customer_id"]
                    else:
                        with conn:
                            cursor = conn.execute("""
                                INSERT INTO customers (full_name, nationality, preferred_lang, customer_tier, customer_notes)
                                VALUES (?, ?, ?, 'RETURNING', ?)
                            """, (c_name, c_nat, lang, f"Mã E-Visa: {c_code}"))
                            cust_id = cursor.lastrowid
                            count_cust += 1
                        
                    with conn:
                        conn.execute("""
                            INSERT INTO trip_history (customer_id, departure_date, route, visa_type, price_paid, order_status, order_id)
                            VALUES (?, ?, ?, ?, ?, 'COMPLETED', ?)
                        """, (cust_id, c_date, c_srv, "E-Visa", c_price, f"EV_{c_code}"))
                        
                        conn.execute("""
                            UPDATE customers 
                            SET total_trips = total_trips + 1,
                                customer_tier = CASE WHEN total_trips + 1 >= 3 THEN 'VIP' ELSE 'RETURNING' END
                            WHERE customer_id = ?
                        """, (cust_id,))
                        count_trips += 1
            print("Successfully processed E-visa Excel list")
        except Exception as e:
            print(f"⚠️ Error reading E-visa Excel: {e}")

    print(f"✅ Imported/Updated {count_cust} unique customers and {count_trips} trip history records.")

def import_telegram_chats():
    """Nạp lịch sử tin nhắn và người dùng từ telegram_chat.json"""
    print("\n--- 2. IMPORTING TELEGRAM CHATS & USERS ---")
    tg_file = resolve_path("telegram_chat.json")
    if not os.path.exists(tg_file):
        print(f"{tg_file} not found, skipping.")
        return
        
    conn = get_db_connection()
    count_chats = 0
    count_msgs = 0
    
    with open(tg_file, "r", encoding="utf-8") as f:
        t_data = json.load(f)
        chat_list = t_data.get("chats", {}).get("list", [])
        print(f"Found {len(chat_list)} Telegram chats")
        
        for chat in chat_list:
            tg_id = str(chat.get("id"))
            chat_name = chat.get("name") or f"Telegram User {tg_id}"
            chat_type = chat.get("type")
            messages = chat.get("messages", [])
            
            if not messages:
                continue
                
            # Tạo hoặc lấy customer profile theo telegram_id
            cursor = conn.cursor()
            cursor.execute("SELECT customer_id, full_name FROM customers WHERE telegram_id = ?", (tg_id,))
            row = cursor.fetchone()
            
            if row:
                cust_id = row["customer_id"]
            else:
                # Kiểm tra xem có trùng tên với khách hàng trong hợp đồng không
                cursor.execute("SELECT customer_id FROM customers WHERE UPPER(full_name) = UPPER(?) AND telegram_id IS NULL", (chat_name,))
                match_name = cursor.fetchone()
                if match_name:
                    cust_id = match_name["customer_id"]
                    with conn:
                        conn.execute("UPDATE customers SET telegram_id = ? WHERE customer_id = ?", (tg_id, cust_id))
                else:
                    with conn:
                        cursor = conn.execute("""
                            INSERT INTO customers (telegram_id, full_name, customer_tier, customer_notes)
                            VALUES (?, ?, 'RETURNING', ?)
                        """, (tg_id, chat_name, f"Chat Type: {chat_type}"))
                        cust_id = cursor.lastrowid
            
            count_chats += 1
            session_id = f"telegram_{tg_id}"
            
            # Import tối đa 30 tin nhắn gần nhất của mỗi chat
            recent_msgs = messages[-30:] if len(messages) > 30 else messages
            for msg in recent_msgs:
                m_type = msg.get("type")
                if m_type != "message":
                    continue
                sender = msg.get("from") or ""
                text = msg.get("text")
                if isinstance(text, list):
                    # Telegram đôi khi lưu text dạng list entities
                    text = "".join([t if isinstance(t, str) else t.get("text", "") for t in text])
                if not text or not str(text).strip():
                    continue
                    
                text_clean = str(text).strip()
                date_str = msg.get("date", "")
                
                # Determine role: bot/admin vs customer
                is_admin_or_bot = any(k in sender.lower() for k in ["bot", "easytrip", "admin", "supporter", "chăm sóc"])
                role = "assistant" if is_admin_or_bot else "user"
                
                with conn:
                    conn.execute("""
                        INSERT INTO chat_messages (customer_id, session_id, platform, role, content, created_at)
                        VALUES (?, ?, 'telegram', ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
                    """, (cust_id, session_id, role, text_clean, date_str if date_str else None))
                    count_msgs += 1

    print(f"✅ Imported {count_chats} Telegram chats and {count_msgs} historical messages.")

def import_meta_chats():
    """Nạp lịch sử tin nhắn từ meta_chat.json"""
    print("\n--- 3. IMPORTING META / FACEBOOK CHATS ---")
    meta_file = resolve_path("meta_chat.json")
    if not os.path.exists(meta_file):
        print(f"{meta_file} not found, skipping.")
        return
        
    conn = get_db_connection()
    count_chats = 0
    count_msgs = 0
    
    with open(meta_file, "r", encoding="utf-8") as f:
        m_data = json.load(f)
        chats = m_data.get("chats", [])
        if isinstance(chats, dict):
            chats = chats.get("list", [])
            
        print(f"Found {len(chats)} Meta chats")
        for chat in chats:
            fb_id = str(chat.get("id") or chat.get("thread_id") or f"fb_{count_chats+1}")
            user_name = chat.get("name") or chat.get("sender_name") or f"Facebook User {fb_id}"
            messages = chat.get("messages", [])
            
            if not messages:
                continue
                
            cursor = conn.cursor()
            cursor.execute("SELECT customer_id FROM customers WHERE facebook_id = ?", (fb_id,))
            row = cursor.fetchone()
            if row:
                cust_id = row["customer_id"]
            else:
                with conn:
                    cursor = conn.execute("""
                        INSERT INTO customers (facebook_id, full_name, customer_tier)
                        VALUES (?, ?, 'RETURNING')
                    """, (fb_id, user_name))
                    cust_id = cursor.lastrowid
                    
            count_chats += 1
            session_id = f"facebook_{fb_id}"
            
            for msg in messages[-30:]:
                sender = msg.get("sender_name") or ""
                text = msg.get("text") or msg.get("content") or ""
                if not text:
                    continue
                role = "assistant" if any(k in sender.lower() for k in ["bot", "easytrip", "page"]) else "user"
                
                with conn:
                    conn.execute("""
                        INSERT INTO chat_messages (customer_id, session_id, platform, role, content)
                        VALUES (?, ?, 'facebook', ?, ?)
                    """, (cust_id, session_id, role, str(text).strip()))
                    count_msgs += 1

    print(f"✅ Imported {count_chats} Meta chats and {count_msgs} historical messages.")

def print_db_summary():
    """In tổng quan cơ sở dữ liệu sau khi nạp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM customers")
    total_customers = cursor.fetchone()[0]
    
    cursor.execute("SELECT customer_tier, COUNT(*) FROM customers GROUP BY customer_tier")
    tiers = cursor.fetchall()
    
    cursor.execute("SELECT preferred_lang, COUNT(*) FROM customers GROUP BY preferred_lang")
    langs = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) FROM trip_history")
    total_trips = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM chat_messages")
    total_msgs = cursor.fetchone()[0]
    
    print("\n" + "="*50)
    print("📊 BÁO CÁO CƠ SỞ DỮ LIỆU EASYTRIP_CHAT.DB")
    print("="*50)
    print(f"👤 Tổng số hồ sơ khách hàng: {total_customers}")
    print(f"🎖️ Phân hạng khách hàng:")
    for tier, count in tiers:
        print(f"   - {tier or 'NONE'}: {count}")
    print(f"🌐 Ngôn ngữ ưu tiên:")
    for lang, count in langs:
        print(f"   - {lang or 'en'}: {count}")
    print(f"✈️ Tổng số chuyến đi/hợp đồng đã lưu: {total_trips}")
    print(f"💬 Tổng số tin nhắn lịch sử đã lưu: {total_msgs}")
    print("="*50 + "\n")

if __name__ == "__main__":
    init_db()
    import_contracts()
    import_telegram_chats()
    import_meta_chats()
    print_db_summary()
