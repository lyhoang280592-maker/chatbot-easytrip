import os
import time
import re
import json
import traceback
import httpx
from typing import Any, Optional, Dict, List
from datetime import datetime
from fastapi import APIRouter, Request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

from memory_store import memory_store, load_session_history
import customer_memory
from ai_agent import process_chat, identify_image_type
from lark_api import create_customer_record, upload_image_to_lark, update_customer_image, update_order_status, create_order
from i18n import get_lang_code, get_msg
from seat_map_generator import generate_seat_map, RELATIVE_COORDINATES

router = APIRouter()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "")
BUS_GROUP_CHAT_ID = os.getenv("BUS_GROUP_CHAT_ID", "")
BUS_GROUP_TOPIC_ID = os.getenv("BUS_GROUP_TOPIC_ID", "")
ADMIN_GROUP_CHAT_ID = os.getenv("ADMIN_GROUP_CHAT_ID", "")
ADMIN_GROUP_TOPIC_ID = os.getenv("ADMIN_GROUP_TOPIC_ID", "")

# Biến toàn cục
date_to_topic_id_map = {}
latest_seat_maps = {}  
scheme_history = {}  

# Load topic map from file if exists
TOPIC_MAP_FILE = "topic_map.json"
try:
    import os
    if os.path.exists(TOPIC_MAP_FILE):
        with open(TOPIC_MAP_FILE, "r") as f:
            date_to_topic_id_map = json.load(f)
        print(f"Loaded topic map: {date_to_topic_id_map}")
except Exception as e:
    print("Lỗi load topic_map.json:", e)


# ============================================================
# CÁC HÀM HELPER
# ============================================================
def log_message(user_id, platform, role, content, customer_id: Optional[int] = None):
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": str(user_id),
        "platform": platform,
        "role": role,
        "content": content,
    }
    if customer_id is not None:
        log_entry["customer_id"] = customer_id
    try:
        with open("chat_history.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        session_id = f"{platform.lower()}_{user_id}"
        customer_memory.save_chat_message(session_id, platform.lower(), role.lower(), content, customer_id=customer_id)
    except Exception:
        pass


def normalize_date(date_str: str) -> str:
    if not date_str: return ""
    # Loại bỏ khoảng trắng và chuyển về chuỗi
    date_str = str(date_str).replace(" ", "")
    # Tách các phần bằng / . -
    parts = [p for p in re.split(r"[/.-]", date_str) if p]
    
    day, month = "", ""
    
    # Tìm ngày và tháng trong các phần (bỏ qua phần có 4 chữ số là Năm)
    numeric_parts = [p for p in parts if p.isdigit()]
    
    if len(numeric_parts) >= 2:
        # Nếu định dạng YYYY-MM-DD
        if len(numeric_parts[0]) == 4:
            month, day = numeric_parts[1], numeric_parts[2] if len(numeric_parts) > 2 else ""
        # Nếu định dạng DD-MM-YYYY hoặc DD-MM
        else:
            day, month = numeric_parts[0], numeric_parts[1]
            
        if day and month:
            if len(day) == 1: day = "0" + day
            if len(month) == 1: month = "0" + month
            # Chỉ lấy 2 chữ số cuối nếu lỡ lấy nhầm năm
            return f"{day[-2:]}/{month[-2:]}"
            
    return str(date_str)


def parse_topic_name(name: str) -> tuple[str, str]:
    if not name: return "", ""
    name_lower = name.lower()
    
    # 1. Tìm ngày dạng DD/MM hoặc DD-MM hoặc DD.MM
    date_match = re.search(r"(\d{1,2})[/.-](\d{1,2})", name)
    date_str = ""
    if date_match:
        day = date_match.group(1)
        month = date_match.group(2)
        if len(day) == 1: day = "0" + day
        if len(month) == 1: month = "0" + month
        date_str = f"{day}/{month}"
        
    # 2. Tìm loại hình dịch vụ
    service_str = ""
    if "90" in name_lower:
        service_str = "90D"
    elif "cambodia" in name_lower or "campuchia" in name_lower or "mộc bài" in name_lower or "moc bai" in name_lower:
        service_str = "Cambodia"
    else:
        # Mặc định là 45D
        service_str = "45D"
        
    return date_str, service_str


async def get_or_register_topic_key(bot, thread_id: int) -> str | None:
    if not thread_id:
        return None
        
    # 1. Tìm trong bộ nhớ hiện tại
    for key, tid in date_to_topic_id_map.items():
        if tid == thread_id:
            return key
            
    # 2. Gọi API Telegram lấy tên topic
    try:
        topic = await bot.get_forum_topic(chat_id=BUS_GROUP_CHAT_ID, message_thread_id=thread_id)
        if topic and topic.name:
            t_date, t_service = parse_topic_name(topic.name)
            if t_date:
                service = t_service or "45D"
                key = f"{t_date}_{service}"
                date_to_topic_id_map[key] = thread_id
                # Lưu vào file
                try:
                    with open(TOPIC_MAP_FILE, "w") as f:
                        json.dump(date_to_topic_id_map, f)
                except:
                    pass
                print(f"📌 Tự động ánh xạ Topic động thành công: '{topic.name}' -> Key: {key}")
                return key
    except Exception as e:
        print(f"Lỗi lấy thông tin Forum Topic {thread_id}: {e}")
        
    return None


def get_customer_service_type(data, history_text: str) -> str:
    history_lower = (history_text or "").lower()
    loai_lower = (getattr(data, "loai_visa", "") or "").lower()
    quoc_tich_lower = (getattr(data, "quoc_tich", "") or "").lower()
    
    cambodia_keywords = [
        "us", "usa", "american", "uk", "british", "germany", "german", "france", "french", 
        "canada", "canadian", "australia", "australian", "india", "indian", "mỹ", "anh", "pháp", "đức"
    ]
    
    is_cambodia = False
    for kw in cambodia_keywords:
        if kw in ["us", "uk", "mỹ", "anh", "đức"]:
            # Strict whole-word matching to avoid matching substrings like "bus"
            if re.search(r"\b" + re.escape(kw) + r"\b", history_lower) or re.search(r"\b" + re.escape(kw) + r"\b", quoc_tich_lower):
                is_cambodia = True
                break
        else:
            if kw in history_lower or kw in quoc_tich_lower:
                is_cambodia = True
                break
                
    if is_cambodia or "cambodia" in history_lower or "campuchia" in history_lower or "mộc bài" in history_lower or "moc bai" in history_lower:
        return "Cambodia"
    elif "90" in loai_lower:
        return "90D"
    else:
        return "45D"  # Mặc định


def get_scheme_command(ngay: str, loai_visa: str, text_history: str) -> str | None:
    if not ngay: return None
    ngay_clean = normalize_date(ngay)
    service = get_customer_service_type(None, f"{loai_visa} {text_history}")
    if service == "Cambodia":
        return f"Scheme {ngay_clean} Cambodia"
    elif service == "90D":
        return f"Scheme {ngay_clean} - 90D laos"
    else:
        return f"Scheme {ngay_clean} - 45D laos"


def calculate_smart_departure(ngay_het_han: str, loai_visa: str = "", destination: str = "laos") -> str | None:
    """Tính ngày khởi hành dựa trên lịch xe buýt.
    - 45 ngày Laos (Nha Trang): chạy MỖI NGÀY → departure = expiry - 1
    - 90 ngày Laos / Cambodia (45 & 90): chạy Thứ 3, 5, CN → tìm ngày gần nhất ≤ expiry - 1
    """
    if not ngay_het_han: return None
    try:
        from datetime import datetime, timedelta
        exp_dt = None
        for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]:
            try:
                exp_dt = datetime.strptime(ngay_het_han, fmt)
                if "%Y" not in fmt and "%y" not in fmt:
                    exp_dt = exp_dt.replace(year=datetime.now().year)
                break
            except: continue
        if not exp_dt: return None

        latest = exp_dt - timedelta(days=1)  # Ngày muộn nhất có thể đi
        loai_lower = (loai_visa or "").lower()
        dest_lower = (destination or "").lower()

        # 45 ngày Laos chạy mỗi ngày
        is_daily = "45" in loai_lower and "cambodia" not in dest_lower and "campuchia" not in dest_lower
        if is_daily:
            return latest.strftime("%d/%m")

        # 90 ngày Laos + Cambodia (45 & 90) chạy Thứ 3, 5, CN
        # weekday(): Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
        valid_days = {1, 3, 6}  # Tue=1, Thu=3, Sun=6
        for i in range(7):
            check = latest - timedelta(days=i)
            if check.weekday() in valid_days:
                return check.strftime("%d/%m")
        return latest.strftime("%d/%m")
    except Exception as e:
        print(f"Departure calc error: {e}")
        return None


