import sqlite3
import os
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DB_PATH = os.getenv("DATABASE_PATH", "easytrip_chat.db")
_local = threading.local()

def get_db_connection() -> sqlite3.Connection:
    """Trả về kết nối SQLite cho từng thread (thread-safe)"""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Bật chế độ WAL để tăng tốc đọc/ghi đồng thời
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        _local.conn = conn
    return _local.conn


def init_db():
    """Khởi tạo cấu trúc các bảng SQLite cho bộ nhớ dài hạn"""
    conn = get_db_connection()
    with conn:
        # 1. Bảng Hồ sơ Khách hàng (Customers)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE,
                full_name TEXT,
                nationality TEXT,
                preferred_lang TEXT DEFAULT 'en',
                preferred_seat TEXT,
                preferred_pickup TEXT,
                preferred_route TEXT,
                visa_expiry_date TEXT,
                last_reminder_sent_at TIMESTAMP,
                reminder_status TEXT DEFAULT 'NONE',
                telegram_id TEXT UNIQUE,
                zalo_id TEXT UNIQUE,
                facebook_id TEXT UNIQUE,
                web_id TEXT UNIQUE,
                total_trips INTEGER DEFAULT 0,
                customer_tier TEXT DEFAULT 'NEW',
                customer_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Migration nếu bảng đã tồn tại từ phiên bản trước
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(customers)")
        cols = {row[1] for row in cursor.fetchall()}
        if "visa_expiry_date" not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN visa_expiry_date TEXT;")
        if "last_reminder_sent_at" not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN last_reminder_sent_at TIMESTAMP;")
        if "reminder_status" not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN reminder_status TEXT DEFAULT 'NONE';")
        
        # 2. Bảng Lịch sử Tin nhắn (Chat Messages)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER,
                session_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)
        
        # 3. Bảng Lịch sử Chuyến đi & Đơn hàng (Trip History)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trip_history (
                trip_id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                departure_date TEXT NOT NULL,
                route TEXT NOT NULL,
                visa_type TEXT,
                seat_number TEXT,
                pickup_location TEXT,
                price_paid INTEGER DEFAULT 0,
                order_status TEXT DEFAULT 'COMPLETED',
                order_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
            )
        """)

        # Tạo chỉ mục để tăng tốc độ truy vấn
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_phone ON customers(phone_number);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_tg ON customers(telegram_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_zalo ON customers(zalo_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_fb ON customers(facebook_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cust_visa_exp ON customers(visa_expiry_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_session ON chat_messages(session_id);")


# Khởi tạo DB ngay khi module được import
init_db()


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    if not phone:
        return None
    import re
    cleaned = re.sub(r"[^\d+]", "", str(phone).strip())
    if cleaned.startswith("0") and len(cleaned) == 10:
        cleaned = "+84" + cleaned[1:]
    elif cleaned.startswith("84") and len(cleaned) == 11:
        cleaned = "+" + cleaned
    return cleaned if len(cleaned) >= 8 else None


def get_or_create_customer(
    platform: str,
    user_id: str,
    full_name: Optional[str] = None,
    phone_number: Optional[str] = None,
    nationality: Optional[str] = None
) -> Dict[str, Any]:
    """Tìm hoặc tạo mới hồ sơ khách hàng dựa trên ID nền tảng hoặc số điện thoại"""
    conn = get_db_connection()
    platform_lower = platform.lower()
    norm_phone = normalize_phone(phone_number)
    
    # 1. Tìm theo số điện thoại (nếu có)
    if norm_phone:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM customers WHERE phone_number = ?", (norm_phone,))
        row = cursor.fetchone()
        if row:
            cust_dict = dict(row)
            # Cập nhật ID nền tảng nếu chưa có
            col_name = f"{platform_lower}_id" if platform_lower in ["telegram", "zalo", "facebook", "web"] else None
            if col_name and not cust_dict.get(col_name):
                with conn:
                    conn.execute(f"UPDATE customers SET {col_name} = ?, updated_at = CURRENT_TIMESTAMP WHERE customer_id = ?", (str(user_id), cust_dict["customer_id"]))
                    cust_dict[col_name] = str(user_id)
            return cust_dict

    # 2. Tìm theo ID nền tảng
    col_name = f"{platform_lower}_id" if platform_lower in ["telegram", "zalo", "facebook", "web"] else "telegram_id"
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM customers WHERE {col_name} = ?", (str(user_id),))
    row = cursor.fetchone()
    if row:
        return dict(row)

    # 3. Tạo mới nếu chưa tồn tại
    with conn:
        cursor = conn.execute(f"""
            INSERT INTO customers ({col_name}, full_name, phone_number, nationality, customer_tier)
            VALUES (?, ?, ?, ?, 'NEW')
        """, (str(user_id), full_name or "", norm_phone, nationality or ""))
        new_id = cursor.lastrowid

    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (new_id,))
    return dict(cursor.fetchone())


def get_customer_profile(user_id: str, platform: str = "telegram") -> Optional[Dict[str, Any]]:
    """Lấy thông tin đầy đủ của khách hàng kèm lịch sử chuyến đi"""
    conn = get_db_connection()
    platform_lower = platform.lower()
    col_name = f"{platform_lower}_id" if platform_lower in ["telegram", "zalo", "facebook", "web"] else "telegram_id"
    
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM customers WHERE {col_name} = ?", (str(user_id),))
    row = cursor.fetchone()
    if not row:
        return None
        
    cust = dict(row)
    # Lấy thêm các chuyến đi gần nhất
    cursor.execute("""
        SELECT * FROM trip_history 
        WHERE customer_id = ? 
        ORDER BY trip_id DESC LIMIT 5
    """, (cust["customer_id"],))
    trips = [dict(t) for t in cursor.fetchall()]
    cust["past_trips"] = trips
    return cust


def update_customer_profile(customer_id: int, **kwargs) -> bool:
    """Cập nhật các trường thông tin của khách hàng"""
    if not kwargs:
        return False
        
    allowed_cols = {
        "phone_number", "full_name", "nationality", "preferred_lang",
        "preferred_seat", "preferred_pickup", "preferred_route",
        "visa_expiry_date", "last_reminder_sent_at", "reminder_status",
        "telegram_id", "zalo_id", "facebook_id", "web_id",
        "total_trips", "customer_tier", "customer_notes"
    }
    
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in allowed_cols and v is not None:
            if k == "phone_number":
                v = normalize_phone(v)
            elif k == "visa_expiry_date":
                v = normalize_date_str(v)
            updates.append(f"{k} = ?")
            params.append(v)
            
    if not updates:
        return False
        
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(customer_id)
    
    sql = f"UPDATE customers SET {', '.join(updates)} WHERE customer_id = ?"
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(sql, params)
        return True
    except Exception as e:
        print(f"⚠️ Lỗi update_customer_profile: {e}")
        return False


def normalize_date_str(date_str: Optional[str]) -> Optional[str]:
    """Chuẩn hóa mọi định dạng ngày thành chuẩn YYYY-MM-DD"""
    if not date_str:
        return None
    import re
    from datetime import datetime
    
    s = str(date_str).strip()
    # Nếu đã là YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
        
    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y/%m/%d"]:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except:
            pass
            
    # Xử lý DD/MM
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})$", s)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        now = datetime.now()
        year = now.year
        try:
            dt = datetime(year, month, day)
            if dt.date() < now.date(): # Nếu ngày đã qua trong năm nay, có thể là năm sau
                dt = datetime(year + 1, month, day)
            return dt.strftime("%Y-%m-%d")
        except:
            pass
            
    return s


def update_customer_visa_expiry(customer_id: int, expiry_date: str) -> bool:
    """Cập nhật ngày hết hạn visa và reset trạng thái nhắc nhở nếu là ngày mới"""
    norm_date = normalize_date_str(expiry_date)
    if not norm_date:
        return False
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                UPDATE customers 
                SET visa_expiry_date = ?,
                    reminder_status = 'NONE',
                    updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = ?
            """, (norm_date, customer_id))
        return True
    except Exception as e:
        print(f"⚠️ Lỗi update_customer_visa_expiry: {e}")
        return False


