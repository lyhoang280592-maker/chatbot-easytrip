"""
wizard_flows.py - Đồng bộ toàn bộ dữ liệu Website EasyTripVisa sang Telegram Bot
Cung cấp luồng Tư Vấn Thông Minh (Intelligent Consultation Engine):
1. Quốc gia (Country Names) + Nhận diện khi khách gõ tên nước
2. Vị trí/Thành phố (Abroad, Nha Trang, Mũi Né, Đà Nẵng, TP.HCM, Hà Nội, Khác)
3. Lịch tháng tương tác chuẩn quốc tế (Calendar Picker)
4. BƯỚC TƯ VẤN THÔNG TIN & ĐỀ XUẤT NÚT BẤM PHÙ HỢP (Khớp Quốc tịch + Hạn visa + Lịch xe + Dịch vụ visa)
5. Chi tiết Lịch trình chuẩn xác (Lào Bờ Y 07:00 & 09:30, Hà Nội Hữu Nghị 09:00 - 19:00, Campuchia Mũi Né/Nha Trang)
"""

import calendar
import re
from datetime import datetime, timedelta
from typing import Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from memory_store import memory_store
from ai_agent import CustomerData

# ============================================================
# CẤU HÌNH DỮ LIỆU ĐỒNG BỘ VỚI WEBSITE (EASYTRIPVISA.COM) & THỰC TẾ
# ============================================================
CITY_OPTIONS = {
    "abroad": {
        "name_vi": "Đang ở nước ngoài (Nhập cảnh vào VN)",
        "name_en": "Currently Abroad (Entering Vietnam)",
        "name_ru": "За рубежом (Въезд во Вьетнам)",
        "name_ko": "해외 체류 중 (베트남 입국 예정)",
        "icon": "✈️",
        "pickup_default": "Sân bay Quốc tế Việt Nam (SGN, HAN, CXR, DAD)",
        "pickup_map": ""
    },
    "nhatrang": {
        "name_vi": "Nha Trang",
        "name_en": "Nha Trang",
        "name_ru": "Нячанг",
        "name_ko": "나트랑",
        "icon": "🏖️",
        "pickup_default": "40 Hòn Chồng = Oceanus Nha Trang (Mường Thanh Viễn Triều)",
        "pickup_map": "https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8",
        "note_cambodia": "Xe đi Cambodia chỉ đón ở 1 điểm duy nhất là 40 Hòn Chồng = Oceanus."
    },
    "muine": {
        "name_vi": "Mũi Né (Phan Thiết)",
        "name_en": "Mui Ne (Phan Thiet)",
        "name_ru": "Муйне (Фантхьет)",
        "name_ko": "무이네 (판티엣)",
        "icon": "🏖️",
        "pickup_default": "04 Trần Phú, Mũi Né hoặc dọc trục Nguyễn Đình Chiểu / Huỳnh Thúc Kháng",
        "pickup_map": "https://maps.app.goo.gl/vysXaB9b4BeauGgV9",
        "schedule": "Khởi hành 01:00 – 02:00 Sáng Thứ 3, Thứ 5, Chủ Nhật (Tuyến đi Campuchia)"
    },
    "danang": {
        "name_vi": "Đà Nẵng / Hội An",
        "name_en": "Da Nang / Hoi An",
        "name_ru": "Дананг / Хойан",
        "name_ko": "다낭 / 호이안",
        "icon": "🌊",
        "pickup_default": "Văn phòng Đà Nẵng / Đón tận cửa khách sạn/villa",
        "pickup_map": ""
    },
    "hcm": {
        "name_vi": "TP. Hồ Chí Minh (Sài Gòn)",
        "name_en": "Ho Chi Minh City",
        "name_ru": "Хошимин (Сайгон)",
        "name_ko": "호치민",
        "icon": "🏙️",
        "pickup_default": "Khu vực trung tâm TP.HCM và hướng gần về phía cửa khẩu Mộc Bài",
        "pickup_map": ""
    },
    "hanoi": {
        "name_vi": "Hà Nội",
        "name_en": "Hanoi",
        "name_ru": "Ханой",
        "name_ko": "하노이",
        "icon": "🏛️",
        "pickup_default": "Văn phòng VIP Limousine Hà Nội / Sân bay Nội Bài",
        "pickup_map": ""
    },
    "other": {
        "name_vi": "Thành phố khác",
        "name_en": "Other City",
        "name_ru": "Другой город",
        "name_ko": "기타 도시",
        "icon": "📍",
        "pickup_default": "Tư vấn điểm đón trung chuyển gần nhất",
        "pickup_map": ""
    }
}

# Danh sách quốc gia được miễn thị thực Việt Nam 45 ngày
VISA_EXEMPT_COUNTRIES = {
    "russia", "belarus", "south korea", "korea", "japan",
    "germany", "france", "italy", "spain", "united kingdom", "uk",
    "denmark", "sweden", "norway", "finland", "poland",
    "singapore", "malaysia", "thailand", "indonesia", "philippines", "vietnam"
}

# ============================================================
# DICTIONARY NHẬN DIỆN QUỐC GIA (KHI KHÁCH NHẮN TEXT)
# ============================================================
COUNTRY_LOOKUP = {
    "russia": ("Russian (Россия)", "ru"),
    "россия": ("Russian (Россия)", "ru"),
    "русский": ("Russian (Россия)", "ru"),
    "nga": ("Russian (Россия)", "ru"),
    "south korea": ("South Korea (대한민국)", "ko"),
    "korea": ("South Korea (대한민국)", "ko"),
    "한국": ("South Korea (대한민국)", "ko"),
    "대한민국": ("South Korea (대한민국)", "ko"),
    "hàn quốc": ("South Korea (대한민국)", "ko"),
    "china": ("China (中国)", "zh"),
    "китай": ("China (中国)", "zh"),
    "中国": ("China (中国)", "zh"),
    "trung quốc": ("China (中国)", "zh"),
    "kazakhstan": ("Kazakhstan", "ru"),
    "казахстан": ("Kazakhstan", "ru"),
    "kyrgyzstan": ("Kyrgyzstan", "ru"),
    "кыргызстан": ("Kyrgyzstan", "ru"),
    "belarus": ("Belarus", "ru"),
    "беларусь": ("Belarus", "ru"),
    "uzbekistan": ("Uzbekistan", "ru"),
    "узбекистан": ("Uzbekistan", "ru"),
    "tajikistan": ("Tajikistan", "ru"),
    "united states": ("United States", "en"),
    "usa": ("United States", "en"),
    "america": ("United States", "en"),
    "сша": ("United States", "en"),
    "mỹ": ("United States", "en"),
    "united kingdom": ("United Kingdom", "en"),
    "uk": ("United Kingdom", "en"),
    "england": ("United Kingdom", "en"),
    "anh": ("United Kingdom", "en"),
    "germany": ("Germany", "en"),
    "германия": ("Germany", "ru"),
    "đức": ("Germany", "en"),
    "france": ("France", "en"),
    "франция": ("France", "ru"),
    "pháp": ("France", "en"),
    "australia": ("Australia", "en"),
    "австралия": ("Australia", "ru"),
    "úc": ("Australia", "en"),
    "canada": ("Canada", "en"),
    "канада": ("Canada", "ru"),
    "india": ("India", "en"),
    "индия": ("India", "ru"),
    "ấn độ": ("India", "en"),
    "vietnam": ("Vietnam (Việt Nam)", "vi"),
    "việt nam": ("Vietnam (Việt Nam)", "vi"),
    "вьетнам": ("Vietnam (Việt Nam)", "ru")
}

def identify_country(text: str) -> tuple[str, str] | None:
    t = text.lower().strip()
    words = set(re.findall(r'[\w\u00C0-\u1EF9]+', t))
    for kw, (cname, clang) in COUNTRY_LOOKUP.items():
        if " " in kw:
            if kw in t:
                return cname, clang
        else:
            if kw in words or t == kw:
                return cname, clang
    return None

def is_country_exempt(country_name: str) -> bool:
    cn = (country_name or "").lower()
    for exempt in VISA_EXEMPT_COUNTRIES:
        if exempt in cn:
            return True
    return False

async def send_step_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, reply_markup=None, parse_mode="Markdown"):
    """Gửi phản hồi an toàn hỗ trợ cả Telegram Business và Chat cá nhân/nhóm thông thường (có cơ chế tự retry không lỗi Markdown)"""
    query = update.callback_query
    chat_id = update.effective_chat.id if update.effective_chat else None
    user_id = str(chat_id) if chat_id else (str(update.effective_user.id) if update.effective_user else "")
    session_id = f"telegram_{user_id}"
    conn_id = memory_store.get(f"{session_id}_business_connection_id") or getattr(getattr(update, "business_message", None), "business_connection_id", None) or getattr(getattr(update, "edited_business_message", None), "business_connection_id", None)
    bot = context.bot if context else None
    
    # 1. Nếu là Telegram Business connection (quản lý chat cá nhân giữa khách và shop có nút Stop)
    if conn_id and chat_id and bot:
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                business_connection_id=conn_id,
                disable_web_page_preview=True
            )
        except Exception as e_biz:
            print(f"⚠️ Telegram Business send error with {parse_mode}: {e_biz}. Retrying plain text...")
            try:
                return await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    reply_markup=reply_markup,
                    business_connection_id=conn_id,
                    disable_web_page_preview=True
                )
            except Exception as e_biz2:
                print(f"❌ Telegram Business send failed completely: {e_biz2}")

    # 2. Phản hồi callback query
    if query and query.message:
        try:
            return await query.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        except Exception as e_qm:
            try:
                return await query.message.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
            except Exception as e_qm2:
                print(f"⚠️ query.message.reply_text error: {e_qm2}")

    # 3. Phản hồi tin nhắn thông thường hoặc tin nhắn business
    target_msg = getattr(update, "message", None) or getattr(update, "business_message", None) or getattr(update, "edited_business_message", None)
    if target_msg:
        try:
            return await target_msg.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        except Exception as e_m:
            try:
                return await target_msg.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
            except Exception as e_m2:
                print(f"⚠️ target_msg.reply_text error: {e_m2}")

    # 4. Fallback gửi trực tiếp qua bot
    if chat_id and bot:
        try:
            return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        except Exception:
            return await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, disable_web_page_preview=True)


def analyze_customer_incoming_message(text: str) -> dict:
    """
    Phân tích đoạn chat của khách hàng khi nhấn chuyển tiếp từ Website sang Telegram:
    Đảm bảo mọi khách hàng bắt đầu từ Web hoặc gửi lời chào ĐỀU được dẫn dắt theo đúng trình tự các bước:
    Bước 1: Chọn Quốc Tịch -> Bước 2: Chọn Thành Phố -> Bước 3: Lịch Tháng -> Bước 4: Bảng Dịch Vụ Phù Hợp.
    """
    t = (text or "").strip()
    tl = t.lower()
    if not tl:
        return {"action": "general", "lang": "en"}
        
    # Phát hiện ngôn ngữ sơ bộ
    detected_lang = "en"
    if any(c in tl for c in ["здравствуйте", "привет", "добр", "хочу", "виза", "визаран", "паспорт", "росси", "дня", "дней", "муйне", "нячанг", "лаос", "камбодж", "оверстей", "срочн", "продлен"]):
        detected_lang = "ru"
    elif any(c in tl for c in ["xin chào", "chào", "tôi muốn", "cho tôi", "báo giá", "làm visa", "hộ chiếu", "mũi né", "nha trang", "quá hạn", "khẩn", "cấp tốc", "tư vấn", "xe buýt", "xe bus", "đà nẵng", "hà nội", "sài gòn", "phí", "giá", "vé", "đặt xe", "chuyến", "lào", "campuchia"]):
        detected_lang = "vi"
    elif any(c in tl for c in ["안녕", "비자"]):
        detected_lang = "ko"

    # 1. Kiểm tra Lời chào / Câu mẫu bắt đầu từ Website (VD: "Здравствуйте, Easy Trip & Visa! Мне нужна консультация...")
    is_initial_onboarding = (
        tl in ["/start", "hi", "hello", "start"] or
        any(tl.startswith(g) for g in [
            "здравствуйте, easy trip", "здравствуйте! я хочу", "здравствуйте! хочу", "здравствуйте", "привет",
            "добрый день", "доброе утро", "добрый вечер",
            "hi easy trip", "hello easy trip", "hi easytrip", "hello easytrip",
            "xin chào", "chào bạn", "chào bot", "chào easytrip", "chào easy trip",
            "hello vietnam visa pass"
        ])
    )

    # 2. Kiểm tra Thành phố xuất phát & Tuyến xe
    city = None
    if any(k in tl for k in ["muine", "mui ne", "mũi né", "муйне", "phan thiết", "phan thiet"]):
        city = "muine"
    elif any(k in tl for k in ["nhatrang", "nha trang", "нячанг"]):
        city = "nhatrang"
    elif any(k in tl for k in ["danang", "da nang", "đà nẵng", "дананг", "hội an", "hoi an"]):
        city = "danang"
    elif any(k in tl for k in ["hcm", "hồ chí minh", "ho chi minh", "хошимин", "sài gòn", "saigon", "tp.hcm", "tp hcm", "tphcm"]):
        city = "hcm"
    elif any(k in tl for k in ["hanoi", "ha noi", "hà nội", "ханой"]):
        city = "hanoi"
    elif any(k in tl for k in ["abroad", "за рубежом", "nước ngoài"]):
        city = "abroad"

    # Nếu khách chuyển tiếp từ Web kèm tuyến xe/thành phố cụ thể (hoặc tin nhắn có đề cập thành phố)
    is_web_or_city = (
        city is not None or
        any(k in tl for k in [
            "express visa run booking", "визаран", "visarun", "visa run",
            "vietnam visa pass", "xe buýt", "xe bus", "chuyến xe", "đặt xe"
        ])
    )
    if is_web_or_city:
        c_code = city
        service_name = ""
        if c_code == "muine" or any(k in tl for k in ["камбодж", "cambodia", "campuchia", "mộc bài", "moc bai"]):
            c_code = "muine"
            service_name = "Визаран Муйне ⇄ Камбоджа (Мокбай)" if detected_lang == "ru" else "Visarun Mũi Né ⇄ Campuchia (Mộc Bài)" if detected_lang == "vi" else "Visarun Mui Ne ⇄ Cambodia (Moc Bai)"
        elif c_code == "danang" or any(k in tl for k in ["lao bảo", "lao bao", "лао бао"]):
            c_code = "danang"
            service_name = "Визаран Дананг ⇄ Лаос (Лао Бао)" if detected_lang == "ru" else "Visarun Đà Nẵng ⇄ Lào (Lao Bảo)" if detected_lang == "vi" else "Visarun Da Nang ⇄ Laos (Lao Bao)"
        elif c_code == "hanoi" or any(k in tl for k in ["hữu nghị", "huu nghi", "хыу нги"]):
            c_code = "hanoi"
            service_name = "Визаран Ханой ⇄ Хыу Нги" if detected_lang == "ru" else "Visarun Hà Nội ⇄ Hữu Nghị" if detected_lang == "vi" else "Visarun Hanoi ⇄ Huu Nghi"
        elif c_code == "hcm":
            service_name = "Индивидуальный трансфер Хошимин ⇄ Мокбай" if detected_lang == "ru" else "Xe riêng TP.HCM ⇄ Mộc Bài" if detected_lang == "vi" else "Private Car HCMC ⇄ Moc Bai"
        else:
            service_name = "Визаран Нячанг ⇄ Лаос / Камбоджа" if detected_lang == "ru" else "Visarun Nha Trang ⇄ Lào / Campuchia" if detected_lang == "vi" else "Visarun Nha Trang ⇄ Laos / Cambodia"

        return {
            "action": "web_lead",
            "city": c_code,
            "service_name": service_name,
            "lang": detected_lang
        }

    # Nếu là lời chào mở đầu / câu hỏi từ website (kể cả hỏi gia hạn visa / visa khẩn) -> Khởi động Bước 1 Chọn Quốc Tịch
    if is_initial_onboarding:
        return {"action": "greeting", "lang": detected_lang}

    # 3. Kiểm tra nếu khách chỉ gõ tên quốc gia (VD: Russia, Kazakhstan, Đức, Pháp)
    country_res = identify_country(t)
    if country_res:
        return {"action": "country_selected", "country": country_res[0], "lang": country_res[1]}

    # 4. Khi đang trong cuộc trò chuyện, khách hỏi trực tiếp về Overstay, TRC, Work, Family
    if any(k in tl for k in ["overstay", "оверстей", "просрочк", "quá hạn", "hết hạn visa"]):
        return {"action": "special_agent", "topic": "overstay", "lang": detected_lang}
    if any(k in tl for k in ["trc", "внж", "tạm trú", "residence card", "карта резидента"]):
        return {"action": "special_agent", "topic": "trc", "lang": detected_lang}
    if any(k in tl for k in ["work permit", "work visa", "рабочая виза", "разрешение на работу", "lao động", "giấy phép lao động"]):
        return {"action": "special_agent", "topic": "work", "lang": detected_lang}
    if any(k in tl for k in ["family visa", "семейная виза", "виза для семьи", "thăm thân"]):
        return {"action": "special_agent", "topic": "family", "lang": detected_lang}

    # 5. Fast Track và E-Visa cấp tốc khi khách yêu cầu rõ
    if any(k in tl for k in ["fast track", "fasttrack", "фаст трек", "đón sân bay"]):
        return {"action": "special_service", "service_id": "special_fast_track", "lang": detected_lang}
    if any(k in tl for k in ["urgent", "срочн", "cấp tốc", "khẩn"]):
        return {"action": "special_service", "service_id": "special_urgent_evisa", "lang": detected_lang}

    return {"action": "general", "lang": detected_lang}

