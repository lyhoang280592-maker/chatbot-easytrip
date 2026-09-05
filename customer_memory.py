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
            
def link_telegram_to_customer(customer_id: int, telegram_id: str) -> Optional[Dict[str, Any]]:
    """Gán telegram_id cho hồ sơ khách hàng cũ và dọn dẹp các hồ sơ tạm không có chuyến đi"""
    if not customer_id or not telegram_id:
        return None
    conn = get_db_connection()
    with conn:
        # Xóa telegram_id ở bất kỳ bản ghi tạm nào chưa có chuyến đi
        conn.execute("""
            UPDATE customers 
            SET telegram_id = NULL 
            WHERE telegram_id = ? AND customer_id != ? AND total_trips = 0
        """, (str(telegram_id), customer_id))
        
        # Gán telegram_id cho bản ghi khách cũ
        conn.execute("""
            UPDATE customers 
            SET telegram_id = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE customer_id = ?
        """, (str(telegram_id), customer_id))
        
    return get_customer_profile(str(telegram_id), "telegram")


def is_slavic_name(name: str) -> bool:
    """Kiểm tra tên có gốc Nga / Slavic hoặc các hậu tố phổ biến"""
    if not name:
        return False
    name_upper = name.upper()
    slavic_roots = [
        'TSARENKO', 'RODICHEV', 'EKATERINA', 'DMITRY', 'DMITRIY', 'ALEXANDER', 'ALEKSANDR',
        'SERGEY', 'SERGEI', 'IVAN', 'ANNA', 'OLGA', 'TATIANA', 'ELENA', 'NATALIA', 'MARIA',
        'ANDREY', 'ANDREI', 'VLADIMIR', 'EVGENY', 'MAXIM', 'ARTEM', 'DENIS', 'IGOR', 'POLINA',
        'DARIA', 'VIKTORIA', 'YULIA', 'ALISA', 'KSENIA', 'ANASTASIA', 'VERONIKA', 'IRINA',
        'SVETLANA', 'LIDIIA', 'OKSANA', 'NIKITINA', 'CHURBAKOV', 'NIUNKO', 'PRIKHODKO',
        'NIKULIN', 'KARIKH', 'VASILIEV', 'POPOV', 'SMIRNOV', 'KUZNETSOV', 'FEDOROV', 'MOROZOV'
    ]
    if any(root in name_upper for root in slavic_roots):
        return True
    for word in name_upper.split():
        if len(word) >= 4 and word.endswith(('OVA', 'EVA', 'INA', 'YEV', 'KOV', 'SKI', 'SKY', 'ENKO', 'ICH', 'UK', 'YUK')):
            return True
    return False