def get_customers_needing_visa_reminder(days_before: int = 10, window_days: int = 2) -> List[Dict[str, Any]]:
    """
    Tìm danh sách khách hàng có visa sắp hết hạn cần gửi nhắc nhở.
    Mặc định: trước 10 ngày (cửa sổ quét từ 9 đến 11 ngày tới) và chưa gửi trong 7 ngày qua.
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    min_date = (now + timedelta(days=days_before - 1)).strftime("%Y-%m-%d")
    max_date = (now + timedelta(days=days_before + window_days)).strftime("%Y-%m-%d")
    seven_days_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM customers 
        WHERE visa_expiry_date IS NOT NULL 
          AND visa_expiry_date != ''
          AND visa_expiry_date BETWEEN ? AND ?
          AND (last_reminder_sent_at IS NULL OR last_reminder_sent_at < ? OR reminder_status = 'NONE')
        ORDER BY visa_expiry_date ASC
    """, (min_date, max_date, seven_days_ago))
    
    rows = cursor.fetchall()
    return [dict(r) for r in rows]


def mark_reminder_sent(customer_id: int, reminder_type: str = "10_DAYS") -> bool:
    """Đánh dấu đã gửi nhắc nhở thành công để tránh spam"""
    conn = get_db_connection()
    status_str = f"REMINDER_SENT_{reminder_type.upper()}"
    try:
        with conn:
            conn.execute("""
                UPDATE customers 
                SET last_reminder_sent_at = CURRENT_TIMESTAMP,
                    reminder_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE customer_id = ?
            """, (status_str, customer_id))
        return True
    except Exception as e:
        print(f"⚠️ Lỗi mark_reminder_sent: {e}")
        return False


