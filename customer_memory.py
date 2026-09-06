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
        if "birth_year" not in cols:
            conn.execute("ALTER TABLE customers ADD COLUMN birth_year TEXT;")
        
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
        "total_trips", "customer_tier", "customer_notes", "birth_year"
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
        
    excluded_names = {
        'NO NAME', 'UNKNOWN', 'TEST', 'ADMIN', 'BOT', 'USER', 'CUSTOMER', 
        'EASYTRIP', 'EASY TRIP', 'EASYTRIP VISA', 'EASYTRIP VISA ASSISTANT'
    }
    common_words = {
        'DATE', 'TIME', 'NAME', 'SEAT', 'SERVICE', 'VISA', 'PASSENGER', 'RECEIPT', 
        'PAYMENT', 'BOT', 'USER', 'ASSISTANT', 'EASYTRIP', 'PLACE', 'PICK', 'DROP', 
        'METHOD', 'CASHIER', 'TRANSFER', 'AMOUNT', 'TYPES', 'ENTRY', 'URGENT', 'HOURS',
        'LAOS', 'CAMBODIA', 'VIETNAM', 'NHA', 'TRANG', 'BO', 'Y', 'MOC', 'BAI', 'BUS',
        'PAID', 'FAST', 'TRACK', 'PEOPLE', 'DAYS', 'DAY', 'SINGLE', 'MULTI'
    }

    import unicodedata
    
    def strip_accents(s: str) -> str:
        if not s:
            return ""
        nfkd_form = unicodedata.normalize('NFKD', s)
        return ''.join([c for c in nfkd_form if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

    normalized_text = strip_accents(normalized_text)

    # 2. Trích xuất Tên và Năm sinh từ nội dung / vé / biên nhận
    name_extracted = None
    m_name = re.search(r'(?:Name|Tên|ФИО|Passenger|Khách)[ \t]*[:：][ \t]*([^\n\r]+)', normalized_text, re.IGNORECASE)
    if m_name:
        val = re.sub(r'[^a-zA-Z\s,]', '', m_name.group(1)).strip().upper()
        if val and len(val) >= 3 and val not in common_words:
            name_extracted = val
        
    year_extracted = None
    m_year = re.search(r'(?:Year\s*of\s*birth|Năm\s*sinh|Год\s*рождения|Birth\s*year|YOB|DOB|Birth)[ \t]*[:：]?[ \t]*(\d{4})', normalized_text, re.IGNORECASE)
    if m_year:
        year_extracted = m_year.group(1)
    else:
        m_year_alt = re.search(r'\b(19\d{2}|20[0-2]\d)\b', normalized_text)
        if m_year_alt:
            year_extracted = m_year_alt.group(1)

    def is_invalid_customer_name(name: str) -> bool:
        if not name or len(name.strip()) < 3:
            return True
        nu = name.strip().upper()
        # Loại trừ nếu chứa chữ số (VD: Happy888, 03/05 - 90D Laos, 24/08) hoặc từ khoá trạng thái đơn hàng
        if re.search(r'\d', nu) or '- PAID' in nu or 'PAID' in nu.split() or 'PEOPLE' in nu.split():
            return True
        system_patterns = [
            'NO NAME', 'UNKNOWN', 'TEST', 'ADMIN', 'BOT', 'USER', 'CUSTOMER',
            'EASY TRIP', 'EASYTRIP', 'ASIA MIX', 'FAST TRACK',
            'НЯЧАНГ', 'NYACHANG', 'NHATRANG', 'NHA TRANG', 'ЧАТ', 'CHAT', 
            'ОБЪЯВЛЕНИЯ', 'БАРАХОЛКА', 'ТУСА', 'АФИША', 'ЭКСКУРСИИ', 'ОНЛАЙН',
            'GROUP', 'HOTEL', 'RESORT', 'TOUR', 'VISA OPERATION'
        ]
        if any(s in nu for s in system_patterns):
            if re.search(r'^[A-Z\s]{4,}\s*\(', nu):
                return False
            return True
        return False

    clean_text = ' ' + re.sub(r'[^A-Z0-9\s]', ' ', normalized_text.upper()) + ' '
    text_words = [w for w in clean_text.split() if len(w) >= 2]

    def match_name_in_window(cust_name_words: List[str], target_words: List[str]) -> float:
        n = len(cust_name_words)
        if n == 0 or len(target_words) < n:
            return 0.0
        best_score = 0.0
        # Kiểm tra cả thứ tự xuôi (Họ Tên) và ngược (Tên Họ)
        for words_to_try in [cust_name_words, list(reversed(cust_name_words))]:
            for i in range(len(target_words) - n + 1):
                window = target_words[i:i + n]
                # Bắt buộc TẤT CẢ các từ trong cụm tên đều phải khớp tối thiểu 75%
                word_ratios = [difflib.SequenceMatcher(None, words_to_try[k], window[k]).ratio() for k in range(n)]
                if min(word_ratios) >= 0.75 and (sum(word_ratios) / n) >= 0.85:
                    score = sum(word_ratios) / n
                    if score > best_score:
                        best_score = score
        return best_score

    c.execute('SELECT * FROM customers WHERE full_name IS NOT NULL AND length(trim(full_name)) >= 3')
    all_customers = [dict(row) for row in c.fetchall() if not is_invalid_customer_name(dict(row)['full_name'])]

    matched_candidates = []
    
    for cust in all_customers:
        cust_name = cust['full_name'].strip().upper()
        if cust_name in excluded_names:
            continue
        clean_cust_name = strip_accents(cust_name)
        clean_cust_name = re.sub(r'[^A-Z\s]', '', clean_cust_name.upper()).strip()
        cust_words = [w for w in re.split(r'\s+', clean_cust_name) if len(w) >= 2 and not w.isdigit() and w not in common_words]
        if not cust_words:
            continue
            
        # A. So khớp cụm từ liền kề qua cửa sổ trượt (Sliding window matching)
        score_text = match_name_in_window(cust_words, text_words)

        # B. So khớp với trường Name trích xuất nếu có
        score_field = 0.0
        if name_extracted and len(name_extracted) >= 4:
            clean_extracted_name = re.sub(r'[^A-Z\s]', '', name_extracted).strip()
            ratio_direct = difflib.SequenceMatcher(None, clean_cust_name, clean_extracted_name).ratio()
            words_cust_sorted = ' '.join(sorted(clean_cust_name.split()))
            words_ext_sorted = ' '.join(sorted(clean_extracted_name.split()))
            ratio_sorted = difflib.SequenceMatcher(None, words_cust_sorted, words_ext_sorted).ratio()
            score_field = max(ratio_direct, ratio_sorted)

        final_score = max(score_text, score_field)

        # RÀNG BUỘC NĂM SINH (NẾU CÓ):
        if final_score >= 0.65 and year_extracted:
            cust_birth = cust.get("birth_year")
            if cust_birth:
                if str(cust_birth).strip() == str(year_extracted).strip():
                    final_score = min(1.0, final_score + 0.15)  # Trùng cả Tên + Năm sinh -> Gia tăng độ tin cậy
                else:
                    final_score = final_score * 0.3  # Khác năm sinh -> Trùng tên nhưng khác người, loại trừ
                    
        if final_score >= 0.80:
            matched_candidates.append((final_score, cust))
                    
    if not matched_candidates:
        return None
        
    matched_candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_match = matched_candidates[0]
    
    # Gom danh sách hành khách đi cùng nếu là vé đoàn / gia đình
    other_members = [c['full_name'] for sc, c in matched_candidates[1:]]
    group_seats = [c.get('preferred_seat') for sc, c in matched_candidates if c.get('preferred_seat')]
    if other_members:
        best_match['accompanying_passengers'] = other_members
    if group_seats:
        best_match['group_seats'] = list(dict.fromkeys(group_seats))

    # Nếu tìm thấy khách và trên vé có năm sinh nhưng trong DB chưa có -> Cập nhật năm sinh
    if year_extracted and not best_match.get("birth_year"):
        try:
            c.execute("UPDATE customers SET birth_year = ? WHERE customer_id = ?", (year_extracted, best_match["customer_id"]))
            conn.commit()
            best_match["birth_year"] = year_extracted
        except Exception:
            pass

    best_match["customer_tier"] = "RETURNING"
    best_match["total_trips"] = max(best_match.get("total_trips") or 1, 1)
    if not best_match.get("nationality") and is_slavic_name(best_match.get("full_name", "")):
        best_match["nationality"] = "Russia"
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM trip_history 
            WHERE customer_id = ? 
            ORDER BY trip_id DESC LIMIT 5
        """, (best_match["customer_id"],))
        trips = [dict(t) for t in cursor.fetchall()]
        best_match["past_trips"] = trips
    except Exception:
        pass
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
   - Korea / Japan citizens (Visa-free 45D Laos): **1,400,000 VND**
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
        last_trip_info = f"Chuyến {latest.get('route', '')} ngày {latest.get('departure_date', '')} (Ghế {latest.get('seat_number', '')}, Điểm đón {latest.get('pickup_location', '')})"

    visa_exp = profile.get("visa_expiry_date") or "Chưa rõ (hãy hỏi lại lịch sự)"
    
    nat_lower = nationality.lower()
    if any(k in nat_lower for k in ["russia", "russian", "nga", "belarus", "kazakh", "ukrain"]) or is_slavic_name(full_name):
        nationality = "Russia"
        lang_directive = "MANDATORY LANGUAGE: RUSSIAN (Русский язык). You MUST reply completely in RUSSIAN (e.g. 'Здравствуйте, {full_name}! С возвращением! Рада снова помочь вам с визараном...'). NEVER respond in English to this Russian customer!"
    elif any(k in nat_lower for k in ["vietnam", "vietnamese", "việt nam"]):
        lang_directive = "MANDATORY LANGUAGE: VIETNAMESE (Tiếng Việt). You MUST reply in VIETNAMESE!"
    elif any(k in nat_lower for k in ["korea", "korean", "hàn quốc"]):
        lang_directive = "MANDATORY LANGUAGE: KOREAN (한국어). You MUST reply in KOREAN (e.g. '안녕하세요, {full_name} 고객님! Easy Trip & Visa를 다시 찾아주셔서 감사합니다...')."
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
- Known Visa Expiry Date: {visa_exp}
- Previous Service: {pref_route}
- Preferred Seat: {pref_seat}
- Preferred Pickup Location: {pref_pickup}
- Personal Notes & Habits: {notes or 'Khách hàng thân thiết, ưu tiên tư vấn nhanh chóng'}

🎯 CRITICAL WORKFLOW & PRICING REQUIREMENTS:
1. {lang_directive}

2. **WARM WELCOME & ASK TO RE-BOOK PREVIOUS SERVICE (HỎI ĐẶT LẠI DỊCH VỤ CŨ)**:
   - Greet the customer warmly by their name ({full_name}) in their native language!
   - Confirm they are a valued returning customer and ask directly: "Would you like to re-book the same service ({pref_route}) for your next upcoming trip?"
   - Mention the special returning customer discounted rate.
   - ⚠️ **CRITICAL RULE: DO NOT RECITE DETAILED OLD TRIP INFO** (Do NOT list old past dates, old seats, or old pickups in detail unless needed, to keep the message clean and concise).
   - ⚠️ **NEVER confirm booking for the old past date**.

3. **TWO-BRANCH HANDLING (XỬ LÝ 2 NHÁNH PHẢN HỒI)**:
   - **Branch A (Customer wants to re-book previous service)**:
     * Ask for their new intended departure date / visa expiry date and provide the Standard Booking Form.
   - **Branch B (Customer does NOT want previous service / wants a different service)**:
     * Ask ONLY these 2 concise questions:
       1. What service type do they want (45D Visa-free / 90D E-visa Single or Multi / or E-visa only)?
       2. What date do they plan to travel (or when does their visa expire)?
     * Then provide the Standard Booking Form to finalize the booking.

4. **SPECIAL RETURNING PRICING & BENEFITS (BÁO GIÁ ƯU ĐÃI KHÁCH CŨ)**:
   - **If customer is Korean / Japan / Visa-free 45-day Laos (như khách {full_name})**:
     * Visarun Free Visa 45-Day Laos (Bo Y): **1,300,000 VND** (Special returning rate, discounted from new customer price 1,400,000 VND!)
   - **If customer is Russian / CIS citizen (Công dân Nga)**:
     * Visarun 90-day E-visa Single Entry (4 hours): **3,000,000 VND** (Special returning rate, discounted from new customer price 3,400,000 VND)
     * Visarun 90-day E-visa Multi Entry (4 hours): **4,000,000 VND** (Single + 1,000,000 VND, discounted from new customer price 4,400,000 VND)
     * Visarun Free Visa (45 days Bo Y): **1,300,000 VND** (Discounted from new customer 1,400,000 VND)
   - **If customer is Other Nationality (US, UK, Australia, Europe, etc.)**:
     * Visarun 90D E-visa (<2 days): **3,550,000 VND** (Discounted from new customer 4,000,000 VND)
     * Visarun Free Visa (45 days Bo Y / Moc Bai): **1,300,000 VND** (Discounted from new customer 1,400,000 VND)
   - Always emphasize that as a Valued Returning Customer ({tier}), they receive **Free Priority Seat Reservation ({pref_seat})** and dedicated fast check-in assistance!

5. **TONE STYLE**:
   - Extremely natural, warm, enthusiastic, attentive, and professional.
======================================================================
"""
    return directive