def validate_and_adjust_departure(ngay_khoi_hanh: str, ngay_het_han: str, loai_visa: str = "", destination: str = "laos") -> str | None:
    """Kiểm tra và tự động điều chỉnh ngày khởi hành cho khớp lịch chạy xe buýt thực tế (Thứ 3, 5, CN).
    Nếu ngày khởi hành khách chọn không khớp lịch chạy xe, bot tự lùi về ngày chạy gần nhất trước đó.
    """
    calculated_date = calculate_smart_departure(ngay_het_han, loai_visa, destination)
    if not ngay_khoi_hanh:
        return calculated_date
        
    ngay_khoi_hanh_clean = normalize_date(ngay_khoi_hanh)
    if ngay_khoi_hanh_clean == calculated_date:
        return calculated_date

    try:
        from datetime import datetime, timedelta
        dt = None
        for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]:
            try:
                dt = datetime.strptime(ngay_khoi_hanh_clean, fmt)
                if "%Y" not in fmt and "%y" not in fmt:
                    dt = dt.replace(year=datetime.now().year)
                break
            except: continue
        if not dt:
            return calculated_date

        loai_lower = (loai_visa or "").lower()
        dest_lower = (destination or "").lower()

        # 45 ngày Laos chạy mỗi ngày
        is_daily = "45" in loai_lower and "cambodia" not in dest_lower and "campuchia" not in dest_lower
        if is_daily:
            return ngay_khoi_hanh_clean

        # Lịch chạy cố định: Thứ 3 (1), Thứ 5 (3), Chủ Nhật (6)
        valid_days = {1, 3, 6}
        if dt.weekday() in valid_days:
            return ngay_khoi_hanh_clean
        
        # Nếu không hợp lệ lịch chạy, tìm ngày chạy gần nhất trước đó
        for i in range(1, 8):
            check = dt - timedelta(days=i)
            if check.weekday() in valid_days:
                adjusted_date = check.strftime("%d/%m")
                print(f"🔄 Điều chỉnh ngày khởi hành: {ngay_khoi_hanh_clean} -> {adjusted_date} (Khớp Thứ 3, 5, CN)")
                return adjusted_date
    except Exception as e:
        print(f"Lỗi validate_and_adjust_departure: {e}")

    return calculated_date



async def send_to_bus_group(context, message: str, date: str | None = None, service: str | None = None):
    if not BUS_GROUP_CHAT_ID: return
    try:
        topic_id = None
        if date:
            ngay_clean = normalize_date(date)
            service = service or "45D"
            key = f"{ngay_clean}_{service}"
            topic_id = date_to_topic_id_map.get(key)
            # Fallback to key without service if not found
            if topic_id is None:
                topic_id = date_to_topic_id_map.get(ngay_clean)
        if topic_id is None and BUS_GROUP_TOPIC_ID:
            topic_id = int(BUS_GROUP_TOPIC_ID)
        bot = context.bot if context else tg_app.bot
        await bot.send_message(chat_id=BUS_GROUP_CHAT_ID, text=message, message_thread_id=topic_id)
    except Exception as e: print("Bus Group Error:", e)


async def get_or_create_seat_map(ngay: str, service: str) -> dict | None:
    """
    Lấy thông tin sơ đồ ghế (file_id, url) cho ngày và dịch vụ cụ thể.
    Nếu chưa có sơ đồ chính thức trên đĩa, tự động tạo sơ đồ trống từ ảnh mẫu.
    """
    ngay_clean = normalize_date(ngay)
    if not ngay_clean:
        return None
        
    service = service or "45D"
    key = f"{ngay_clean}_{service}"
    file_path = f"static/map_{ngay_clean.replace('/', '_')}_{service}.jpg"

    # 1. Kiểm tra bộ nhớ và đĩa cứng
    if key in latest_seat_maps:
        if os.path.exists(file_path):
            return latest_seat_maps[key]

    # 2. Nếu file tồn tại trên đĩa (đã được tải về từ đối tác) nhưng chưa có trong latest_seat_maps
    if os.path.exists(file_path):
        file_id = None
        try:
            bot = tg_app.bot
            target_chat_id = BUS_GROUP_CHAT_ID or ADMIN_TELEGRAM_ID
            topic_id = date_to_topic_id_map.get(key)
            if topic_id is None and BUS_GROUP_TOPIC_ID:
                topic_id = int(BUS_GROUP_TOPIC_ID)
                
            if target_chat_id:
                with open(file_path, "rb") as f:
                    msg = await bot.send_photo(
                        chat_id=target_chat_id,
                        photo=f,
                        caption=f"📋 Đồng bộ sơ đồ chính thức ngày {ngay_clean} - Dịch vụ: {service}",
                        message_thread_id=topic_id if BUS_GROUP_CHAT_ID else None
                    )
                    file_id = msg.photo[-1].file_id
        except Exception as e:
            print(f"Không thể upload sơ đồ {key} lên Telegram: {e}")

        map_data = {
            "file_id": file_id,
            "url": f"/static/map_{ngay_clean.replace('/', '_')}_{service}.jpg"
        }
        latest_seat_maps[key] = map_data
        return map_data

    # 3. Tự động vẽ sơ đồ trống từ ảnh mẫu nếu chưa có ảnh từ đối tác
    print(f"🧠 Sơ đồ cho {key} chưa tồn tại. Tự động vẽ sơ đồ trống từ ảnh mẫu...")
    try:
        # Tự động tạo thư mục static nếu thiếu
        if not os.path.exists("static"):
            os.makedirs("static")
            
        # Tạo sơ đồ trống ban đầu (không có ghế nào bận)
        generate_seat_map([], output_path=file_path)
        
        # Thử upload lên Telegram để lấy file_id phục vụ gửi siêu tốc lần sau
        file_id = None
        try:
            bot = tg_app.bot
            target_chat_id = BUS_GROUP_CHAT_ID or ADMIN_TELEGRAM_ID
            topic_id = date_to_topic_id_map.get(key)
            if topic_id is None and BUS_GROUP_TOPIC_ID:
                topic_id = int(BUS_GROUP_TOPIC_ID)
                
            if target_chat_id:
                with open(file_path, "rb") as f:
                    msg = await bot.send_photo(
                        chat_id=target_chat_id,
                        photo=f,
                        caption=f"📋 Khởi tạo sơ đồ trống ngày {ngay_clean} - Dịch vụ: {service}",
                        message_thread_id=topic_id if BUS_GROUP_CHAT_ID else None
                    )
                    file_id = msg.photo[-1].file_id
        except Exception as e:
            print(f"Không thể upload sơ đồ tự tạo {key} lên Telegram: {e}")

        map_data = {
            "file_id": file_id,
            "url": f"/static/map_{ngay_clean.replace('/', '_')}_{service}.jpg"
        }
        latest_seat_maps[key] = map_data
        return map_data
    except Exception as e:
        print(f"Lỗi khi tự động tạo sơ đồ ghế trống: {e}")
        return None


async def send_to_admin_group(context, message: str):
    if not ADMIN_GROUP_CHAT_ID: return
    try:
        topic_id = int(ADMIN_GROUP_TOPIC_ID) if ADMIN_GROUP_TOPIC_ID else None
        bot = context.bot if context else tg_app.bot
        await bot.send_message(chat_id=ADMIN_GROUP_CHAT_ID, text=message, message_thread_id=topic_id)
    except Exception as e: print("Admin Group Error:", e)