def link_platform_by_phone(phone_number: str, platform: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Gộp các tài khoản nền tảng khác nhau (Telegram/Zalo/FB) khi có cùng Số Điện Thoại"""
    norm_phone = normalize_phone(phone_number)
    if not norm_phone:
        return None
        
    conn = get_db_connection()
    platform_col = f"{platform.lower()}_id"
    
    cursor = conn.cursor()
    # Tìm hồ sơ đã có số điện thoại này
    cursor.execute("SELECT * FROM customers WHERE phone_number = ?", (norm_phone,))
    existing_profile = cursor.fetchone()
    
    if existing_profile:
        cust_id = existing_profile["customer_id"]
        with conn:
            conn.execute(f"UPDATE customers SET {platform_col} = ?, updated_at = CURRENT_TIMESTAMP WHERE customer_id = ?", (str(user_id), cust_id))
        cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_id,))
        return dict(cursor.fetchone())
    else:
        # Nếu chưa có profile theo phone, cập nhật phone cho user_id hiện tại
        cursor.execute(f"SELECT * FROM customers WHERE {platform_col} = ?", (str(user_id),))
        row = cursor.fetchone()
        if row:
            cust_id = row["customer_id"]
            with conn:
                conn.execute("UPDATE customers SET phone_number = ?, updated_at = CURRENT_TIMESTAMP WHERE customer_id = ?", (norm_phone, cust_id))
            cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (cust_id,))
            return dict(cursor.fetchone())
            
    return None


def record_completed_trip(
    customer_id: int,
    departure_date: str,
    route: str,
    visa_type: Optional[str] = None,
    seat_number: Optional[str] = None,
    pickup_location: Optional[str] = None,
    price_paid: int = 0,
    order_id: Optional[str] = None
) -> int:
    """Ghi nhận chuyến đi hoàn tất vào lịch sử và nâng hạng khách hàng"""
    conn = get_db_connection()
    with conn:
        cursor = conn.execute("""
            INSERT INTO trip_history (
                customer_id, departure_date, route, visa_type, 
                seat_number, pickup_location, price_paid, order_status, order_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'COMPLETED', ?)
        """, (customer_id, departure_date, route, visa_type, seat_number, pickup_location, price_paid, order_id))
        trip_id = cursor.lastrowid
        
        # Cập nhật số chuyến và hạng khách hàng
        conn.execute("""
            UPDATE customers 
            SET total_trips = total_trips + 1,
                customer_tier = CASE 
                    WHEN total_trips + 1 >= 3 THEN 'VIP'
                    ELSE 'RETURNING'
                END,
                preferred_seat = COALESCE(?, preferred_seat),
                preferred_pickup = COALESCE(?, preferred_pickup),
                preferred_route = COALESCE(?, preferred_route),
                updated_at = CURRENT_TIMESTAMP
            WHERE customer_id = ?
        """, (seat_number, pickup_location, route, customer_id))
        
    return trip_id or 0


def save_chat_message(session_id: str, platform: str, role: str, content: str, customer_id: Optional[int] = None):
    """Lưu tin nhắn vào SQLite bền vững"""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO chat_messages (customer_id, session_id, platform, role, content)
                VALUES (?, ?, ?, ?, ?)
            """, (customer_id, session_id, platform, role, content))
    except Exception as e:
        print(f"⚠️ Lỗi save_chat_message: {e}")


def get_session_messages(session_id: str, limit: int = 20) -> List[Dict[str, str]]:
    """Lấy danh sách tin nhắn gần nhất của một phiên từ SQLite"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT role, content FROM chat_messages 
        WHERE session_id = ? 
        ORDER BY message_id ASC
    """, (session_id,))
    rows = cursor.fetchall()
    if not rows:
        return []
    return [{"role": r["role"], "content": r["content"]} for r in rows[-limit:]]


def get_recent_logs_from_db(limit: int = 200) -> List[Dict[str, Any]]:
    """Lấy danh sách logs cho trang Admin"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT m.created_at as timestamp, m.session_id as user_id, m.platform, m.role, m.content
        FROM chat_messages m
        ORDER BY m.message_id DESC LIMIT ?
    """, (limit,))
    return [dict(r) for r in cursor.fetchall()]