def find_customer_by_booking_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Tra soát CSDL khách hàng từ chuỗi text thông tin booking gần nhất hoặc kết quả đọc OCR từ ảnh vé.
    Hỗ trợ:
    1. Tìm theo Số điện thoại chính xác.
    2. Chuẩn hóa ký tự Cyrillic/Latin và trích xuất trường Name từ mẫu vé.
    3. Đối soát chuyến đi theo Ngày khởi hành + Số ghế (Date + Seat) có xác nhận họ tên tương đồng.
    4. Đối soát tên khách hàng đa tầng (Exact match & Fuzzy similarity) loại trừ bot/admin dummy.
    """
    if not text or len(text.strip()) < 3:
        return None
        
    import re
    import difflib
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Chuẩn hóa các ký tự Cyrillic hay bị OCR nhầm sang Latin
    charmap = {
        'а': 'a', 'А': 'A', 'с': 'c', 'С': 'C', 'е': 'e', 'Е': 'E',
        'о': 'o', 'О': 'O', 'р': 'p', 'Р': 'P', 'х': 'x', 'Х': 'X',
        'у': 'y', 'У': 'Y', 'В': 'B', 'М': 'M', 'Т': 'T', 'К': 'K',
        'Н': 'H'
    }
    normalized_text = text
    for k, v in charmap.items():
        normalized_text = normalized_text.replace(k, v)
        
    excluded_names = {'EASYTRIP VISA', 'EASY TRIP', 'EASYTRIP', 'ADMIN', 'BOT', 'USER', 'TEST'}
    
    # 2. Tìm theo số điện thoại nếu có
    phone_matches = re.findall(r'(\+?\d[\d\s\-\.]{7,15}\d)', normalized_text)
    for p in phone_matches:
        cleaned_p = re.sub(r'[^\d+]', '', p)
        if len(cleaned_p) >= 8:
            c.execute('SELECT * FROM customers WHERE phone_number LIKE ?', ('%' + cleaned_p[-8:] + '%',))
            row = c.fetchone()
            if row:
                cust = dict(row)
                if cust.get('full_name', '').strip().upper() not in excluded_names:
                    cust["customer_tier"] = "RETURNING"
                    cust["total_trips"] = max(cust.get("total_trips") or 1, 1)
                    return cust
                
    # 3. Trích xuất tên từ các mẫu biên nhận / vé xe
    name_extracted = None
    m_name = re.search(r'(?:Name|Tên|ФИО|Passenger|Khách)\s*[:：]\s*([^\n\r,]+)', normalized_text, re.IGNORECASE)
    if m_name:
        name_extracted = re.sub(r'[^a-zA-Z\s]', '', m_name.group(1)).strip().upper()
        
    # 4. Đối soát qua Lịch sử chuyến đi: Số ghế + Ngày khởi hành (Date + Seat)
    # Xử lý các lỗi OCR ký tự ghế phổ biến (VD: 4l2 -> A12, 412 -> A12, Bl -> B1)
    clean_seat_text = normalized_text.upper().replace('4L2', 'A12').replace('412', 'A12').replace('BL', 'B1')
    seat_m = re.search(r'\b([AB]\d{1,2})\b', clean_seat_text)
    seat = seat_m.group(1) if seat_m else None
    
    date_matches = re.findall(r'(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?', normalized_text)
    normalized_dates = []
    for d, m, y in date_matches:
        day = f'{int(d):02d}'
        month = f'{int(m):02d}'
        if y:
            year = f'20{y}' if len(y) == 2 else y
            normalized_dates.append(f'{year}-{month}-{day}')
            normalized_dates.append(f'{day}/{month}/{year}')
        normalized_dates.append(f'{day}/{month}')
        normalized_dates.append(f'{month}-{day}')
        
    if seat and normalized_dates:
        for dt_str in normalized_dates:
            c.execute('''
                SELECT c.* FROM trip_history t 
                JOIN customers c ON t.customer_id = c.customer_id 
                WHERE t.seat_number = ? AND (t.departure_date LIKE ? OR t.departure_date LIKE ?)
            ''', (seat, f'%{dt_str}%', f'%{dt_str.replace("/", "-")}%'))
            row = c.fetchone()
            if row:
                cust = dict(row)
                cust_full = cust.get('full_name', '').strip().upper()
                if cust_full not in excluded_names:
                    # Kiểm tra đối chiếu tên để tránh nhận nhầm khách khác từng ngồi cùng số ghế vào ngày khác
                    if name_extracted:
                        sim = difflib.SequenceMatcher(None, cust_full, name_extracted).ratio()
                        if sim >= 0.50:
                            cust["customer_tier"] = "RETURNING"
                            cust["total_trips"] = max(cust.get("total_trips") or 1, 1)
                            return cust
                    else:
                        cust_words = [w for w in re.split(r'\s+', cust_full) if len(w) >= 2]
                        if any(w in normalized_text.upper() for w in cust_words):
                            cust["customer_tier"] = "RETURNING"
                            cust["total_trips"] = max(cust.get("total_trips") or 1, 1)
                            return cust

    # 5. Tra soát Tên khách hàng (Exact & Fuzzy Sequence Matching)
    c.execute('SELECT * FROM customers WHERE full_name IS NOT NULL AND length(trim(full_name)) >= 3')
    all_customers = [dict(row) for row in c.fetchall() if dict(row)['full_name'].strip().upper() not in excluded_names]
    
    clean_text = ' ' + re.sub(r'[^a-zA-Z0-9\s]', ' ', normalized_text.upper()) + ' '
    text_words = [w for w in clean_text.split() if len(w) >= 2]
    
    best_match = None
    best_score = 0.0
    
    for cust in all_customers:
        cust_name = cust['full_name'].strip().upper()
        cust_words = [w for w in re.split(r'\s+', cust_name) if len(w) >= 2 and not w.isdigit()]
        if not cust_words:
            continue
            
        # So khớp trực tiếp với tên trích xuất từ biên lai (VD: Name: Choi Hac Jaun)
        if name_extracted and len(name_extracted) >= 4:
            direct_sim = difflib.SequenceMatcher(None, cust_name, name_extracted).ratio()
            if direct_sim >= 0.70 and direct_sim > best_score:
                best_score = direct_sim
                best_match = cust
                continue
                
        # So khớp chuỗi từ khóa trong nội dung text
        if len(cust_words) >= 2:
            if all(re.search(r'\b' + re.escape(w) + r'\b', clean_text) for w in cust_words):
                score = 0.95
                if score > best_score:
                    best_score = score
                    best_match = cust
            else:
                # Kiểm tra độ tương đồng từng từ (phòng trường hợp OCR sai 1-2 ký tự)
                word_scores = []
                for cw in cust_words:
                    max_w_sim = max([difflib.SequenceMatcher(None, cw, tw).ratio() for tw in text_words], default=0.0)
                    word_scores.append(max_w_sim)
                if min(word_scores) >= 0.65 and (sum(word_scores) / len(word_scores)) >= 0.75:
                    score = sum(word_scores) / len(word_scores)
                    if score > best_score:
                        best_score = score
                        best_match = cust
        elif len(cust_words) == 1 and len(cust_name) >= 5:
            if re.search(r'\b' + re.escape(cust_name) + r'\b', clean_text):
                score = 0.90
                if score > best_score:
                    best_score = score
                    best_match = cust
                    
    if best_match and best_score >= 0.70:
        best_match["customer_tier"] = "RETURNING"
        best_match["total_trips"] = max(best_match.get("total_trips") or 1, 1)
        if not best_match.get("nationality") and is_slavic_name(best_match.get("full_name", "")):
            best_match["nationality"] = "Russia"
        return best_match
        
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
    if not profile:
        return ""
        
    tier = str(profile.get("customer_tier") or "NEW").upper()
    total_trips = int(profile.get("total_trips") or 0)
    past_trips = profile.get("past_trips") or []
    
    # Nếu là trường hợp chọn khách cũ nhưng không tìm thấy trong CRM
    if profile.get("unverified_returning_attempt"):
        full_name = profile.get("full_name") or ""
        nat_lower = (profile.get("nationality") or "").lower()
        is_ru = any(k in nat_lower for k in ["russia", "russian", "nga", "belarus", "kazakh", "ukrain"]) or is_slavic_name(full_name)
        if is_ru:
            notice_sample = "Мы не нашли информацию о вашем предыдущем бронировании в нашей базе данных, поэтому для вашей поездки будет действовать стандартный тариф, указанный на нашем сайте."
            lang_dir = "MANDATORY LANGUAGE: RUSSIAN (Русский язык). You MUST reply completely in RUSSIAN!"
        elif any(k in nat_lower for k in ["vietnam", "vietnamese", "việt nam"]):
            notice_sample = "Chúng tôi không tìm thấy thông tin của bạn trên cơ sở dữ liệu của chúng tôi, vì vậy chúng ta sẽ áp dụng giá niêm yết trên website."
            lang_dir = "MANDATORY LANGUAGE: VIETNAMESE (Tiếng Việt)."
        else:
            notice_sample = "We could not find your previous booking information in our database, so standard website listed prices will apply to your booking."
            lang_dir = "MANDATORY LANGUAGE: ENGLISH."

        directive = f"""