# ============================================================
# KHỞI TẠO BOT
# ============================================================
# KHỞI TẠO BOT
# ============================================================
tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def send_new_customer_welcome_menu(chat_id: str | int, target_msg, conn_id=None):
    welcome_text = (
        "Welcome to Easy Trip & Visa. I'm here to help you with your Visarun trip. \n"
        "Could you please tell me: \n"
        "Your nationality\n"
        "Current city\n"
        "visa expiry date?"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚌 Laos Visa Run 45 Days (Visa Free)", callback_data="service|laos_45d")],
        [InlineKeyboardButton("🚌 Laos Visa Run 90 Days (E-Visa)", callback_data="service|laos_90d")],
        [InlineKeyboardButton("🚌 Cambodia Visa Run 90 Days", callback_data="service|cambodia_90d")],
        [
            InlineKeyboardButton("⚡ Urgent E-Visa Service", callback_data="service|evisa_urgent"),
            InlineKeyboardButton("✈️ Airport Fast Track & Motorbike", callback_data="service|fast_track")
        ],
        [InlineKeyboardButton("💬 Direct Telegram Support", url="https://t.me/easytripvisa_co_ltd")],
        [InlineKeyboardButton("💬 Direct WhatsApp Support", url="https://wa.me/84868462071")]
    ])
    
    if target_msg:
        if conn_id:
            await target_msg.reply_text(welcome_text, reply_markup=keyboard, parse_mode="Markdown", business_connection_id=conn_id)  # type: ignore
        else:
            await target_msg.reply_text(welcome_text, reply_markup=keyboard, parse_mode="Markdown")


async def send_returning_customer_request(chat_id: str | int, target_msg, conn_id=None):
    returning_prompt = (
        "🌟 **RETURNING CUSTOMER / FRIEND REFERRAL LOYALTY DISCOUNT**\n\n"
        "If you are a returning customer, **or a friend/relative booked on your behalf in the past**, or you previously used **another account/channel**, please send your **previous booking confirmation message, ticket screenshot, or your Full Passport Name / Phone number** to verify and receive your exclusive discount.\n\n"
        "📌 **Example Booking Format:**\n"
        "```text\n"
        "10/09 - 90D - Laos\n"
        "FULL NAME (As on Passport)\n"
        "Seat: B10\n"
        "Pickup: 40 Hon Chong - 9:30 PM\n"
        "```\n\n"
        "────────────────────\n"
        "🌟 **СПЕЦИАЛЬНАЯ ЦЕНА ДЛЯ ПОСТОЯННЫХ КЛИЕНТОВ И ИХ ДРУЗЕЙ**\n\n"
        "Если вы уже путешествовали с нами, **или бронировали через друзей/знакомых**, либо ранее писали с **другого аккаунта/устройства**, пожалуйста, отправьте **текст предыдущего бронирования, скриншот билета или ваши ФИО на латинице (по загранпаспорту) / номер телефона** для подтверждения и получения специальной цены постоянного клиента.\n\n"
        "📌 **Пример формата бронирования:**\n"
        "```text\n"
        "10/09 - 90D - Laos\n"
        "ФИО (по загранпаспорту)\n"
        "Место: B10\n"
        "Посадка: 40 Hon Chong - 21:30\n"
        "```"
    )
    if target_msg:
        if conn_id:
            await target_msg.reply_text(returning_prompt, parse_mode="Markdown", business_connection_id=conn_id)  # type: ignore
        else:
            await target_msg.reply_text(returning_prompt, parse_mode="Markdown")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id) if update.effective_user else ""
    session_id = f"telegram_{user_id}"
    
    # Reset phiên chat trong bộ nhớ khi /start
    memory_store[session_id] = []
    memory_store[f"{session_id}_mode"] = "auto"
    if f"{session_id}_data" in memory_store:
        del memory_store[f"{session_id}_data"]
    if f"{session_id}_draft" in memory_store:
        del memory_store[f"{session_id}_draft"]
    if f"{session_id}_awaiting_old_booking" in memory_store:
        del memory_store[f"{session_id}_awaiting_old_booking"]

    welcome_question = (
        "👋 **Welcome to Easy Trip & Visa!**\n"
        "Have you (or a friend on your behalf) booked any service with us before?\n\n"
        "👋 **Здравствуйте! Добро пожаловать в Easy Trip & Visa.**\n"
        "Вы (или ваши знакомые для вас) уже пользовались нашими услугами ранее?"
    )
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 Returning / Friend Booked (Discount) / Постоянный клиент", callback_data="cust_type|returning")],
        [InlineKeyboardButton("🆕 New Customer / Новый клиент", callback_data="cust_type|new")],
        [InlineKeyboardButton("💬 Direct Telegram Support", url="https://t.me/easytripvisa_co_ltd")],
        [InlineKeyboardButton("💬 Direct WhatsApp Support", url="https://wa.me/84868462071")]
    ])
    
    target_msg: Any = update.message or (update.callback_query.message if update.callback_query else None)
    if target_msg:
        await target_msg.reply_text(welcome_question, reply_markup=keyboard, parse_mode="Markdown")


async def get_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.effective_chat:
        await update.message.reply_text(f"📍 Chat ID: `{update.effective_chat.id}`\nType: {update.effective_chat.type}", parse_mode='Markdown')


