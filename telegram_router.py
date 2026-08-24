import os
import time
import re
import json
import traceback
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

from memory_store import memory_store
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
def log_message(user_id, platform, role, content):
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": str(user_id),
        "platform": platform,
        "role": role,
        "content": content,
    }
    try:
        with open("chat_history.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
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



async def send_to_bus_group(context, message: str, date: str = None, service: str = None):
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


async def get_or_create_seat_map(ngay: str, service: str) -> dict:
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
tg_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode="Markdown")

async def get_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📍 Chat ID: `{update.effective_chat.id}`\nType: {update.effective_chat.type}", parse_mode='Markdown')


# ============================================================
# LOGIC XỬ LÝ TIN NHẮN TỪ KHÁCH HÀNG (TEXT & NÚT BẤM)
# ============================================================
async def process_customer_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str):
    session_id = f"telegram_{user_id}"
    log_message(user_id, "Telegram", "User", text)
    if session_id not in memory_store: memory_store[session_id] = []
    
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
            ai_response = await process_chat(memory_store[session_id])
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

    ai_response = await process_chat(memory_store[session_id])
    reply = ai_response.reply_message
    memory_store[session_id].append({"role": "assistant", "content": reply})
    log_message(user_id, "Telegram", "Bot", reply)
    
    target_msg = update.message or update.business_message or (update.callback_query.message if update.callback_query else None)
    conn_id = update.business_message.business_connection_id if update.business_message else None
    
    if conn_id:
        await target_msg.reply_text(reply, business_connection_id=conn_id)
    else:
        await target_msg.reply_text(reply)

    data = ai_response.extracted_data
    memory_store[f"{session_id}_data"] = data

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
    ngay_di = validate_and_adjust_departure(data.ngay_khoi_hanh, data.ngay_het_han_visa or "", data.loai_visa or "", dest)
    if ngay_di:
        data.ngay_khoi_hanh = ngay_di

    # --- 2. GỬI SCHEME KHI KHÁCH ĐÃ ĐẾN PHASE SEAT_SELECTION ---
    if ai_response.current_phase == "SEAT_SELECTION" and ngay_di:
        now = time.time()
        if (now - scheme_history.get(ngay_di, 0)) > 900:
            scheme_cmd = get_scheme_command(ngay_di, data.loai_visa, history_text)
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
                
                if map_data.get("file_id"):
                     if conn_id:
                         await target_msg.reply_photo(photo=map_data["file_id"], caption=caption, business_connection_id=conn_id)
                     else:
                         await target_msg.reply_photo(photo=map_data["file_id"], caption=caption)
                elif os.path.exists(map_data["url"].lstrip("/")):
                    with open(map_data["url"].lstrip("/"), "rb") as f:
                        if conn_id:
                            msg = await target_msg.reply_photo(photo=f, caption=caption, business_connection_id=conn_id)
                        else:
                            msg = await target_msg.reply_photo(photo=f, caption=caption)
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
            
            if os.path.exists("qr_code.jpg"):
                if conn_id:
                    await target_msg.reply_photo(photo=open("qr_code.jpg", "rb"), caption=get_msg("please_pay", lang), business_connection_id=conn_id)
                else:
                    await target_msg.reply_photo(photo=open("qr_code.jpg", "rb"), caption=get_msg("please_pay", lang))
            
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
        await send_to_admin_group(context, f"Có khách mới đã hoàn thành thông tin: {data.ho_ten}")
        memory_store[f"{session_id}_completed"] = True

# ============================================================
# HANDLER: XỬ LÝ TIN NHẮN VĂN BẢN (CHÍNH THỨC)
# ============================================================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    message = update.message or update.business_message or (update.edited_business_message if update.edited_business_message else None)
    if not message:
        return
    text = message.text or ""

    session_id = f"telegram_{chat_id}"
    if update.business_message:
        memory_store[f"{session_id}_business_connection_id"] = update.business_message.business_connection_id
    elif getattr(update, "edited_business_message", None):
        memory_store[f"{session_id}_business_connection_id"] = update.edited_business_message.business_connection_id

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
                reg_cmd = f"✅ ĐÃ THANH TOÁN\n{session_data.ho_ten} - {session_data.ghe_chon}"
                await send_to_bus_group(context, reg_cmd, date=session_data.ngay_khoi_hanh)
                if "telegram_" in client_session_key: 
                    data = memory_store.get(f"{client_session_key}_data")
                    lang = get_lang_code(getattr(data, "quoc_tich", "")) if data else "en"
                    conn_id = memory_store.get(f"{client_session_key}_business_connection_id")
                    await context.bot.send_message(chat_id=uid, text=get_msg("payment_confirmed", lang), business_connection_id=conn_id)
                await message.reply_text(f"Đã xử lý thanh toán cho {customer_name}")
            return

        # ----- BUS GROUP HANDLER -----
        if update.effective_chat.type in ["group", "supergroup"] and chat_id == BUS_GROUP_CHAT_ID:
            thread_id = update.effective_message.message_thread_id
            
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
            if update.effective_message.forum_topic_created:
                topic_name = update.effective_message.forum_topic_created.name
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
            key = await get_or_register_topic_key(bot_instance, thread_id)
            
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
        if update.effective_chat.type != "private": return
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
        session_id = f"telegram_{update.effective_chat.id}"
        data = memory_store.get(f"{session_id}_data")
        lang = get_lang_code(getattr(data, "quoc_tich", "")) if data else "en"
        conn_id = memory_store.get(f"{session_id}_business_connection_id")
        if conn_id:
            await message.reply_text(get_msg("system_busy", lang), business_connection_id=conn_id)
        else:
            await message.reply_text(get_msg("system_busy", lang))