======================================================================
⚠️ CRITICAL DIRECTIVE: NOT FOUND IN CRM DATABASE (USE STANDARD WEBSITE PRICE)
======================================================================
The customer previously selected 'Returning Customer' or provided old booking info, BUT their information was NOT found in our CRM database.

🎯 MANDATORY INSTRUCTIONS:
1. {lang_dir}
2. **CLEAR NOTICE TO CUSTOMER**: You MUST state clearly at the very beginning of your response that we could not find their information in our database, so standard website prices will apply:
   - Example statement: "{notice_sample}"
3. **STRICTLY APPLY STANDARD WEBSITE LISTED PRICING (NEW / RETAIL)**:
   - Russian citizens: Visarun 90D Single: **3,400,000 VND** / Multi: **4,400,000 VND** / Free Visa 45D: **1,400,000 VND**
   - Other nationalities: Cambodia 90D: **4,000,000 VND** / Free Visa 45D: **1,400,000 VND**
   - DO NOT offer returning customer discounts.
4. **POLITELY ASK FOR NEXT TRIP DETAILS**:
   - Ask for their intended departure date or preferred visa type to proceed.
======================================================================
"""
        return directive

    # Chỉ áp dụng khi là khách cũ có hồ sơ
    if tier not in ["RETURNING", "VIP"] and total_trips <= 0 and len(past_trips) == 0:
        return ""
        
    full_name = profile.get("full_name") or "Khách hàng"
    nationality = profile.get("nationality") or "Russia"
    pref_seat = profile.get("preferred_seat") or "Chưa có vị trí cố định"
    pref_pickup = profile.get("preferred_pickup") or "Oceanus Nha Trang"
    pref_route = profile.get("preferred_route") or "Visa Run"
    notes = profile.get("customer_notes") or ""
    
    last_trip_info = "Chưa có chuyến đi trước đó"
    if past_trips:
        latest = past_trips[0]
        last_trip_info = f"Chuyến {latest.get('route', '')} ngày {latest.get('departure_date', '')} (Ghế {latest.get('seat_number', '')})"

    visa_exp = profile.get("visa_expiry_date") or "Chưa rõ (hãy hỏi lại lịch sự)"
    
    nat_lower = nationality.lower()
    if any(k in nat_lower for k in ["russia", "russian", "nga", "belarus", "kazakh", "ukrain"]) or is_slavic_name(full_name):
        nationality = "Russia"
        lang_directive = "MANDATORY LANGUAGE: RUSSIAN (Русский язык). You MUST reply completely in RUSSIAN (e.g. 'Здравствуйте, {full_name}! С возвращением! Рада снова помочь вам с визараном...'). NEVER respond in English to this Russian customer!"
    elif any(k in nat_lower for k in ["vietnam", "vietnamese", "việt nam"]):
        lang_directive = "MANDATORY LANGUAGE: VIETNAMESE (Tiếng Việt). You MUST reply in VIETNAMESE!"
    elif any(k in nat_lower for k in ["korea", "korean", "hàn quốc"]):
        lang_directive = "MANDATORY LANGUAGE: KOREAN (한국어). You MUST reply in KOREAN!"
    elif any(k in nat_lower for k in ["china", "chinese", "trung quốc"]):
        lang_directive = "MANDATORY LANGUAGE: CHINESE (中文). You MUST reply in CHINESE!"
    else:
        lang_directive = "MANDATORY LANGUAGE: ENGLISH. Reply in clear, professional English."
    
    directive = f"""