# ============================================================
# LOGIC XỬ LÝ TIN NHẮN TỪ KHÁCH HÀNG (TEXT & NÚT BẤM)
# ============================================================
async def process_customer_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str):
    session_id = f"telegram_{user_id}"
    
    # 0. Bắn tín hiệu "Đang soạn tin nhắn..." (Typing Indicator) tức thì
    try:
        target_chat_id = update.effective_chat.id if update.effective_chat else int(user_id)
        await context.bot.send_chat_action(chat_id=target_chat_id, action="typing")
    except Exception:
        pass

    # 1. Truy xuất / Tra soát hồ sơ khách hàng bền vững từ SQLite & CRM
    full_name_tg = update.effective_user.full_name if update.effective_user else None
    is_awaiting_old = memory_store.get(f"{session_id}_awaiting_old_booking", False)
    
    # Tra soát xem tin nhắn có chứa thông tin booking cũ / tên khách cũ không
    matched_cust = customer_memory.find_customer_by_booking_text(text)
    
    if matched_cust:
        print(f"🎯 Đã nhận diện Khách Cũ từ tin nhắn/booking: {matched_cust.get('full_name')} (ID {matched_cust.get('customer_id')})")
        cust_id_target = matched_cust.get("customer_id")
        cust_profile = None
        if cust_id_target:
            cust_profile = customer_memory.link_telegram_to_customer(cust_id_target, user_id)
        if not cust_profile:
            cust_profile = matched_cust
        memory_store.pop(f"{session_id}_awaiting_old_booking", None)
    else:
        cust_profile = customer_memory.get_or_create_customer("telegram", user_id, full_name=full_name_tg)
        if is_awaiting_old:
            memory_store.pop(f"{session_id}_awaiting_old_booking", None)
            if cust_profile:
                cust_profile["unverified_returning_attempt"] = True

    cust_id = cust_profile.get("customer_id") if cust_profile else None


    log_message(user_id, "Telegram", "User", text, customer_id=cust_id)
    load_session_history(session_id)
    
    # Ghi nhận tên hiển thị & thời gian cập nhật cuối
    if update.effective_user:
        memory_store[f"{session_id}_name"] = update.effective_user.full_name
    memory_store[f"{session_id}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Kiểm tra chế độ Bot
    mode = memory_store.get(f"{session_id}_mode", "auto")
    if mode == "manual":
        # Chế độ thủ công, chỉ ghi nhận tin nhắn, không trả lời tự động
        memory_store[session_id].append({"role": "user", "content": text})
        return
        
    if mode == "copilot":
        # Chế độ Co-pilot, tạo tin nhắn nháp và thông báo cho admin duyệt
        memory_store[session_id].append({"role": "user", "content": text})
        try:
            ai_response = await process_chat(memory_store[session_id], customer_profile=cust_profile)
            reply = ai_response.reply_message
            memory_store[f"{session_id}_draft"] = reply
            memory_store[f"{session_id}_draft_data"] = ai_response.extracted_data
            memory_store[f"{session_id}_draft_phase"] = ai_response.current_phase
            
            # Gửi tin nhắn thông báo cho admin duyệt
            admin_id = os.getenv("ADMIN_TELEGRAM_ID")
            if admin_id:
                cust_name = memory_store.get(f"{session_id}_name", "Khách hàng")
                await context.bot.send_message(
                    chat_id=int(admin_id),
                    text=f"🤖 **[Dự thảo Co-Pilot] (Telegram)**\n👤 Khách hàng: {cust_name}\n💬 Hỏi: \"{text}\"\n📝 Dự thảo: \"{reply}\"\n👉 Vui lòng duyệt trên Live Chat Studio!"
                )
        except Exception as e:
            print("Lỗi tạo bản nháp Co-Pilot Telegram:", e)
        return

    # Lấy trạng thái trước đó để so sánh thay đổi
    prev_data = memory_store.get(f"{session_id}_data")
    prev_seat = getattr(prev_data, "ghe_chon", None) if prev_data else None

    memory_store[session_id].append({"role": "user", "content": text})

    # Gọi AI Agent kèm hồ sơ khách cũ để cá nhân hóa ngữ điệu
    ai_response = await process_chat(memory_store[session_id], customer_profile=cust_profile)
    reply = ai_response.reply_message
    memory_store[session_id].append({"role": "assistant", "content": reply})
    log_message(user_id, "Telegram", "Bot", reply, customer_id=cust_id)
    
    target_msg: Any = update.message or update.business_message or (update.callback_query.message if update.callback_query else None)
    conn_id = update.business_message.business_connection_id if update.business_message else None
    
    if target_msg:
        if conn_id:
            await target_msg.reply_text(reply, business_connection_id=conn_id)  # type: ignore
        else:
            await target_msg.reply_text(reply)

        # Tự động gửi ảnh sơ đồ ghế nếu khách hỏi hoặc AI đề cập sơ đồ ghế
        seat_keywords = ["sơ đồ", "seat map", "seatmap", "схема", "chọn ghế", "xem ghế", "chỗ ngồi", "ghế trống"]
        if any(kw in text.lower() for kw in seat_keywords) or any(kw in reply.lower() for kw in ["sơ đồ", "seat map", "схема"]):
            try:
                target_chat_id = update.effective_chat.id if update.effective_chat else int(user_id)
                out_seat_img = f"seat_map_{user_id}.jpg"
                booked_seats = ["B1", "A3", "B5"]
                generate_seat_map(booked_seats, output_path=out_seat_img)
                if os.path.exists(out_seat_img):
                    with open(out_seat_img, "rb") as photo_file:
                        caption_map = "🚌 Sơ đồ ghế xe EasyTrip (Ghế có dấu X màu vàng là đã có khách đặt)"
                        if conn_id:
                            await context.bot.send_photo(chat_id=target_chat_id, photo=photo_file, caption=caption_map, business_connection_id=conn_id)  # type: ignore
                        else:
                            await context.bot.send_photo(chat_id=target_chat_id, photo=photo_file, caption=caption_map)
            except Exception as e_map:
                print(f"⚠️ Lỗi gửi ảnh sơ đồ ghế: {e_map}")

    data = ai_response.extracted_data
    memory_store[f"{session_id}_data"] = data

    # Tự động cập nhật hồ sơ khách hàng vào Database SQLite
    if cust_id:
        profile_updates = {}
        if getattr(data, "ho_ten", None): profile_updates["full_name"] = data.ho_ten
        if getattr(data, "quoc_tich", None): profile_updates["nationality"] = data.quoc_tich
        if getattr(data, "so_dien_thoai", None):
            profile_updates["phone_number"] = str(data.so_dien_thoai)
            customer_memory.link_platform_by_phone(str(data.so_dien_thoai), "telegram", str(user_id))
        if getattr(data, "ghe_chon", None): profile_updates["preferred_seat"] = data.ghe_chon
        if getattr(data, "diem_don", None): profile_updates["preferred_pickup"] = data.diem_don
        if getattr(data, "ngay_het_han_visa", None): profile_updates["visa_expiry_date"] = data.ngay_het_han_visa
        if profile_updates:
            customer_memory.update_customer_profile(cust_id, **profile_updates)

    # Tự động báo Admin Group khi khách nói đã chuyển tiền / thanh toán
    text_lower = text.lower()
    payment_keywords = ["paid", "thanh toan", "chuyen tien", "chuyển tiền", "đã ck", "da ck", "sent money", "оплатил", "оплата", "перевел", "bill", "chuyển khoản", "chuyen khoan"]
    if any(kw in text_lower for kw in payment_keywords):
        admin_pay_msg = (
            f"💰 **KHÁCH BÁO ĐÃ CHUYỂN TIỀN**\n"
            f"👤 Tên: {getattr(data, 'ho_ten', 'Khách hàng')} ({getattr(data, 'quoc_tich', '')})\n"
            f"📞 SĐT: {getattr(data, 'so_dien_thoai', '')}\n"
            f"💬 Tin nhắn: \"{text}\"\n"
            f"👉 [Admin vui lòng đối soát tài khoản!](https://t.me/easytripvisa_co_ltd)"
        )
        await send_to_admin_group(context, admin_pay_msg)

    # Xác định ngày đi và loại dịch vụ của khách
    history_text = " ".join([m["content"] for m in memory_store[session_id]])
    service_type = get_customer_service_type(data, history_text)
    
    dest = "cambodia" if service_type == "Cambodia" else "laos"
    ngay_di = validate_and_adjust_departure(data.ngay_khoi_hanh or "", data.ngay_het_han_visa or "", data.loai_visa or "", dest)
    if ngay_di:
        data.ngay_khoi_hanh = ngay_di

    # --- 2. GỬI SCHEME KHI KHÁCH ĐÃ ĐẾN PHASE SEAT_SELECTION ---
    if ai_response.current_phase == "SEAT_SELECTION" and ngay_di:
        now = time.time()
        if (now - scheme_history.get(ngay_di, 0)) > 900:
            scheme_cmd = get_scheme_command(ngay_di, data.loai_visa or "", history_text)
            if scheme_cmd:
                await send_to_bus_group(context, scheme_cmd, date=ngay_di, service=service_type)
                scheme_history[ngay_di] = now
                print(f"🚀 Scheme sent: {scheme_cmd} (phase=SEAT_SELECTION, service={service_type})")

    # --- 5. GỬI SƠ ĐỒ GHẾ ĐA NGÔN NGỮ ---
    if ngay_di:
        should_send_map = False
        if ai_response.current_phase == "SEAT_SELECTION" and not getattr(data, "ghe_chon", None):
            should_send_map = True
        
        user_text_lower = text.lower()
        reply_lower = reply.lower()
        map_keywords = [
            "sơ đồ", "seat map", "chờ", "ghế trống", "vị trí", "chỗ", "sơ đồ ghế", "chọn ghế",
            "map", "seat selection", "select seat", "available seats",
            "карта мест", "выбор места", "схема мест", "свободные места", "карта",
            "좌석", "좌석 배치도", "배치도"
        ]
        if any(kw in user_text_lower or kw in reply_lower for kw in map_keywords):
            should_send_map = True

        if should_send_map:
            map_data = await get_or_create_seat_map(ngay_di, service_type)
            if map_data:
                lang = get_lang_code(getattr(data, "quoc_tich", "")) if data else "en"
                caption = get_msg("seat_map_caption", lang, date=ngay_di)
                
                if map_data.get("file_id") and target_msg:
                    if conn_id:
                        await target_msg.reply_photo(photo=map_data["file_id"], caption=caption, business_connection_id=conn_id)  # type: ignore
                    else:
                        await target_msg.reply_photo(photo=map_data["file_id"], caption=caption)
                elif os.path.exists(map_data["url"].lstrip("/")) and target_msg:
                    with open(map_data["url"].lstrip("/"), "rb") as f:
                        if conn_id:
                            msg = await target_msg.reply_photo(photo=f, caption=caption, business_connection_id=conn_id)  # type: ignore
                        else:
                            msg = await target_msg.reply_photo(photo=f, caption=caption)
                        if msg and msg.photo:
                            map_data["file_id"] = msg.photo[-1].file_id
                            latest_seat_maps[f"{ngay_di}_{service_type}"] = map_data

    # --- 8. GỬI LỆNH ĐẶT GHẾ VÀO TOPIC ĐỐI TÁC KHI KHÁCH VỪA CHỌN GHẾ ---
    curr_seat = getattr(data, "ghe_chon", None)
    if curr_seat and curr_seat != prev_seat:
        notif_key = f"{session_id}_bus_notified_{curr_seat}"
        if not memory_store.get(notif_key):
            lang = get_lang_code(getattr(data, "quoc_tich", "")) if data else "en"
            if not getattr(data, "diem_don", None):
                data.diem_don = "Oceanus"
            
            if os.path.exists("qr_code.jpg") and target_msg:
                with open("qr_code.jpg", "rb") as qr_f:
                    if conn_id:
                        await target_msg.reply_photo(photo=qr_f, caption=get_msg("please_pay", lang), business_connection_id=conn_id)  # type: ignore
                    else:
                        await target_msg.reply_photo(photo=qr_f, caption=get_msg("please_pay", lang))
            
            bus_msg = (
                f"🚌 **ĐẶT CHỖ MỚI**\n"
                f"👤 Khách hàng: {data.ho_ten or 'Khách'} / {data.nam_sinh or ''}\n"
                f"🌏 Quốc tịch: {data.quoc_tich or ''}\n"
                f"📞 SĐT: {data.so_dien_thoai or ''}\n"
                f"💺 Ghế chọn: {curr_seat}\n"
                f"📍 Điểm đón: {data.diem_don}\n"
                f"⚠️ *Vui lòng đối tác đặt chỗ trên hệ thống của mình!*"
            )
            await send_to_bus_group(context, bus_msg, date=ngay_di, service=service_type)
            memory_store[notif_key] = True
            print(f"📢 Đã gửi tin nhắn đặt chỗ {curr_seat} vào topic đối tác!")

    if (ai_response.is_complete or ai_response.current_phase == "COMPLETED") and not memory_store.get(f"{session_id}_completed"):
        order_res = await create_order(data, channel="Telegram")
        record_id = order_res.get("record_id")
        memory_store[f"{session_id}_record_id"] = record_id
        
        # Lưu chuyến đi vào SQLite trip_history
        if cust_id:
            try:
                customer_memory.record_completed_trip(
                    customer_id=cust_id,
                    departure_date=ngay_di or data.ngay_khoi_hanh or datetime.now().strftime("%d/%m"),
                    route=service_type,
                    visa_type=data.loai_visa,
                    seat_number=data.ghe_chon,
                    pickup_location=data.diem_don,
                    price_paid=4000000 if service_type == "Cambodia" else 2000000,
                    order_id=record_id
                )
            except Exception as e_trip:
                print(f"⚠️ Lỗi lưu trip_history vào SQLite: {e_trip}")

        await send_to_admin_group(context, f"Có khách mới đã hoàn thành thông tin: {data.ho_ten}")
        memory_store[f"{session_id}_completed"] = True

# ============================================================
# HANDLER: XỬ LÝ TIN NHẮN VĂN BẢN (CHÍNH THỨC)
# ============================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    message: Any = update.message or update.business_message or (update.edited_business_message if update.edited_business_message else None)
    if not message:
        return
    text = message.text or ""

    session_id = f"telegram_{chat_id}"
    if update.business_message:
        memory_store[f"{session_id}_business_connection_id"] = update.business_message.business_connection_id
    elif getattr(update, "edited_business_message", None):
        memory_store[f"{session_id}_business_connection_id"] = getattr(update.edited_business_message, "business_connection_id", None)

    try:
        # ----- ADMIN COMMANDS (Reply to message) -----
        if (chat_id == ADMIN_TELEGRAM_ID or update.effective_chat.type in ["group", "supergroup"]) and message.reply_to_message:
            cmd_text = text.lower().strip()
            reply_text = message.reply_to_message.text or ""
            
            if "full" in cmd_text or "hết chỗ" in cmd_text:
                target_session_id = None
                sid_match = re.search(r"#sid:([\w\d_]+)", reply_text)
                if sid_match: target_session_id = sid_match.group(1)
                
                if not target_session_id:
                    date_match = re.search(r"(\d{1,2}/\d{1,2})", reply_text)
                    target_date = date_match.group(1) if date_match else None
                    for key, val in memory_store.items():
                        if key.endswith("_data") and hasattr(val, "ngay_khoi_hanh"):
                            if target_date and normalize_date(val.ngay_khoi_hanh) == normalize_date(target_date):
                                target_session_id = key.replace("_data", "")
                                break
                
                if target_session_id:
                    data = memory_store.get(f"{target_session_id}_data")
                    visa_expiry = getattr(data, "ngay_het_han_visa", None) if data else None
                    suggested_dates_str = "the next few days"
                    date_match_rep = re.search(r"(\d{1,2}/\d{1,2})", reply_text)
                    t_date = date_match_rep.group(1) if date_match_rep else ""
                    
                    if visa_expiry:
                        try:
                            from datetime import datetime, timedelta
                            exp_dt = None
                            for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]:
                                try:
                                    exp_dt = datetime.strptime(visa_expiry, fmt)
                                    if "%Y" not in fmt and "%y" not in fmt: exp_dt = exp_dt.replace(year=datetime.now().year)
                                    break
                                except: continue
                            if exp_dt:
                                start_dt = datetime.now() + timedelta(days=1)
                                end_dt = exp_dt - timedelta(days=1)
                                dates = []
                                curr = start_dt
                                while curr <= end_dt and len(dates) < 3:
                                    if curr.strftime("%d/%m") != normalize_date(t_date): dates.append(curr.strftime("%d/%m"))
                                    curr += timedelta(days=1)
                                if dates: suggested_dates_str = ", ".join(dates)
                        except: pass

                    nationality = getattr(data, 'quoc_tich', 'Unknown')
                    ai_prompt = (
                        f"CONTEXT: The bus trip on {t_date} is FULL. Notify the customer.\n"
                        f"CUSTOMER: {nationality}, Name: {getattr(data, 'ho_ten', 'Customer')}.\n"
                        f"INSTRUCTION: Write a polite notification in the customer's NATIVE LANGUAGE.\n"
                        f"CONTENT: Apologize that {t_date} is full. Suggest: {suggested_dates_str}.\n"
                        f"Mention ONLY pickup at Oceanus (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8)."
                    )
                    ai_res = await process_chat([{"role": "system", "content": ai_prompt}])
                    msg = ai_res.reply_message
                    platform = "Telegram" if "telegram_" in target_session_id else "Zalo" if "zalo_" in target_session_id else "Website"
                    uid = target_session_id.split("_")[1]
                    if platform == "Telegram":
                        conn_id = memory_store.get(f"{target_session_id}_business_connection_id")
                        await context.bot.send_message(chat_id=uid, text=msg, business_connection_id=conn_id)
                    elif platform == "Zalo": 
                        from main import send_zalo_message
                        await send_zalo_message(uid, msg)
                    
                    name = getattr(data, "ho_ten", "khách") if data else "khách"
                    await message.reply_text(f"✅ Đã báo {name} ({nationality}) bằng tiếng bản địa.\nGợi ý: {suggested_dates_str}")
                else: await message.reply_text("⚠️ Không tìm thấy khách.")
                return

        # ----- ADMIN DIRECT COMMANDS -----
        if chat_id == ADMIN_TELEGRAM_ID and text.lower().startswith("xác nhận thanh toán"):
            parts = text.split(" ", 2)
            customer_name = parts[2].strip() if len(parts) > 2 else ""
            client_session_key = None
            for key, val in memory_store.items():
                if key.endswith("_data") and hasattr(val, "ho_ten") and val.ho_ten and customer_name.lower() in val.ho_ten.lower():
                    client_session_key = key.replace("_data", "")
                    break
            if client_session_key:
                session_data = memory_store.get(f"{client_session_key}_data")
                uid = client_session_key.replace("telegram_", "")
                if session_data:
                    ho_ten = getattr(session_data, "ho_ten", "")
                    ghe_chon = getattr(session_data, "ghe_chon", "")
                    ngay_kh = getattr(session_data, "ngay_khoi_hanh", "")
                    reg_cmd = f"✅ ĐÃ THANH TOÁN\n{ho_ten} - {ghe_chon}"
                    await send_to_bus_group(context, reg_cmd, date=ngay_kh)
                if "telegram_" in client_session_key: 
                    data = memory_store.get(f"{client_session_key}_data")
                    lang = get_lang_code(getattr(data, "quoc_tich", "")) if data else "en"
                    conn_id = memory_store.get(f"{client_session_key}_business_connection_id")
                    await context.bot.send_message(chat_id=uid, text=get_msg("payment_confirmed", lang), business_connection_id=conn_id)  # type: ignore
                await message.reply_text(f"Đã xử lý thanh toán cho {customer_name}")
            return

        # ----- BUS GROUP HANDLER -----
        if update.effective_chat.type in ["group", "supergroup"] and chat_id == BUS_GROUP_CHAT_ID:
            eff_msg = update.effective_message
            thread_id = eff_msg.message_thread_id if eff_msg else None
            
            # 1. HỖ TRỢ LỆNH /link <ngày> <loại hình>
            if text.startswith("/link"):
                parts = text.split()
                if len(parts) >= 3:
                    target_date = normalize_date(parts[1])
                    target_service = parts[2].upper()
                    # Chuẩn hóa loại hình
                    if "90" in target_service: target_service = "90D"
                    elif "CAMBODIA" in target_service or "CAMP" in target_service: target_service = "Cambodia"
                    else: target_service = "45D"
                    
                    key = f"{target_date}_{target_service}"
                    date_to_topic_id_map[key] = thread_id
                    
                    # Save to file
                    try:
                        with open(TOPIC_MAP_FILE, "w") as f:
                            json.dump(date_to_topic_id_map, f)
                    except Exception as e:
                        print("Lỗi save topic_map.json:", e)
                        
                    await message.reply_text(f"✅ Đã liên kết topic này với khóa: `{key}`!", parse_mode="Markdown")
                else:
                    await message.reply_text("⚠️ Hướng dẫn sử dụng: `/link <ngày> <dịch vụ>`\nVí dụ: `/link 20/05 Cambodia` hoặc `/link 20/05 45D`")
                return

            # Tự động parse ngày + dịch vụ khi admin tạo topic mới
            if eff_msg and getattr(eff_msg, "forum_topic_created", None):
                topic_name = getattr(eff_msg.forum_topic_created, "name", "")
                t_date, t_service = parse_topic_name(topic_name)
                if t_date and t_service:
                    key = f"{t_date}_{t_service}"
                    date_to_topic_id_map[key] = thread_id
                    try:
                        with open(TOPIC_MAP_FILE, "w") as f:
                            json.dump(date_to_topic_id_map, f)
                    except Exception as e:
                        print("Lỗi save topic_map.json:", e)
                    print(f"📌 Tự động liên kết Topic: {topic_name} -> {key}")

            # Tìm xem topic này thuộc về Ngày + Dịch vụ nào (tự động đăng ký động nếu thiếu)
            bot_instance = context.bot if context else tg_app.bot
            key = await get_or_register_topic_key(bot_instance, thread_id) if thread_id is not None else None
            
            # Tách ghế (e.g. A1, B2)
            seat_pattern = r"\b[AB]\d{1,2}\b"
            seats_found = re.findall(seat_pattern, text.upper())
            
            if seats_found and key:
                parts_key = key.split("_")
                ngay = parts_key[0]
                service = parts_key[1] if len(parts_key) > 1 else "45D"
                
                text_lower = text.lower()
                is_empty_list = True # Mặc định là ghế trống
                if "hết" in text_lower or "đặt" in text_lower or "đã bán" in text_lower:
                    is_empty_list = False
                
                valid_seats = set(RELATIVE_COORDINATES.keys())
                found_set = set(seats_found) & valid_seats
                
                if found_set:
                    if is_empty_list:
                        booked_seats = valid_seats - found_set
                    else:
                        booked_seats = found_set
                        
                    output_file = f"static/map_{ngay.replace('/', '_')}_{service}.jpg"
                    generate_seat_map(list(booked_seats), output_path=output_file)
                    
                    with open(output_file, "rb") as f:
                        msg = await context.bot.send_photo(
                            chat_id=BUS_GROUP_CHAT_ID,
                            photo=f,
                            caption=f"✅ Đã cập nhật sơ đồ ngày {ngay} - {service}!",
                            message_thread_id=thread_id
                        )
                    
                    latest_seat_maps[key] = {
                        "file_id": msg.photo[-1].file_id,
                        "url": f"/static/map_{ngay.replace('/', '_')}_{service}.jpg"
                    }
                    print(f"Sơ đồ {key} đã được cập nhật thành công!")
            return

        # ----- CUSTOMER FLOW -----
        if not update.effective_chat or update.effective_chat.type != "private" or not update.effective_user:
            return
        user_id = str(update.effective_user.id)
        await process_customer_text_message(update, context, user_id, text)

    except Exception as e:
        import traceback
        error_msg = f"❌ ERROR IN HANDLE_TEXT: {e}"
        print(error_msg)
        traceback.print_exc()
        # Notify Admin about the error
        await send_to_admin_group(context, f"🔴 SYSTEM ERROR: {error_msg}")
        
        # Professional fallback for user
        chat_id_val = update.effective_chat.id if update.effective_chat else "unknown"
        session_id = f"telegram_{chat_id_val}"
        data = memory_store.get(f"{session_id}_data")
        lang = get_lang_code(getattr(data, "quoc_tich", "")) if data else "en"
        conn_id = memory_store.get(f"{session_id}_business_connection_id")
        if conn_id:
            await message.reply_text(get_msg("system_busy", lang), business_connection_id=conn_id)  # type: ignore
        else:
            await message.reply_text(get_msg("system_busy", lang))