# ============================================================
# CÁC BÀN PHÍM BƯỚC 1, 2, 3
# ============================================================

def get_nationality_keyboard():
    """Bước 1: Chọn Tên Quốc Gia (Country Names)"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇷🇺 Russia (Россия)", callback_data="step|nat|ru"),
            InlineKeyboardButton("🇰🇷 South Korea (대한민국)", callback_data="step|nat|ko")
        ],
        [
            InlineKeyboardButton("🇨🇳 China (中国)", callback_data="step|nat|zh"),
            InlineKeyboardButton("🇺🇸 United States / Europe", callback_data="step|nat|en")
        ],
        [
            InlineKeyboardButton("🇰🇿 🇰🇬 Kazakhstan / Kyrgyzstan / CIS", callback_data="step|nat|cis"),
            InlineKeyboardButton("🇻🇳 Vietnam (Việt Nam)", callback_data="step|nat|vi")
        ],
        [
            InlineKeyboardButton("🌐 Other Country (Quốc gia khác)", callback_data="step|nat|other")
        ]
    ])

def get_city_keyboard(lang: str = "en"):
    """Bước 2: Chọn Thành phố (Abroad lên đầu, Nha Trang, Mũi Né...)"""
    abroad_lbl = "✈️ За рубежом (Въезд во Вьетнам)" if lang == "ru" else "✈️ Đang ở nước ngoài (Nhập cảnh vào VN)" if lang == "vi" else "✈️ Currently Abroad (Entering Vietnam)"
    other_lbl = "📍 Другой город" if lang == "ru" else "📍 Thành phố khác" if lang == "vi" else "📍 Other City"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(abroad_lbl, callback_data="step|city|abroad")
        ],
        [
            InlineKeyboardButton("🏖️ Nha Trang", callback_data="step|city|nhatrang"),
            InlineKeyboardButton("🏖️ Mũi Né (Phan Thiết)", callback_data="step|city|muine")
        ],
        [
            InlineKeyboardButton("🌊 Đà Nẵng / Hội An", callback_data="step|city|danang"),
            InlineKeyboardButton("🏙️ TP. Hồ Chí Minh", callback_data="step|city|hcm")
        ],
        [
            InlineKeyboardButton("🏛️ Hà Nội", callback_data="step|city|hanoi"),
            InlineKeyboardButton(other_lbl, callback_data="step|city|other")
        ]
    ])

def get_calendar_keyboard(year: int, month: int, lang: str = "ru"):
    """Bước 3: Lịch tháng tương tác chuẩn quốc tế (Calendar Picker)"""
    cal = calendar.monthcalendar(year, month)
    month_names = {
        "ru": ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
        "en": ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "vi": ["", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"],
        "ko": ["", "1월", "2월", "3월", "4월", "5월", "6월", "7월", "8월", "9월", "10월", "11월", "12월"]
    }
    m_name = month_names.get(lang, month_names["en"])[month]
    
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    
    rows = []
    # Header: Month & Navigation
    rows.append([
        InlineKeyboardButton("◀", callback_data=f"step|cal_nav|{prev_y}|{prev_m}"),
        InlineKeyboardButton(f"📅 {m_name} {year}", callback_data="step|ignore"),
        InlineKeyboardButton("▶", callback_data=f"step|cal_nav|{next_y}|{next_m}")
    ])
    
    # Days of week header
    if lang == "ru":
        days_header = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    elif lang == "vi":
        days_header = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    elif lang == "ko":
        days_header = ["월", "화", "수", "목", "금", "토", "일"]
    else:
        days_header = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    rows.append([InlineKeyboardButton(d, callback_data="step|ignore") for d in days_header])
    
    # Grid of days
    now = datetime.now()
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="step|ignore"))
            else:
                date_str = f"{day:02d}/{month:02d}"
                is_past = (year < now.year) or (year == now.year and month < now.month) or (year == now.year and month == now.month and day < now.day)
                lbl = f"·{day}·" if is_past else str(day)
                row.append(InlineKeyboardButton(lbl, callback_data=f"step|date|{date_str}"))
        rows.append(row)
        
    urgent_lbl = "⚡ Срочно (1-2 дня)" if lang == "ru" else "⚡ Khẩn cấp (1-2 ngày)" if lang == "vi" else "⚡ Urgent (1-2 days)"
    manual_lbl = "✍️ Ввести вручную" if lang == "ru" else "✍️ Nhập ngày khác" if lang == "vi" else "✍️ Enter date"
    rows.append([
        InlineKeyboardButton(urgent_lbl, callback_data="step|date|urgent"),
        InlineKeyboardButton(manual_lbl, callback_data="step|date|manual")
    ])
    return InlineKeyboardMarkup(rows)

# ============================================================
# BƯỚC 4: BỘ TƯ VẤN THÔNG MINH (SMART ADVISORY KEYBOARD)
# ============================================================

def get_smart_advisory_keyboard(city: str, country: str, lang: str = "en"):
    """Đề xuất nút bấm chính xác phù hợp Quốc tịch + Thành phố + Lịch xe"""
    exempt = is_country_exempt(country)
    rows = []
    
    # 1. Đề xuất tuyến Visarun chính theo thành phố
    if city == "danang":
        rows.append([InlineKeyboardButton("🚌 Visarun Đà Nẵng Lao Bao - Lao Bảo Laos (90D)", callback_data="step|svc|dn_bus")])
        if exempt:
            rows.append([InlineKeyboardButton("⭐ Miễn thị thực 45 ngày (Lao Bảo) - 850.000 ₫", callback_data="step|svc|dn_bus")])
            rows.append([InlineKeyboardButton("📑 Combo trọn gói E-Visa 90 ngày (Lao Bảo) - 3.900.000 ₫", callback_data="step|svc|dn_combo_ultra")])
        else:
            rows.append([InlineKeyboardButton("📑 Combo trọn gói E-Visa 90 ngày (Lao Bảo) - 3.900.000 ₫", callback_data="step|svc|dn_combo_ultra")])
            
    elif city == "nhatrang":
        if lang == "ru":
            rows.append([InlineKeyboardButton("🚌 Визаран Nha Trang - Lào Bờ Y 45 ngày (Безвиз)", callback_data="step|svc|nt_bus_laos_45d")])
            rows.append([InlineKeyboardButton("🚌 Визаран Nha Trang - Lào Bờ Y 90 ngày (E-Visa)", callback_data="step|svc|nt_bus_laos_90d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Cambodia (30/45/90D)", callback_data="step|svc|nt_bus_cambodia")])
        elif lang == "vi":
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Lào Bờ Y 45 ngày", callback_data="step|svc|nt_bus_laos_45d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Lào Bờ Y 90 ngày", callback_data="step|svc|nt_bus_laos_90d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Cambodia (30/45/90D)", callback_data="step|svc|nt_bus_cambodia")])
        else:
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Laos Bo Y 45 Days (Visa-Free)", callback_data="step|svc|nt_bus_laos_45d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Laos Bo Y 90 Days (E-Visa)", callback_data="step|svc|nt_bus_laos_90d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Cambodia (30/45/90D)", callback_data="step|svc|nt_bus_cambodia")])

        if exempt:
            rows.append([InlineKeyboardButton("⭐ Miễn thị thực 45 ngày (Lào Bờ Y) - 1.400.000 ₫" if lang == "vi" else "⭐ Безвиз 45 дней (Лаос Бо-И) - 1.400.000 ₫" if lang == "ru" else "⭐ 45-Day Visa-Free (Laos Bo Y) - 1,400,000 VND", callback_data="step|svc|nt_bus_laos_45d")])
            rows.append([InlineKeyboardButton("📑 Trọn gói E-Visa 90 ngày (Lào Bờ Y) - 4.000.000 ₫" if lang == "vi" else "📑 Пакет E-Visa 90 дней (Лаос Бо-И) - 4.000.000 ₫" if lang == "ru" else "📑 90-Day E-Visa Package (Laos Bo Y) - 4,000,000 VND", callback_data="step|svc|nt_bus_laos_90d")])
        else:
            # Khách không miễn visa
            rows.append([InlineKeyboardButton("📑 Trọn gói E-Visa 90 ngày (Lào Bờ Y) - 4.000.000 ₫" if lang == "vi" else "📑 Пакет E-Visa 90 дней (Лаос Бо-И) - 4.000.000 ₫" if lang == "ru" else "📑 90-Day E-Visa Package (Laos Bo Y) - 4,000,000 VND", callback_data="step|svc|nt_bus_laos_90d")])
            rows.append([InlineKeyboardButton("📑 Trọn gói E-Visa 90 ngày (Campuchia Mộc Bài) - 4.000.000 ₫" if lang == "vi" else "📑 Пакет E-Visa 90 дней (Мокбай) - 4.000.000 ₫" if lang == "ru" else "📑 90-Day E-Visa Package (Moc Bai) - 4,000,000 VND", callback_data="step|svc|nt_combo_evisa")])
            
    elif city == "muine":
        rows.append([InlineKeyboardButton("🚌 Visarun Mũi Né - Cambodia (30/45/90D)", callback_data="step|svc|mn_bus_cambodia")])
        if exempt:
            rows.append([InlineKeyboardButton("⭐ Vé xe Mũi Né ⇄ Campuchia (Miễn visa) - 1.400.000 ₫", callback_data="step|svc|mn_bus_cambodia")])
            rows.append([InlineKeyboardButton("📑 Trọn gói Bus Mũi Né + E-Visa 90 ngày - 4.000.000 ₫", callback_data="step|svc|mn_combo_evisa")])
        else:
            rows.append([InlineKeyboardButton("📑 Trọn gói Bus Mũi Né + E-Visa 90 ngày - 4.000.000 ₫", callback_data="step|svc|mn_combo_evisa")])
            
    elif city == "hanoi":
        rows.append([InlineKeyboardButton("🚌 Визаран Hà Nội - Hữu Nghị (45/90D)", callback_data="step|svc|hn_bus_huunghi")])
        if exempt:
            rows.append([InlineKeyboardButton("⭐ Vé VIP Limousine Hà Nội ⇄ Hữu Nghị (Miễn visa 45D) - 1.200.000 ₫", callback_data="step|svc|hn_bus_huunghi")])
        rows.append([InlineKeyboardButton("📑 Trọn gói VIP Limousine + E-Visa 90 ngày Hữu Nghị", callback_data="step|svc|hn_bus_huunghi")])
        
    elif city == "hcm":
        rows.append([InlineKeyboardButton("🚗 Xe Ô Tô Riêng 4–7 Chỗ TP.HCM ⇄ Mộc Bài - 2.300.000 ₫", callback_data="step|svc|hcm_car_private")])
        rows.append([InlineKeyboardButton("✈️ VIP Fast Track Sân Bay Tân Sơn Nhất - 1.200.000 ₫", callback_data="step|svc|hcm_fasttrack")])
        
    elif city == "abroad":
        rows.append([InlineKeyboardButton("⚡ Urgent E-visa (Làm visa cấp tốc trước khi bay)", callback_data="step|svc|abroad_evisa_urgent")])
        rows.append([InlineKeyboardButton("✈️ Airport VIP Fast Track Đón Cửa Máy Bay", callback_data="step|svc|abroad_fasttrack")])

    # 2. Các nút dịch vụ đặc biệt: Tách riêng 4 nút chuyên biệt (Overstay, TRC, Work, Family)
    if lang == "ru":
        rows.append([
            InlineKeyboardButton("⚡ Срочная E-Visa (Urgent)", callback_data="step|svc|special_urgent_evisa"),
            InlineKeyboardButton("✈️ VIP Fast Track (Аэропорт)", callback_data="step|svc|special_fast_track")
        ])
        rows.append([
            InlineKeyboardButton("⚠️ Просрочка визы (Overstay)", callback_data="step|agent|overstay"),
            InlineKeyboardButton("🪪 Карта резидента TRC (2 года)", callback_data="step|agent|trc")
        ])
        rows.append([
            InlineKeyboardButton("💼 Рабочая виза (Work Visa)", callback_data="step|agent|work"),
            InlineKeyboardButton("👨‍👩‍👧 Семейная виза (Family)", callback_data="step|agent|family")
        ])
    elif lang == "vi":
        rows.append([
            InlineKeyboardButton("⚡ Urgent E-visa Cấp Tốc", callback_data="step|svc|special_urgent_evisa"),
            InlineKeyboardButton("✈️ Airport VIP Fast Track", callback_data="step|svc|special_fast_track")
        ])
        rows.append([
            InlineKeyboardButton("⚠️ Quá hạn visa (Overstay)", callback_data="step|agent|overstay"),
            InlineKeyboardButton("🪪 Thẻ tạm trú TRC 2 năm", callback_data="step|agent|trc")
        ])
        rows.append([
            InlineKeyboardButton("💼 Visa lao động (Work Visa)", callback_data="step|agent|work"),
            InlineKeyboardButton("👨‍👩‍👧 Visa thăm thân / Gia đình", callback_data="step|agent|family")
        ])
    else:
        rows.append([
            InlineKeyboardButton("⚡ Urgent E-visa", callback_data="step|svc|special_urgent_evisa"),
            InlineKeyboardButton("✈️ Airport VIP Fast Track", callback_data="step|svc|special_fast_track")
        ])
        rows.append([
            InlineKeyboardButton("⚠️ Visa Overstay", callback_data="step|agent|overstay"),
            InlineKeyboardButton("🪪 TRC Residence Card (2Y)", callback_data="step|agent|trc")
        ])
        rows.append([
            InlineKeyboardButton("💼 Work Visa & Permit", callback_data="step|agent|work"),
            InlineKeyboardButton("👨‍👩‍👧 Family / Visitor Visa", callback_data="step|agent|family")
        ])

    rows.append([
        InlineKeyboardButton("🔄 " + ("Сменить город" if lang == "ru" else "Đổi thành phố" if lang == "vi" else "Change City"), callback_data="step|back|city"),
        InlineKeyboardButton("🔄 " + ("Сменить страну" if lang == "ru" else "Đổi quốc tịch" if lang == "vi" else "Change Country"), callback_data="step|back|nationality")
    ])
    return InlineKeyboardMarkup(rows)

def get_routes_keyboard(city: str, lang: str = "en", country: str = ""):
    return get_smart_advisory_keyboard(city, country, lang)

ROUTE_SERVICES = {
    "nhatrang": [
        {"id": "nt_bus_laos_45d", "name_vi": "🚌 Sleeper Bus Nha Trang ⇄ Bờ Y (45 Ngày Miễn Visa)", "price": 1400000},
        {"id": "nt_bus_laos_90d", "name_vi": "🚌 Sleeper Bus Nha Trang ⇄ Bờ Y (90 Ngày E-Visa)", "price": 1400000},
        {"id": "nt_bus_cambodia", "name_vi": "🚌 Sleeper Bus Nha Trang ⇄ Mộc Bài (Campuchia)", "price": 1400000},
        {"id": "nt_combo_evisa", "name_vi": "⭐ Combo Trọn Gói: Bus + E-Visa 90 Ngày", "price": 4000000}
    ],
    "muine": [
        {"id": "mn_bus_cambodia", "name_vi": "🚌 Sleeper Bus Mũi Né ⇄ Mộc Bài (Campuchia)", "price": 1400000},
        {"id": "mn_combo_evisa", "name_vi": "⭐ Combo Trọn Gói: Bus Mũi Né + E-Visa 90 Ngày", "price": 4000000}
    ],
    "danang": [
        {"id": "dn_bus", "name_vi": "🚌 Sleeper Bus Đà Nẵng ⇄ Lao Bảo (Lào)", "price": 850000},
        {"id": "dn_combo_ultra", "name_vi": "⭐ Combo: Bus + E-Visa Ultra Fast 3-4h", "price": 3900000}
    ],
    "hcm": [
        {"id": "hcm_car_private", "name_vi": "🚗 Xe Ô Tô Riêng 4–7 Chỗ TP.HCM ⇄ Mộc Bài (Campuchia)", "price": 2300000},
        {"id": "hcm_fasttrack", "name_vi": "✈️ VIP Fast Track Sân Bay Tân Sơn Nhất (SGN)", "price": 1200000}
    ],
    "hanoi": [
        {"id": "hn_bus_huunghi", "name_vi": "🚐 VIP Limousine Hà Nội ⇄ Hữu Nghị (TQ)", "price": 1200000},
        {"id": "hn_fasttrack", "name_vi": "✈️ VIP Fast Track Sân Bay Nội Bài (HAN)", "price": 1200000}
    ]
}

# ============================================================
# NỘI DUNG TƯ VẤN CHI TIẾT (LỊCH TRÌNH, LƯU Ý ĐIỂM ĐÓN & BIÊN GIỚI)
# ============================================================

ITINERARIES = {
    "laos_boy_45d": {
        "title_vi": "🚌 TUYẾN: NHA TRANG ⇄ CỬA KHẨU BỜ Y (LÀO) — MIỄN THỊ THỰC 45 NGÀY",
        "title_ru": "🚌 МАРШРУТ: НЯЧАНГ ⇄ КПП БО-И (ЛАОС) — БЕЗВИЗ 45 ДНЕЙ",
        "title_en": "🚌 ROUTE: NHA TRANG ⇄ BO Y BORDER (LAOS) — 45-DAY VISA-FREE",
        "price": "1.400.000 VND (Vé xe giường nằm khứ hồi)",
        "schedule_vi": (
            "⏰ LỊCH TRÌNH CHI TIẾT (XE CHẠY MỖI NGÀY):\n"
            "• 21:00: Tập trung tại điểm đón xe buýt ở Nha Trang.\n"
            "• 21:15 - 21:30: Xe giường nằm khởi hành đi Cửa khẩu Quốc tế Bờ Y (Kon Tum).\n"
            "• 06:00 (Sáng hôm sau): Đến cửa khẩu Bờ Y, nghỉ ngơi, ăn sáng, cafe.\n"
            "• 07:00: Cửa khẩu mở cửa. Xếp hàng và xuất cảnh cùng với những hành khách khác.\n"
            "• 07:30: Đi bộ sang cửa khẩu Lào làm thủ tục đóng dấu nhập cảnh và xuất cảnh Lào.\n"
            "• 08:30: Quay lại làm thủ tục nhập cảnh Việt Nam, nhận dấu miễn thị thực 45 ngày mới.\n"
            "• 09:30: Lên xe buýt quay trở về Nha Trang (về tới nơi khoảng 18:30 - 19:00 chiều)."
        ),
        "schedule_ru": (
            "⏰ ДЕТАЛЬНОЕ РАСПИСАНИЕ (АВТОБУС ХОДИТ ЕЖЕДНЕВНО):\n"
            "• 21:00: Сбор на посадочной точке в Нячанге.\n"
            "• 21:15 - 21:30: Отправление комфортабельного слипбаса в сторону КПП Бо-И (Контум).\n"
            "• 06:00 (следующее утро): Прибытие на границу Бо-И, завтрак, кофе, отдых.\n"
            "• 07:00: Открытие границы. Очередь и выезд из Вьетнама вместе с другими пассажирами.\n"
            "• 07:30: Переход границы Лаоса, получение въездного и выездного штампа Лаоса.\n"
            "• 08:30: Возвращение на КПП Вьетнама, получение нового 45-дневного безвизового штампа.\n"
            "• 09:30: Посадка в автобус и выезд обратно в Нячанг (прибытие около 18:30 - 19:00 вечера)."
        ),
        "pickup_vi": "📍 Điểm đón: 40 Hòn Chồng = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) hoặc Số 4 Trần Phú, Nha Trang.",
        "pickup_ru": "📍 Точка сбора: 40 Hon Chong = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) или No. 4 Tran Phu, Нячанг.",
        "border_vi": "⚠️ LƯU Ý TẠI CỬA KHẨU: Hộ chiếu gốc còn hạn trên 6 tháng; tiền mặt (khoảng 150.000 VND) nộp phí thủ tục biên phòng.",
        "border_ru": "⚠️ ВАЖНО НА ГРАНИЦЕ: Загранпаспорт сроком от 6 мес.; наличные (ок. 150.000 VND) на оплату пограничных сборов.",
        "booking_vi": (
            "📝 CÁCH THỨC ĐĂNG KÝ (QUY TRÌNH 4 BƯỚC ĐƠN GIẢN):\n"
            "1️⃣ Gửi ảnh chụp trang Hộ chiếu (rõ 4 góc, còn hạn trên 6 tháng) vào khung chat này.\n"
            "2️⃣ Bấm nút 'Kiểm tra sơ đồ chỗ & Chọn số ghế' bên dưới để chọn vị trí nằm mong muốn.\n"
            "3️⃣ Bấm nút 'Phương thức thanh toán' để chuyển khoản (VCB / VRB) hoặc nộp tiền mặt tại văn phòng Nha Trang.\n"
            "4️⃣ Nhận vé điện tử xác nhận đặt chỗ. Biển số xe & số liên hệ tài xế sẽ được gửi trước giờ chạy 2 tiếng."
        ),
        "booking_ru": (
            "📝 КАК ЗАБРОНИРОВАТЬ МЕСТО (ИНСТРУКЦИЯ ИЗ 4 ШАГОВ):\n"
            "1️⃣ Отправьте фото страницы загранпаспорта (срок действия от 6 месяцев) прямо в этот чат.\n"
            "2️⃣ Нажмите кнопку 'Запросить проверку мест и выбрать место' ниже, чтобы забронировать желаемую полку.\n"
            "3️⃣ Нажмите кнопку 'Способы оплаты' для перевода (Vietcombank, VRB) или оплаты наличными в офисе Нячанга.\n"
            "4️⃣ Получите официальный электронный посадочный талон. Контакты водителя и номер автобуса высылаются за 2 часа до отправления."
        ),
        "booking_en": (
            "📝 HOW TO REGISTER (SIMPLE 4-STEP BOOKING):\n"
            "1️⃣ Send a clear photo of your passport page (valid 6+ months) in this chat.\n"
            "2️⃣ Click 'Check availability & Select Seat' below to select your desired sleeper bed.\n"
            "3️⃣ Click 'Payment Methods' to pay via Vietcombank, VRB Bank, or Cash at our Nha Trang office.\n"
            "4️⃣ Receive your booking confirmation receipt. Bus info and driver contact will be sent 2 hours before departure."
        )
    },
    "laos_boy_90d": {
        "title_vi": "🚌 TUYẾN: NHA TRANG ⇄ CỬA KHẨU BỜ Y (LÀO) — E-VISA 90 NGÀY",
        "title_ru": "🚌 МАРШРУТ: НЯЧАНГ ⇄ КПП БО-И (ЛАОС) — E-VISA 90 ДНЕЙ",
        "title_en": "🚌 ROUTE: NHA TRANG ⇄ BO Y BORDER (LAOS) — 90-DAY E-VISA",
        "price": "1.400.000 VND (Chỉ vé xe khứ hồi) | 4.000.000 VND (Combo Trọn Gói Bus + E-Visa 90 ngày)",
        "schedule_vi": (
            "⏰ LỊCH TRÌNH CHI TIẾT (XE CHẠY THỨ 3, THỨ 5, CHỦ NHẬT):\n"
            "• 21:00: Tập trung tại điểm đón xe buýt ở Nha Trang.\n"
            "• 21:15 - 21:30: Xe giường nằm khởi hành đi Cửa khẩu Quốc tế Bờ Y.\n"
            "• 06:00 (Sáng hôm sau): Đến cửa khẩu Bờ Y, nghỉ ngơi, ăn sáng, cafe.\n"
            "• 07:00: Cửa khẩu mở cửa. Xếp hàng làm thủ tục xuất cảnh Việt Nam.\n"
            "• 07:30: Đi bộ sang cửa khẩu Lào làm thủ tục đóng dấu nhập cảnh và xuất cảnh Lào.\n"
            "• 08:30: Quay lại cửa khẩu Việt Nam xuất trình E-Visa 90 ngày (đã in sẵn ra giấy) để hải quan đóng dấu thời hạn 90 ngày mới.\n"
            "• 09:30: Lên xe buýt quay trở về Nha Trang (về tới nơi khoảng 18:30 - 19:00 chiều)."
        ),
        "schedule_ru": (
            "⏰ ДЕТАЛЬНОЕ РАСПИСАНИЕ (АВТОБУС ХОДИТ ВО ВТ, ЧТ, ВС):\n"
            "• 21:00: Сбор на посадочной точке в Нячанге.\n"
            "• 21:15 - 21:30: Отправление комфортабельного слипбаса в сторону КПП Бо-И.\n"
            "• 06:00 (следующее утро): Прибытие на границу Бо-И, завтрак, кофе, отдых.\n"
            "• 07:00: Открытие границы. Очередь и выезд из Вьетнама.\n"
            "• 07:30: Переход границы Лаоса, получение въездного и выездного штампа Лаоса.\n"
            "• 08:30: Возвращение на вьетнамский КПП, предъявление распечатанной E-Visa 90 дней и получение штампа на 90 дней.\n"
            "• 09:30: Посадка в автобус и выезд обратно в Нячанг (прибытие около 18:30 - 19:00)."
        ),
        "pickup_vi": "📍 Điểm đón: 40 Hòn Chồng = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) hoặc Số 4 Trần Phú, Nha Trang.",
        "pickup_ru": "📍 Точка сбора: 40 Hon Chong = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) или No. 4 Tran Phu, Нячанг.",
        "border_vi": "⚠️ LƯU Ý TẠI CỬA KHẨU: Hộ chiếu gốc còn hạn trên 6 tháng; BẮT BUỘC in E-Visa ra giấy (2 bản); tiền mặt (khoảng 150.000 VND) nộp phí biên phòng.",
        "border_ru": "⚠️ ВАЖНО НА ГРАНИЦЕ: Загранпаспорт сроком от 6 мес.; ОБЯЗАТЕЛЬНО распечатать E-Visa на бумаге (2 копии); наличные (ок. 150.000 VND) на пограничные сборы.",
        "booking_vi": (
            "📝 CÁCH THỨC ĐĂNG KÝ (COMBO E-VISA 90 NGÀY HOẶC ĐẶT XE):\n"
            "1️⃣ Gửi ảnh Hộ chiếu + ảnh thẻ 4x6 (nền trắng) trước ngày đi 3–5 ngày để làm E-Visa cửa khẩu Bờ Y (có hỗ trợ gói khẩn 1–2 ngày / trong ngày nếu gấp).\n"
            "2️⃣ Chọn ngày khởi hành (Thứ 3, Thứ 5, Chủ Nhật) và bấm nút 'Kiểm tra sơ đồ chỗ & Chọn số ghế'.\n"
            "3️⃣ Bấm nút 'Phương thức thanh toán' để thanh toán vé hoặc trọn gói qua Vietcombank, VRB hoặc tiền mặt tại văn phòng Nha Trang.\n"
            "4️⃣ Nhận file E-Visa 90 ngày in sẵn cùng vé xe điện tử để an tâm khởi hành."
        ),
        "booking_ru": (
            "📝 КАК ЗАБРОНИРОВАТЬ И ОФОРМИТЬ E-VISA НА 90 ДНЕЙ:\n"
            "1️⃣ Отправьте фото загранпаспорта + фото 4x6 (белый фон) за 3–5 рабочих дней до поездки для оформления E-Visa на КПП Бо-И (доступно срочное оформление 1–2 дня или 4 часа).\n"
            "2️⃣ Выберите дату выезда (Вторник, Четверг, Воскресенье) и нажмите кнопку 'Запросить проверку мест и выбрать место'.\n"
            "3️⃣ Нажмите кнопку 'Способы оплаты' для оплаты билета или полного пакета (Vietcombank, VRB, наличные в офисе).\n"
            "4️⃣ Получите готовую распечатанную визу E-Visa 90 дней и электронный билет."
        ),
        "booking_en": (
            "📝 HOW TO REGISTER & APPLY FOR 90-DAY E-VISA:\n"
            "1️⃣ Send passport photo + 4x6 photo 3–5 days prior to departure for Bo Y border E-Visa (urgent 1–2 days / 4 hours available).\n"
            "2️⃣ Choose departure date (Tuesday, Thursday, Sunday) and click 'Check availability & Select Seat'.\n"
            "3️⃣ Click 'Payment Methods' to pay via Vietcombank, VRB, or Cash at office.\n"
            "4️⃣ Receive your printed 90-Day E-Visa and bus ticket confirmation."
        )
    },
    "laos_boy": {
        "title_vi": "🚌 TUYẾN: NHA TRANG ⇄ CỬA KHẨU BỜ Y (LÀO) — 45/90 NGÀY",
        "title_ru": "🚌 МАРШРУТ: НЯЧАНГ ⇄ КПП БО-И (ЛАОС) — 45/90 ДНЕЙ",
        "title_en": "🚌 ROUTE: NHA TRANG ⇄ BO Y BORDER (LAOS) — 45/90 DAYS",
        "price": "1.400.000 VND (Vé xe khứ hồi) | 4.000.000 VND (Combo E-visa 90 ngày)",
        "schedule_vi": (
            "⏰ LỊCH TRÌNH CHI TIẾT (ITINERARY):\n"
            "• 21:00: Tập trung tại điểm đón xe buýt.\n"
            "• 21:15 - 21:30: Xe giường nằm khởi hành đi cửa khẩu Bờ Y.\n"
            "• 06:00 (Sáng hôm sau): Đến cửa khẩu Bờ Y, ăn sáng, cafe nghỉ ngơi.\n"
            "• 07:00: Cửa khẩu mở cửa. Xếp hàng và xuất cảnh cùng với những hành khách khác.\n"
            "• 07:30: Đi bộ sang cửa khẩu Lào làm thủ tục đóng dấu nhập cảnh và xuất cảnh Lào.\n"
            "• 08:30: Quay lại làm thủ tục nhập cảnh Việt Nam (nhận tem miễn thị thực 45 ngày mới hoặc E-Visa 90 ngày).\n"
            "• 09:30: Lên xe buýt quay trở về Nha Trang (về tới nơi khoảng 18:30 - 19:00 chiều)."
        ),
        "schedule_ru": (
            "⏰ ДЕТАЛЬНОЕ РАСПИСАНИЕ:\n"
            "• 21:00: Сбор на посадочной точке.\n"
            "• 21:15 - 21:30: Отправление комфортабельного слипбаса в сторону КПП Бо-И.\n"
            "• 06:00 (следующее утро): Прибытие на границу, завтрак, кофе.\n"
            "• 07:00: Открытие границы. Очередь и прохождение паспортного контроля на выезд из Вьетнама вместе с остальными пассажирами.\n"
            "• 07:30: Переход границы Лаоса, получение въездного и выездного штампа Лаоса.\n"
            "• 08:30: Возвращение на вьетнамский КПП, оформление въезда во Вьетнам (новый штамп 45 дней или E-Visa 90 дней).\n"
            "• 09:30: Посадка в автобус и выезд обратно в Нячанг (прибытие около 18:30 - 19:00 вечера)."
        ),
        "pickup_vi": "📍 Điểm đón: 40 Hòn Chồng = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) hoặc Số 4 Trần Phú, Nha Trang.",
        "pickup_ru": "📍 Точка сбора: 40 Hon Chong = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) или No. 4 Tran Phu, Нячанг.",
        "border_vi": "⚠️ LƯU Ý TẠI CỬA KHẨU: Hộ chiếu gốc còn hạn trên 6 tháng; 02 ảnh thẻ 4x6 nền trắng; tiền mặt (khoảng 150.000 VND) nộp phí dán tem biên phòng.",
        "border_ru": "⚠️ ВАЖНО НА ГРАНИЦЕ: Загранпаспорт сроком от 6 мес.; 2 фото 4x6 см (белый фон); наличные (ок. 150.000 VND) на оплату пограничных сборов.",
        "booking_vi": (
            "📝 CÁCH THỨC ĐĂNG KÝ (QUY TRÌNH 4 BƯỚC ĐƠN GIẢN):\n"
            "1️⃣ Gửi ảnh chụp trang Hộ chiếu (rõ 4 góc, còn hạn trên 6 tháng) vào khung chat này.\n"
            "2️⃣ Bấm nút 'Kiểm tra sơ đồ chỗ & Chọn số ghế' bên dưới để chọn vị trí nằm mong muốn.\n"
            "3️⃣ Bấm nút 'Phương thức thanh toán' để chuyển khoản (VCB / VRB) hoặc nộp tiền mặt tại văn phòng Nha Trang.\n"
            "4️⃣ Nhận vé điện tử xác nhận đặt chỗ. Biển số xe & số liên hệ tài xế sẽ được gửi trước giờ chạy 2 tiếng."
        ),
        "booking_ru": (
            "📝 КАК ЗАБРОНИРОВАТЬ МЕСТО (ИНСТРУКЦИЯ ИЗ 4 ШАГОВ):\n"
            "1️⃣ Отправьте фото страницы загранпаспорта прямо в этот чат.\n"
            "2️⃣ Нажмите кнопку 'Запросить проверку мест и выбрать место' ниже.\n"
            "3️⃣ Нажмите кнопку 'Способы оплаты' для перевода (VCB / VRB) или оплаты наличными в офисе.\n"
            "4️⃣ Получите официальный электронный посадочный талон."
        ),
        "booking_en": (
            "📝 HOW TO REGISTER (SIMPLE 4-STEP BOOKING):\n"
            "1️⃣ Send a clear photo of your passport page in this chat.\n"
            "2️⃣ Click 'Check availability & Select Seat' below to select your desired sleeper bed.\n"
            "3️⃣ Click 'Payment Methods' to pay via VCB, VRB, or Cash at office.\n"
            "4️⃣ Receive your booking confirmation receipt."
        )
    },
    "hanoi_huunghi": {
        "title_vi": "🚌 TUYẾN: HÀ NỘI ⇄ CỬA KHẨU QUỐC TẾ HỮU NGHỊ (45/90 NGÀY)",
        "title_ru": "🚌 МАРШРУТ: ХАНОЙ ⇄ МЕЖДУНАРОДНЫЙ КПП ХЫУ НГИ (45/90 ДНЕЙ)",
        "title_en": "🚌 ROUTE: HANOI ⇄ HUU NGHI INTERNATIONAL BORDER (45/90 DAYS)",
        "price": "1.200.000 VND (Vé VIP Limousine khứ hồi)",
        "schedule_vi": (
            "⏰ LỊCH TRÌNH CHI TIẾT (ITINERARY):\n"
            "• 08:30: Tập trung tại điểm đón (Văn phòng VIP Limousine Hà Nội).\n"
            "• 09:00: Khởi hành đi Cửa khẩu Quốc tế Hữu Nghị (Lạng Sơn - giáp Trung Quốc).\n"
            "• 12:00: Đến Cửa khẩu Hữu Nghị, nghỉ ngơi, ăn trưa nhẹ.\n"
            "• 12:30: Làm thủ tục xuất cảnh Việt Nam tại cửa khẩu Hữu Nghị, di chuyển sang khu vực vùng đệm đóng dấu/thủ tục tái nhập cảnh.\n"
            "• 14:00 - 15:00: Hoàn tất thủ tục nhập cảnh trở lại Việt Nam với tem 45 ngày miễn thị thực mới hoặc E-Visa 90 ngày.\n"
            "• 15:30: Lên xe VIP Limousine quay trở về Hà Nội.\n"
            "• 18:30 - 19:00: Về đến Hà Nội, hoàn thành chuyến đi thuận lợi."
        ),
        "schedule_ru": (
            "⏰ ДЕТАЛЬНОЕ РАСПИСАНИЕ:\n"
            "• 08:30: Сбор у офиса VIP Лимузинов в Ханое.\n"
            "• 09:00: Выезд на комфортабельном VIP Лимузине к КПП Хыу Нги.\n"
            "• 12:00: Прибытие на КПП Хыу Нги, обед и подготовка документов.\n"
            "• 12:30: Прохождение паспортного контроля на выезд из Вьетнама, переход в нейтральную зону.\n"
            "• 14:00 - 15:00: Оформление обратного въезда во Вьетнам со штампом 45 дней или 90-дневной E-Visa.\n"
            "• 15:30: Посадка в VIP Лимузин и возвращение в Ханой.\n"
            "• 18:30 - 19:00: Прибытие в Ханой, завершение поездки."
        ),
        "pickup_vi": "📍 Điểm đón: Văn phòng VIP Limousine Hà Nội (Hoặc đón tại Sân bay Nội Bài theo yêu cầu).",
        "pickup_ru": "📍 Точка сбора: Офис VIP Лимузинов в Ханое (или встреча в аэропорту Нойбай).",
        "border_vi": "⚠️ LƯU Ý TẠI CỬA KHẨU: Hộ chiếu gốc còn hạn trên 6 tháng; 02 ảnh thẻ 4x6; in sẵn bản E-Visa ra giấy (nếu đi diện 90 ngày).",
        "border_ru": "⚠️ ВАЖНО НА ГРАНИЦЕ: Загранпаспорт (от 6 мес.); 2 фото 4x6; распечатанная на бумаге E-Visa (если оформляете 90 дней).",
        "booking_vi": (
            "📝 CÁCH THỨC ĐĂNG KÝ (QUY TRÌNH 4 BƯỚC ĐƠN GIẢN):\n"
            "1️⃣ Gửi ảnh Hộ chiếu vào khung chat này để kiểm tra điều kiện xuất nhập cảnh.\n"
            "2️⃣ Bấm nút 'Kiểm tra sơ đồ chỗ & Chọn số ghế' để chọn chỗ ngồi Limousine.\n"
            "3️⃣ Bấm nút 'Phương thức thanh toán' để thanh toán vé qua VCB, VRB hoặc tiền mặt.\n"
            "4️⃣ Nhận vé xác nhận điện tử và hướng dẫn đón xe tại Hà Nội."
        ),
        "booking_ru": (
            "📝 КАК ЗАБРОНИРОВАТЬ МЕСТО (ИНСТРУКЦИЯ ИЗ 4 ШАГОВ):\n"
            "1️⃣ Отправьте фото загранпаспорта прямо в этот чат.\n"
            "2️⃣ Нажмите кнопку 'Запросить проверку мест и выбрать место' ниже.\n"
            "3️⃣ Нажмите кнопку 'Способы оплаты' для перевода (VCB, VRB) или наличными.\n"
            "4️⃣ Получите подтверждение бронирования и адрес посадки в Ханое."
        ),
        "booking_en": (
            "📝 HOW TO REGISTER (SIMPLE 4-STEP BOOKING):\n"
            "1️⃣ Send passport photo in this chat.\n"
            "2️⃣ Click 'Check availability & Select Seat' below.\n"
            "3️⃣ Click 'Payment Methods' to pay via VCB, VRB, or Cash.\n"
            "4️⃣ Receive your booking confirmation receipt."
        )
    },
    "cambodia_mocbai": {
        "title_vi": "🚌 TUYẾN: NHA TRANG / MŨI NÉ ⇄ MỘC BÀI (CAMPUCHIA) (30/45/90 NGÀY)",
        "title_ru": "🚌 МАРШРУТ: НЯЧАНГ / МУЙНЕ ⇄ МОКБАЙ (КАМБОДЖА) (30/45/90 ДНЕЙ)",
        "title_en": "🚌 ROUTE: NHA TRANG / MUI NE ⇄ MOC BAI (CAMBODIA)",
        "price": "1.400.000 VND (Vé xe khứ hồi) | 4.000.000 VND (Combo E-visa 90 ngày)",
        "schedule_vi": (
            "⏰ LỊCH TRÌNH CHI TIẾT (ITINERARY):\n"
            "• Nha Trang: 21:00 đón tại DUY NHẤT 40 Hòn Chồng = Oceanus (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) (Thứ 3, T5, CN).\n"
            "• Mũi Né: 01:00 – 02:00 sáng đón tại 04 Trần Phú hoặc dọc đường Nguyễn Đình Chiểu / Huỳnh Thúc Kháng (https://maps.app.goo.gl/vysXaB9b4BeauGgV9).\n"
            "• 06:30: Đến Cửa khẩu Mộc Bài. 07:30 cửa khẩu mở cửa, xếp hàng làm thủ tục xuất cảnh Việt Nam.\n"
            "• 08:00: Sang Campuchia làm visa Campuchia (khoảng $35 - $50).\n"
            "• 08:30 - 11:30: Nghỉ ngơi tại cafe khu vực cửa khẩu trong khi nhận E-Visa.\n"
            "• 11:30: Nhận E-Visa in giấy tại tiệm photo cửa khẩu, xếp hàng nhập cảnh lại Việt Nam.\n"
            "• 13:00: Lên xe buýt quay trở về Mũi Né / Nha Trang."
        ),
        "schedule_ru": (
            "⏰ ДЕТАЛЬНОЕ РАСПИСАНИЕ:\n"
            "• Нячанг: Сбор в 21:00 ТОЛЬКО на 40 Hon Chong = Oceanus (Вт, Чт, Вс).\n"
            "• Муйне: Посадка 01:00 – 02:00 ночи на 04 Tran Phu или вдоль Nguyen Dinh Chieu / Huynh Thuc Khang.\n"
            "• 06:30: Прибытие на КПП Мокбай. 07:30 открытие границы, выезд из Вьетнама.\n"
            "• 08:00: Оформление камбоджийской визы (ок. $35 - $50).\n"
            "• 08:30 - 11:30: Ожидание E-Visa в комфортном кафе нейтральной зоны.\n"
            "• 11:30: Получение распечатанной визы в пункте печати на границе, прохождение въезда во Вьетнам.\n"
            "• 13:00: Посадка в автобус и возвращение в Муйне / Нячанг."
        ),
        "pickup_vi": "📍 Điểm đón: Nha Trang đón duy nhất 40 Hòn Chồng = Oceanus. Mũi Né đón 04 Trần Phú hoặc dọc Nguyễn Đình Chiểu / Huỳnh Thúc Kháng.",
        "pickup_ru": "📍 Точка сбора: Нячанг — только 40 Hon Chong = Oceanus. Муйне — 04 Tran Phu или по ул. Nguyen Dinh Chieu.",
        "border_vi": "⚠️ LƯU Ý TẠI CỬA KHẨU: Tiền mặt USD làm visa Campuchia; BẮT BUỘC in E-Visa ra giấy để cán bộ hải quan Mộc Bài đóng dấu.",
        "border_ru": "⚠️ ВАЖНО НА ГРАНИЦЕ: Наличные USD на камбоджийскую визу; ОБЯЗАТЕЛЬНО распечатать E-Visa на бумаге для пограничников Мокбай.",
        "booking_vi": (
            "📝 CÁCH THỨC ĐĂNG KÝ (QUY TRÌNH 4 BƯỚC ĐƠN GIẢN):\n"
            "1️⃣ Gửi ảnh Hộ chiếu + ảnh thẻ 4x6 (nền trắng) vào khung chat (để làm E-Visa nếu chọn gói 90 ngày).\n"
            "2️⃣ Bấm nút 'Kiểm tra sơ đồ chỗ & Chọn số ghế' bên dưới để chọn ghế giường nằm.\n"
            "3️⃣ Bấm nút 'Phương thức thanh toán' để thanh toán vé qua Vietcombank, VRB hoặc tiền mặt tại văn phòng Nha Trang.\n"
            "4️⃣ Nhận vé điện tử xác nhận đặt chỗ. Biển số xe & số liên hệ tài xế sẽ được gửi trước giờ chạy 2 tiếng."
        ),
        "booking_ru": (
            "📝 КАК ЗАБРОНИРОВАТЬ МЕСТО (ИНСТРУКЦИЯ ИЗ 4 ШАГОВ):\n"
            "1️⃣ Отправьте фото загранпаспорта + фото 4x6 (для визы) прямо в этот чат.\n"
            "2️⃣ Нажмите кнопку 'Запросить проверку мест и выбрать место' ниже, чтобы выбрать спальное место.\n"
            "3️⃣ Нажмите кнопку 'Способы оплаты' для перевода (Vietcombank, VRB) или оплаты наличными в офисе Нячанга.\n"
            "4️⃣ Получите официальный электронный посадочный талон. Контакты водителя высылаются за 2 часа до отправления."
        ),
        "booking_en": (
            "📝 HOW TO REGISTER (SIMPLE 4-STEP BOOKING):\n"
            "1️⃣ Send a clear photo of your passport page + 4x6 photo in this chat.\n"
            "2️⃣ Click 'Check availability & Select Seat' below to select your desired sleeper bed.\n"
            "3️⃣ Click 'Payment Methods' to pay via Vietcombank, VRB Bank, or Cash at our Nha Trang office.\n"
            "4️⃣ Receive your booking confirmation receipt. Bus info will be sent 2 hours before departure."
        )
    }
}

def get_itinerary_message(route_key: str, lang: str = "ru") -> str:
    itin = ITINERARIES.get(route_key, ITINERARIES.get("laos_boy_45d", ITINERARIES["laos_boy"]))
    title = itin.get(f"title_{lang}", itin["title_en"])
    sched = itin.get(f"schedule_{lang}", itin["schedule_vi"])
    pickup = itin.get(f"pickup_{lang}", itin["pickup_vi"])
    border = itin.get(f"border_{lang}", itin["border_vi"])
    booking = itin.get(f"booking_{lang}", itin.get("booking_vi", ""))
    
    booking_section = f"\n\n{booking}" if booking else ""
    
    if lang == "ru":
        return (
            f"📋 **{title}**\n"
            f"💰 **Стоимость:** {itin['price']}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sched}\n\n"
            f"{pickup}\n\n"
            f"{border}"
            f"{booking_section}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 **СЛЕДУЮЩИЙ ШАГ:**\n"
            "Пожалуйста, нажмите кнопку ниже, чтобы проверить свободные места, выбрать место в автобусе и отправить фото паспорта для бронирования!"
        )
    elif lang == "vi":
        return (
            f"📋 **{title}**\n"
            f"💰 **Chi phí:** {itin['price']}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sched}\n\n"
            f"{pickup}\n\n"
            f"{border}"
            f"{booking_section}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 **BƯỚC TIẾP THEO:**\n"
            "Vui lòng bấm nút bên dưới để kiểm tra sơ đồ chỗ trống, chọn số ghế trên xe và gửi ảnh Hộ chiếu để chúng tôi giữ chỗ cho bạn!"
        )
    else:
        return (
            f"📋 **{title}**\n"
            f"💰 **Price:** {itin['price']}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sched}\n\n"
            f"{pickup}\n\n"
            f"{border}"
            f"{booking_section}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 **NEXT STEP:**\n"
            "Please click the button below to check seat availability, select your preferred seat, and send your passport photo to reserve!"
        )

# ============================================================
# MẪU THÔNG TIN THANH TOÁN & BOOKING FINAL & CHÍNH SÁCH HUỶ - HOÀN
# ============================================================

def get_payment_methods_keyboard(lang: str = "ru"):
    """Bàn phím chọn 2 ngân hàng VCB và VRB hoặc tiền mặt tại VP Nha Trang"""
    vcb_lbl = "🏦 Vietcombank (VCB)"
    vrb_lbl = "🏦 VRB Bank (Việt - Nga)"
    cash_lbl = "🏢 " + ("Оплата наличными (Офис Нячанг)" if lang == "ru" else "Tiền mặt tại VP Nha Trang" if lang == "vi" else "Cash at Nha Trang Office")
    back_lbl = "🔙 " + ("Назад к услугам" if lang == "ru" else "Quay lại danh sách dịch vụ" if lang == "vi" else "Back to Services")
    mgr_lbl = "💬 " + ("Менеджер" if lang == "ru" else "Hỗ trợ" if lang == "vi" else "Support")
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(vcb_lbl, callback_data="step|pay|vcb"),
            InlineKeyboardButton(vrb_lbl, callback_data="step|pay|vrb")
        ],
        [
            InlineKeyboardButton(cash_lbl, callback_data="step|pay|cash")
        ],
        [
            InlineKeyboardButton(back_lbl, callback_data="step|back|services"),
            InlineKeyboardButton(mgr_lbl, url="https://t.me/easytripvisa_co_ltd")
        ]
    ])

def get_payment_detail_keyboard(lang: str = "ru"):
    """Bàn phím sau khi xem chi tiết phương thức thanh toán"""
    other_pay_lbl = "🔄 " + ("Выбрать другой банк / способ" if lang == "ru" else "Chọn ngân hàng / phương thức khác" if lang == "vi" else "Other payment method")
    back_svc_lbl = "🔙 " + ("Назад к услугам" if lang == "ru" else "Quay lại dịch vụ" if lang == "vi" else "Back to Services")
    chat_lbl = "💬 " + ("Менеджер" if lang == "ru" else "Chat với nhân viên" if lang == "vi" else "Support Manager")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(other_pay_lbl, callback_data="step|pay_menu")],
        [
            InlineKeyboardButton(back_svc_lbl, callback_data="step|back|services"),
            InlineKeyboardButton(chat_lbl, url="https://t.me/easytripvisa_co_ltd")
        ]
    ])

def get_payment_detail_message(method: str, lang: str = "ru") -> str:
    """Mô tả chi tiết cách thức chuyển khoản qua VCB, VRB hoặc Tiền mặt tại VP"""
    if method == "vcb":
        if lang == "ru":
            return (
                "💳 **ИНСТРУКЦИЯ ПО ОПЛАТЕ: VIETCOMBANK (VCB)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 **Банк:** Joint Stock Commercial Bank for Foreign Trade of Viet Nam (Vietcombank)\n"
                "👤 **Получатель (Beneficiary):** EASY TRIP & VISA CO. LTD\n"
                "🔢 **Номер счета (Account Number):** `1068582577`\n"
                "🌐 **SWIFT-код:** `BFTVVNVX`\n"
                "📝 **Назначение перевода:** `[Имя Фамилия] [Год рождения]`\n"
                "*(Пример: IVANOV 1997)*\n\n"
                "📲 **Mã QR & Hướng dẫn chính thức (QR-код и подробности):**\n"
                "🏢 **Оплата наличными в офисе:**\n"
                "📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Карты: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Горячая линия поддержки:** +84 85 320 1277\n\n"
                "📸 **После перевода, пожалуйста, отправьте чек / квитанцию в этот чат для подтверждения!**"
            )
        elif lang == "vi":
            return (
                "💳 **HƯỚNG DẪN CHUYỂN KHOẢN: VIETCOMBANK (VCB)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 **Ngân hàng:** Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank)\n"
                "👤 **Chủ tài khoản:** CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 **Số tài khoản:** `1068582577`\n"
                "🌐 **Mã SWIFT:** `BFTVVNVX`\n"
                "📝 **Cú pháp nội dung:** `[Họ tên khách] [năm sinh]`\n"
                "*(Ví dụ: IVANOV 1997)*\n\n"
                "📲 **Mã QR & Hướng dẫn chính thức:**\n"
                "🏢 **Thanh toán tiền mặt tại văn phòng:**\n"
                "📍 Địa chỉ: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Bản đồ: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Hotline hỗ trợ:** +84 85 320 1277\n\n"
                "📸 **Quý khách vui lòng gửi ảnh chụp biên lai chuyển khoản vào đây để chúng tôi xác nhận giữ chỗ!**"
            )
        else:
            return (
                "💳 **PAYMENT INSTRUCTIONS: VIETCOMBANK (VCB)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 **Bank:** Joint Stock Commercial Bank for Foreign Trade of Viet Nam (Vietcombank)\n"
                "👤 **Beneficiary:** EASY TRIP & VISA CO. LTD\n"
                "🔢 **Account Number:** `1068582577`\n"
                "🌐 **SWIFT Code:** `BFTVVNVX`\n"
                "📝 **Transfer Memo:** `[Full Name] [Year of Birth]`\n"
                "*(Example: IVANOV 1997)*\n\n"
                "📲 **Official QR Code & Instructions:**\n"
                "🏢 **Cash Payment at Office:**\n"
                "📍 Address: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Map: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Hotline Support:** +84 85 320 1277\n\n"
                "📸 **Please send your payment screenshot / receipt in this chat after completing!**"
            )

    elif method == "vrb":
        if lang == "ru":
            return (
                "💳 **ИНСТРУКЦИЯ ПО ОПЛАТЕ: VRB (ВЬЕТНАМСКО-РОССИЙСКИЙ БАНК)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 **Банк:** Вьетнамско-Российский Совместный Банк (Vietnam - Russia Joint Venture Bank - VRB)\n"
                "📍 **Филиал:** Khánh Hòa (Нячанг)\n"
                "👤 **Получатель (Beneficiary):** CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 **Номер счета:** `1068582577` (hoặc chuyển khoản liên ngân hàng Napas 24/7 đến VRB)\n"
                "📝 **Назначение перевода:** `[Имя Фамилия] [Год рождения]`\n"
                "*(Пример: IVANOV 1997)*\n\n"
                "🌟 **Преимущества расчетов через VRB:**\n"
                "• Прямые взаиморасчеты Россия – Вьетнам (в RUB и VND)\n"
                "• Удобно для переводов картами МИР и через банки-партнеры РФ\n"
                "📲 **Mã QR & Hướng dẫn chính thức:**\n"
                "🏢 **Оплата наличными в офисе:**\n"
                "📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Карты: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Горячая линия поддержки:** +84 85 320 1277\n\n"
                "📸 **После перевода, пожалуйста, отправьте чек / квитанцию в этот чат!**"
            )
        elif lang == "vi":
            return (
                "💳 **HƯỚNG DẪN CHUYỂN KHOẢN: NGÂN HÀNG LIÊN DOANH VIỆT - NGA (VRB)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 **Ngân hàng:** Ngân hàng Liên doanh Việt - Nga (VRB)\n"
                "📍 **Chi nhánh:** Khánh Hòa\n"
                "👤 **Chủ tài khoản:** CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 **Số tài khoản:** `1068582577` (hoặc chuyển khoản liên ngân hàng Napas 24/7)\n"
                "📝 **Cú pháp nội dung:** `[Họ tên khách] [năm sinh]`\n"
                "*(Ví dụ: IVANOV 1997)*\n\n"
                "🌟 **Đặc điểm nổi bật của VRB:**\n"
                "• Cổng thanh toán song phương trực tiếp Việt Nam – LB Nga (đồng VND & RUB)\n"
                "• Thuận tiện cho kiều bào, du khách Nga sử dụng thẻ MIR và ngân hàng Nga\n"
                "📲 **Mã QR & Hướng dẫn chính thức:**\n"
                "🏢 **Thanh toán tiền mặt tại văn phòng:**\n"
                "📍 Địa chỉ: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Bản đồ: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Hotline hỗ trợ:** +84 85 320 1277\n\n"
                "📸 **Quý khách vui lòng gửi ảnh biên lai chuyển khoản vào đây để chúng tôi xác nhận giữ chỗ!**"
            )
        else:
            return (
                "💳 **PAYMENT INSTRUCTIONS: VRB (VIETNAM - RUSSIA JOINT VENTURE BANK)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 **Bank:** Vietnam - Russia Joint Venture Bank (VRB)\n"
                "📍 **Branch:** Khanh Hoa\n"
                "👤 **Beneficiary:** CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 **Account Number:** `1068582577`\n"
                "📝 **Transfer Memo:** `[Full Name] [Year of Birth]`\n"
                "*(Example: IVANOV 1997)*\n\n"
                "🌟 **VRB Highlights:**\n"
                "• Direct bilateral payment gateway between Vietnam & Russia (RUB & VND)\n"
                "• Convenient for Russian payment systems and MIR transactions\n"
                "📲 **Official QR Code & Instructions:**\n"
                "🏢 **Cash Payment at Office:**\n"
                "📍 Address: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Map: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Hotline Support:** +84 85 320 1277\n\n"
                "📸 **Please send your payment screenshot / receipt in this chat after completing!**"
            )

    else:  # 3. Tiền mặt tại văn phòng ở Nha Trang (step|pay|cash)
        if lang == "ru":
            return (
                "🏢 **ОПЛАТА НАЛИЧНЫМИ В ОФИСЕ (НЯЧАНГ)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📍 **Адрес:** 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "⏰ **Время работы:** 08:30 – 17:30 (Понедельник – Суббота)\n"
                "🗺️ **Карты Google Maps:** https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Горячая линия поддержки:** +84 85 320 1277\n\n"
                "💡 Вы можете подойти в наш офис для оплаты наличными (VND / USD) и личной консультации с нашими сотрудниками!"
            )
        elif lang == "vi":
            return (
                "🏢 **THANH TOÁN TIỀN MẶT TẠI VĂN PHÒNG (NHA TRANG)**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📍 **Địa chỉ:** 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "⏰ **Thời gian làm việc:** 08:30 – 17:30 (Thứ 2 đến Thứ 7)\n"
                "🗺️ **Bản đồ Google Maps:** https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Hotline hỗ trợ:** +84 85 320 1277\n\n"
                "💡 Quý khách có thể đến trực tiếp văn phòng để đóng tiền mặt và nhận hướng dẫn chi tiết từ chuyên viên phụ trách!"
            )
        else:
            return (
                "🏢 **CASH PAYMENT AT NHA TRANG OFFICE**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📍 **Address:** 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "⏰ **Working Hours:** 08:30 AM – 05:30 PM (Monday – Saturday)\n"
                "🗺️ **Google Maps:** https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 **Hotline Support:** +84 85 320 1277\n\n"
                "💡 You are welcome to visit our office in person to pay in cash (VND / USD) and meet our specialists!"
            )

def get_payment_instruction_text(lang: str = "ru") -> str:
    if lang == "ru":
        return (
            "💳 **ОФИЦИАЛЬНЫЕ СПОСОБЫ ОПЛАТЫ (EASY TRIP & VISA)**\n"
            "🏦 **1. Vietcombank (VCB):** `1068582577` (EASY TRIP & VISA CO. LTD)\n"
            "   📝 Назначение: `[Имя Фамилия] [Год рождения]` (Пример: IVANOV 1997)\n"
            "🏦 **2. VRB Bank (Вьетнамско-Российский банк):** `1068582577`\n"
            "   📝 Назначение: `[Имя Фамилия] [Год рождения]` (Пример: IVANOV 1997)\n"
            "🏢 **3. Оплата наличными в офисе:**\n"
            "   📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
            "   🗺️ Карты: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
            "   📞 Горячая линия: +84 85 320 1277\n\n"
            "📸 После оплаты отправьте квитанцию / чек об оплате в этот чат!"
        )
    elif lang == "vi":
        return (
            "💳 **THÔNG TIN THANH TOÁN CHÍNH THỨC (EASY TRIP & VISA)**\n"
            "🏦 **1. Vietcombank (VCB):** `1068582577` (CONG TY TNHH EASY TRIP & VISA)\n"
            "   📝 Cú pháp nội dung: `[Họ tên khách] [năm sinh]` (Ví dụ: IVANOV 1997)\n"
            "🏦 **2. Ngân hàng Liên doanh Việt - Nga (VRB):** `1068582577`\n"
            "   📝 Cú pháp nội dung: `[Họ tên khách] [năm sinh]` (Ví dụ: IVANOV 1997)\n"
            "🏢 **3. Thanh toán tiền mặt tại văn phòng:**\n"
            "   📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
            "   🗺️ Bản đồ: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
            "   📞 Hotline hỗ trợ: +84 85 320 1277\n\n"
            "📸 Quý khách vui lòng gửi ảnh chụp biên lai chuyển khoản vào đây sau khi thanh toán!"
        )
    else:
        return (
            "💳 **OFFICIAL PAYMENT DETAILS (EASY TRIP & VISA)**\n"
            "🏦 **1. Vietcombank (VCB):** `1068582577` (EASY TRIP & VISA CO. LTD)\n"
            "   📝 Memo: `[Full Name] [Year of Birth]` (Example: IVANOV 1997)\n"
            "🏦 **2. VRB Bank (Vietnam - Russia Bank):** `1068582577`\n"
            "   📝 Memo: `[Full Name] [Year of Birth]` (Example: IVANOV 1997)\n"
            "🏢 **3. Cash at Office:**\n"
            "   📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
            "   🗺️ Map: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
            "   📞 Hotline: +84 85 320 1277\n\n"
            "📸 Please send your payment receipt / screenshot in this chat once completed!"
        )

def generate_booking_final_message(data: Any, lang: str = "ru") -> str:
    ho_ten = getattr(data, "ho_ten", "") or "Customer"
    quoc_tich = getattr(data, "quoc_tich", "") or "Unknown"
    loai_visa = getattr(data, "loai_visa", "") or "Visa Run Service"
    ngay_kh = getattr(data, "ngay_khoi_hanh", "") or "TBD"
    ghe_chon = getattr(data, "ghe_chon", "") or "Confirmed"
    diem_don = getattr(data, "diem_don", "") or "Oceanus Nha Trang (40 Hòn Chồng)"
    
    if lang == "ru":
        return (
            "🎉 **БРОНИРОВАНИЕ ПОДТВЕРЖДЕНО! (EASY TRIP & VISA)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Пассажир:** {ho_ten}\n"
            f"🛂 **Гражданство:** {quoc_tich}\n"
            f"🚌 **Маршрут:** {loai_visa}\n"
            f"📅 **Дата выезда:** {ngay_kh}\n"
            "⏰ **Время посадки:** 21:00 (Выезд: 21:15 – 21:30)\n"
            f"📍 **Точка сбора:** {diem_don}\n"
            f"💺 **Место в автобусе:** {ghe_chon}\n"
            "💰 **Статус оплаты:** ОПЛАЧЕНО ✅\n\n"
            "ℹ️ **Номер автобуса и контакт водителя будут отправлены вам за 2 часа до отправления.**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 **ПРАВИЛА ОТМЕНЫ И ВОЗВРАТА СРЕДСТВ:**\n"
            "1. **Билеты на автобус:** Отмена или перенос даты ДО 14:00 в день поездки — 100% возврат или бесплатный перенос. Отмена ПОСЛЕ 14:00 или неявка (No-show) — возврат не производится.\n"
            "2. **Оформление визы (E-Visa):** После подачи документов на официальный портал Иммиграционной службы и оплаты госпошлины — сбор возврату НЕ ПОДЛЕЖИТ. В случае технической ошибки с нашей стороны — 100% возврат.\n"
            "3. **Правила безопасности:** Курение (включая вейп), провоз алкоголя и запрещенных веществ строго запрещены. Нарушители высаживаются без компенсации.\n\n"
            "📞 Горячая линия поддержки 24/7: +84 85 320 1277\n"
            "Желаем вам приятного и легкого путешествия! 🚌✨"
        )
    elif lang == "vi":
        return (
            "🎉 **XÁC NHẬN ĐẶT CHỖ THÀNH CÔNG! (EASY TRIP & VISA)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Hành khách:** {ho_ten}\n"
            f"🛂 **Quốc tịch:** {quoc_tich}\n"
            f"🚌 **Tuyến đi:** {loai_visa}\n"
            f"📅 **Ngày khởi hành:** {ngay_kh}\n"
            "⏰ **Giờ tập trung:** 21:00 (Khởi hành: 21:15 – 21:30)\n"
            f"📍 **Điểm đón:** {diem_don}\n"
            f"💺 **Số ghế:** {ghe_chon}\n"
            "💰 **Thanh toán:** ĐÃ HOÀN TẤT ✅\n\n"
            "ℹ️ **Biển số xe buýt và số điện thoại tài xế sẽ được gửi đến quý khách trước giờ khởi hành 2 tiếng.**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 **CHÍNH SÁCH HUỶ VÉ & HOÀN TIỀN:**\n"
            "1. **Vé xe buýt:** Hủy hoặc đổi lịch TRƯỚC 14:00 ngày khởi hành — hoàn 100% hoặc đổi ngày miễn phí. Hủy SAU 14:00 hoặc không có mặt (No-show) — không hoàn tiền vé xe.\n"
            "2. **Dịch vụ Visa / E-Visa:** Một khi hồ sơ đã nộp lên Cổng Dịch vụ công Xuất Nhập Cảnh và đóng phí — phí visa không được hoàn lại. Lỗi tính toán từ phía công ty — hoàn tiền 100%.\n"
            "3. **An toàn trên xe:** Nghiêm cấm hút thuốc/vape, mang chất cấm hoặc gây rối. Vi phạm sẽ bị mời xuống xe tại điểm an toàn gần nhất và không hoàn tiền.\n\n"
            "📞 Hotline hỗ trợ 24/7: +84 85 320 1277\n"
            "Chúc quý khách có một chuyến đi an toàn và thuận lợi! 🚌✨"
        )
    else:
        return (
            "🎉 **BOOKING CONFIRMED! (EASY TRIP & VISA)**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Passenger:** {ho_ten}\n"
            f"🛂 **Nationality:** {quoc_tich}\n"
            f"🚌 **Route:** {loai_visa}\n"
            f"📅 **Departure Date:** {ngay_kh}\n"
            "⏰ **Boarding Time:** 21:00 (Departure: 21:15 – 21:30)\n"
            f"📍 **Pickup Location:** {diem_don}\n"
            f"💺 **Seat Number:** {ghe_chon}\n"
            "💰 **Payment Status:** PAID ✅\n\n"
            "ℹ️ **Bus license plate and driver's phone number will be sent to you 2 hours before departure.**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 **CANCELLATION & REFUND POLICY:**\n"
            "1. **Bus Transportation:** Cancellation or rescheduling BEFORE 14:00 on the departure day — 100% refund or free date change. Cancellation AFTER 14:00 or No-show — non-refundable.\n"
            "2. **Visa / E-Visa Service:** Once submitted to the Immigration Portal and government fees are paid — visa fees are non-refundable. Company operational error — 100% refund.\n"
            "3. **Bus Safety:** Smoking/vaping and prohibited substances are strictly banned. Violators will be dismissed without refund.\n\n"
            "📞 24/7 Hotline Support: +84 85 320 1277\n"
            "We wish you a pleasant and smooth journey! 🚌✨"
        )

# ============================================================
# BỘ XỬ LÝ SỰ KIỆN CALLBACK TỪ NÚT BẤM (STEP HANDLER)
# ============================================================

async def handle_step_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, parts: list[str], process_customer_text_message_fn):
    """Xử lý từng bước trong Wizard Onboarding Bot (Hỗ trợ cả CallbackQuery và Text Message từ Web)"""
    query = update.callback_query
    if not update.effective_user and not update.effective_chat:
        return
    if query:
        try:
            await query.answer()
        except Exception:
            pass
    
    step_type = parts[1]
    user_id = str(update.effective_user.id)
    session_id = f"telegram_{user_id}"
    
    if session_id not in memory_store:
        memory_store[session_id] = []
        
    cust_data = memory_store.get(f"{session_id}_data")
    if not cust_data or not isinstance(cust_data, CustomerData):
        cust_data = CustomerData()
        memory_store[f"{session_id}_data"] = cust_data
        
    if step_type == "ignore":
        return

    # 🟢 BƯỚC 1 -> BƯỚC 2: Chọn Quốc Gia
    if step_type == "nat":
        val = parts[2]
        if val == "other":
            memory_store[f"{session_id}_waiting_country"] = True
            prompt = (
                "🌐 **Пожалуйста, напишите название вашей страны** в чате.\n"
                "Наш бот и менеджер мгновенно подберут для вас оптимальный визовый маршрут!\n\n"
                "🌐 **Please type your country name** in the chat.\n"
                "🌐 **Vui lòng nhập tên quốc gia của bạn** vào khung chat:"
            )
            await send_step_reply(update, context, prompt, parse_mode="Markdown")
            return
            
        nat_map = {
            "ru": ("Russian (Россия)", "ru"),
            "ko": ("South Korea (대한민국)", "ko"),
            "zh": ("China (中国)", "zh"),
            "en": ("United States / Europe", "en"),
            "cis": ("Kazakhstan / Kyrgyzstan / CIS", "ru"),
            "vi": ("Việt Nam", "vi")
        }
        cname, lang = nat_map.get(val, ("Other Country", "en"))
        cust_data.quoc_tich = cname
        memory_store[f"{session_id}_lang"] = lang
        
        # Nếu đã có sẵn thành phố từ Web Lead (VD: Khách chọn Mũi Né từ web) -> Tự động chuyển ngay sang Lịch Quốc Tế
        if cust_data.thanh_pho and cust_data.thanh_pho in CITY_OPTIONS and cust_data.thanh_pho != "other":
            now = datetime.now()
            c_name_disp = CITY_OPTIONS[cust_data.thanh_pho].get(f"name_{lang}", cust_data.thanh_pho.upper())
            cal_prompts = {
                "ru": f"✅ Гражданство: **{cname}**\n📍 Город отправления: **{c_name_disp}**\n\n📅 **Выберите дату выезда в календаре**:",
                "en": f"✅ Nationality: **{cname}**\n📍 Departure City: **{c_name_disp}**\n\n📅 **Please pick a departure date on the calendar**:",
                "vi": f"✅ Quốc tịch: **{cname}**\n📍 Thành phố xuất phát: **{c_name_disp}**\n\n📅 **Vui lòng chọn ngày khởi hành trên lịch**:"
            }
            keyboard = get_calendar_keyboard(now.year, now.month, lang)
            await send_step_reply(update, context, cal_prompts.get(lang, cal_prompts["en"]), reply_markup=keyboard)
            return

        city_prompts = {
            "ru": f"✅ Гражданство: **{cname}**\n\n📍 **В каком городе Вьетнама вы сейчас находитесь?**\n(Или выберите 'За рубежом', если только планируете въезд):",
            "en": f"✅ Nationality: **{cname}**\n\n📍 **Which city in Vietnam are you currently staying in?**\n(Or select 'Currently Abroad' if you are planning to enter):",
            "vi": f"✅ Quốc gia: **{cname}**\n\n📍 **Bạn hiện đang ở thành phố nào tại Việt Nam?**\n(Hoặc chọn 'Đang ở nước ngoài' nếu sắp bay vào VN):",
            "ko": f"✅ 국적: **{cname}**\n\n📍 **현재 베트남 어느 도시에 머물고 계신가요?**:"
        }
        keyboard = get_city_keyboard(lang)
        await send_step_reply(update, context, city_prompts.get(lang, city_prompts["en"]), reply_markup=keyboard)
        return

    # 🟢 BƯỚC 2 -> BƯỚC 3: Chọn Thành Phố / Vị trí
    elif step_type == "city":
        city_key = parts[2]
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        if city_key == "other":
            memory_store[f"{session_id}_waiting_other_city"] = True
            msg = {
                "ru": "📍 **Пожалуйста, напишите ваш город или текущий адрес** в чате.\nНаш бот и команда подберут для вас ближайший пункт отправления и оптимальный трансфер!",
                "en": "📍 **Please type your city or address** in the chat.\nWe will calculate and suggest the nearest bus pickup location for you!",
                "vi": "📍 **Vui lòng nhập tên thành phố hoặc vị trí hiện tại của bạn** vào khung chat.\nChúng tôi sẽ tính toán tuyến xe buýt hoặc phương án đón gần bạn nhất!"
            }
            await send_step_reply(update, context, msg.get(lang, msg["en"]), parse_mode="Markdown")
            return
            
        cust_data.thanh_pho = city_key
        city_obj = CITY_OPTIONS.get(city_key, {})
        cname = city_obj.get(f"name_{lang}", city_key.title())
        
        # Nếu khách đang ở nước ngoài -> Chuyển sang tư vấn dịch vụ nhập cảnh
        if city_key == "abroad":
            svc_prompts = {
                "ru": "✈️ **УСЛУГИ ДЛЯ ВЪЕЗДА ВО ВЬЕТНАМ (EASY TRIP & VISA):**\n(Выберите необходимый сервис):",
                "en": "✈️ **SERVICES FOR ENTERING VIETNAM (EASY TRIP & VISA):**\n(Please select a service):",
                "vi": "✈️ **DỊCH VỤ NHẬP CẢNH VIỆT NAM (EASY TRIP & VISA):**\n(Vui lòng chọn dịch vụ bạn cần):"
            }
            kb = get_smart_advisory_keyboard("abroad", cust_data.quoc_tich or "", lang)
            await send_step_reply(update, context, svc_prompts.get(lang, svc_prompts["en"]), reply_markup=kb, parse_mode="Markdown")
            return
            
        # Ở trong nước -> Mở Lịch tháng tương tác chuẩn quốc tế
        now = datetime.now()
        cal_prompts = {
            "ru": f"✅ Вы выбрали: **{cname}**\n\n📅 **Выберите дату в календаре** (когда заканчивается ваша текущая виза или желаемая дата выезда):",
            "en": f"✅ Selected: **{cname}**\n\n📅 **Please pick a date on the calendar** (your visa expiry date or desired departure date):",
            "vi": f"✅ Điểm khởi hành: **{cname}**\n\n📅 **Vui lòng chọn ngày trên lịch** (ngày hết hạn visa hoặc ngày bạn muốn đi):"
        }
        keyboard = get_calendar_keyboard(now.year, now.month, lang)
        await send_step_reply(update, context, cal_prompts.get(lang, cal_prompts["en"]), reply_markup=keyboard, parse_mode="Markdown")
        return

    # 🟢 ĐIỀU HƯỚNG LỊCH THÁNG
    elif step_type == "cal_nav":
        nav_y = int(parts[2])
        nav_m = int(parts[3])
        lang = memory_store.get(f"{session_id}_lang", "en")
        keyboard = get_calendar_keyboard(nav_y, nav_m, lang)
        if query and query.message:
            try:
                await query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        return

    # 🟢 BƯỚC 3 -> BƯỚC 4: Chọn Ngày -> MỞ BỘ TƯ VẤN THÔNG MINH
    elif step_type == "date":
        date_val = parts[2]
        lang = memory_store.get(f"{session_id}_lang", "en")
        cust_data.ngay_het_han_visa = date_val
        cust_data.ngay_khoi_hanh = date_val
        
        city_key = cust_data.thanh_pho or "nhatrang"
        cname = cust_data.quoc_tich or "Unknown"
        exempt = is_country_exempt(cname)
        
        advisory_header = {
            "ru": (
                f"📊 **РЕЗУЛЬТАТ АНАЛИЗА ДАННЫХ ДЛЯ ВИЗАРАНА:**\n"
                f"• Гражданство: **{cname}** ({'Безвизовый въезд 45 дней ✅' if exempt else 'Требуется E-Visa 90 дней 📑'})\n"
                f"• Город отправления: **{city_key.upper()}**\n"
                f"• Дата выезда / окончания визы: **{date_val}**\n\n"
                "👉 **РЕКОМЕНДОВАННЫЕ ВАРИАНТЫ УСЛУГ (Выберите подходящий пакет):**"
            ),
            "en": (
                f"📊 **VISA RUN ADVISORY SUMMARY:**\n"
                f"• Nationality: **{cname}** ({'45-Day Visa-Free Eligible ✅' if exempt else '90-Day E-Visa Required 📑'})\n"
                f"• Departure City: **{city_key.upper()}**\n"
                f"• Expiry / Departure Date: **{date_val}**\n\n"
                "👉 **RECOMMENDED PACKAGES (Please choose an option):**"
            ),
            "vi": (
                f"📊 **KẾT QUẢ PHÂN TÍCH TƯ VẤN VISARUN:**\n"
                f"• Quốc tịch: **{cname}** ({'Được Miễn thị thực 45 ngày ✅' if exempt else 'Cần đăng ký E-Visa 90 ngày 📑'})\n"
                f"• Thành phố xuất phát: **{city_key.upper()}**\n"
                f"• Ngày hết hạn / khởi hành: **{date_val}**\n\n"
                "👉 **CÁC GÓI DỊCH VỤ PHÙ HỢP NHẤT (Vui lòng chọn gói):**"
            )
        }
        keyboard = get_smart_advisory_keyboard(city_key, cname, lang)
        await send_step_reply(update, context, advisory_header.get(lang, advisory_header["en"]), reply_markup=keyboard, parse_mode="Markdown")
        return

    # 🟢 BƯỚC 4: Khách chọn gói dịch vụ -> TRẢ VỀ BẢN TƯ VẤN LỊCH TRÌNH & LƯU Ý
    elif step_type == "svc":
        svc_id = parts[2]
        lang = memory_store.get(f"{session_id}_lang", "en")
        city_key = cust_data.thanh_pho or "nhatrang"
        
        # 1. Xử lý trường hợp dịch vụ khẩn cấp Urgent E-Visa
        if "urgent" in svc_id:
            cust_data.loai_visa = "Urgent E-Visa"
            urgent_msg = {
                "ru": (
                    "⚡ **СРОЧНОЕ ОФОРМЛЕНИЕ E-VISA ВО ВЬЕТНАМ (URGENT E-VISA)**\n\n"
                    "Easy Trip Visa гарантирует получение визы точно в срок:\n"
                    "• 🚀 **Супер-срочно:** 1–2 часа\n"
                    "• ⏱️ **В течение дня:** 4 часа\n"
                    "• 📅 **Ускоренно:** 1–2 рабочих дня\n\n"
                    "📋 **Для оформления отправьте прямо в этот чат:**\n"
                    "1. Четкое фото страницы загранпаспорта (без бликов, видны 4 угла)\n"
                    "2. Фото как на паспорт (4x6 см на белом фоне)\n"
                    "3. Название пункта въезда (аэропорт или наземный КПП)\n"
                    "4. Точную дату въезда во Вьетнам\n\n"
                    "💳 Способы оплаты: Нажмите кнопку ниже для реквизитов (VCB, VRB, офис)."
                ),
                "vi": (
                    "⚡ **DỊCH VỤ E-VISA CẤP TỐC / KHẨN CẤP (URGENT E-VISA)**\n\n"
                    "Easy Trip Visa cam kết ra visa đúng hẹn, an toàn 100%:\n"
                    "• 🚀 **Siêu tốc:** 1–2 giờ\n"
                    "• ⏱️ **Trong ngày:** 4 giờ\n"
                    "• 📅 **Khẩn thường:** 1–2 ngày làm việc\n\n"
                    "📋 **Hồ sơ gửi ngay vào khung chat:**\n"
                    "1. Ảnh chụp trang thông tin Hộ chiếu (rõ nét, đủ 4 góc)\n"
                    "2. Ảnh thẻ 4x6 (nền trắng, chụp thẳng rõ mặt)\n"
                    "3. Cửa khẩu nhập cảnh (Sân bay hoặc cửa khẩu đường bộ)\n"
                    "4. Ngày dự kiến nhập cảnh\n\n"
                    "💳 Thông tin thanh toán: Bấm nút bên dưới để chọn hình thức chuyển khoản (VCB, VRB, VP)."
                ),
                "en": (
                    "⚡ **VIETNAM URGENT E-VISA SERVICE**\n\n"
                    "Easy Trip Visa provides guaranteed on-time processing:\n"
                    "• 🚀 **Super Urgent:** 1–2 hours\n"
                    "• ⏱️ **Same Day:** 4 hours\n"
                    "• 📅 **Expedited:** 1–2 business days\n\n"
                    "📋 **Please send in this chat:**\n"
                    "1. Clear photo of passport info page (all 4 corners visible)\n"
                    "2. Passport-style 4x6 portrait photo (white background)\n"
                    "3. Entry port (Airport or Land Border)\n"
                    "4. Expected date of entry\n\n"
                    "💳 Payment details: Click the Payment button below for VCB, VRB, or cash."
                )
            }
            kb_urgent = InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 " + ("Отправить фото паспорта" if lang == "ru" else "Gửi ảnh Hộ chiếu" if lang == "vi" else "Send Passport Photo"), callback_data="step|request_seats")],
                [InlineKeyboardButton("💳 " + ("Способы оплаты (VCB, VRB, Офис)" if lang == "ru" else "Phương thức thanh toán (VCB, VRB, VP)" if lang == "vi" else "Payment Methods (VCB, VRB, Office)"), callback_data="step|pay_menu")],
                [InlineKeyboardButton("💬 " + ("Менеджер поддержки" if lang == "ru" else "Chat với nhân viên hỗ trợ" if lang == "vi" else "Support Manager"), url="https://t.me/easytripvisa_co_ltd")]
            ])
            await send_step_reply(update, context, urgent_msg.get(lang, urgent_msg["en"]), reply_markup=kb_urgent, parse_mode="Markdown")
            return
            
        # 2. Xử lý trường hợp VIP Fast Track sân bay
        elif "fasttrack" in svc_id or "fast_track" in svc_id:
            cust_data.loai_visa = "Airport VIP Fast Track"
            fasttrack_msg = {
                "ru": (
                    "✈️ **AIRPORT VIP FAST TRACK (ВСТРЕЧА И ПРОХОД БЕЗ ОЧЕРЕДЕЙ)**\n\n"
                    "💰 Стоимость: **1.200.000 VND / человек**\n"
                    "📍 Доступно в аэропортах: Cam Ranh (CXR), Tân Sơn Nhất (SGN), Nội Bài (HAN), Đà Nẵng (DAD)\n\n"
                    "🌟 **Привилегии сервиса:**\n"
                    "• Персональный ассистент встречает вас у выхода из самолета с именной табличкой\n"
                    "• Проход паспортного контроля через дипломатический коридор (без ожидания в общей очереди)\n"
                    "• Помощь с получением багажа и сопровождение до выхода\n\n"
                    "📋 **Для бронирования отправьте в этот чат:**\n"
                    "1. Номер рейса и дату/время прилета\n"
                    "2. Фамилию и имя на латинице (как в паспорте)\n"
                    "3. Название аэропорта прилета"
                ),
                "vi": (
                    "✈️ **DỊCH VỤ AIRPORT VIP FAST TRACK (ĐÓN TẠI CỬA MÁY BAY)**\n\n"
                    "💰 Chi phí: **1.200.000 ₫ / khách**\n"
                    "📍 Áp dụng tại sân bay: Cam Ranh (CXR), Tân Sơn Nhất (SGN), Nội Bài (HAN), Đà Nẵng (DAD)\n\n"
                    "🌟 **Quyền lợi dịch vụ:**\n"
                    "• Nhân viên đón khách ngay tại cửa ra máy bay với bảng tên riêng\n"
                    "• Dẫn khách qua làn ưu tiên Ngoại Giao / Fast Track không phải xếp hàng chờ đợi\n"
                    "• Hỗ trợ nhận hành lý và dẫn ra xe riêng\n\n"
                    "📋 **Thông tin cần gửi vào chat:**\n"
                    "1. Số hiệu chuyến bay và ngày giờ hạ cánh\n"
                    "2. Họ tên trên hộ chiếu\n"
                    "3. Sân bay đến"
                ),
                "en": (
                    "✈️ **AIRPORT VIP FAST TRACK SERVICE**\n\n"
                    "💰 Price: **1,200,000 VND / pax**\n"
                    "📍 Available at: Cam Ranh (CXR), Tan Son Nhat (SGN), Noi Bai (HAN), Da Nang (DAD)\n\n"
                    "🌟 **VIP Benefits:**\n"
                    "• Personal assistant meets you at the arrival gate with your name board\n"
                    "• Fast-track escort through Diplomatic / Priority lane (skip all queues)\n"
                    "• Baggage collection assistance and escort to exit or driver\n\n"
                    "📋 **Please send in this chat:**\n"
                    "1. Flight number & arrival date/time\n"
                    "2. Full name as in passport\n"
                    "3. Arrival airport"
                )
            }
            kb_ft = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 " + ("Способы оплаты (VCB, VRB, Офис)" if lang == "ru" else "Phương thức thanh toán (VCB, VRB, VP)" if lang == "vi" else "Payment Methods (VCB, VRB, Office)"), callback_data="step|pay_menu")],
                [InlineKeyboardButton("💬 " + ("Менеджер поддержки" if lang == "ru" else "Chat với nhân viên hỗ trợ" if lang == "vi" else "Support Manager"), url="https://t.me/easytripvisa_co_ltd")]
            ])
            await send_step_reply(update, context, fasttrack_msg.get(lang, fasttrack_msg["en"]), reply_markup=kb_ft, parse_mode="Markdown")
            return

        # 3. Xác định tuyến hành trình xe buýt để hiển thị lịch trình chi tiết
        if "hanoi" in svc_id or city_key == "hanoi":
            route_key = "hanoi_huunghi"
            route_name = "Hà Nội ⇄ Hữu Nghị"
        elif "cambodia" in svc_id or "mocbai" in svc_id or city_key == "muine" or svc_id == "mn_bus_cambodia":
            route_key = "cambodia_mocbai"
            route_name = "Nha Trang / Mũi Né ⇄ Campuchia Mộc Bài"
        elif "45" in svc_id or svc_id == "nt_bus_laos_45d":
            route_key = "laos_boy_45d"
            route_name = "Nha Trang ⇄ Lào Bờ Y (45 Ngày)"
        elif "90" in svc_id or svc_id in ("nt_bus_laos_90d", "nt_combo_evisa"):
            route_key = "laos_boy_90d"
            route_name = "Nha Trang ⇄ Lào Bờ Y (90 Ngày)"
        else:
            route_key = "laos_boy_45d"
            route_name = "Nha Trang ⇄ Lào Bờ Y (45 Ngày)"
            
        cust_data.loai_visa = route_name
        
        # Lấy bản thông tin lịch trình chi tiết
        itin_msg = get_itinerary_message(route_key, lang)
        
        # Bàn phím hành động tiếp theo (Có nút chọn VCB, VRB, Tiền mặt & Nút quay lại)
        next_action_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💺 " + ("Запросить проверку мест и выбрать место" if lang == "ru" else "Kiểm tra sơ đồ chỗ & Chọn số ghế" if lang == "vi" else "Check availability & Select Seat"), callback_data="step|request_seats")],
            [InlineKeyboardButton("💳 " + ("Способы оплаты (VCB, VRB, Офис)" if lang == "ru" else "Phương thức thanh toán (VCB, VRB, VP)" if lang == "vi" else "Payment Methods (VCB, VRB, Office)"), callback_data="step|pay_menu")],
            [
                InlineKeyboardButton("🔙 " + ("Назад к услугам" if lang == "ru" else "Quay lại danh sách dịch vụ" if lang == "vi" else "Back to Services"), callback_data="step|back|services"),
                InlineKeyboardButton("💬 " + ("Менеджер" if lang == "ru" else "Hỗ trợ" if lang == "vi" else "Support"), url="https://t.me/easytripvisa_co_ltd")
            ]
        ])
        
        await send_step_reply(update, context, itin_msg, reply_markup=next_action_kb, parse_mode="Markdown")
            
        # Thông báo Admin Group
        from telegram_router import send_to_admin_group
        u_name = getattr(update.effective_user, "full_name", "Customer")
        u_handle = getattr(update.effective_user, "username", "N/A")
        await send_to_admin_group(
            context,
            f"🚀 **KHÁCH XEM BẢNG TƯ VẤN CHI TIẾT**\n"
            f"👤 Khách: {u_name} (@{u_handle})\n"
            f"🛂 Quốc tịch: {cust_data.quoc_tich}\n"
            f"📍 Tuyến: {route_name} ({city_key.upper()})\n"
            f"📅 Ngày đi: {cust_data.ngay_khoi_hanh}"
        )
        return

    # 🟢 BƯỚC 5: Khách bấm "Yêu cầu kiểm tra sơ đồ & Chọn số ghế"
    elif step_type == "request_seats":
        lang = memory_store.get(f"{session_id}_lang", "en")
        seat_req_msg = {
            "ru": (
                "⏳ **Мы проверяем наличие свободных мест в автобусе...**\n\n"
                "📸 Пожалуйста, отправьте фото страницы с информацией загранпаспорта и напишите желаемое место (например: **A2**, **B3**).\n\n"
                + get_payment_instruction_text(lang)
            ),
            "en": (
                "⏳ **We are checking seat availability on the bus...**\n\n"
                "📸 Please send a clear photo of your passport page and type your preferred seat number (e.g. **A2**, **B3**).\n\n"
                + get_payment_instruction_text(lang)
            ),
            "vi": (
                "⏳ **Chúng tôi đang kiểm tra sơ đồ chỗ trống trên xe buýt...**\n\n"
                "📸 Quý khách vui lòng chụp gửi ảnh mặt Hộ chiếu và nhắn lại số ghế mong muốn (ví dụ: **A2**, **B3**).\n\n"
                + get_payment_instruction_text(lang)
            )
        }
        kb_pay = get_payment_methods_keyboard(lang)
        await send_step_reply(update, context, seat_req_msg.get(lang, seat_req_msg["en"]), reply_markup=kb_pay, parse_mode="Markdown")
            
        # Chuyển phase trong AI Agent sang SEAT_SELECTION
        simulated_text = f"Customer requested seat checking for {cust_data.loai_visa} on {cust_data.ngay_khoi_hanh}. Nationality: {cust_data.quoc_tich}."
        await process_customer_text_message_fn(update, context, user_id, simulated_text)
        return

    # 🟢 DỊCH VỤ ĐẶC BIỆT: TÁCH RIÊNG 4 NÚT CHUYÊN BIỆT (Overstay, TRC, Work, Family)
    elif step_type in ("special_consult", "agent"):
        topic = parts[2] if len(parts) > 2 else "overstay"
        lang = memory_store.get(f"{session_id}_lang", "en")
        from telegram_router import send_to_admin_group
        u_name = getattr(update.effective_user, "full_name", "Customer")
        u_handle = getattr(update.effective_user, "username", "N/A")
        
        topic_info = {
            "overstay": {
                "title_admin": "🚨 YÊU CẦU TƯ VẤN: QUÁ HẠN VISA (VISA OVERSTAY)",
                "desc_admin": "Quá hạn visa cần xử lý khẩn cấp tránh bị phạt nặng / cấm nhập cảnh.",
                "ru": (
                    "⚠️ **Консультация по просрочке визы (Visa Overstay)**\n\n"
                    "Мы зафиксировали ваш запрос! Наша команда помогает легально урегулировать просрочку визы во Вьетнаме, минимизировать штрафы и избежать черного списка.\n\n"
                    "📋 **Пожалуйста, отправьте в этот чат:**\n"
                    "1. Фото главной страницы загранпаспорта\n"
                    "2. Фото штампа последнего въезда или текущей визы\n"
                    "3. Точную дату окончания срока действия вашей визы\n\n"
                    "Наш специалист по миграционным вопросам ответит вам прямо здесь в течение нескольких минут!\n"
                    "💬 Или свяжитесь напрямую со старшим менеджером: @easytripvisa_co_ltd"
                ),
                "en": (
                    "⚠️ **Visa Overstay Consultation & Legal Settlement**\n\n"
                    "We have logged your request! Easy Trip Visa assists with legal overstay settlement in Vietnam, minimizing fines and preventing blacklisting.\n\n"
                    "📋 **Please send in this chat:**\n"
                    "1. Photo of your passport info page\n"
                    "2. Photo of your latest entry stamp or visa sticker\n"
                    "3. The exact date your visa expired\n\n"
                    "Our migration specialist will review and respond directly in this chat shortly!\n"
                    "💬 Or message senior manager directly: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "⚠️ **Tư vấn & Xử lý Quá hạn Visa (Visa Overstay)**\n\n"
                    "Easy Trip Visa đã tiếp nhận yêu cầu của quý khách! Chúng tôi chuyên xử lý quá hạn visa hợp pháp, giảm thiểu mức phạt và bảo vệ lịch xử xuất nhập cảnh.\n\n"
                    "📋 **Quý khách vui lòng gửi vào khung chat này:**\n"
                    "1. Ảnh trang thông tin Hộ chiếu\n"
                    "2. Ảnh dấu nhập cảnh hoặc visa gần nhất\n"
                    "3. Ngày hết hạn visa chính xác\n\n"
                    "Chuyên viên phụ trách xuất nhập cảnh sẽ tư vấn trực tiếp cho bạn ngay tại đây!\n"
                    "💬 Hoặc liên hệ trực tiếp quản lý: @easytripvisa_co_ltd"
                )
            },
            "trc": {
                "title_admin": "🪪 YÊU CẦU TƯ VẤN: THẺ TẠM TRÚ TRC 2 NĂM",
                "desc_admin": "Làm thẻ tạm trú 2 năm (diện thăm thân TT, lao động LĐ, đầu tư ĐT).",
                "ru": (
                    "🪪 **Оформление карты временного резидента (TRC на 2 года)**\n\n"
                    "Мы зафиксировали ваш запрос на получение TRC (ВНЖ Вьетнама на 2 года)!\n\n"
                    "📋 **Пожалуйста, укажите желаемое основание:**\n"
                    "• Семейная виза / брак с гражданином Вьетнама (Thăm thân)\n"
                    "• Рабочая виза / официальный контракт с компанией (Work Permit)\n"
                    "• Инвестиции / открытие юридического лица во Вьетнаме\n\n"
                    "Отправьте фото вашего паспорта в этот чат, и юрист Easy Trip Visa подробно проконсультирует вас!\n"
                    "💬 Консультация старшего менеджера: @easytripvisa_co_ltd"
                ),
                "en": (
                    "🪪 **2-Year Temporary Residence Card (TRC)**\n\n"
                    "We have received your TRC inquiry! A 2-year TRC allows multiple entries and legal stay without visas.\n\n"
                    "📋 **Please tell us your intended category:**\n"
                    "• Family ties / Marriage with Vietnamese citizen\n"
                    "• Employment / Work Permit sponsor\n"
                    "• Business investment / Company establishment\n\n"
                    "Please send your passport photo in this chat, and our legal advisor will guide you step by step!\n"
                    "💬 Or contact manager: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "🪪 **Tư vấn làm Thẻ tạm trú (TRC) thời hạn 2 năm**\n\n"
                    "Chúng tôi đã tiếp nhận yêu cầu tư vấn Thẻ tạm trú (TRC 2 năm) của quý khách!\n\n"
                    "📋 **Quý khách vui lòng cho biết diện làm hồ sơ:**\n"
                    "• Diện kết hôn / thăm thân với công dân Việt Nam (kí hiệu TT)\n"
                    "• Diện lao động có Giấy phép lao động / Work Permit (kí hiệu LĐ2)\n"
                    "• Diện góp vốn đầu tư thành lập công ty (kí hiệu ĐT)\n\n"
                    "Vui lòng gửi ảnh mặt Hộ chiếu để chuyên viên tư vấn chi tiết danh mục hồ sơ cần chuẩn bị!\n"
                    "💬 Hoặc liên hệ trực tiếp: @easytripvisa_co_ltd"
                )
            },
            "work": {
                "title_admin": "💼 YÊU CẦU TƯ VẤN: VISA LAO ĐỘNG & WORK PERMIT",
                "desc_admin": "Làm Giấy phép lao động (Work Permit) và Visa lao động.",
                "ru": (
                    "💼 **Рабочая виза и разрешение на работу (Work Permit)**\n\n"
                    "Мы зафиксировали ваш запрос на оформление Work Permit и рабочей визы!\n\n"
                    "📋 **Пожалуйста, уточните детали:**\n"
                    "1. Есть ли у вас приглашающая компания/работодатель во Вьетнаме?\n"
                    "2. Ваша специальность, диплом и справка о несудимости?\n\n"
                    "Наш специалист визового отдела свяжется с вами прямо в этом чате в течение нескольких минут!\n"
                    "💬 Связаться с руководителем: @easytripvisa_co_ltd"
                ),
                "en": (
                    "💼 **Work Visa & Work Permit (Giấy phép lao động)**\n\n"
                    "We have logged your Work Visa request! Easy Trip Visa provides full sponsorship and work permit processing.\n\n"
                    "📋 **Please provide details:**\n"
                    "1. Do you have a sponsoring company / employer in Vietnam?\n"
                    "2. Do you have your university degree and criminal record certificate ready?\n\n"
                    "Our corporate visa specialist will assist you directly in this chat shortly!\n"
                    "💬 Or contact manager: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "💼 **Tư vấn Visa lao động & Giấy phép lao động (Work Permit)**\n\n"
                    "Easy Trip Visa đã ghi nhận yêu cầu tư vấn Giấy phép lao động (Work Permit) của quý khách!\n\n"
                    "📋 **Quý khách vui lòng cho biết:**\n"
                    "1. Đã có công ty/doanh nghiệp tại Việt Nam bảo lãnh tuyển dụng chưa?\n"
                    "2. Bằng cấp đại học/chuyên môn và Lý lịch tư pháp đã có sẵn chưa?\n\n"
                    "Chuyên viên hồ sơ doanh nghiệp sẽ hỗ trợ giải đáp trực tiếp ngay tại đây!\n"
                    "💬 Hoặc liên hệ trực tiếp quản lý: @easytripvisa_co_ltd"
                )
            },
            "family": {
                "title_admin": "👨‍👩‍👧 YÊU CẦU TƯ VẤN: VISA THĂM THÂN / GIA ĐÌNH",
                "desc_admin": "Làm Visa thăm thân (TT) cho vợ/chồng/con/cha mẹ.",
                "ru": (
                    "👨‍👩‍👧 **Оформление визы для членов семьи (Family Visit Visa)**\n\n"
                    "Мы зафиксировали ваш запрос на оформление семейной визы (TT)!\n\n"
                    "📋 **Пожалуйста, подготовьте и отправьте:**\n"
                    "1. Фото загранпаспорта заявителя и приглашающего лица\n"
                    "2. Документ о родстве (свидетельство о браке / о рождении с переводом и легализацией)\n\n"
                    "Наш специалист по семейным визам ответит вам в этом чате в течение нескольких минут!\n"
                    "💬 Написать менеджеру: @easytripvisa_co_ltd"
                ),
                "en": (
                    "👨‍👩‍👧 **Family Visit / Visitor Visa (Thăm thân)**\n\n"
                    "We have logged your Family Visa request! We assist spouses, children, and parents with family visas in Vietnam.\n\n"
                    "📋 **Please prepare:**\n"
                    "1. Passport photos of applicant and sponsoring family member\n"
                    "2. Proof of relationship (Marriage certificate / Birth certificate legalized and translated)\n\n"
                    "Our family visa consultant will assist you directly in this chat shortly!\n"
                    "💬 Or message manager: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "👨‍👩‍👧 **Tư vấn Visa Thăm thân / Gia đình (Kí hiệu TT)**\n\n"
                    "Easy Trip Visa đã ghi nhận yêu cầu làm Visa thăm thân cho thân nhân gia đình!\n\n"
                    "📋 **Quý khách vui lòng chuẩn bị:**\n"
                    "1. Ảnh hộ chiếu của người xin visa và người bảo lãnh tại Việt Nam\n"
                    "2. Giấy tờ chứng minh quan hệ (Đăng ký kết hôn / Giấy khai sinh đã hợp pháp hóa lãnh sự và dịch thuật)\n\n"
                    "Chuyên viên tư vấn sẽ hướng dẫn chi tiết từng bước hồ sơ ngay tại đây!\n"
                    "💬 Hoặc liên hệ quản lý: @easytripvisa_co_ltd"
                )
            }
        }
        
        info = topic_info.get(topic, topic_info["overstay"])
        
        await send_to_admin_group(
            context,
            f"{info['title_admin']}\n"
            f"👤 Khách: {u_name} (@{u_handle})\n"
            f"🛂 Quốc tịch: {cust_data.quoc_tich}\n"
            f"📍 Vị trí: {cust_data.thanh_pho}\n"
            f"⚠️ Chi tiết: {info['desc_admin']}\n"
            f"👉 [Nhân viên vui lòng chat hỗ trợ khách ngay!](https://t.me/{u_handle if u_handle != 'N/A' else 'easytripvisa_co_ltd'})"
        )
        
        kb_agent = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 " + ("Написать менеджеру напрямую" if lang == "ru" else "Nhắn tin trực tiếp với quản lý" if lang == "vi" else "Chat directly with Manager"), url="https://t.me/easytripvisa_co_ltd")],
            [InlineKeyboardButton("📢 " + ("Официальный канал" if lang == "ru" else "Kênh thông tin Easy Trip Visa" if lang == "vi" else "Official Channel"), url="https://t.me/visaEASYTRIP")]
        ])
        
        await send_step_reply(update, context, info.get(lang, info["en"]), reply_markup=kb_agent, parse_mode="Markdown")
        return

    # 🟢 BƯỚC THANH TOÁN: Danh mục ngân hàng (VCB, VRB, Tiền mặt tại VP)
    elif step_type == "pay_menu":
        lang = memory_store.get(f"{session_id}_lang", "en")
        menu_title = {
            "ru": (
                "💳 **ВЫБЕРИТЕ СПОСОБ ОПЛАТЫ (EASY TRIP & VISA)**\n\n"
                "Пожалуйста, выберите подходящий банк для безналичного перевода или вариант оплаты наличными в офисе Нячанга:"
            ),
            "vi": (
                "💳 **CHỌN PHƯƠNG THỨC THANH TOÁN (EASY TRIP & VISA)**\n\n"
                "Quý khách vui lòng chọn ngân hàng chuyển khoản phù hợp hoặc đến văn phòng nộp tiền mặt:"
            ),
            "en": (
                "💳 **SELECT PAYMENT METHOD (EASY TRIP & VISA)**\n\n"
                "Please choose your preferred bank for transfer or select cash payment at our Nha Trang office:"
            )
        }
        kb_pay = get_payment_methods_keyboard(lang)
        await send_step_reply(update, context, menu_title.get(lang, menu_title["en"]), reply_markup=kb_pay, parse_mode="Markdown")
        return

    # 🟢 CHI TIẾT CÁCH THỨC CHUYỂN KHOẢN (VCB / VRB / TIỀN MẶT)
    elif step_type == "pay":
        method = parts[2] if len(parts) > 2 else "vcb"
        lang = memory_store.get(f"{session_id}_lang", "en")
        detail_msg = get_payment_detail_message(method, lang)
        detail_kb = get_payment_detail_keyboard(lang)
        await send_step_reply(update, context, detail_msg, reply_markup=detail_kb, parse_mode="Markdown")
        return

    # 🟢 NÚT TRỞ VỀ THAO TÁC TRƯỚC ĐÓ (BACK TO PREVIOUS STEP)
    elif step_type == "back":
        back_target = parts[2] if len(parts) > 2 else "city"
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        # 1. Trở về danh sách dịch vụ để khách thay đổi lựa chọn hoặc nghiên cứu thêm
        if back_target in ("services", "advisory", "svc"):
            city_key = cust_data.thanh_pho or "nhatrang"
            cname = cust_data.quoc_tich or "Russia"
            exempt = is_country_exempt(cname)
            date_val = cust_data.ngay_het_han_visa or cust_data.ngay_khoi_hanh or "TBD"
            
            advisory_header = {
                "ru": (
                    f"📊 **РЕЗУЛЬТАТ ПОДБОРА ВИЗАРАНА:**\n"
                    f"• Гражданство: **{cname}** ({'Безвизовый въезд на 45 дней ✅' if exempt else 'Требуется электронная виза 90 дней 📑'})\n"
                    f"• Город отправления: **{city_key.upper()}**\n"
                    f"• Дата выезда: **{date_val}**\n\n"
                    "👉 **ДОСТУПНЫЕ ПАКЕТЫ И УСЛУГИ (Выберите вариант для изменения):**"
                ),
                "en": (
                    f"📊 **VISA RUN ADVISORY SUMMARY:**\n"
                    f"• Nationality: **{cname}** ({'Visa-Free 45 Days Exempt ✅' if exempt else 'Requires 90-Day E-Visa 📑'})\n"
                    f"• Departure City: **{city_key.upper()}**\n"
                    f"• Expiry / Departure Date: **{date_val}**\n\n"
                    "👉 **RECOMMENDED PACKAGES (Choose an option to change):**"
                ),
                "vi": (
                    f"📊 **KẾT QUẢ PHÂN TÍCH TƯ VẤN VISARUN:**\n"
                    f"• Quốc tịch: **{cname}** ({'Được Miễn thị thực 45 ngày ✅' if exempt else 'Cần đăng ký E-Visa 90 ngày 📑'})\n"
                    f"• Thành phố xuất phát: **{city_key.upper()}**\n"
                    f"• Ngày hết hạn / khởi hành: **{date_val}**\n\n"
                    "👉 **CÁC GÓI DỊCH VỤ PHÙ HỢP NHẤT (Chọn gói để thay đổi):**"
                )
            }
            keyboard = get_smart_advisory_keyboard(city_key, cname, lang)
            await send_step_reply(update, context, advisory_header.get(lang, advisory_header["en"]), reply_markup=keyboard, parse_mode="Markdown")
            return
            
        # 2. Trở về chọn lại quốc gia
        elif back_target in ("nationality", "nat"):
            keyboard = get_nationality_keyboard()
            await send_step_reply(update, context, "🌐 Chọn lại quốc gia / Выберите страну / Choose country:", reply_markup=keyboard)
            return
            
        # 3. Trở về chọn lại thành phố
        elif back_target == "city":
            keyboard = get_city_keyboard(lang)
            await send_step_reply(update, context, "📍 Chọn lại thành phố / Выберите город / Choose city:", reply_markup=keyboard)
            return