======================================================================
🌟 CRITICAL DIRECTIVE - RETURNING CUSTOMER IDENTIFIED (HIGH PRIORITY)
======================================================================
Customer Profile:
- Full Name: {full_name}
- Nationality: {nationality}
- Loyalty Tier: {tier} (Total past trips completed: {max(total_trips, 1)})
- Recent Past Trip: {last_trip_info}
- Known Visa Expiry Date: {visa_exp}
- Preferred Seat: {pref_seat}
- Preferred Pickup Location: {pref_pickup}
- Preferred Route: {pref_route}
- Personal Notes & Habits: {notes or 'Khách hàng thân thiết, ưu tiên tư vấn nhanh chóng'}

🎯 CRITICAL LANGUAGE & PRICING REQUIREMENTS:
1. {lang_directive}

2. **WARM WELCOME AS A VALUED RETURNING FRIEND**:
   - Greet the customer warmly by their name ({full_name}) in their native language!
   - Acknowledge that they are a returning customer (e.g. 'С возвращением!' in Russian or 'Welcome back!').
   - Politely ask how their previous trip was.

3. **ZERO REDUNDANCY (DO NOT ASK KNOWN DETAILS)**:
   - DO NOT ask for their nationality again (you already know they are from {nationality}).
   - DO NOT re-explain basic visa run rules from scratch unless they explicitly ask.

4. **PROACTIVE SCHEDULING & PREFERENCES**:
   - Ask for their new visa expiry date or departure date to arrange the next trip.
   - Mention that you will reserve their favorite seat ({pref_seat}) and pick them up at {pref_pickup}.

5. **SPECIAL PRICING & BENEFITS (APPLY RETURNING DISCOUNT ACCURATELY)**:
   - **If customer is Russian / CIS citizen (Công dân Nga)**:
     * Visarun 90-day E-visa Single Entry (4 hours): **3,000,000 VND** (Special returning rate, discounted from new customer price 3,400,000 VND)
     * Visarun 90-day E-visa Multi Entry (4 hours): **4,000,000 VND** (Single + 1,000,000 VND, discounted from new customer price 4,400,000 VND)
     * Visarun Free Visa (45 days Bo Y): **1,300,000 VND** (Discounted from new customer 1,400,000 VND)
   - **If customer is Other Nationality (US, UK, Australia, Europe, etc.)**:
     * Visarun 90D E-visa (<2 days): **3,550,000 VND** (Discounted from new customer 4,000,000 VND)
     * Visarun Free Visa (45 days Bo Y / Moc Bai): **1,300,000 VND** (Discounted from new customer 1,400,000 VND)
   - Always emphasize that as a Valued Returning Customer ({tier}), they receive **Free Priority Seat Reservation ({pref_seat})** and dedicated fast check-in assistance!

6. **TONE STYLE**:
   - Extremely natural, warm, enthusiastic, attentive, and professional.
======================================================================
"""
    return directive