_easyocr_reader = None

def get_ocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            _easyocr_reader = easyocr.Reader(['en', 'ru'], gpu=False, verbose=False)
        except Exception as e:
            _easyocr_reader = False
    return _easyocr_reader if _easyocr_reader is not False else None

def extract_text_from_image(image_path: str) -> str:
    """Trích xuất văn bản từ hình ảnh vé/tin nhắn bằng Cloud OCR và EasyOCR (hỗ trợ Tiếng Anh, Tiếng Nga, Hàn, Việt)"""
    # 1. Primary: Fast Cloud OCR (0 MB RAM, không tốn RAM máy chủ, độ chính xác cao)
    try:
        with open(image_path, 'rb') as f:
            files = {'file': f}
            data = {
                'apikey': 'K88574768888957',
                'language': 'eng',
                'isOverlayRequired': False,
                'OCREngine': '2'
            }
            r = httpx.post('https://api.ocr.space/parse/image', files=files, data=data, timeout=12)
            if r.status_code == 200:
                res = r.json()
                parsed = res.get('ParsedResults', [])
                if parsed:
                    text = parsed[0].get('ParsedText', '')
                    if text and len(text.strip()) > 3:
                        return text
    except Exception as e:
        print(f"⚠️ Cloud OCR fallback notice: {e}")
        
    # 2. Secondary fallback: Local EasyOCR if available
    try:
        reader = get_ocr_reader()
        if reader:
            results = reader.readtext(image_path, detail=0)
            return " \n".join(results)
    except Exception as e:
        print(f"⚠️ Local OCR Error: {e}")
        
    return ""