# ============================================================
# HANDLER: XỬ LÝ ẢNH
# ============================================================
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    message = update.message or update.business_message
    if not message:
        return
        
    session_id = f"telegram_{chat_id}"
    if update.business_message:
        memory_store[f"{session_id}_business_connection_id"] = update.business_message.business_connection_id

    try:
        # ----- LUỒNG ĐỐI TÁC XE BUÝT: GỬI SƠ ĐỒ GHẾ VÀO TOPIC ĐỐI TÁC -----
        if update.effective_chat.type in ["group", "supergroup"] and chat_id == BUS_GROUP_CHAT_ID:
            thread_id = update.effective_message.message_thread_id
            
            # 1. Tìm key liên kết (e.g. "04/06_Cambodia" hoặc "04/06") từ topic id (tự động đăng ký động nếu thiếu)
            bot_instance = context.bot if context else tg_app.bot
            linked_key = await get_or_register_topic_key(bot_instance, thread_id)
            
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
            if not ngay and update.effective_message.reply_to_message and update.effective_message.reply_to_message.forum_topic_created:
                topic_name = update.effective_message.reply_to_message.forum_topic_created.name
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
                                        await tg_app.bot.send_photo(chat_id=uid, photo=file_id, caption=caption, business_connection_id=conn_id)
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
        if update.effective_chat.type != "private": return
        photo_file = await message.photo[-1].get_file()
        file_path = f"temp_{photo_file.file_id}.jpg"
        await photo_file.download_to_drive(file_path)
        img_type = await identify_image_type(file_path)
        
        record_id = memory_store.get(f"telegram_{chat_id}_record_id")
        if record_id:
            token = await upload_image_to_lark(file_path)
            if token: 
                await update_customer_image(record_id, img_type if img_type != "Exit Stamp" else "Exit stamp", token)
        
        data = memory_store.get(f"{session_id}_data")
        customer_name = getattr(data, "ho_ten", "Khách hàng") if data else "Khách hàng"
        nationality = getattr(data, "quoc_tich", "") if data else ""
        phone = getattr(data, "so_dien_thoai", "") if data else ""
        
        # Báo cáo lập tức cho Admin Group kèm link chat trực tiếp
        admin_notif_msg = (
            f"📸 **KHÁCH HÀNG GỬI ẢNH MỚI (HỘ CHIẾU/HOÁ ĐƠN)**\n"
            f"👤 Tên: {customer_name} ({nationality})\n"
            f"📞 SĐT: {phone}\n"
            f"📂 Thể loại nhận diện: {img_type}\n"
            f"👉 [Admin vui lòng kiểm tra và xử lý giao dịch!](https://t.me/easytripvisa_co_ltd)"
        )
        await send_to_admin_group(context, admin_notif_msg)
        
        lang = get_lang_code(nationality) if data else "en"
        conn_id = update.business_message.business_connection_id if update.business_message else None
        if conn_id:
            await message.reply_text(get_msg("image_received", lang, img_type=img_type), business_connection_id=conn_id)
        else:
            await message.reply_text(get_msg("image_received", lang, img_type=img_type))
    except Exception as e:
        print(f"❌ PHOTO ERROR: {e}")

# ============================================================
# CALLBACK & WEBHOOK
# ============================================================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        parts = (query.data or "").split("|")
        if len(parts) < 2: return
        
        # 1. Xử lý các nút bấm dịch vụ từ phía Khách Hàng
        if parts[0] == "service":
            service_key = parts[1]
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
            await query.message.reply_text(f"👉 You selected: **{user_text}**", parse_mode="Markdown")
            
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

        if action == "paid":
            await update_order_status(record_id, "PAID")
            confirm_msg = get_msg("payment_confirmed", lang)
            try:
                if platform == "Telegram":
                    conn_id = memory_store.get(f"{session_id}_business_connection_id")
                    await context.bot.send_message(chat_id=uid, text=confirm_msg, business_connection_id=conn_id)
                elif platform == "Zalo": 
                    from main import send_zalo_message
                    await send_zalo_message(uid, confirm_msg)
            except: pass
            
            try:
                from google_sheet_sync import sync_order_to_sheet
                await sync_order_to_sheet({"Order ID": order_meta.get("order_id", ""), "Status": "PAID", "Full Name": getattr(order_data, 'ho_ten', 'Customer'), "Agent": getattr(order_data, 'agent', 'Direct')})
            except: pass
            await query.edit_message_text(text=query.message.text + "\n\n✅ Đã xác nhận PAID!")

        elif action == "cancel":
            await update_order_status(record_id, "CANCELLED")
            await query.edit_message_text(text=query.message.text + "\n\n❌ Đã huỷ đơn.")
    except Exception as e:
        print(f"❌ CALLBACK ERROR: {e}")

tg_app.add_handler(CommandHandler("start", start_command))
tg_app.add_handler(CommandHandler("getid", get_id_command))
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