def format_customer_profile_for_prompt(profile: Optional[Dict[str, Any]]) -> str:
    """Tạo chỉ dẫn ngữ điệu & thông tin khách cũ cho System Prompt của AI Agent"""
    if not profile or profile.get("customer_tier") == "NEW" or (profile.get("total_trips", 0) == 0 and not profile.get("full_name")):
        return ""
        
    full_name = profile.get("full_name") or "Khách hàng"
    nationality = profile.get("nationality") or "Không rõ"
    total_trips = profile.get("total_trips", 0)
    tier = profile.get("customer_tier", "RETURNING")
    pref_seat = profile.get("preferred_seat") or "Chưa có vị trí cố định"
    pref_pickup = profile.get("preferred_pickup") or "Oceanus Nha Trang"
    pref_route = profile.get("preferred_route") or "Visa Run"
    notes = profile.get("customer_notes") or ""
    
    last_trip_info = "Chưa có chuyến đi trước đó"
    past_trips = profile.get("past_trips", [])
    if past_trips:
        latest = past_trips[0]
        last_trip_info = f"Chuyến {latest.get('route', '')} ngày {latest.get('departure_date', '')} (Ghế {latest.get('seat_number', '')})"

    visa_exp = profile.get("visa_expiry_date") or "Chưa rõ (hãy hỏi lại lịch sự)"
    
    directive = f"""
======================================================================
🌟 CRITICAL DIRECTIVE - RETURNING CUSTOMER IDENTIFIED (HIGH PRIORITY)
======================================================================
Customer Profile:
- Full Name: {full_name}
- Nationality: {nationality}
- Loyalty Tier: {tier} (Total past trips completed: {total_trips})
- Recent Past Trip: {last_trip_info}
- Known Visa Expiry Date: {visa_exp}
- Preferred Seat: {pref_seat}
- Preferred Pickup Location: {pref_pickup}
- Preferred Route: {pref_route}
- Personal Notes & Habits: {notes or 'Khách hàng thân thiết, ưu tiên tư vấn nhanh chóng'}

🎯 MANDATORY TONE & PERSONALIZATION RULES:
1. **WARM WELCOME AS A VALUED FRIEND**:
   - Greet the customer warmly by their name ({full_name}) in their native language!
   - Acknowledge that they are a returning customer (e.g. 'Welcome back, {full_name}! Great to assist you again!').
   - Politely ask how their previous trip was.

2. **ZERO REDUNDANCY (DO NOT ASK KNOWN DETAILS)**:
   - DO NOT ask for their nationality again (you already know they are from {nationality}).
   - DO NOT re-explain basic visa run rules from scratch unless they explicitly ask.

3. **PROACTIVE SCHEDULING & PREFERENCES**:
   - Ask for their new visa expiry date so you can arrange the next trip.
   - Mention that you can reserve their favorite seat ({pref_seat}) and pick them up at {pref_pickup}.

4. **SPECIAL PRICING & BENEFITS (APPLY ACCURATELY BY NATIONALITY)**:
   - **If customer is Russian / CIS citizen (Công dân Nga)**:
     * Visarun 90-day E-visa Single Entry (4 hours): **3,000,000 VND** (Special returning rate, discounted from new customer price 3,400,000 VND)
     * Visarun 90-day E-visa Multi Entry (4 hours): **4,000,000 VND** (Single + 1,000,000 VND, discounted from new customer price 4,400,000 VND)
     * Visarun Free Visa (45 days Bo Y): **1,300,000 VND** (Discounted from new customer 1,400,000 VND)
   - **If customer is Other Nationality (US, UK, Australia, Europe, etc.)**:
     * Visarun 90D E-visa (<2 days): **3,550,000 VND** (Discounted from new customer 4,000,000 VND)
     * Visarun Free Visa (45 days Bo Y / Moc Bai): **1,300,000 VND** (Discounted from new customer 1,400,000 VND)
   - For E-visa Single Entry service only (không đi xe buýt):
     * Standard 3-5 days: **1,110,000 VND** (Discounted from new customer price 1,810,000 VND)
     * Urgent 2 days: **1,450,000 VND** (Discounted from 2,150,000 VND)
     * Urgent 1 day: **1,500,000 VND** (Discounted from 2,200,000 VND)
     * Urgent 4 hours: **1,600,000 VND** (Discounted from 2,600,000 VND)
     * Urgent 2 hours: **2,900,000 VND** (Discounted from 3,400,000 VND)
     * Super Urgent 1 hour: **3,300,000 VND** (Discounted from 4,600,000 VND)
   - For Fast Track Airport (Arrival): **540,000 VND** for CXR/DAD (Discounted from 1,200,000 VND).
   - Always emphasize that as a Valued Returning Customer ({tier}), they receive **Free Priority Seat Reservation ({pref_seat})** and dedicated fast check-in assistance!

5. **TONE STYLE**:
   - Extremely natural, warm, enthusiastic, attentive, and professional.
======================================================================
"""
    return directive