# ============================================================
# HANDLER: XỬ LÝ ẢNH
# ============================================================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    message: Any = update.message or update.business_message
    if not message:
        return
        
    session_id = f"telegram_{chat_id}"
    if update.business_message:
        memory_store[f"{session_id}_business_connection_id"] = update.business_message.business_connection_id

    try:
        # ----- LUỒNG ĐỐI TÁC XE BUÝT: GỬI SƠ ĐỒ GHẾ VÀO TOPIC ĐỐI TÁC -----
        if update.effective_chat.type in ["group", "supergroup"] and chat_id == BUS_GROUP_CHAT_ID:
            eff_msg = update.effective_message
            thread_id = eff_msg.message_thread_id if eff_msg else None
            
            # 1. Tìm key liên kết (e.g. "04/06_Cambodia" hoặc "04/06") từ topic id (tự động đăng ký động nếu thiếu)
            bot_instance = context.bot if context else tg_app.bot
            linked_key = await get_or_register_topic_key(bot_instance, thread_id) if thread_id is not None else None
            
            ngay = None
            service = "45D"  # Mặc định
            
            if linked_key:
                parts = linked_key.split("_")
                ngay = parts[0]
                if len(parts) > 1:
                    service = parts[1]
            
            # 2. Nếu không tìm thấy key liên kết, thử parse từ caption hoặc topic name
            caption = message.caption or ""
            date_match = re.search(r"(\d{1,2}/\d{1,2})", caption)
            if date_match:
                ngay = normalize_date(date_match.group(1))
                # Đoán loại hình từ caption
                if "cambodia" in caption.lower() or "camp" in caption.lower():
                    service = "Cambodia"
                elif "90" in caption.lower():
                    service = "90D"
            
            # 3. Nếu vẫn không có ngày, thử lấy từ forum_topic_created
            reply_msg = eff_msg.reply_to_message if eff_msg else None
            if not ngay and reply_msg and getattr(reply_msg, "forum_topic_created", None):
                topic_name = getattr(reply_msg.forum_topic_created, "name", "")
                parsed_date, parsed_service = parse_topic_name(topic_name)
                if parsed_date:
                    ngay = parsed_date
                    service = parsed_service
                    # Lưu liên kết để lần sau không cần parse lại
                    key = f"{ngay}_{service}"
                    date_to_topic_id_map[key] = thread_id
                    try:
                        with open(TOPIC_MAP_FILE, "w") as f:
                            json.dump(date_to_topic_id_map, f)
                    except:
                        pass

            if ngay:
                photo_file = await message.photo[-1].get_file()
                
                # Lưu dưới định dạng chuẩn có hậu tố _service (ví dụ: map_04_06_Cambodia.jpg)
                local_path = f"static/map_{ngay.replace('/', '_')}_{service}.jpg"
                await photo_file.download_to_drive(local_path)
                
                file_id = message.photo[-1].file_id
                # Lưu vào bộ nhớ đệm sơ đồ
                map_data = {
                    "file_id": file_id, 
                    "url": f"/static/map_{ngay.replace('/', '_')}_{service}.jpg"
                }
                latest_seat_maps[f"{ngay}_{service}"] = map_data
                latest_seat_maps[ngay] = map_data  # Fallback
                
                await message.reply_text(f"✅ Đã đồng bộ sơ đồ ngày {ngay} ({service})!")

                # --- TỰ ĐỘNG CHUYỂN TIẾP CHO KHÁCH HÀNG ĐANG ĐỢI ---
                # Quét memory_store để tìm các khách hàng đang ở phase SEAT_SELECTION,
                # chưa chọn ghế, và đi đúng ngày + dịch vụ này để chủ động gửi sơ đồ mới nhất!
                for key_session, messages_history in memory_store.items():
                    if key_session.endswith("_data"):
                        customer_data = messages_history
                        cust_ngay = normalize_date(getattr(customer_data, "ngay_khoi_hanh", ""))
                        if cust_ngay == ngay:
                            session_id = key_session.replace("_data", "")
                            cust_history = " ".join([m.get("content", "") for m in memory_store.get(session_id, []) if isinstance(m, dict)])
                            cust_service = get_customer_service_type(customer_data, cust_history)
                            
                            # Nếu khách trùng tuyến và chưa chọn ghế
                            if cust_service == service and not getattr(customer_data, "ghe_chon", None):
                                platform = "Telegram" if "telegram_" in session_id else "Zalo" if "zalo_" in session_id else "Website"
                                uid = session_id.split("_")[1]
                                
                                lang = get_lang_code(getattr(customer_data, "quoc_tich", ""))
                                caption = get_msg("seat_map_caption", lang, date=ngay)
                                
                                print(f"🚀 Tự động gửi sơ đồ chính thức mới cho khách {getattr(customer_data, 'ho_ten', 'Khách')} ({platform})")
                                
                                try:
                                    if platform == "Telegram":
                                        conn_id = memory_store.get(f"{session_id}_business_connection_id")
                                        await tg_app.bot.send_photo(chat_id=uid, photo=file_id, caption=caption, business_connection_id=conn_id)  # type: ignore
                                    elif platform == "Zalo":
                                        from main import send_zalo_image, send_zalo_message
                                        domain = os.getenv("RENDER_EXTERNAL_URL", "https://chatbot-easytrip.onrender.com").rstrip("/")
                                        image_url = f"{domain}/static/map_{ngay.replace('/', '_')}_{service}.jpg"
                                        await send_zalo_message(uid, caption)
                                        await send_zalo_image(uid, image_url)
                                except Exception as e_forward:
                                    print(f"Lỗi chuyển tiếp sơ đồ cho {uid}: {e_forward}")
            return

        # ----- LUỒNG KHÁCH HÀNG: GỬI ẢNH (HỘ CHIẾU/HOÁ ĐƠN THANH TOÁN) -----
        if not update.effective_chat or update.effective_chat.type != "private": return
        photo_file = await message.photo[-1].get_file()
        file_path = f"temp_{photo_file.file_id}.jpg"
        await photo_file.download_to_drive(file_path)
        img_type = await identify_image_type(file_path)
        
        record_id = memory_store.get(f"telegram_{chat_id}_record_id")
        if record_id:
            token = await upload_image_to_lark(file_path)
            if token: 
                await update_customer_image(record_id, img_type if img_type != "Exit Stamp" else "Exit stamp", token)
        
        conn_id = update.business_message.business_connection_id if update.business_message else memory_store.get(f"{session_id}_business_connection_id")
        data = memory_store.get(f"{session_id}_data")
        customer_name = getattr(data, "ho_ten", "Khách hàng") if data else "Khách hàng"
        nationality = getattr(data, "quoc_tich", "") if data else ""
        phone = getattr(data, "so_dien_thoai", "") if data else ""
        
        # Báo cáo lập tức cho Admin Group kèm link chat trực tiếp
        admin_notif_msg = (
            f"📸 **KHÁCH HÀNG GỬI ẢNH MỚI (HỘ CHIẾU/HOÁ ĐƠN/VÉ CŨ)**\n"
            f"👤 Tên: {customer_name} ({nationality})\n"
            f"📞 SĐT: {phone}\n"
            f"📂 Thể loại nhận diện: {img_type}\n"
            f"👉 [Admin vui lòng kiểm tra và xử lý giao dịch!](https://t.me/easytripvisa_co_ltd)"
        )
        await send_to_admin_group(context, admin_notif_msg)

        # 1. Trích xuất OCR từ ảnh để tự động kiểm tra vé cũ / thông tin booking
        ocr_text = extract_text_from_image(file_path)
        matched_cust = customer_memory.find_customer_by_booking_text(ocr_text) if ocr_text else None
        
        # Nhận diện nếu ảnh là vé / biên nhận / thông tin đặt xe cũ
        is_ticket_or_receipt = any(kw in ocr_text.upper() for kw in [
            "RECEIPT", "PAYMENT", "DATE OF", "SERVICE TYPES", "SEAT NUMBER", 
            "PICK UP", "DEPARTURE DATE", "E-VISA", "VISARUN", "VISA RUN", "HON CHONG", "40 HON CHONG"
        ]) if ocr_text else False

        # 1. Nếu tìm thấy khách cũ trên CRM (dù gửi lần đầu hay gửi lại)
        if matched_cust:
            memory_store.pop(f"{session_id}_awaiting_old_booking", None)
            user_id = str(update.effective_user.id) if update.effective_user else ""
            print(f"🎯 OCR đã nhận diện Khách Cũ từ ảnh vé: {matched_cust.get('full_name')}")
            if matched_cust.get("customer_id") and user_id:
                customer_memory.link_telegram_to_customer(matched_cust["customer_id"], user_id)
            # Cho AI phản hồi trực tiếp dựa trên nội dung ảnh đã đọc
            await process_customer_text_message(update, context, user_id, ocr_text)
            return

        # 2. Nếu khách đang trong luồng chọn Khách Cũ HOẶC gửi ảnh biên nhận/vé nhưng không tìm thấy trên CRM
        if is_awaiting_old or is_ticket_or_receipt:
            memory_store.pop(f"{session_id}_awaiting_old_booking", None)
            not_found_photo_msg = (
                "ℹ️ **We could not find your booking information in our database.**\n"
                "Therefore, our **standard website listed prices** will apply to your booking.\n\n"
                "👉 Please let us know your **intended departure date or preferred visa type** to proceed!\n\n"
                "────────────────────\n"
                "ℹ️ **Мы не нашли информацию о вашем бронировании в нашей базе данных.**\n"
                "Поэтому для вашей поездки будет действовать **стандартный тариф, указанный на нашем сайте**.\n\n"
                "👉 Пожалуйста, напишите **желаемую дату поездки или интересующий тип визы**!"
            )
            if conn_id:
                await message.reply_text(not_found_photo_msg, parse_mode="Markdown", business_connection_id=conn_id)  # type: ignore
            else:
                await message.reply_text(not_found_photo_msg, parse_mode="Markdown")
            return

        lang = get_lang_code(nationality) if data else "en"
        if conn_id:
            await message.reply_text(get_msg("image_received", lang, img_type=img_type), business_connection_id=conn_id)  # type: ignore
        else:
            await message.reply_text(get_msg("image_received", lang, img_type=img_type))
    except Exception as e:
        print(f"❌ PHOTO ERROR: {e}")

# ============================================================
# CALLBACK & WEBHOOK
# ============================================================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()
    try:
        parts = (query.data or "").split("|")
        if len(parts) < 2: return
        
        # 0. Xử lý lựa chọn Khách Cũ vs Khách Mới
        if parts[0] == "cust_type":
            cust_choice = parts[1]
            if not update.effective_user:
                return
            user_id = str(update.effective_user.id)
            session_id = f"telegram_{user_id}"
            conn_id = memory_store.get(f"{session_id}_business_connection_id")
            target_msg = query.message
            
            if cust_choice == "new":
                memory_store[f"{session_id}_customer_tier"] = "NEW"
                memory_store.pop(f"{session_id}_awaiting_old_booking", None)
                await send_new_customer_welcome_menu(user_id, target_msg, conn_id=conn_id)
            elif cust_choice == "returning":
                memory_store[f"{session_id}_awaiting_old_booking"] = True
                await send_returning_customer_request(user_id, target_msg, conn_id=conn_id)
            return

        # 1. Xử lý các nút bấm dịch vụ từ phía Khách Hàng
        if parts[0] == "service":
            service_key = parts[1]
            if not update.effective_user:
                return
            user_id = str(update.effective_user.id)
            session_id = f"telegram_{user_id}"
            
            service_texts = {
                "laos_45d": "I would like to book the Laos Visa Run 45 Days (Visa Free)",
                "laos_90d": "I would like to book the Laos Visa Run 90 Days (E-visa)",
                "cambodia_90d": "I would like to book the Cambodia Visa Run 90 Days",
                "evisa_urgent": "I would like to book the Urgent Vietnam E-visa Service",
                "fast_track": "I would like to inquire about Airport Fast Track & Motorbike Rental"
            }
            user_text = service_texts.get(service_key, "Service Inquiry")
            
            # Gửi tin nhắn xác nhận nút đã chọn
            if query.message:
                q_msg: Any = query.message
                await q_msg.reply_text(f"👉 You selected: **{user_text}**", parse_mode="Markdown")
            
            # Xử lý tin nhắn giả lập bằng AI Agent
            await process_customer_text_message(update, context, user_id, user_text)
            return

        if len(parts) < 3: return
        action, record_id, session_id = parts[0], parts[1], parts[2]
        order_meta = memory_store.get(f"{session_id}_order", {})
        order_data = order_meta.get("data")
        platform = order_meta.get("platform", "")
        uid = order_meta.get("user_id", "")
        lang = get_lang_code(getattr(order_data, "quoc_tich", "")) if order_data else "en"

        q_msg_text = getattr(query.message, "text", "") or ""
        if action == "paid":
            await update_order_status(record_id, "PAID")
            confirm_msg = get_msg("payment_confirmed", lang)
            try:
                if platform == "Telegram":
                    conn_id = memory_store.get(f"{session_id}_business_connection_id")
                    await context.bot.send_message(chat_id=uid, text=confirm_msg, business_connection_id=conn_id)  # type: ignore
                elif platform == "Zalo": 
                    from main import send_zalo_message
                    await send_zalo_message(uid, confirm_msg)
            except: pass
            
            try:
                from google_sheet_sync import sync_order_to_sheet
                await sync_order_to_sheet({"Order ID": order_meta.get("order_id", ""), "Status": "PAID", "Full Name": getattr(order_data, 'ho_ten', 'Customer'), "Agent": getattr(order_data, 'agent', 'Direct')})
            except: pass
            await query.edit_message_text(text=q_msg_text + "\n\n✅ Đã xác nhận PAID!")

        elif action == "cancel":
            await update_order_status(record_id, "CANCELLED")
            await query.edit_message_text(text=q_msg_text + "\n\n❌ Đã huỷ đơn.")
    except Exception as e:
        print(f"❌ CALLBACK ERROR: {e}")

async def check_visa_reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lệnh Admin: Quét và gửi nhắc nhở hết hạn visa thủ công ngay lập tức"""
    if not update.effective_message:
        return
    status_msg = await update.effective_message.reply_text("⏳ Đang quét cơ sở dữ liệu và gửi nhắc nhở hết hạn visa (trước 10 ngày)...")
    try:
        from visa_reminder import check_and_send_daily_reminders
        report = await check_and_send_daily_reminders(bot=context.bot)
        found = report.get("total_found", 0)
        sent = report.get("reminders_sent", 0)
        await status_msg.edit_text(
            f"✅ **HOÀN TẤT QUÉT NHẮC NHỞ VISA**\n\n"
            f"📊 Tìm thấy: {found} khách sắp hết hạn (trong 9-11 ngày tới)\n"
            f"📤 Đã gửi qua Telegram Bot: {sent}\n"
            f"🔔 Báo cáo chi tiết đã được gửi vào Admin Group!"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Lỗi khi quét nhắc nhở: {e}")

tg_app.add_handler(CommandHandler("start", start_command))
tg_app.add_handler(CommandHandler("getid", get_id_command))
tg_app.add_handler(CommandHandler("check_visa_reminders", check_visa_reminders_command))
tg_app.add_handler(CommandHandler("remind_visa", check_visa_reminders_command))
tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
tg_app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE & filters.TEXT, handle_text))
tg_app.add_handler(MessageHandler(filters.UpdateType.EDITED_BUSINESS_MESSAGE & filters.TEXT, handle_text))
tg_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
tg_app.add_handler(MessageHandler(filters.UpdateType.BUSINESS_MESSAGE & filters.PHOTO, handle_photo))
tg_app.add_handler(CallbackQueryHandler(handle_callback))

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        await tg_app.process_update(update)
    except Exception as e:
        import traceback
        print(f"❌ Error processing Telegram webhook update: {e}")
        traceback.print_exc()
    return Response(status_code=200)
