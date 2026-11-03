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
    if any(k in tl for k in ["nhatrang", "nha trang", "нячанг", "нячанга"]):
        city = "nhatrang"
    elif any(k in tl for k in ["muine", "mui ne", "mũi né", "муйне", "phan thiết", "phan thiet"]):
        city = "muine"
    elif any(k in tl for k in ["danang", "da nang", "đà nẵng", "дананг", "hội an", "hoi an"]):
        city = "danang"
    elif any(k in tl for k in ["hcm", "hồ chí minh", "ho chi minh", "хошимин", "sài gòn", "saigon", "tp.hcm", "tp hcm", "tphcm"]):
        city = "hcm"
    elif any(k in tl for k in ["hanoi", "ha noi", "hà nội", "ханой", "ханоя"]):
        city = "hanoi"
    elif any(k in tl for k in ["abroad", "за рубежом", "nước ngoài"]):
        city = "abroad"
    else:
        # Nếu chưa có tên thành phố, suy đoán theo cửa khẩu đặc thù
        if any(k in tl for k in ["bờ y", "bo y", "бо-и", "бо и"]):
            city = "nhatrang"
        elif any(k in tl for k in ["lao bảo", "lao bao", "лао бао"]):
            city = "danang"
        elif any(k in tl for k in ["hữu nghị", "huu nghi", "хыу нги"]):
            city = "hanoi"

    # Nếu khách chuyển tiếp từ Web kèm tuyến xe/thành phố cụ thể (hoặc tin nhắn có đề cập thành phố)
    is_web_or_city = (
        city is not None or
        any(k in tl for k in [
            "express visa run booking", "визаран", "visarun", "visa run",
            "vietnam visa pass", "xe buýt", "xe bus", "chuyến xe", "đặt xe"
        ])
    )
    if is_web_or_city:
        c_code = city or "nhatrang"
        service_name = ""
        is_cambodia = any(k in tl for k in ["камбодж", "cambodia", "campuchia", "mộc bài", "moc bai"])
        is_laos = any(k in tl for k in ["лаос", "laos", "lào", "bờ y", "bo y", "бо-и", "бо и", "lao bảo", "lao bao", "лао бао"])
        is_90d = any(k in tl for k in ["90", "4.400.000", "4400000", "4.000.000", "4000000"])
        is_45d = any(k in tl for k in ["45", "1.400.000", "1400000", "безвиз", "miễn visa"])

        if c_code == "nhatrang":
            if is_cambodia:
                if is_90d:
                    service_name = (
                        "Визаран Нячанг ⇄ Камбоджа (Мокбай) — 90 дней E-Visa (4.400.000 VND)"
                        if detected_lang == "ru" else
                        "Visarun Nha Trang ⇄ Campuchia (Mộc Bài) — 90 ngày E-Visa (4.400.000 VND)"
                        if detected_lang == "vi" else
                        "Visarun Nha Trang ⇄ Cambodia (Moc Bai) — 90-Day E-Visa (4,400,000 VND)"
                    )
                else:
                    service_name = (
                        "Визаран Нячанг ⇄ Камбоджа (Мокбай)"
                        if detected_lang == "ru" else
                        "Visarun Nha Trang ⇄ Campuchia (Mộc Bài)"
                        if detected_lang == "vi" else
                        "Visarun Nha Trang ⇄ Cambodia (Moc Bai)"
                    )
            elif is_laos or any(k in tl for k in ["bờ y", "bo y", "бо-и", "бо и"]):
                if is_45d:
                    service_name = (
                        "Визаран Nha Trang - Lào Bờ Y 45 ngày (Безвиз 1.400.000 VND)"
                        if detected_lang == "ru" else
                        "Visarun Nha Trang - Lào Bờ Y 45 ngày (Miễn thị thực 1.400.000 VND)"
                        if detected_lang == "vi" else
                        "Visarun Nha Trang - Laos Bo Y 45 Days (Visa-Free 1,400,000 VND)"
                    )
                elif is_90d:
                    service_name = (
                        "Визаран Nha Trang - Lào Bờ Y 90 ngày (E-Visa 4.000.000 VND)"
                        if detected_lang == "ru" else
                        "Visarun Nha Trang - Lào Bờ Y 90 ngày (E-Visa 4.000.000 VND)"
                        if detected_lang == "vi" else
                        "Visarun Nha Trang - Laos Bo Y 90 Days (E-Visa 4,000,000 VND)"
                    )
                else:
                    service_name = (
                        "Визаран Nha Trang ⇄ Lào Bờ Y"
                        if detected_lang == "ru" else
                        "Visarun Nha Trang ⇄ Lào Bờ Y"
                        if detected_lang == "vi" else
                        "Visarun Nha Trang ⇄ Laos Bo Y"
                    )
            else:
                service_name = (
                    "Визаран Нячанг ⇄ Лаос / Камбоджа"
                    if detected_lang == "ru" else
                    "Visarun Nha Trang ⇄ Lào / Campuchia"
                    if detected_lang == "vi" else
                    "Visarun Nha Trang ⇄ Laos / Cambodia"
                )

        elif c_code == "muine":
            if is_90d:
                service_name = (
                    "Визаран Муйне ⇄ Камбоджа (Мокбай) — 90 дней E-Visa (4.000.000 VND)"
                    if detected_lang == "ru" else
                    "Visarun Mũi Né ⇄ Campuchia (Mộc Bài) — 90 ngày E-Visa (4.000.000 VND)"
                    if detected_lang == "vi" else
                    "Visarun Mui Ne ⇄ Cambodia (Moc Bai) — 90-Day E-Visa"
                )
            else:
                service_name = (
                    "Визаран Муйне ⇄ Камбоджа (Мокбай)"
                    if detected_lang == "ru" else
                    "Visarun Mũi Né ⇄ Campuchia (Mộc Bài)"
                    if detected_lang == "vi" else
                    "Visarun Mui Ne ⇄ Cambodia (Moc Bai)"
                )

        elif c_code == "danang":
            if is_90d:
                service_name = (
                    "Визаран Дананг ⇄ Лаос (Лао Бао) — 90 дней E-Visa (3.900.000 VND)"
                    if detected_lang == "ru" else
                    "Visarun Đà Nẵng ⇄ Lào (Lao Bảo) — 90 ngày E-Visa (3.900.000 VND)"
                    if detected_lang == "vi" else
                    "Visarun Da Nang ⇄ Laos (Lao Bao) — 90-Day E-Visa"
                )
            else:
                service_name = (
                    "Визаран Дананг ⇄ Лаос (Лао Бао)"
                    if detected_lang == "ru" else
                    "Visarun Đà Nẵng ⇄ Lào (Lao Bảo)"
                    if detected_lang == "vi" else
                    "Visarun Da Nang ⇄ Laos (Lao Bao)"
                )

        elif c_code == "hanoi":
            service_name = (
                "Визаран Ханой ⇄ Хыу Нги"
                if detected_lang == "ru" else
                "Visarun Hà Nội ⇄ Hữu Nghị"
                if detected_lang == "vi" else
                "Visarun Hanoi ⇄ Huu Nghi"
            )

        elif c_code == "hcm":
            service_name = (
                "Индивидуальный трансфер Хошимин ⇄ Мокбай"
                if detected_lang == "ru" else
                "Xe riêng TP.HCM ⇄ Mộc Bài"
                if detected_lang == "vi" else
                "Private Car HCMC ⇄ Moc Bai"
            )

        elif c_code == "abroad":
            service_name = (
                "Оформление визы во Вьетнам (E-Visa / Fast Track)"
                if detected_lang == "ru" else
                "Thị thực nhập cảnh Việt Nam (E-Visa / Fast Track)"
                if detected_lang == "vi" else
                "Vietnam Entry Visa (E-Visa / Fast Track)"
            )

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
    if lang == "ru":
        abroad_lbl = "✈️ За рубежом (Въезд во Вьетнам)"
        nt_lbl = "🏖️ Нячанг"
        mn_lbl = "🏖️ Муйне (Фантхьет)"
        dn_lbl = "🌊 Дананг / Хойан"
        hcm_lbl = "🏙️ Хошимин (Сайгон)"
        hn_lbl = "🏛️ Ханой"
        other_lbl = "📍 Другой город"
    elif lang == "vi":
        abroad_lbl = "✈️ Đang ở nước ngoài (Nhập cảnh VN)"
        nt_lbl = "🏖️ Nha Trang"
        mn_lbl = "🏖️ Mũi Né (Phan Thiết)"
        dn_lbl = "🌊 Đà Nẵng / Hội An"
        hcm_lbl = "🏙️ TP. Hồ Chí Minh"
        hn_lbl = "🏛️ Hà Nội"
        other_lbl = "📍 Thành phố khác"
    else:
        abroad_lbl = "✈️ Currently Abroad (Entering Vietnam)"
        nt_lbl = "🏖️ Nha Trang"
        mn_lbl = "🏖️ Mui Ne (Phan Thiet)"
        dn_lbl = "🌊 Da Nang / Hoi An"
        hcm_lbl = "🏙️ Ho Chi Minh City"
        hn_lbl = "🏛️ Hanoi"
        other_lbl = "📍 Other City"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(abroad_lbl, callback_data="step|city|abroad")
        ],
        [
            InlineKeyboardButton(nt_lbl, callback_data="step|city|nhatrang"),
            InlineKeyboardButton(mn_lbl, callback_data="step|city|muine")
        ],
        [
            InlineKeyboardButton(dn_lbl, callback_data="step|city|danang"),
            InlineKeyboardButton(hcm_lbl, callback_data="step|city|hcm")
        ],
        [
            InlineKeyboardButton(hn_lbl, callback_data="step|city|hanoi"),
            InlineKeyboardButton(other_lbl, callback_data="step|city|other")
        ]
    ])

def get_calendar_keyboard(year: int, month: int, lang: str = "ru", prefix: str = "step|date"):
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
                row.append(InlineKeyboardButton(lbl, callback_data=f"{prefix}|{date_str}"))
        rows.append(row)
        
    urgent_lbl = "⚡ Срочно (1-2 дня)" if lang == "ru" else "⚡ Khẩn cấp (1-2 ngày)" if lang == "vi" else "⚡ Urgent (1-2 days)"
    manual_lbl = "✍️ Ввести вручную" if lang == "ru" else "✍️ Nhập ngày khác" if lang == "vi" else "✍️ Enter date"
    rows.append([
        InlineKeyboardButton(urgent_lbl, callback_data=f"{prefix}|urgent"),
        InlineKeyboardButton(manual_lbl, callback_data=f"{prefix}|manual")
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
        if lang == "ru":
            rows.append([InlineKeyboardButton("🚌 Визаран Дананг ⇄ Лаос (Лао Бао)", callback_data="step|svc|dn_bus")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Безвиз 45 дней (Лао Бао) — 950.000 ₫", callback_data="step|svc|dn_bus")])
                rows.append([InlineKeyboardButton("📑 Пакет: Bus + E-Visa 90 дней (Лао Бао) — 3.800.000 ₫", callback_data="step|svc|dn_combo_ultra")])
            else:
                rows.append([InlineKeyboardButton("📑 Пакет: Bus + E-Visa 90 дней (Лао Бао) — 3.800.000 ₫", callback_data="step|svc|dn_combo_ultra")])
        elif lang == "vi":
            rows.append([InlineKeyboardButton("🚌 Visarun Đà Nẵng ⇄ Lao Bảo (Lào)", callback_data="step|svc|dn_bus")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Miễn thị thực 45 ngày (Lao Bảo) - 850.000 ₫", callback_data="step|svc|dn_bus")])
                rows.append([InlineKeyboardButton("📑 Combo trọn gói E-Visa 90 ngày (Lao Bảo) - 3.900.000 ₫", callback_data="step|svc|dn_combo_ultra")])
            else:
                rows.append([InlineKeyboardButton("📑 Combo trọn gói E-Visa 90 ngày (Lao Bảo) - 3.900.000 ₫", callback_data="step|svc|dn_combo_ultra")])
        else:
            rows.append([InlineKeyboardButton("🚌 Visarun Da Nang ⇄ Lao Bao (Laos)", callback_data="step|svc|dn_bus")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ 45-Day Visa-Free (Lao Bao) - 850,000 VND", callback_data="step|svc|dn_bus")])
                rows.append([InlineKeyboardButton("📑 90-Day E-Visa Package (Lao Bao) - 3,900,000 VND", callback_data="step|svc|dn_combo_ultra")])
            else:
                rows.append([InlineKeyboardButton("📑 90-Day E-Visa Package (Lao Bao) - 3,900,000 VND", callback_data="step|svc|dn_combo_ultra")])
            
    elif city == "nhatrang":
        if lang == "ru":
            rows.append([InlineKeyboardButton("🚌 Визаран Нячанг ⇄ Лаос (Бо-И) 45 дней (Безвиз)", callback_data="step|svc|nt_bus_laos_45d")])
            rows.append([InlineKeyboardButton("🚌 Визаран Нячанг ⇄ Лаос (Бо-И) 90 дней (E-Visa)", callback_data="step|svc|nt_bus_laos_90d")])
            rows.append([InlineKeyboardButton("🚌 Визаран Нячанг ⇄ Камбоджа (Мокбай) (30/45/90 дней)", callback_data="step|svc|nt_bus_cambodia")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Безвиз 45 дней (Лаос Бо-И) — 1.400.000 ₫", callback_data="step|svc|nt_bus_laos_45d")])
                rows.append([InlineKeyboardButton("📑 Пакет E-Visa 90 дней (Лаос Бо-И) — 3.400.000 ₫", callback_data="step|svc|nt_bus_laos_90d")])
                rows.append([InlineKeyboardButton("📑 Пакет E-Visa 90 дней (Камбоджа Мокбай) — 3.400.000 ₫", callback_data="step|svc|nt_combo_evisa")])
            else:
                rows.append([InlineKeyboardButton("📑 Пакет E-Visa 90 дней (Лаос Бо-И) — 3.400.000 ₫", callback_data="step|svc|nt_bus_laos_90d")])
                rows.append([InlineKeyboardButton("📑 Пакет E-Visa 90 дней (Камбоджа Мокбай) — 3.400.000 ₫", callback_data="step|svc|nt_combo_evisa")])
        elif lang == "vi":
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Lào Bờ Y 45 ngày", callback_data="step|svc|nt_bus_laos_45d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Lào Bờ Y 90 ngày", callback_data="step|svc|nt_bus_laos_90d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Cambodia (30/45/90D)", callback_data="step|svc|nt_bus_cambodia")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Miễn thị thực 45 ngày (Lào Bờ Y) - 1.400.000 ₫", callback_data="step|svc|nt_bus_laos_45d")])
                rows.append([InlineKeyboardButton("📑 Trọn gói E-Visa 90 ngày (Lào Bờ Y) - 4.000.000 ₫", callback_data="step|svc|nt_bus_laos_90d")])
                rows.append([InlineKeyboardButton("📑 Trọn gói E-Visa 90 ngày (Campuchia Mộc Bài) - 4.400.000 ₫", callback_data="step|svc|nt_combo_evisa")])
            else:
                rows.append([InlineKeyboardButton("📑 Trọn gói E-Visa 90 ngày (Lào Bờ Y) - 4.000.000 ₫", callback_data="step|svc|nt_bus_laos_90d")])
                rows.append([InlineKeyboardButton("📑 Trọn gói E-Visa 90 ngày (Campuchia Mộc Bài) - 4.400.000 ₫", callback_data="step|svc|nt_combo_evisa")])
        else:
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Laos Bo Y 45 Days (Visa-Free)", callback_data="step|svc|nt_bus_laos_45d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Laos Bo Y 90 Days (E-Visa)", callback_data="step|svc|nt_bus_laos_90d")])
            rows.append([InlineKeyboardButton("🚌 Visarun Nha Trang - Cambodia (30/45/90D)", callback_data="step|svc|nt_bus_cambodia")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ 45-Day Visa-Free (Laos Bo Y) - 1,400,000 VND", callback_data="step|svc|nt_bus_laos_45d")])
                rows.append([InlineKeyboardButton("📑 90-Day E-Visa Package (Laos Bo Y) - 4,000,000 VND", callback_data="step|svc|nt_bus_laos_90d")])
                rows.append([InlineKeyboardButton("📑 90-Day E-Visa Package (Cambodia Moc Bai) - 4,400,000 VND", callback_data="step|svc|nt_combo_evisa")])
            else:
                rows.append([InlineKeyboardButton("📑 90-Day E-Visa Package (Laos Bo Y) - 4,000,000 VND", callback_data="step|svc|nt_bus_laos_90d")])
                rows.append([InlineKeyboardButton("📑 90-Day E-Visa Package (Cambodia Moc Bai) - 4,400,000 VND", callback_data="step|svc|nt_combo_evisa")])
            
    elif city == "muine":
        if lang == "ru":
            rows.append([InlineKeyboardButton("🚌 Визаран Муйне ⇄ Камбоджа (Мокбай) (30/45/90 дней)", callback_data="step|svc|mn_bus_cambodia")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Билет Муйне ⇄ Камбоджа (Безвиз) — 1.400.000 ₫", callback_data="step|svc|mn_bus_cambodia")])
                rows.append([InlineKeyboardButton("📑 Пакet: Bus + E-Visa 90 дней — 4.000.000 ₫", callback_data="step|svc|mn_combo_evisa")])
            else:
                rows.append([InlineKeyboardButton("📑 Пакет: Bus + E-Visa 90 дней — 4.000.000 ₫", callback_data="step|svc|mn_combo_evisa")])
        elif lang == "vi":
            rows.append([InlineKeyboardButton("🚌 Visarun Mũi Né - Cambodia (30/45/90D)", callback_data="step|svc|mn_bus_cambodia")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Vé xe Mũi Né ⇄ Campuchia (Miễn visa) - 1.400.000 ₫", callback_data="step|svc|mn_bus_cambodia")])
                rows.append([InlineKeyboardButton("📑 Trọn gói Bus Mũi Né + E-Visa 90 ngày - 4.000.000 ₫", callback_data="step|svc|mn_combo_evisa")])
            else:
                rows.append([InlineKeyboardButton("📑 Trọn gói Bus Mũi Né + E-Visa 90 ngày - 4.000.000 ₫", callback_data="step|svc|mn_combo_evisa")])
        else:
            rows.append([InlineKeyboardButton("🚌 Visarun Mui Ne - Cambodia (30/45/90D)", callback_data="step|svc|mn_bus_cambodia")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Bus Ticket Mui Ne ⇄ Cambodia (Visa-Free) - 1,400,000 VND", callback_data="step|svc|mn_bus_cambodia")])
                rows.append([InlineKeyboardButton("📑 Package: Bus + 90-Day E-Visa - 4,000,000 VND", callback_data="step|svc|mn_combo_evisa")])
            else:
                rows.append([InlineKeyboardButton("📑 Package: Bus + 90-Day E-Visa - 4,000,000 VND", callback_data="step|svc|mn_combo_evisa")])
            
    elif city == "hanoi":
        if lang == "ru":
            rows.append([InlineKeyboardButton("🚌 Визаран Ханой ⇄ Хыу Нги (45/90 дней)", callback_data="step|svc|hn_bus_huunghi")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ VIP Лимузин Ханой ⇄ Хыу Нги (Безвиз 45 дней) — 1.200.000 ₫", callback_data="step|svc|hn_bus_huunghi")])
            rows.append([InlineKeyboardButton("📑 Пакет: VIP Лимузин + E-Visa 90 дней (Хыу Нги)", callback_data="step|svc|hn_bus_huunghi")])
        elif lang == "vi":
            rows.append([InlineKeyboardButton("🚌 Visarun Hà Nội - Hữu Nghị (45/90D)", callback_data="step|svc|hn_bus_huunghi")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ Vé VIP Limousine Hà Nội ⇄ Hữu Nghị (Miễn visa 45D) - 1.200.000 ₫", callback_data="step|svc|hn_bus_huunghi")])
            rows.append([InlineKeyboardButton("📑 Trọn gói VIP Limousine + E-Visa 90 ngày Hữu Nghị", callback_data="step|svc|hn_bus_huunghi")])
        else:
            rows.append([InlineKeyboardButton("🚌 Visarun Hanoi - Huu Nghi (45/90D)", callback_data="step|svc|hn_bus_huunghi")])
            if exempt:
                rows.append([InlineKeyboardButton("⭐ VIP Limousine Hanoi ⇄ Huu Nghi (45D Visa-Free) - 1,200,000 VND", callback_data="step|svc|hn_bus_huunghi")])
            rows.append([InlineKeyboardButton("📑 Package: VIP Limousine + 90-Day E-Visa Huu Nghi", callback_data="step|svc|hn_bus_huunghi")])
        
    elif city == "hcm":
        if lang == "ru":
            rows.append([InlineKeyboardButton("🚗 Индивидуальное авто Хошимин ⇄ Мокбай — 2.300.000 ₫", callback_data="step|svc|hcm_car_private")])
            rows.append([InlineKeyboardButton("✈️ VIP Fast Track Аэропорт Таншоннят (SGN) — 1.200.000 ₫", callback_data="step|svc|hcm_fasttrack")])
        elif lang == "vi":
            rows.append([InlineKeyboardButton("🚗 Xe Ô Tô Riêng 4–7 Chỗ TP.HCM ⇄ Mộc Bài - 2.300.000 ₫", callback_data="step|svc|hcm_car_private")])
            rows.append([InlineKeyboardButton("✈️ VIP Fast Track Sân Bay Tân Sơn Nhất - 1.200.000 ₫", callback_data="step|svc|hcm_fasttrack")])
        else:
            rows.append([InlineKeyboardButton("🚗 Private Car HCMC ⇄ Moc Bai - 2,300,000 VND", callback_data="step|svc|hcm_car_private")])
            rows.append([InlineKeyboardButton("✈️ VIP Fast Track Tan Son Nhat Airport (SGN) - 1,200,000 VND", callback_data="step|svc|hcm_fasttrack")])
        
    elif city == "abroad":
        if lang == "ru":
            rows.append([InlineKeyboardButton("⚡ Срочная E-Visa (до вылета во Вьетнам)", callback_data="step|svc|abroad_evisa_urgent")])
            rows.append([InlineKeyboardButton("✈️ Airport VIP Fast Track (встреча у трапа)", callback_data="step|svc|abroad_fasttrack")])
        elif lang == "vi":
            rows.append([InlineKeyboardButton("⚡ Urgent E-visa (Làm visa cấp tốc trước khi bay)", callback_data="step|svc|abroad_evisa_urgent")])
            rows.append([InlineKeyboardButton("✈️ Airport VIP Fast Track Đón Cửa Máy Bay", callback_data="step|svc|abroad_fasttrack")])
        else:
            rows.append([InlineKeyboardButton("⚡ Urgent E-Visa (Before departure)", callback_data="step|svc|abroad_evisa_urgent")])
            rows.append([InlineKeyboardButton("✈️ Airport VIP Fast Track Gate Escort", callback_data="step|svc|abroad_fasttrack")])

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
        "price_vi": "1.400.000 VND (Vé xe giường nằm khứ hồi)",
        "price_ru": "1.400.000 VND (Билет на комфортабельный слипбас туда и обратно)",
        "price_en": "1,400,000 VND (Round-trip sleeper bus ticket)",
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
            "⚠️ ПРАВИЛА РЕГИСТРАЦИИ НА РЕЙС (БО-И 45 ДНЕЙ БЕЗВИЗ):\n"
            "1️⃣ Документы: Четкое фото страницы загранпаспорта (срок действия строго более 6 месяцев).\n"
            "2️⃣ Экспресс-оформление: Быстрая регистрация и подтверждение места на слипбасе в течение 15 минут.\n"
            "3️⃣ Без распечатки на бумаге: На КПП Бо-И и Лаобао распечатывать визу НЕ ТРЕБУЕТСЯ.\n"
            "4️⃣ Льготы для детей до 9 лет (Babysitter Vietnam): 100% БЕСПЛАТНЫЙ билет на автобус при размещении с родителями.\n\n"
            "👉 Нажмите дату выезда на календаре ниже (🟢 отмечены дни рейсов Вт, Чт, Вс) или выберите пакет:"
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
        "price_vi": "1.400.000 VND (Chỉ vé xe khứ hồi) | 4.000.000 VND (Combo Trọn Gói Bus + E-Visa 90 ngày)",
        "price_ru": "1.400.000 VND (Только билет на автобус) | 3.400.000 VND (Пакет: Автобус + E-Visa на 90 дней)",
        "price_en": "1,400,000 VND (Bus only) | 4,000,000 VND (Package: Bus + 90-day E-Visa)",
        "schedule_vi": (
            "⏰ LỊCH TRÌNH CHI TIẾT (XE CHẠY THỨ 3, THỨ 5, CHỦ NHẬT):\n"
            "• 21:00: Tập trung tại điểm đón xe buýt ở Nha Trang.\n"
            "• 21:15 - 21:30: Xe giường nằm khởi hành đi Cửa khẩu Quốc tế Bờ Y.\n"
            "• 06:00 (Sáng hôm sau): Đến cửa khẩu Bờ Y, nghỉ ngơi, ăn sáng, cafe.\n"
            "• 07:00: Cửa khẩu mở cửa. Xếp hàng làm thủ tục xuất cảnh Việt Nam.\n"
            "• 07:30: Đi bộ sang cửa khẩu Lào làm thủ tục đóng dấu nhập cảnh và xuất cảnh Lào.\n"
            "• 08:30: Quay lại cửa khẩu Việt Nam xuất trình E-Visa 90 ngày (trên điện thoại hoặc bản in) để hải quan đóng dấu thời hạn 90 ngày mới.\n"
            "• 09:30: Lên xe buýt quay trở về Nha Trang (về tới nơi khoảng 18:30 - 19:00 chiều)."
        ),
        "schedule_ru": (
            "⏰ ДЕТАЛЬНОЕ РАСПИСАНИЕ (АВТОБУС ХОДИТ ВО ВТ, ЧТ, ВС):\n"
            "• 21:00: Сбор на посадочной точке в Нячанге.\n"
            "• 21:15 - 21:30: Отправление комфортабельного слипбаса в сторону КПП Бо-И.\n"
            "• 06:00 (следующее утро): Прибытие на границу Бо-И, завтрак, кофе, отдых.\n"
            "• 07:00: Открытие границы. Очередь и выезд из Вьетнама.\n"
            "• 07:30: Переход границы Лаоса, получение въездного и выездного штампа Лаоса.\n"
            "• 08:30: Возвращение на вьетнамский КПП, предъявление E-Visa 90 дней (в телефоне) и получение штампа на 90 дней.\n"
            "• 09:30: Посадка в автобус и выезд обратно в Нячанг (прибытие около 18:30 - 19:00)."
        ),
        "pickup_vi": "📍 Điểm đón: 40 Hòn Chồng = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) hoặc Số 4 Trần Phú, Nha Trang.",
        "pickup_ru": "📍 Точка сбора: 40 Hon Chong = Oceanus Nha Trang (https://maps.app.goo.gl/y8DjaoCNDsRyZN9B8) или No. 4 Tran Phu, Нячанг.",
        "border_vi": "⚠️ LƯU Ý TẠI CỬA KHẨU BỜ Y: Hộ chiếu gốc còn hạn trên 6 tháng; TIỀN MẶT (khoảng 150.000 VND) nộp phí đóng dấu biên phòng (Riêng cửa khẩu Bờ Y và Lao Bảo KHÔNG CẦN in E-Visa ra giấy, chỉ cần lưu file ảnh trên điện thoại).",
        "border_ru": "⚠️ ВАЖНО НА КПП БО-И: Загранпаспорт сроком от 6 мес.; наличные (ок. 150.000 VND) на оплату пограничных сборов (На КПП Бо-И и Лаобао РАСПЕЧАТЫВАТЬ E-Visa НА БУМАГЕ НЕ ТРЕБУЕТСЯ, достаточно файла на телефоне).",
        "booking_vi": (
            "⚠️ QUY TẮC ĐĂNG KÝ BẮT BUỘC (TUYẾN BỜ Y 90 NGÀY E-VISA):\n"
            "1️⃣ Hồ sơ đăng ký: Gửi ảnh chụp trang Hộ chiếu (rõ 4 góc, còn hạn trên 6 tháng) + 01 ảnh thẻ 4x6 nền trắng.\n"
            "2️⃣ Thời gian xử lý: Gói trọn gói đã bao gồm visa xử lý khẩn cấp siêu tốc (trong 2.5 đến 3 giờ), nhận visa hoàn tất nhanh chóng trước chuyến đi.\n"
            "3️⃣ Không cần in giấy: Cửa khẩu Bờ Y và Lao Bảo kiểm tra điện tử, quý khách KHÔNG CẦN in E-Visa ra giấy (chỉ cần lưu file ảnh trên điện thoại).\n"
            "4️⃣ Hộ chiếu gốc: Còn hạn sử dụng trên 6 tháng.\n"
            "5️⃣ Ưu đãi trẻ em dưới 9 tuổi (Babysitter Vietnam): 100% MIỄN PHÍ VÉ XE BUÝT (0 ₫) nằm chung giường với bố mẹ + gói E-Visa khẩn trợ giá chỉ 1.480.000 ₫ (đăng ký trước tối thiểu 4 ngày).\n\n"
            "👉 Vui lòng chọn ngày đi trên lịch bên dưới (🟢 ngày màu xanh là ngày xe chạy T3, T5, CN) hoặc chọn gói dịch vụ:"
        ),
        "booking_ru": (
            "⚠️ ПРАВИЛА РЕГИСТРАЦИИ (БО-И 90 ДНЕЙ E-VISA):\n"
            "1️⃣ Документы: Фото загранпаспорта (срок более 6 мес.) + фото 4x6 на белом фоне.\n"
            "2️⃣ Экспресс-оформление: Пакет включает срочную обработку E-Visa за 2.5–3 часа — виза будет готова точно к рейсу.\n"
            "3️⃣ Без распечатки на бумаге: На КПП Бо-И и Лаобао распечатывать визу НЕ ТРЕБУЕТСЯ (достаточно показать файл с телефона).\n"
            "4️⃣ Льготы для детей до 9 лет (Babysitter Vietnam): 100% БЕСПЛАТНЫЙ билет на автобус при размещении с родителями + льготная E-Visa за 1.480.000 VND (при бронировании за 4 дня).\n\n"
            "👉 Нажмите дату выезда на календаре ниже (🟢 дни рейсов Вт, Чт, Вс) или выберите пакет:"
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
        "price": "1.400.000 VND (Vé xe khứ hồi) | 4.000.000 VND (Combo Bus + E-Visa 90 ngày) | 4.400.000 VND (Combo Bus + E-Visa 90 ngày + Visa Campuchia 24h)",
        "price_vi": "1.400.000 VND (Vé xe khứ hồi) | 4.000.000 VND (Combo Bus + E-Visa 90 ngày) | 4.400.000 VND (Combo Bus + E-Visa 90 ngày + Visa Campuchia 24h)",
        "price_ru": "1.400.000 VND (Билет туда-обратно) | 3.400.000 VND (Пакет Bus + E-Visa 90 дней) | 4.400.000 VND (Пакет Bus + E-Visa 90 дней + виза Камбоджи за 24ч)",
        "price_en": "1,400,000 VND (Round-trip bus) | 4,000,000 VND (Package: Bus + 90-Day E-Visa) | 4,400,000 VND (Package: Bus + E-Visa + Cambodia 24h Visa)",
        "price_vi": "1.400.000 VND (Vé xe khứ hồi) | 4.000.000 VND (Combo Bus + E-Visa 90 ngày) | 4.400.000 VND (Combo Bus + E-Visa 90 ngày + Visa Campuchia 24h)",
        "price_ru": "1.400.000 VND (Билет туда-обратно) | 3.400.000 VND (Пакет Bus + E-Visa 90 дней) | 4.400.000 VND (Пакет Bus + E-Visa 90 дней + виза Камбоджи за 24ч)",
        "price_en": "1,400,000 VND (Round-trip bus) | 4,000,000 VND (Package: Bus + 90-Day E-Visa) | 4,400,000 VND (Package: Bus + E-Visa + Cambodia 24h Visa)",
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
        "price_vi": "1.200.000 VND (Vé VIP Limousine khứ hồi)",
        "price_ru": "1.200.000 VND (Билет на VIP Лимузин туда и обратно)",
        "price_en": "1,200,000 VND (Round-trip VIP Limousine ticket)",
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
        "price": "1.400.000 VND (Vé xe khứ hồi) | 4.000.000 VND (Combo Bus + E-Visa 90 ngày) | 4.400.000 VND (Combo Bus + E-Visa 90 ngày + Visa Campuchia 24h)",
        "price_vi": "1.400.000 VND (Vé xe khứ hồi) | 4.000.000 VND (Combo Bus + E-Visa 90 ngày) | 4.400.000 VND (Combo Bus + E-Visa 90 ngày + Visa Campuchia 24h)",
        "price_ru": "1.400.000 VND (Билет туда-обратно) | 3.400.000 VND (Пакет Bus + E-Visa 90 дней) | 4.400.000 VND (Пакет Bus + E-Visa 90 дней + виза Камбоджи за 24ч)",
        "price_en": "1,400,000 VND (Round-trip bus) | 4,000,000 VND (Package: Bus + 90-Day E-Visa) | 4,400,000 VND (Package: Bus + E-Visa + Cambodia 24h Visa)",
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
            "⚠️ QUY TẮC ĐĂNG KÝ THEO TỪNG DIỆN (CAMPUCHIA MỘC BÀI):\n"
            "1️⃣ Diện Miễn thị thực 45 ngày: Đặt chỗ trước 24 giờ. Chỉ cần hộ chiếu gốc còn hạn trên 6 tháng.\n"
            "2️⃣ Combo E-Visa 90 ngày thường (4.000.000 VND): Gửi ảnh hộ chiếu + ảnh thẻ 4x6 trước ngày đi 3–5 ngày làm việc.\n"
            "3️⃣ Combo E-Visa hỏa tốc 24 giờ (4.400.000 VND): Đăng ký trước ngày đi 1 ngày. E-Visa được in sẵn trao tận tay tại Mộc Bài lúc 11:30 trưa.\n"
            "4️⃣ Lệ phí visa Campuchia: Chuẩn bị tiền mặt USD (khoảng 35$ - 50$) nộp tại cửa khẩu Campuchia.\n5️⃣ Chính sách trẻ em dưới 9 tuổi: Miễn phí 100% vé xe buýt (0 ₫ khi nằm chung bố mẹ) + E-visa khẩn 1.480.000 ₫ (đăng ký trước 4 ngày).\n\n"
            "👉 Vui lòng chọn ngày đi trên lịch bên dưới (🟢 ngày màu xanh là ngày xe chạy T3, T5, CN) hoặc chọn gói dịch vụ:"
        ),
        "booking_ru": (
            "⚠️ ПРАВИЛА РЕГИСТРАЦИИ ПО КАТЕГОРИЯМ (КАМБОДЖА МОКБАЙ):\n"
            "1️⃣ Безвизовый въезд 45 дней: Бронирование за 24 часа. Нужен только загранпаспорт от 6 месяцев.\n"
            "2️⃣ Стандартный пакет E-Visa 90 дней (4.000.000 VND): Подача фото паспорта и фото 4x6 за 3–5 рабочих дней до поездки.\n"
            "3️⃣ Экспресс-пакет 24 часа (4.400.000 VND): Оформление за 1 день до выезда. E-Visa выдается в распечатанном виде на границе Мокбай в 11:30 утра.\n"
            "4️⃣ Виза Камбоджи: Подготовьте наличные USD (ок. $35 – $50) для оплаты визового сбора на КПП Камбоджи.\n5️⃣ Программа поддержки детей до 9 лет: 100% бесплатный билет на автобус (0 VND) + E-Visa за 1.480.000 VND при регистрации за 4 дня.\n\n"
            "👉 Выберите дату выезда в календаре ниже (🟢 дни рейсов Вт, Чт, Вс) или выберите пакет:"
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
    price = itin.get(f"price_{lang}", itin.get("price_ru" if lang == "ru" else "price"))
    sched = itin.get(f"schedule_{lang}", itin["schedule_vi"])
    pickup = itin.get(f"pickup_{lang}", itin["pickup_vi"])
    border = itin.get(f"border_{lang}", itin["border_vi"])
    booking = itin.get(f"booking_{lang}", itin.get("booking_vi", ""))
    
    booking_section = f"\n\n{booking}" if booking else ""
    
    if lang == "ru":
        return (
            f"📋 {title}\n"
            f"💰 Стоимость: {price}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sched}\n\n"
            f"{pickup}\n\n"
            f"{border}"
            f"{booking_section}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 Следующий шаг:\n"
            "Пожалуйста, нажмите кнопку ниже, чтобы проверить свободные места, выбрать место в автобусе и отправить фото паспорта для бронирования!"
        )
    elif lang == "vi":
        return (
            f"📋 {title}\n"
            f"💰 Chi phí: {itin['price']}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sched}\n\n"
            f"{pickup}\n\n"
            f"{border}"
            f"{booking_section}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 Bước tiếp theo:\n"
            "Vui lòng bấm nút bên dưới để kiểm tra sơ đồ chỗ trống, chọn số ghế trên xe và gửi ảnh Hộ chiếu để chúng tôi giữ chỗ cho bạn!"
        )
    else:
        return (
            f"📋 {title}\n"
            f"💰 Price: {itin['price']}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{sched}\n\n"
            f"{pickup}\n\n"
            f"{border}"
            f"{booking_section}\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "👉 Next step:\n"
            "Please click the button below to check seat availability, select your preferred seat, and send your passport photo to reserve!"
        )

# ============================================================
# MẪU THÔNG TIN THANH TOÁN & BOOKING FINAL & CHÍNH SÁCH HUỶ - HOÀN
# ============================================================


def get_evisa_integrated_calendar_keyboard(year: int, month: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Bàn phím tích hợp E-Visa: Các nút gói dịch vụ khẩn cấp + Lịch chọn ngày trực quan"""
    cal = calendar.monthcalendar(year, month)
    month_names = {
        "ru": ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"],
        "en": ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
        "vi": ["", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"]
    }
    m_name = month_names.get(lang, month_names["en"])[month]
    
    prev_y, prev_m = (year - 1, 12) if month == 1 else (year, month - 1)
    next_y, next_m = (year + 1, 1) if month == 12 else (year, month + 1)
    
    rows = []
    
    # Hàng 1 & 2: Các nút chọn nhanh gói dịch vụ khẩn cấp
    if lang == "ru":
        rows.append([
            InlineKeyboardButton("⚡ 4 часа (В день подачи)", callback_data="step|evisa|calc_stay|1night"),
            InlineKeyboardButton("⏱️ 1 рабочий день", callback_data="step|evisa|calc_stay|2nights")
        ])
        rows.append([
            InlineKeyboardButton("📅 2 рабочих дня", callback_data="step|evisa|calc_stay|3nights"),
            InlineKeyboardButton("🗓️ 3–5 рабочих дней", callback_data="step|evisa|calc_stay|4plus")
        ])
    elif lang == "vi":
        rows.append([
            InlineKeyboardButton("⚡ Gói siêu khẩn 4 Giờ", callback_data="step|evisa|calc_stay|1night"),
            InlineKeyboardButton("⏱️ Gói khẩn 1 Ngày", callback_data="step|evisa|calc_stay|2nights")
        ])
        rows.append([
            InlineKeyboardButton("📅 Gói khẩn 2 Ngày", callback_data="step|evisa|calc_stay|3nights"),
            InlineKeyboardButton("🗓️ Gói thường 3–5 Ngày", callback_data="step|evisa|calc_stay|4plus")
        ])
    else:
        rows.append([
            InlineKeyboardButton("⚡ Same-Day (4 Hours)", callback_data="step|evisa|calc_stay|1night"),
            InlineKeyboardButton("⏱️ 1 Working Day", callback_data="step|evisa|calc_stay|2nights")
        ])
        rows.append([
            InlineKeyboardButton("📅 2 Working Days", callback_data="step|evisa|calc_stay|3nights"),
            InlineKeyboardButton("🗓️ 3–5 Working Days", callback_data="step|evisa|calc_stay|4plus")
        ])

    # Hàng điều hướng lịch tháng
    rows.append([
        InlineKeyboardButton("◀", callback_data=f"step|evisa_cal_nav|{prev_y}|{prev_m}"),
        InlineKeyboardButton(f"📅 {m_name} {year}", callback_data="step|ignore"),
        InlineKeyboardButton("▶", callback_data=f"step|evisa_cal_nav|{next_y}|{next_m}")
    ])
    
    # Header thứ trong tuần
    if lang == "ru":
        days_header = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    elif lang == "vi":
        days_header = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    else:
        days_header = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    rows.append([InlineKeyboardButton(d, callback_data="step|ignore") for d in days_header])
    
    # Bàn cờ các ngày
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
                row.append(InlineKeyboardButton(lbl, callback_data=f"step|evisa_date|{date_str}"))
        rows.append(row)
        
    back_lbl = "🔙 " + ("Назад к услугам" if lang == "ru" else "Quay lại dịch vụ" if lang == "vi" else "Back to Services")
    mgr_lbl = "💬 " + ("Менеджер" if lang == "ru" else "Hỗ trợ" if lang == "vi" else "Support")
    rows.append([
        InlineKeyboardButton(back_lbl, callback_data="step|back|services"),
        InlineKeyboardButton(mgr_lbl, url="https://t.me/easytripvisa_co_ltd")
    ])
    return InlineKeyboardMarkup(rows)


def get_bus_integrated_calendar_keyboard(route_key: str, year: int, month: int, lang: str = "ru") -> InlineKeyboardMarkup:
    """Bàn phím Lịch tháng thông minh cho xe buýt (chỉ tập trung chọn ngày khởi hành, các ngày chạy xe T3, T5, CN được đánh dấu 🟢)"""
    import calendar
    cal = calendar.monthcalendar(year, month)
    
    # Month navigation
    prev_m = 12 if month == 1 else month - 1
    prev_y = year - 1 if month == 1 else year
    next_m = 1 if month == 12 else month + 1
    next_y = year + 1 if month == 12 else year
    
    m_names_ru = ["", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
    m_names_vi = ["", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4", "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8", "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"]
    m_names_en = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    
    m_name = m_names_ru[month] if lang == "ru" else m_names_vi[month] if lang == "vi" else m_names_en[month]
    
    rows = []
    
    # Hàng điều hướng lịch tháng
    rows.append([
        InlineKeyboardButton("◀", callback_data=f"step|bus_cal_nav|{route_key}|{prev_y}|{prev_m}"),
        InlineKeyboardButton(f"📅 {m_name} {year}", callback_data="step|ignore"),
        InlineKeyboardButton("▶", callback_data=f"step|bus_cal_nav|{route_key}|{next_y}|{next_m}")
    ])
    
    # Days header
    if lang == "ru":
        days_header = ["Пн", "Вт*", "Ср", "Чт*", "Пт", "Сб", "Вс*"]
    elif lang == "vi":
        days_header = ["T2", "T3*", "T4", "T5*", "T6", "T7", "CN*"]
    else:
        days_header = ["Mo", "Tu*", "We", "Th*", "Fr", "Sa", "Su*"]
    rows.append([InlineKeyboardButton(d, callback_data="step|ignore") for d in days_header])
    
    # Grid of days (Lào và Campuchia chạy Thứ 3=1, Thứ 5=3, Chủ Nhật=6)
    now = datetime.now()
    for week in cal:
        row = []
        for day_idx, day in enumerate(week):
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="step|ignore"))
            else:
                date_str = f"{day:02d}/{month:02d}"
                is_past = (year < now.year) or (year == now.year and month < now.month) or (year == now.year and month == now.month and day < now.day)
                is_bus_operating = day_idx in (1, 3, 6)
                if is_past:
                    lbl = f"·{day}·"
                elif is_bus_operating:
                    lbl = f"🟢{day}"
                else:
                    lbl = str(day)
                row.append(InlineKeyboardButton(lbl, callback_data=f"step|bus_date|{route_key}|{date_str}"))
        rows.append(row)
        
    back_lbl = "🔙 " + ("Назад к услугам" if lang == "ru" else "Quay lại danh sách" if lang == "vi" else "Back to Services")
    rows.append([
        InlineKeyboardButton(back_lbl, callback_data="step|back|services")
    ])
    return InlineKeyboardMarkup(rows)


def is_russian_speaking_user(country_or_lang: str = "", cust_data: Any = None) -> bool:
    """Kiểm tra xem khách hàng có phải là người Nga hoặc đến từ các quốc gia nói tiếng Nga không"""
    if country_or_lang:
        col = str(country_or_lang).lower().strip()
        if col in ("ru", "cis", "russia", "russian", "belarus", "kazakhstan", "kyrgyzstan", "uzbekistan", "tajikistan"):
            return True
        if any(k in col for k in ["russ", "росс", "nga", "kazakh", "казах", "kyrgyz", "кыргыз", "belarus", "беларус", "uzbek", "узбек", "tajik", "таджик", "cis"]):
            return True
            
    if cust_data and getattr(cust_data, "quoc_tich", None):
        qn = str(cust_data.quoc_tich).lower()
        if any(k in qn for k in ["russ", "росс", "nga", "kazakh", "казах", "kyrgyz", "кыргыз", "belarus", "беларус", "uzbek", "узбек", "tajik", "таджик", "cis"]):
            return True
            
    return False


def calculate_party_pricing(route_key: str, adults: int, kids_under9: int, kids_over9: int, lang: str = "ru", country: str = "") -> dict:
    """Tính toán chi phí minh bạch cho gia đình/nhóm khách:
       - Khách Nga / CIS: 3.400.000 VND / người lớn cho tuyến 90D theo https://www.easytripvisa.com/russian
       - Khách Quốc tế: 4.000.000 VND (Lào 90D) / 4.400.000 VND (Campuchia 90D)
       - Tuyến 45D: 1.400.000 VND
       - Trẻ em dưới 9 tuổi: 100% miễn phí vé xe (0 VND), E-visa khẩn trợ giá 1.480.000 VND (nếu đi 90D)
    """
    is_cambodia = "cambodia" in route_key or "mocbai" in route_key
    is_45d = "45d" in route_key
    is_russian = is_russian_speaking_user(country or lang)
    
    # Giá vé người lớn / trẻ trên 9 tuổi
    if is_45d:
        adult_unit = 1_400_000
        service_title = "45-Day Visa-Free (Miễn thị thực 45 ngày)"
    elif is_russian:
        # Luồng giá riêng cho khách Nga & các nước nói tiếng Nga (3.400.000 VND theo website easytripvisa.com/russian)
        adult_unit = 3_400_000
        service_title = "Nha Trang - Lào Bờ Y / Campuchia 90D (Gói riêng khách nói tiếng Nga 3.400.000 ₫)"
    elif is_cambodia:
        adult_unit = 4_400_000
        service_title = "Cambodia Moc Bai Combo 90D"
    else:
        # Lào Bờ Y 90D khách quốc tế
        adult_unit = 4_000_000
        service_title = "Nha Trang - Laos Bo Y Combo 90D"

    # Trẻ em dưới 9 tuổi: 100% miễn phí vé xe (0 VND), E-visa khẩn trợ giá 1.480.000 VND (nếu đi 90D) hoặc 0 VND (nếu 45D)
    child_unit = 0 if is_45d else 1_480_000
    
    total_adults_count = adults + kids_over9
    total_adults_price = total_adults_count * adult_unit
    total_kids_under9_price = kids_under9 * child_unit
    
    grand_total = total_adults_price + total_kids_under9_price
    bus_ticket_saved = kids_under9 * 1_400_000
    
    return {
        "adult_unit": adult_unit,
        "child_unit": child_unit,
        "total_adults_count": total_adults_count,
        "adults": adults,
        "kids_over9": kids_over9,
        "kids_under9": kids_under9,
        "total_adults_price": total_adults_price,
        "total_kids_under9_price": total_kids_under9_price,
        "grand_total": grand_total,
        "bus_ticket_saved": bus_ticket_saved,
        "service_title": service_title,
        "is_russian": is_russian
    }


def get_party_counter_keyboard(route_key: str, date_val: str, adults: int, kids_under9: int, kids_over9: int, lang: str = "ru", country: str = "") -> InlineKeyboardMarkup:
    """Bàn phím bộ đếm thông minh tăng giảm số lượng thành viên trong gia đình/nhóm"""
    p_info = calculate_party_pricing(route_key, adults, kids_under9, kids_over9, lang=lang, country=country)
    total = p_info["grand_total"]
    
    lbl_adults = "👨 Взрослые" if lang == "ru" else "👨 Người lớn" if lang == "vi" else "👨 Adults"
    lbl_k_over9 = "👦 Дети ≥ 9 лет" if lang == "ru" else "👦 Trẻ em ≥ 9 tuổi" if lang == "vi" else "👦 Kids ≥ 9yo"
    lbl_k_under9 = "👶 Дети < 9 лет" if lang == "ru" else "👶 Trẻ em < 9 tuổi" if lang == "vi" else "👶 Kids < 9yo"
    
    confirm_lbl = f"✅ Подтвердить ({total:,.0f} ₫)" if lang == "ru" else f"✅ Xác nhận ({total:,.0f} ₫)" if lang == "vi" else f"✅ Confirm ({total:,.0f} VND)"
    change_date_lbl = "📅 Сменить дату" if lang == "ru" else "📅 Chọn ngày khác" if lang == "vi" else "📅 Change date"
    
    rows = [
        [
            InlineKeyboardButton(lbl_adults, callback_data="step|ignore"),
            InlineKeyboardButton("➖", callback_data=f"step|party|{route_key}|{date_val}|{max(1, adults-1)}|{kids_under9}|{kids_over9}"),
            InlineKeyboardButton(f" {adults} ", callback_data="step|ignore"),
            InlineKeyboardButton("➕", callback_data=f"step|party|{route_key}|{date_val}|{adults+1}|{kids_under9}|{kids_over9}")
        ],
        [
            InlineKeyboardButton(lbl_k_over9, callback_data="step|ignore"),
            InlineKeyboardButton("➖", callback_data=f"step|party|{route_key}|{date_val}|{adults}|{kids_under9}|{max(0, kids_over9-1)}"),
            InlineKeyboardButton(f" {kids_over9} ", callback_data="step|ignore"),
            InlineKeyboardButton("➕", callback_data=f"step|party|{route_key}|{date_val}|{adults}|{kids_under9}|{kids_over9+1}")
        ],
        [
            InlineKeyboardButton(lbl_k_under9, callback_data="step|ignore"),
            InlineKeyboardButton("➖", callback_data=f"step|party|{route_key}|{date_val}|{adults}|{max(0, kids_under9-1)}|{kids_over9}"),
            InlineKeyboardButton(f" {kids_under9} ", callback_data="step|ignore"),
            InlineKeyboardButton("➕", callback_data=f"step|party|{route_key}|{date_val}|{adults}|{kids_under9+1}|{kids_over9}")
        ],
        [
            InlineKeyboardButton(confirm_lbl, callback_data=f"step|party_confirm|{route_key}|{date_val}|{adults}|{kids_under9}|{kids_over9}")
        ],
        [
            InlineKeyboardButton(change_date_lbl, callback_data=f"step|svc|{route_key}")
        ]
    ]
    return InlineKeyboardMarkup(rows)

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
                "💳 Инструкция по оплате: Vietcombank (VCB)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 Банк: Joint Stock Commercial Bank for Foreign Trade of Viet Nam (Vietcombank)\n"
                "👤 Получатель: EASY TRIP & VISA CO. LTD\n"
                "🔢 Номер счета: `1068582577`\n"
                "🌐 SWIFT-код: `BFTVVNVX`\n"
                "📝 Назначение перевода: `[Имя Фамилия] [Год рождения]`\n"
                "*(Пример: IVANOV 1997)*\n\n"
                "📲 QR-код и реквизиты компании:\n"
                "🏢 Оплата наличными в офисе:\n"
                "📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Карты: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Горячая линия поддержки: +84 85 320 1277\n\n"
                "📸 После перевода отправьте чек в этот чат для подтверждения!"
            )
        elif lang == "vi":
            return (
                "💳 Hướng dẫn chuyển khoản: Vietcombank (VCB)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 Ngân hàng: Ngân hàng TMCP Ngoại thương Việt Nam (Vietcombank)\n"
                "👤 Chủ tài khoản: CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 Số tài khoản: `1068582577`\n"
                "🌐 Mã SWIFT: `BFTVVNVX`\n"
                "📝 Cú pháp nội dung: `[Họ tên khách] [năm sinh]`\n"
                "*(Ví dụ: IVANOV 1997)*\n\n"
                "📲 Mã QR & Thông tin tài khoản:\n"
                "🏢 Thanh toán tiền mặt tại văn phòng:\n"
                "📍 Địa chỉ: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Bản đồ: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Hotline hỗ trợ: +84 85 320 1277\n\n"
                "📸 Quý khách vui lòng gửi ảnh chụp biên lai chuyển khoản vào đây để chúng tôi xác nhận giữ chỗ!"
            )
        else:
            return (
                "💳 Payment Instructions: Vietcombank (VCB)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 Bank: Joint Stock Commercial Bank for Foreign Trade of Viet Nam (Vietcombank)\n"
                "👤 Beneficiary: EASY TRIP & VISA CO. LTD\n"
                "🔢 Account Number: `1068582577`\n"
                "🌐 SWIFT Code: `BFTVVNVX`\n"
                "📝 Transfer Memo: `[Full Name] [Year of Birth]`\n"
                "*(Example: IVANOV 1997)*\n\n"
                "📲 QR Code & Account Details:\n"
                "🏢 Cash Payment at Office:\n"
                "📍 Address: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Map: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Hotline Support: +84 85 320 1277\n\n"
                "📸 Please send your payment receipt in this chat after completing!"
            )

    elif method == "vrb":
        if lang == "ru":
            return (
                "💳 Инструкция по оплате: VRB (Вьетнамско-Российский банк)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 Банк: Вьетнамско-Российский Совместный Банк (Vietnam - Russia Joint Venture Bank - VRB)\n"
                "📍 Филиал: Khánh Hòa (Нячанг)\n"
                "👤 Получатель: CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 Номер счета: `1068582577` (или межбанковский перевод Napas 24/7 на счет VRB)\n"
                "📝 Назначение перевода: `[Имя Фамилия] [Год рождения]`\n"
                "*(Пример: IVANOV 1997)*\n\n"
                "🌟 Преимущества расчетов через VRB:\n"
                "• Прямые взаиморасчеты Россия – Вьетнам (в RUB и VND)\n"
                "• Удобно для переводов картами МИР и через банки-партнеры РФ\n"
                "📲 **Официальный QR-код и реквизиты компании:**\n"
                "🏢 Оплата наличными в офисе:\n"
                "📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Карты: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Горячая линия поддержки: +84 85 320 1277\n\n"
                "📸 **После перевода, пожалуйста, отправьте чек / квитанцию в этот чат!**"
            )
        elif lang == "vi":
            return (
                "💳 Hướng dẫn chuyển khoản: Ngân hàng Liên doanh Việt - Nga (VRB)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 Ngân hàng: Ngân hàng Liên doanh Việt - Nga (VRB)\n"
                "📍 Chi nhánh: Khánh Hòa\n"
                "👤 Chủ tài khoản: CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 Số tài khoản: `1068582577` (hoặc chuyển khoản liên ngân hàng Napas 24/7)\n"
                "📝 Cú pháp nội dung: `[Họ tên khách] [năm sinh]`\n"
                "*(Ví dụ: IVANOV 1997)*\n\n"
                "🌟 Đặc điểm nổi bật của VRB:\n"
                "• Cổng thanh toán song phương trực tiếp Việt Nam – LB Nga (đồng VND & RUB)\n"
                "• Thuận tiện cho kiều bào, du khách Nga sử dụng thẻ MIR và ngân hàng Nga\n"
                "📲 Mã QR & Thông tin tài khoản:\n"
                "🏢 Thanh toán tiền mặt tại văn phòng:\n"
                "📍 Địa chỉ: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Bản đồ: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Hotline hỗ trợ: +84 85 320 1277\n\n"
                "📸 **Quý khách vui lòng gửi ảnh biên lai chuyển khoản vào đây để chúng tôi xác nhận giữ chỗ!**"
            )
        else:
            return (
                "💳 Payment Instructions: VRB Bank\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🏦 Bank: Vietnam - Russia Joint Venture Bank (VRB)\n"
                "📍 Branch: Khanh Hoa\n"
                "👤 Beneficiary: CONG TY TNHH EASY TRIP & VISA\n"
                "🔢 Account Number: `1068582577`\n"
                "📝 Transfer Memo: `[Full Name] [Year of Birth]`\n"
                "*(Example: IVANOV 1997)*\n\n"
                "🌟 VRB Highlights:\n"
                "• Direct bilateral payment gateway between Vietnam & Russia (RUB & VND)\n"
                "• Convenient for Russian payment systems and MIR transactions\n"
                "📲 QR Code & Account Details:\n"
                "🏢 Cash Payment at Office:\n"
                "📍 Address: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "🗺️ Map: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Hotline Support: +84 85 320 1277\n\n"
                "📸 Please send your payment receipt in this chat after completing!"
            )

    else:  # 3. Tiền mặt tại văn phòng ở Nha Trang (step|pay|cash)
        if lang == "ru":
            return (
                "🏢 Оплата наличными в офисе (Нячанг)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📍 Адрес: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "⏰ Время работы: 08:30 – 17:30 (Понедельник – Суббота)\n"
                "🗺️ Карты Google Maps: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Горячая линия поддержки: +84 85 320 1277\n\n"
                "💡 Вы можете подойти в наш офис для оплаты наличными (VND / USD) и личной консультации с нашими сотрудниками!"
            )
        elif lang == "vi":
            return (
                "🏢 Thanh toán tiền mặt tại văn phòng (Nha Trang)\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📍 Địa chỉ: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "⏰ Thời gian làm việc: 08:30 – 17:30 (Thứ 2 đến Thứ 7)\n"
                "🗺️ Bản đồ Google Maps: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Hotline hỗ trợ: +84 85 320 1277\n\n"
                "💡 Quý khách có thể đến trực tiếp văn phòng để đóng tiền mặt và nhận hướng dẫn chi tiết từ chuyên viên phụ trách!"
            )
        else:
            return (
                "🏢 Cash Payment at Nha Trang Office\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "📍 Address: 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
                "⏰ Working Hours: 08:30 AM – 05:30 PM (Monday – Saturday)\n"
                "🗺️ Google Maps: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
                "📞 Hotline Support: +84 85 320 1277\n\n"
                "💡 You are welcome to visit our office in person to pay in cash (VND / USD) and meet our specialists!"
            )

def get_payment_instruction_text(lang: str = "ru") -> str:
    if lang == "ru":
        return (
            "💳 Способы оплаты (Easy Trip & Visa):\n"
            "🏦 1. Vietcombank (VCB): `1068582577` (EASY TRIP & VISA CO. LTD)\n"
            "   📝 Назначение: `[Имя Фамилия] [Год рождения]` (Пример: IVANOV 1997)\n"
            "🏦 2. VRB Bank: `1068582577`\n"
            "   📝 Назначение: `[Имя Фамилия] [Год рождения]` (Пример: IVANOV 1997)\n"
            "🏢 3. Наличными в офисе:\n"
            "   📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
            "   🗺️ Карты: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
            "   📞 Горячая линия: +84 85 320 1277\n\n"
            "📸 После оплаты отправьте квитанцию / чек об оплате в этот чат!"
        )
    elif lang == "vi":
        return (
            "💳 Thông tin thanh toán (Easy Trip & Visa):\n"
            "🏦 1. Vietcombank (VCB): `1068582577` (CONG TY TNHH EASY TRIP & VISA)\n"
            "   📝 Cú pháp nội dung: `[Họ tên khách] [năm sinh]` (Ví dụ: IVANOV 1997)\n"
            "🏦 2. Ngân hàng Việt - Nga (VRB): `1068582577`\n"
            "   📝 Cú pháp nội dung: `[Họ tên khách] [năm sinh]` (Ví dụ: IVANOV 1997)\n"
            "🏢 3. Tiền mặt tại văn phòng:\n"
            "   📍 21 Phan Vinh, Phường Nha Trang, TP. Nha Trang, Khánh Hòa\n"
            "   🗺️ Bản đồ: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n"
            "   📞 Hotline hỗ trợ: +84 85 320 1277\n\n"
            "📸 Quý khách vui lòng gửi ảnh chụp biên lai chuyển khoản vào đây sau khi thanh toán!"
        )
    else:
        return (
            "💳 Payment Details (Easy Trip & Visa):\n"
            "🏦 1. Vietcombank (VCB): `1068582577` (EASY TRIP & VISA CO. LTD)\n"
            "   📝 Memo: `[Full Name] [Year of Birth]` (Example: IVANOV 1997)\n"
            "🏦 2. VRB Bank: `1068582577`\n"
            "   📝 Memo: `[Full Name] [Year of Birth]` (Example: IVANOV 1997)\n"
            "🏢 3. Cash at Office:\n"
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
            "🎉 Бронирование подтверждено! (Easy Trip & Visa)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Пассажир: {ho_ten}\n"
            f"🛂 Гражданство: {quoc_tich}\n"
            f"🚌 Маршрут: {loai_visa}\n"
            f"📅 Дата выезда: {ngay_kh}\n"
            "⏰ Время посадки: 21:00 (Выезд: 21:15 – 21:30)\n"
            f"📍 Точка сбора: {diem_don}\n"
            f"💺 Место в автобусе: {ghe_chon}\n"
            "💰 Статус оплаты: ОПЛАЧЕНО ✅\n\n"
            "ℹ️ Номер автобуса и контакт водителя будут отправлены вам за 2 часа до отправления.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 Правила отмены и возврата средств:\n"
            "1. Билеты на автобус: Отмена или перенос даты ДО 14:00 в день поездки — 100% возврат или бесплатный перенос. Отмена ПОСЛЕ 14:00 или неявка (No-show) — возврат не производится.\n"
            "2. Оформление визы (E-Visa): После подачи документов на официальный портал Иммиграционной службы и оплаты госпошлины — сбор возврату НЕ ПОДЛЕЖИТ. В случае технической ошибки с нашей стороны — 100% возврат.\n"
            "3. Правила безопасности: Курение (включая вейп), провоз алкоголя и запрещенных веществ строго запрещены. Нарушители высаживаются без компенсации.\n\n"
            "📞 Горячая линия поддержки 24/7: +84 85 320 1277\n"
            "Желаем вам приятного и легкого путешествия! 🚌✨"
        )
    elif lang == "vi":
        return (
            "🎉 Xác nhận đặt chỗ thành công! (Easy Trip & Visa)\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Hành khách: {ho_ten}\n"
            f"🛂 Quốc tịch: {quoc_tich}\n"
            f"🚌 Tuyến đi: {loai_visa}\n"
            f"📅 Ngày khởi hành: {ngay_kh}\n"
            "⏰ Giờ tập trung: 21:00 (Khởi hành: 21:15 – 21:30)\n"
            f"📍 Điểm đón: {diem_don}\n"
            f"💺 Số ghế: {ghe_chon}\n"
            "💰 Thanh toán: ĐÃ HOÀN TẤT ✅\n\n"
            "ℹ️ Biển số xe buýt và số điện thoại tài xế sẽ được gửi đến quý khách trước giờ khởi hành 2 tiếng.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "📋 Chính sách hủy vé & hoàn tiền:\n"
            "1. Vé xe buýt: Hủy hoặc đổi lịch TRƯỚC 14:00 ngày khởi hành — hoàn 100% hoặc đổi ngày miễn phí. Hủy SAU 14:00 hoặc không có mặt (No-show) — không hoàn tiền vé xe.\n"
            "2. Dịch vụ Visa / E-Visa: Một khi hồ sơ đã nộp lên Cổng Dịch vụ công Xuất Nhập Cảnh và đóng phí — phí visa không được hoàn lại. Lỗi tính toán từ phía công ty — hoàn tiền 100%.\n"
            "3. An toàn trên xe: Nghiêm cấm hút thuốc/vape, mang chất cấm hoặc gây rối. Vi phạm sẽ bị mời xuống xe tại điểm an toàn gần nhất và không hoàn tiền.\n\n"
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
# BỘ ĐẾM THỜI GIAN & TÍNH TOÁN CẤP E-VISA KHẨN CẤP THÔNG MINH
# (LOẠI TRỪ T7, CN - BẢO TOÀN 90 NGÀY - VÙNG ĐỆM AN TOÀN)
# ============================================================

def add_working_days(start_date: datetime, num_days: int) -> datetime:
    """Cộng thêm số ngày làm việc (bỏ qua Thứ Bảy và Chủ Nhật)."""
    cur = start_date
    added = 0
    while added < num_days:
        cur += timedelta(days=1)
        if cur.weekday() < 5:  # 0=T2, ..., 4=T6
            added += 1
    return cur

def calculate_working_days_between(start_dt: datetime, end_dt: datetime) -> int:
    """Đếm số ngày làm việc giữa 2 ngày (bỏ qua Thứ Bảy và Chủ Nhật)."""
    cur = start_dt.date()
    target = end_dt.date()
    days = 0
    while cur < target:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days

def get_weekday_name(dt: datetime, lang: str = "vi") -> str:
    weekday = dt.weekday()
    names = {
        "vi": ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"],
        "ru": ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"],
        "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    }
    return names.get(lang, names["en"])[weekday]

def calculate_evisa_smart_schedule(
    stay_type: str = None,
    target_date_str: str = None,
    now: datetime = None,
    lang: str = "vi"
) -> dict:
    if not now:
        now = datetime.now()

    submit_dt = now
    if submit_dt.weekday() >= 5:  # T7 hoặc CN
        days_to_monday = 7 - submit_dt.weekday()
        submit_dt = (submit_dt + timedelta(days=days_to_monday)).replace(hour=8, minute=30, second=0)
    elif submit_dt.hour >= 14:
        if stay_type not in ("1night", "4h"):
            submit_dt = add_working_days(submit_dt, 1).replace(hour=8, minute=30, second=0)

    # A. Phân loại theo số đêm lưu trú / gói giờ
    if stay_type:
        if stay_type == "baby_under9":
            delivery_dt = submit_dt.replace(hour=17, minute=30, second=0)
            activation_dt = add_working_days(delivery_dt, 1)
            return {
                "package_id": "urgent_baby_under9",
                "package_name": {
                    "vi": "👶 GÓI E-VISA NHÂN ĐẠO TRẺ EM DƯỚI 9 TUỔI (BABYSITTER VIETNAM)",
                    "ru": "👶 ЛЬГОТНЫЙ ТАРИФ ДЛЯ ДЕТЕЙ ДО 9 ЛЕТ (BABYSITTER VIETNAM)",
                    "en": "👶 SUBSIDIZED E-VISA FOR CHILDREN UNDER 9 (BABYSITTER VIETNAM)"
                },
                "price": "1.480.000 ₫ (Single) | 100% Miễn phí vé xe buýt (0 ₫ khi đi cùng bố mẹ)",
                "submit_time": f"13:30 {get_weekday_name(submit_dt, lang)} ({submit_dt.strftime('%d/%m')})",
                "delivery_time": f"17:30 {get_weekday_name(delivery_dt, lang)} ({delivery_dt.strftime('%d/%m')})",
                "activation_date": f"{activation_dt.strftime('%d/%m/%Y')} ({get_weekday_name(activation_dt, lang)})",
                "buffer_note": {
                    "vi": "💛 Chương trình xã hội Babysitter Vietnam: 100% tài trợ vé xe buýt khứ hồi + E-visa khẩn cấp siêu tốc 3-4 giờ.",
                    "ru": "💛 Гуманитарная программа Babysitter Vietnam: 100% бесплатный билет на автобус + E-Visa за 3-4 часа всего 1.480.000 VND.",
                    "en": "💛 Babysitter Vietnam Social Program: 100% Free sleeper bus ticket + 3-4H urgent E-visa at 1,480,000 VND."
                },
                "validity_note": {
                    "vi": "📌 Điều kiện: Đăng ký trước ngày kích hoạt tối thiểu 4 ngày. Trẻ em nằm chung giường với bố mẹ.",
                    "ru": "📌 Условия: Предварительная регистрация за 4 дня до выезда. Ребенок делит спальное место с родителями.",
                    "en": "📌 Requirements: Advance registration at least 4 days before travel. Child shares sleeper bed with parents."
                }
            }
        if stay_type in ("1night", "4h"):
            delivery_dt = submit_dt.replace(hour=17, minute=30, second=0)
            activation_dt = add_working_days(delivery_dt, 1)
            return {
                "package_id": "urgent_4h",
                "package_name": {
                    "vi": "⚡ GÓI SIÊU KHẨN CẤP 4 GIỜ (SUPER URGENT 4H)",
                    "ru": "⚡ ТАРИФ СУПЕР-СРОЧНЫЙ (ЗА 4 ЧАСА)",
                    "en": "⚡ SUPER URGENT 4-HOUR PACKAGE (SAME DAY)"
                },
                "price": "2.600.000 ₫ (Single) | 3.600.000 ₫ (Multi)",
                "submit_time": f"13:30 {get_weekday_name(submit_dt, lang)} ({submit_dt.strftime('%d/%m')})",
                "delivery_time": f"17:30 {get_weekday_name(delivery_dt, lang)} ({delivery_dt.strftime('%d/%m')})",
                "activation_date": f"{activation_dt.strftime('%d/%m/%Y')} ({get_weekday_name(activation_dt, lang)})",
                "buffer_note": {
                    "vi": "🛡️ Trả visa lúc 17:30 chiều nay -> Khách kịp nhận file trước khi bay về sáng mai, đảm bảo check-in an toàn 100%.",
                    "ru": "🛡️ Готовая виза в 17:30 сегодня -> Вы получаете файл до вылета завтра утром, гарантируя спокойную регистрацию на рейс.",
                    "en": "🛡️ Delivered at 17:30 today -> Issued before tomorrow's return flight, ensuring smooth airport check-in."
                },
                "validity_note": {
                    "vi": "📅 Visa kích hoạt đúng ngày hạ cánh Việt Nam -> Bảo toàn trọn vẹn 90 ngày lưu trú.",
                    "ru": "📅 Виза активируется строго в день прилета -> Полные 90 дней пребывания без потерь.",
                    "en": "📅 Activated on return entry date -> Full 90-day validity preserved."
                }
            }

        elif stay_type == "2nights":
            delivery_dt = add_working_days(submit_dt, 1).replace(hour=17, minute=30, second=0)
            activation_dt = add_working_days(delivery_dt, 1)
            return {
                "package_id": "urgent_1day",
                "package_name": {
                    "vi": "⏱️ GÓI KHẨN CẤP 1 NGÀY LÀM VIỆC (1 WORKING DAY)",
                    "ru": "⏱️ ТАРИФ СРОЧНЫЙ (ЗА 1 ДЕНЬ)",
                    "en": "⏱️ EXPEDITED 1 WORKING DAY PACKAGE"
                },
                "price": "2.200.000 ₫ (Single) | 3.200.000 ₫ (Multi)",
                "submit_time": f"13:30 {get_weekday_name(submit_dt, lang)} ({submit_dt.strftime('%d/%m')})",
                "delivery_time": f"17:30 {get_weekday_name(delivery_dt, lang)} ({delivery_dt.strftime('%d/%m')})",
                "activation_date": f"{activation_dt.strftime('%d/%m/%Y')} ({get_weekday_name(activation_dt, lang)})",
                "buffer_note": {
                    "vi": "🛡️ Nhận visa lúc 17:30 trước ngày bay về 14–16 tiếng -> Vùng đệm an toàn tuyệt đối, phòng ngừa trễ chuyến hoặc nghẽn mạng.",
                    "ru": "🛡️ Выдача в 17:30 накануне вылета (за 14–16 часов) -> Надежный запас времени для посадочных талонов.",
                    "en": "🛡️ Issued at 17:30 the day prior to departure (14-16h buffer) -> Safe buffer against flight delays."
                },
                "validity_note": {
                    "vi": "📅 Kích hoạt đúng ngày nhập cảnh -> Đủ 90 ngày tại Việt Nam (Không tính T7 & CN trong thời gian duyệt).",
                    "ru": "📅 Активация в день въезда -> Полные 90 дней (Сб и Вс не учитываются в сроках).",
                    "en": "📅 Active on entry date -> Full 90 days stay (Excludes Sat & Sun during processing)."
                }
            }

        elif stay_type == "3nights":
            delivery_dt = add_working_days(submit_dt, 2).replace(hour=17, minute=30, second=0)
            activation_dt = add_working_days(delivery_dt, 1)
            return {
                "package_id": "urgent_2days",
                "package_name": {
                    "vi": "📅 GÓI KHẨN CẤP 2 NGÀY LÀM VIỆC (2 WORKING DAYS)",
                    "ru": "📅 ТАРИФ СРОЧНЫЙ (ЗА 2 ДНЯ)",
                    "en": "📅 EXPEDITED 2 WORKING DAYS PACKAGE"
                },
                "price": "2.150.000 ₫ (Single) | 3.150.000 ₫ (Multi)",
                "submit_time": f"13:30 {get_weekday_name(submit_dt, lang)} ({submit_dt.strftime('%d/%m')})",
                "delivery_time": f"17:30 {get_weekday_name(delivery_dt, lang)} ({delivery_dt.strftime('%d/%m')})",
                "activation_date": f"{activation_dt.strftime('%d/%m/%Y')} ({get_weekday_name(activation_dt, lang)})",
                "buffer_note": {
                    "vi": "🛡️ Trả visa lúc 17:30 trước ngày bay về -> Có trọn vẹn 1 buổi tối kiểm tra và in E-visa giấy.",
                    "ru": "🛡️ Выдача в 17:30 за день до вылета -> Спокойный вечер для проверки визы.",
                    "en": "🛡️ Issued at 17:30 before flight day -> Safe buffer to print paper visa."
                },
                "validity_note": {
                    "vi": "📅 Kích hoạt đúng ngày bay về -> Tối đa 90 ngày lưu trú (Bộ đếm trừ T7, CN).",
                    "ru": "📅 Активация в день въезда -> Полные 90 дней (Сб и Вс не считаются).",
                    "en": "📅 Valid from arrival date -> Full 90-day stay preserved."
                }
            }

        else:
            delivery_dt = add_working_days(submit_dt, 3).replace(hour=17, minute=30, second=0)
            activation_dt = add_working_days(delivery_dt, 1)
            return {
                "package_id": "urgent_3days",
                "package_name": {
                    "vi": "🏖️ GÓI TIÊU CHUẨN 3–5 NGÀY LÀM VIỆC (STANDARD EXPEDITED)",
                    "ru": "🏖️ ТАРИФ СТАНДАРТ (ЗА 3–5 ДНЕЙ)",
                    "en": "🏖️ STANDARD 3-5 WORKING DAYS PACKAGE"
                },
                "price": "1.810.000 ₫ (Single) | 2.810.000 ₫ (Multi)",
                "submit_time": f"13:30 {get_weekday_name(submit_dt, lang)} ({submit_dt.strftime('%d/%m')})",
                "delivery_time": f"17:30 {get_weekday_name(delivery_dt, lang)} ({delivery_dt.strftime('%d/%m')})",
                "activation_date": f"{activation_dt.strftime('%d/%m/%Y')} ({get_weekday_name(activation_dt, lang)})",
                "buffer_note": {
                    "vi": "🛡️ Lựa chọn tiết kiệm chi phí nhất khi lưu trú dài ngày ở nước ngoài.",
                    "ru": "🛡️ Самый экономичный тариф при длительном пребывании за границей.",
                    "en": "🛡️ Most cost-effective option for longer overseas stays."
                },
                "validity_note": {
                    "vi": "📅 Kích hoạt đúng ngày bay về -> Đủ 90 ngày (Bộ đếm trừ T7, CN).",
                    "ru": "📅 Активация в день въезда -> Полные 90 дней.",
                    "en": "📅 Valid from arrival date -> Full 90 days stay."
                }
            }

    # B. Phân loại theo ngày mục tiêu khách chọn từ Calendar
    if target_date_str:
        try:
            target_dt = datetime.strptime(target_date_str, "%d/%m/%Y")
        except ValueError:
            target_dt = datetime.strptime(target_date_str, "%d/%m").replace(year=now.year)
        
        work_days = calculate_working_days_between(submit_dt, target_dt)
        if work_days <= 0:
            return calculate_evisa_smart_schedule(stay_type="1night", now=now, lang=lang)
        elif work_days == 1:
            return calculate_evisa_smart_schedule(stay_type="2nights", now=now, lang=lang)
        elif work_days == 2:
            return calculate_evisa_smart_schedule(stay_type="3nights", now=now, lang=lang)
        else:
            return calculate_evisa_smart_schedule(stay_type="4plus", now=now, lang=lang)

    return calculate_evisa_smart_schedule(stay_type="2nights", now=now, lang=lang)

def get_evisa_main_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Bàn phím lựa chọn phân luồng E-visa ban đầu"""
    if lang == "ru":
        btn_flight = "🎫 У меня есть авиабилеты"
        btn_no_flight = "📅 Еще нет билетов / За рубежом"
        btn_quick = "⚡ Срочно в течение дня (4 часа)"
        btn_back = "🔙 Назад к услугам"
    elif lang == "vi":
        btn_flight = "🎫 Tôi đã có vé máy bay"
        btn_no_flight = "📅 Chưa mua vé / Đang ở nước ngoài"
        btn_quick = "⚡ Cần gấp trong ngày (4 Giờ)"
        btn_back = "🔙 Quay lại dịch vụ"
    else:
        btn_flight = "🎫 I have flight tickets"
        btn_no_flight = "📅 No tickets yet / Currently Abroad"
        btn_quick = "⚡ Same Day Urgent (4 Hours)"
        btn_back = "🔙 Back to services"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(btn_flight, callback_data="step|evisa|has_flight")],
        [InlineKeyboardButton(btn_no_flight, callback_data="step|evisa|no_flight")],
        [InlineKeyboardButton(btn_quick, callback_data="step|evisa|quick_4h")],
        [InlineKeyboardButton(btn_back, callback_data="step|back|services")]
    ])

def get_evisa_flight_keyboard(lang: str = "ru") -> InlineKeyboardMarkup:
    """Bàn phím chọn số đêm lưu trú khi khách đã có vé"""
    if lang == "ru":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌙 1 ночь за границей ➜ Тариф 4 Часа", callback_data="step|evisa|calc_stay|1night")],
            [InlineKeyboardButton("🌙 2 ночи за границей ➜ Тариф 1 День", callback_data="step|evisa|calc_stay|2nights")],
            [InlineKeyboardButton("🌙 3 ночи за границей ➜ Тариф 2 Дня", callback_data="step|evisa|calc_stay|3nights")],
            [InlineKeyboardButton("🏖️ 4–5+ ночей ➜ Тариф 3–5 Дней", callback_data="step|evisa|calc_stay|4plus")],
            [InlineKeyboardButton("👶 Ребенок до 9 лет (1.480.000 ₫ + 100% Бесплатный автобус)", callback_data="step|evisa|calc_stay|baby_under9")],
            [InlineKeyboardButton("🔙 Назад", callback_data="step|evisa|main")]
        ])
    elif lang == "vi":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌙 Ở lại 1 đêm ➜ Gói khẩn 4 Giờ", callback_data="step|evisa|calc_stay|1night")],
            [InlineKeyboardButton("🌙 Ở lại 2 đêm ➜ Gói khẩn 1 Ngày", callback_data="step|evisa|calc_stay|2nights")],
            [InlineKeyboardButton("🌙 Ở lại 3 đêm ➜ Gói khẩn 2 Ngày", callback_data="step|evisa|calc_stay|3nights")],
            [InlineKeyboardButton("🏖️ Ở lại 4–5+ đêm ➜ Gói 3–5 Ngày", callback_data="step|evisa|calc_stay|4plus")],
            [InlineKeyboardButton("👶 Trẻ em dưới 9 tuổi (1.480.000 ₫ + Miễn phí 100% xe buýt)", callback_data="step|evisa|calc_stay|baby_under9")],
            [InlineKeyboardButton("🔙 Quay lại", callback_data="step|evisa|main")]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌙 1 night abroad ➜ 4-Hour Package", callback_data="step|evisa|calc_stay|1night")],
            [InlineKeyboardButton("🌙 2 nights abroad ➜ 1-Day Package", callback_data="step|evisa|calc_stay|2nights")],
            [InlineKeyboardButton("🌙 3 nights abroad ➜ 2-Day Package", callback_data="step|evisa|calc_stay|3nights")],
            [InlineKeyboardButton("🏖️ 4–5+ nights ➜ 3–5 Day Package", callback_data="step|evisa|calc_stay|4plus")],
            [InlineKeyboardButton("👶 Child under 9 (1,480,000 VND + 100% Free Bus)", callback_data="step|evisa|calc_stay|baby_under9")],
            [InlineKeyboardButton("🔙 Back", callback_data="step|evisa|main")]
        ])

def generate_evisa_consultation_message(info: dict, lang: str = "ru") -> str:
    """Soạn tin nhắn bảng tư vấn khoa học & minh bạch"""
    pkg_name = info["package_name"].get(lang, info["package_name"]["en"])
    price = info["price"]
    sub_t = info["submit_time"]
    del_t = info["delivery_time"]
    act_d = info["activation_date"]
    buf_n = info["buffer_note"].get(lang, info["buffer_note"]["en"])
    val_n = info["validity_note"].get(lang, info["validity_note"]["en"])

    if lang == "ru":
        return (
            f"⚡ Расчет и план оформления срочной E-Visa\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Рекомендуемый тариф: {pkg_name}\n"
            f"💰 Стоимость оформления: {price}\n\n"
            f"📊 **НАУЧНЫЙ ГРАФИК ОБРАБОТКИ:**\n"
            f"• 🕒 Время подачи документов: {sub_t}\n"
            f"• 🕒 Время выдачи готовой визы: {del_t}\n"
            f"• {buf_n}\n"
            f"• 📅 Дата активации визы: {act_d}\n"
            f"• {val_n}\n"
            f"• 🚫 **Правило выходных:** Суббота и Воскресенье не входят в расчет Иммиграционной службы.\n\n"
            f"📋 **ДОКУМЕНТЫ ДЛЯ СТАРТА ОФОРМЛЕНИЯ:**\n"
            f"1️⃣ Четкое фото страницы загранпаспорта (без бликов, видны 4 угла)\n"
            f"2️⃣ 01 Фото как на паспорт (4x6 см на белом фоне)\n"
            f"3️⃣ Пункт въезда (Аэропорт или наземный КПП)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 Нажмите кнопки ниже для отправки фото или выбора оплаты:"
        )
    elif lang == "vi":
        return (
            f"⚡ Bảng tính toán & kế hoạch cấp E-visa khẩn cấp\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 Gói dịch vụ đề xuất: {pkg_name}\n"
            f"💰 Chi phí trọn gói: {price}\n\n"
            f"📊 Lộ trình xử lý an toàn:\n"
            f"• 🕒 Thời điểm nộp hồ sơ: {sub_t}\n"
            f"• 🕒 Thời điểm trả E-visa: {del_t}\n"
            f"• {buf_n}\n"
            f"• 📅 Ngày kích hoạt E-visa: {act_d}\n"
            f"• {val_n}\n"
            f"• 🚫 Bộ đếm thời gian: Không tính Thứ 7 & Chủ Nhật theo quy định Xuất nhập cảnh.\n\n"
            f"📋 Hồ sơ cần gửi để tiến hành:\n"
            f"1️⃣ Ảnh chụp trang Hộ chiếu (rõ nét, đủ 4 góc)\n"
            f"2️⃣ 01 Ảnh thẻ 4x6 chân dung (nền trắng, chụp thẳng rõ mặt)\n"
            f"3️⃣ Cửa khẩu nhập cảnh (Sân bay hoặc đường bộ)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 Vui lòng gửi ảnh Hộ chiếu hoặc bấm nút thanh toán bên dưới:"
        )
    else:
        return (
            f"⚡ **URGENT E-VISA SCHEDULE & SMART CALCULATION**\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 **Recommended Package:** {pkg_name}\n"
            f"💰 **Official Price:** {price}\n\n"
            f"📊 **SCIENTIFIC PROCESSING TIMELINE:**\n"
            f"• 🕒 **Submission Slot:** {sub_t}\n"
            f"• 🕒 **E-visa Delivery:** {del_t}\n"
            f"• {buf_n}\n"
            f"• 📅 **Effective Entry Date:** {act_d}\n"
            f"• {val_n}\n"
            f"• 🚫 **Weekend Rule:** Saturdays & Sundays are excluded by Immigration.\n\n"
            f"📋 **DOCUMENTS REQUIRED:**\n"
            f"1️⃣ Clear photo of passport info page (4 corners visible)\n"
            f"2️⃣ 4x6 passport photo (white background)\n"
            f"3️⃣ Entry checkpoint (Airport or Border)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 Click buttons below to send passport or proceed to payment:"
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

    # ⚡ BƯỚC XỬ LÝ E-VISA KHẨN CẤP THÔNG MINH (INTERACTIVE BUTTONS & COUNTDOWN)
    if step_type == "evisa":
        action = parts[2]
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        # 1. Menu chính E-visa
        if action == "main":
            intro_msg = {
                "ru": "⚡ Система расчета срочной E-Visa:\nПожалуйста, выберите ваш статус перелета:",
                "vi": "⚡ Tính toán gói E-visa khẩn cấp:\nVui lòng chọn tình trạng chuyến bay của bạn:",
                "en": "⚡ Smart E-Visa Schedule Calculator:\nPlease select your flight status:"
            }
            await send_step_reply(update, context, intro_msg.get(lang, intro_msg["en"]), reply_markup=get_evisa_main_keyboard(lang), parse_mode="Markdown")
            return

        # 2. Khách đã có vé -> Chọn số đêm ở nước ngoài
        elif action == "has_flight":
            stay_msg = {
                "ru": (
                    "✈️ Сколько ночей вы проведете за границей до возвращения во Вьетнам?\n\n"
                    "*(Время пребывания определяет безопасный тариф, чтобы виза была выдана ДО вашей посадки на рейс)*:"
                ),
                "vi": (
                    "✈️ Bạn dự kiến lưu trú ở nước ngoài bao lâu trước khi bay về Việt Nam?\n\n"
                    "*(Thời gian ở nước ngoài quyết định gói E-visa an toàn nhất để visa được cấp TRƯỚC giờ bạn lên máy bay về lại VN)*:"
                ),
                "en": (
                    "✈️ How many nights will you stay abroad before flying back to Vietnam?\n\n"
                    "*(Your stay duration determines the safest package so your visa is issued BEFORE your return flight check-in)*:"
                )
            }
            await send_step_reply(update, context, stay_msg.get(lang, stay_msg["en"]), reply_markup=get_evisa_flight_keyboard(lang), parse_mode="Markdown")
            return

        # 3. Khách chưa có vé / đang ở nước ngoài -> Mở lịch chọn ngày
        elif action == "no_flight":
            cal_msg = {
                "ru": "📅 Выберите дату получения визы / въезда во Вьетнам в календаре:\n*(Умный счетчик автоматически исключит субботу и воскресенье)*:",
                "vi": "📅 Chọn ngày bạn muốn nhận E-visa / dự kiến bay vào Việt Nam trên lịch:\n*(Bộ đếm thông minh sẽ tự động trừ Thứ 7 và Chủ Nhật)*:",
                "en": "📅 Select your desired visa delivery / entry date on the calendar:\n*(The smart counter automatically excludes Saturdays & Sundays)*:"
            }
            now = datetime.now()
            await send_step_reply(update, context, cal_msg.get(lang, cal_msg["en"]), reply_markup=get_calendar_keyboard(now.year, now.month, lang, prefix="step|evisa_date"))
            return

        # 4. Gói khẩn trong ngày (4h)
        elif action == "quick_4h":
            sched = calculate_evisa_smart_schedule(stay_type="1night", lang=lang)
            cust_data.loai_visa = f"Urgent E-Visa (4H Same Day)"
            msg = generate_evisa_consultation_message(sched, lang)
            action_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 " + ("Отправить фото паспорта" if lang == "ru" else "Gửi ảnh Hộ chiếu & Ảnh thẻ" if lang == "vi" else "Send Passport Photo"), callback_data="step|request_seats")],
                [InlineKeyboardButton("💳 " + ("Способы оплаты (VCB, VRB, Офис)" if lang == "ru" else "Phương thức thanh toán (VCB, VRB, VP)" if lang == "vi" else "Payment Methods (VCB, VRB, Office)"), callback_data="step|pay_menu")],
                [InlineKeyboardButton("🔄 " + ("Выбрать другой вариант" if lang == "ru" else "Chọn phương án khác" if lang == "vi" else "Choose another option"), callback_data="step|evisa|main")],
                [InlineKeyboardButton("💬 " + ("Менеджер поддержки" if lang == "ru" else "Chat với nhân viên hỗ trợ" if lang == "vi" else "Support Manager"), url="https://t.me/easytripvisa_co_ltd")]
            ])
            await send_step_reply(update, context, msg, reply_markup=action_kb, parse_mode="Markdown")
            return

        # 5. Tính toán theo số đêm lưu trú
        elif action == "calc_stay":
            stay_key = parts[3]
            sched = calculate_evisa_smart_schedule(stay_type=stay_key, lang=lang)
            pkg_title = sched["package_name"].get(lang, sched["package_name"]["en"])
            cust_data.loai_visa = f"Urgent E-Visa ({pkg_title})"
            msg = generate_evisa_consultation_message(sched, lang)
            action_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📸 " + ("Отправить фото паспорта" if lang == "ru" else "Gửi ảnh Hộ chiếu & Ảnh thẻ" if lang == "vi" else "Send Passport Photo"), callback_data="step|request_seats")],
                [InlineKeyboardButton("💳 " + ("Способы оплаты (VCB, VRB, Офис)" if lang == "ru" else "Phương thức thanh toán (VCB, VRB, VP)" if lang == "vi" else "Payment Methods (VCB, VRB, Office)"), callback_data="step|pay_menu")],
                [InlineKeyboardButton("🔄 " + ("Выбрать другой вариант" if lang == "ru" else "Chọn thời gian khác" if lang == "vi" else "Change selection"), callback_data="step|evisa|has_flight")],
                [InlineKeyboardButton("💬 " + ("Менеджер поддержки" if lang == "ru" else "Chat với nhân viên hỗ trợ" if lang == "vi" else "Support Manager"), url="https://t.me/easytripvisa_co_ltd")]
            ])
            await send_step_reply(update, context, msg, reply_markup=action_kb, parse_mode="Markdown")
            return

    # ⚡ KHÁCH CHỌN NGÀY E-VISA TỪ BỘ LỊCH THÔNG MINH
    elif step_type == "evisa_date":
        target_val = parts[2]
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        if target_val in ("urgent", "manual"):
            sched = calculate_evisa_smart_schedule(stay_type="1night", lang=lang)
        else:
            sched = calculate_evisa_smart_schedule(target_date_str=target_val, lang=lang)
            
        pkg_title = sched["package_name"].get(lang, sched["package_name"]["en"])
        cust_data.loai_visa = f"Urgent E-Visa ({pkg_title})"
        msg = generate_evisa_consultation_message(sched, lang)
        action_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📸 " + ("Отправить фото паспорта" if lang == "ru" else "Gửi ảnh Hộ chiếu & Ảnh thẻ" if lang == "vi" else "Send Passport Photo"), callback_data="step|request_seats")],
            [InlineKeyboardButton("💳 " + ("Способы оплаты (VCB, VRB, Офис)" if lang == "ru" else "Phương thức thanh toán (VCB, VRB, VP)" if lang == "vi" else "Payment Methods (VCB, VRB, Office)"), callback_data="step|pay_menu")],
            [InlineKeyboardButton("🔄 " + ("Выбрать другую дату" if lang == "ru" else "Chọn ngày khác" if lang == "vi" else "Pick another date"), callback_data="step|evisa|no_flight")],
            [InlineKeyboardButton("💬 " + ("Менеджер поддержки" if lang == "ru" else "Chat với nhân viên hỗ trợ" if lang == "vi" else "Support Manager"), url="https://t.me/easytripvisa_co_ltd")]
        ])
        await send_step_reply(update, context, msg, reply_markup=action_kb, parse_mode="Markdown")
        return

    # 🟢 BƯỚC 1 -> BƯỚC 2: Chọn Quốc Gia
    if step_type == "nat":
        val = parts[2]
        if val == "other":
            memory_store[f"{session_id}_waiting_country"] = True
            prompt = (
                "🌐 Пожалуйста, напишите название вашей страны в чате.\n"
                "Наш бот и менеджер мгновенно подберут для вас оптимальный визовый маршрут!\n\n"
                "🌐 Please type your country name in the chat.\n"
                "🌐 Vui lòng nhập tên quốc gia của bạn vào khung chat:"
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
                "ru": f"✅ Гражданство: {cname}\n📍 Город отправления: {c_name_disp}\n\n📅 Выберите дату выезда в календаре:",
                "en": f"✅ Nationality: {cname}\n📍 Departure City: {c_name_disp}\n\n📅 Please pick a departure date on the calendar:",
                "vi": f"✅ Quốc tịch: {cname}\n📍 Thành phố xuất phát: {c_name_disp}\n\n📅 Vui lòng chọn ngày khởi hành trên lịch:"
            }
            keyboard = get_calendar_keyboard(now.year, now.month, lang)
            await send_step_reply(update, context, cal_prompts.get(lang, cal_prompts["en"]), reply_markup=keyboard)
            return

        city_prompts = {
            "ru": f"✅ Гражданство: {cname}\n\n📍 В каком городе Вьетнама вы сейчас находитесь?\n(Или выберите 'За рубежом', если только планируете въезд):",
            "en": f"✅ Nationality: {cname}\n\n📍 Which city in Vietnam are you currently staying in?\n(Or select 'Currently Abroad' if you are planning to enter):",
            "vi": f"✅ Quốc gia: {cname}\n\n📍 Bạn hiện đang ở thành phố nào tại Việt Nam?\n(Hoặc chọn 'Đang ở nước ngoài' nếu sắp bay vào VN):",
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
                "ru": "📍 Пожалуйста, напишите ваш город или текущий адрес в чате.\nНаш бот и команда подберут для вас ближайший пункт отправления и оптимальный трансфер!",
                "en": "📍 Please type your city or address in the chat.\nWe will calculate and suggest the nearest bus pickup location for you!",
                "vi": "📍 Vui lòng nhập tên thành phố hoặc vị trí của bạn vào khung chat.\nChúng tôi sẽ tính toán tuyến xe buýt hoặc phương án đón gần bạn nhất!"
            }
            await send_step_reply(update, context, msg.get(lang, msg["en"]), parse_mode="Markdown")
            return
            
        cust_data.thanh_pho = city_key
        city_obj = CITY_OPTIONS.get(city_key, {})
        cname = city_obj.get(f"name_{lang}", city_key.title())
        
        # Nếu khách đang ở nước ngoài -> Chuyển sang tư vấn dịch vụ nhập cảnh
        if city_key == "abroad":
            svc_prompts = {
                "ru": "✈️ Услуги для въезда во Вьетнам (Easy Trip & Visa):\n(Выберите необходимый сервис):",
                "en": "✈️ Services for Entering Vietnam (Easy Trip & Visa):\n(Please select a service):",
                "vi": "✈️ Dịch vụ nhập cảnh Việt Nam (Easy Trip & Visa):\n(Vui lòng chọn dịch vụ bạn cần):"
            }
            kb = get_smart_advisory_keyboard("abroad", cust_data.quoc_tich or "", lang)
            await send_step_reply(update, context, svc_prompts.get(lang, svc_prompts["en"]), reply_markup=kb, parse_mode="Markdown")
            return
            
        # Ở trong nước -> Mở Lịch tháng tương tác chuẩn quốc tế
        now = datetime.now()
        cal_prompts = {
            "ru": f"✅ Вы выбрали: {cname}\n\n📅 Выберите дату в календаре (когда заканчивается текущая виза hoặc ngày muốn đi):",
            "en": f"✅ Selected: {cname}\n\n📅 Please pick a date on the calendar (your visa expiry date or desired departure date):",
            "vi": f"✅ Điểm khởi hành: {cname}\n\n📅 Vui lòng chọn ngày trên lịch (ngày hết hạn visa hoặc ngày bạn muốn đi):"
        }
        keyboard = get_calendar_keyboard(now.year, now.month, lang)
        await send_step_reply(update, context, cal_prompts.get(lang, cal_prompts["en"]), reply_markup=keyboard, parse_mode="Markdown")
        return

    # 🟢 ĐIỀU HƯỚNG LỊCH THÁNG TÍCH HỢP CHO E-VISA
    elif step_type == "evisa_cal_nav":
        nav_y = int(parts[2])
        nav_m = int(parts[3])
        lang = memory_store.get(f"{session_id}_lang", "en")
        keyboard = get_evisa_integrated_calendar_keyboard(nav_y, nav_m, lang)
        if query and query.message:
            try:
                await query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        return

    # 🟢 ĐIỀU HƯỚNG LỊCH THÁNG TÍCH HỢP CHO XE BUÝT (LÀO / CAMPUCHIA)
    elif step_type == "bus_cal_nav":
        route_key = parts[2]
        nav_y = int(parts[3])
        nav_m = int(parts[4])
        lang = memory_store.get(f"{session_id}_lang", "en")
        keyboard = get_bus_integrated_calendar_keyboard(route_key, nav_y, nav_m, lang)
        if query and query.message:
            try:
                await query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        return

    # 🟢 KHÁCH CHỌN NGÀY TỪ LỊCH XE BUÝT TÍCH HỢP
    elif step_type == "bus_date":
        route_key = parts[2]
        date_val = parts[3]
        lang = memory_store.get(f"{session_id}_lang", "en")
        cust_data.ngay_khoi_hanh = date_val
        cust_data.ngay_het_han_visa = date_val
        
        # Kiểm tra ngày trong tuần (0=T2, 1=T3, 2=T4, 3=T5, 4=T6, 5=T7, 6=CN)
        day_num, month_num = [int(x) for x in date_val.split("/")]
        now_dt = datetime.now()
        cur_year = now_dt.year if month_num >= now_dt.month else now_dt.year + 1
        sel_dt = datetime(cur_year, month_num, day_num)
        is_bus_operating = sel_dt.weekday() in (1, 3, 6)
        
        wk_name = get_weekday_name(sel_dt, lang)
        
        if is_bus_operating:
            # Chuyển sang bước chọn số lượng thành viên trong đoàn / gia đình
            party_msg = {
                "ru": (
                    f"✅ Дата подтверждена: **{date_val}** ({wk_name}) 🚌✨\n"
                    f"Маршрут: {cust_data.loai_visa or 'Visarun'}\n\n"
                    "👨‍👩‍👧 **ВЫБЕРИТЕ СОСТАВ ПАССАЖИРОВ ВАШЕЙ СЕМЬИ / ГРУППЫ:**\n"
                    "• Взрослые и дети от 9 лет: отдельное спальное место + виза\n"
                    "• Дети до 9 лет (Babysitter Vietnam): 100% бесплатный автобус (0 ₫) + субсидированная E-Visa 1.480.000 ₫\n\n"
                    "👉 Нажимайте кнопки ➖ / ➕ ниже для настройки количества участников:"
                ),
                "vi": (
                    f"✅ Xác nhận ngày khởi hành: **{date_val}** ({wk_name}) 🚌✨\n"
                    f"Tuyến xe: {cust_data.loai_visa or 'Visarun'}\n\n"
                    "👨‍👩‍👧 **CHỌN SỐ LƯỢNG THÀNH VIÊN TRONG GIA ĐÌNH / ĐOÀN CỦA BẠN:**\n"
                    "• Người lớn & Trẻ em ≥ 9 tuổi: 1 giường nằm riêng + gói visa\n"
                    "• Trẻ em dưới 9 tuổi (Babysitter Vietnam): Miễn phí 100% vé xe (0 ₫) + E-Visa khẩn trợ giá 1.480.000 ₫\n\n"
                    "👉 Bấm các nút ➖ / ➕ bên dưới để điều chỉnh số lượng thành viên:"
                ),
                "en": (
                    f"✅ Departure Date Confirmed: **{date_val}** ({wk_name}) 🚌✨\n"
                    f"Route: {cust_data.loai_visa or 'Visarun'}\n\n"
                    "👨‍👩‍👧 **SELECT YOUR FAMILY / GROUP PASSENGERS:**\n"
                    "• Adults & Kids ≥ 9yo: Individual sleeper bed + visa\n"
                    "• Kids < 9yo (Babysitter Vietnam): 100% Free Bus (0 VND) + Subsidized E-Visa 1,480,000 VND\n\n"
                    "👉 Use ➖ / ➕ buttons below to adjust passenger count:"
                )
            }
            # Mặc định ban đầu: 1 người lớn, 0 trẻ dưới 9, 0 trẻ trên 9
            kb_party = get_party_counter_keyboard(route_key, date_val, adults=1, kids_under9=0, kids_over9=0, lang=lang, country=cust_data.quoc_tich)
            await send_step_reply(update, context, party_msg.get(lang, party_msg["en"]), reply_markup=kb_party, parse_mode="Markdown")
            return
        else:
            warn_msg = {
                "ru": (
                    f"⚠️ Внимание: **{date_val}** ({wk_name}) — в этот день рейса нет!\n\n"
                    "Автобус по этому маршруту отправляется ТОЛЬКО по **Вторникам (Вт), Четвергам (Чт) и Воскресеньям (Вс)**.\n\n"
                    "Пожалуйста, выберите на календаре зеленую дату (🟢), соответствующую расписанию рейсов:"
                ),
                "vi": (
                    f"⚠️ Lưu ý: Ngày **{date_val}** ({wk_name}) không có chuyến xe chạy!\n\n"
                    "Tuyến xe này chỉ khởi hành cố định vào **Thứ 3, Thứ 5 và Chủ Nhật** hàng tuần.\n\n"
                    "Quý khách vui lòng chọn ngày có chấm xanh (🟢) trên lịch để đảm bảo đúng lịch xe chạy:"
                ),
                "en": (
                    f"⚠️ Notice: **{date_val}** ({wk_name}) is a non-operating day!\n\n"
                    "The bus strictly operates on **Tuesdays, Thursdays, and Sundays**.\n\n"
                    "Please select one of the green dates (🟢) on the calendar:"
                )
            }
            now = datetime.now()
            kb_bus = get_bus_integrated_calendar_keyboard(route_key, now.year, now.month, lang)
            await send_step_reply(update, context, warn_msg.get(lang, warn_msg["en"]), reply_markup=kb_bus, parse_mode="Markdown")
            return

    # 🟢 KHÁCH CHỌN GÓI DỊCH VỤ XE BUÝT CỤ THỂ
    
    # 🟢 BỘ ĐẾM GIA ĐÌNH/NHÓM: ĐIỀU CHỈNH SỐ LƯỢNG THÀNH VIÊN (➖ / ➕)
    elif step_type == "party":
        route_key = parts[2]
        date_val = parts[3]
        adults = int(parts[4])
        kids_under9 = int(parts[5])
        kids_over9 = int(parts[6])
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        kb_party = get_party_counter_keyboard(route_key, date_val, adults, kids_under9, kids_over9, lang=lang, country=cust_data.quoc_tich)
        if query and query.message:
            try:
                await query.message.edit_reply_markup(reply_markup=kb_party)
            except Exception:
                pass
        return

    # 🟢 XÁC NHẬN THÀNH VIÊN ĐOÀN -> TỔNG HỢP CHI PHÍ & CHỜ NHÂN VIÊN GỬI SƠ ĐỒ CHỖ
    elif step_type == "party_confirm":
        route_key = parts[2]
        date_val = parts[3]
        adults = int(parts[4])
        kids_under9 = int(parts[5])
        kids_over9 = int(parts[6])
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        pricing = calculate_party_pricing(route_key, adults, kids_under9, kids_over9, lang=lang, country=cust_data.quoc_tich)
        cust_data.ngay_khoi_hanh = date_val
        
        # Ghi nhận tổng số chỗ cần xếp
        total_seats_needed = adults + kids_over9
        cust_data.ghe_chon = f"Chờ nhân viên gửi sơ đồ ({total_seats_needed} giường người lớn/trẻ lớn + {kids_under9} bé chung giường)"
        
        # Soạn bảng tổng hợp đơn hàng chi tiết & khoa học
        if lang == "ru":
            summary_msg = (
                f"🧾 **СВОДКА БРОНИРОВАНИЯ ДЛЯ СЕМЬИ / ГРУППЫ**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚌 **Маршрут:** {cust_data.loai_visa or 'Visarun'}\n"
                f"📅 **Дата выезда:** {date_val}\n\n"
                f"👥 **Состав пассажиров:**\n"
                f"• 👨 Взрослые: **{adults} чел.** × {pricing['adult_unit']:,.0f} ₫ = **{adults * pricing['adult_unit']:,.0f} ₫**\n"
            )
            if kids_over9 > 0:
                summary_msg += f"• 👦 Дети от 9 лет (отдельное место): **{kids_over9} чел.** × {pricing['adult_unit']:,.0f} ₫ = **{kids_over9 * pricing['adult_unit']:,.0f} ₫**\n"
            if kids_under9 > 0:
                summary_msg += (
                    f"• 👶 Дети до 9 лет (Babysitter Vietnam): **{kids_under9} чел.**\n"
                    f"   └ 🚌 Билет на автобус: **100% БЕСПЛАТНО (0 ₫)** (экономия {kids_under9 * 1_400_000:,.0f} ₫)\n"
                    f"   └ ⚡ E-Visa со скидкой: **{pricing['total_kids_under9_price']:,.0f} ₫**\n"
                )
            summary_msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **ИТОГО К ОПЛАТЕ:** **{pricing['grand_total']:,.0f} VND**\n"
                f"🛏️ **Количество спальных мест на рейсе:** **{total_seats_needed} места**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 **Следующий шаг:**\n"
                f"1️⃣ Наш менеджер прямо сейчас отправит вам актуальную схему свободных мест в автобусе для выбора удобных полок.\n"
                f"2️⃣ Пожалуйста, пришлите в этот чат четкие фото загранпаспортов всех участников поездки.\n"
                f"3️⃣ После согласования мест нажмите кнопку оплаты ниже:"
            )
        elif lang == "vi":
            summary_msg = (
                f"🧾 **BẢNG TỔNG HỢP ĐƠN HÀNG GIA ĐÌNH / ĐOÀN**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚌 **Tuyến dịch vụ:** {cust_data.loai_visa or 'Visarun'}\n"
                f"📅 **Ngày khởi hành:** {date_val}\n\n"
                f"👥 **Chi tiết thành viên & chi phí:**\n"
                f"• 👨 Người lớn: **{adults} khách** × {pricing['adult_unit']:,.0f} ₫ = **{adults * pricing['adult_unit']:,.0f} ₫**\n"
            )
            if kids_over9 > 0:
                summary_msg += f"• 👦 Trẻ em ≥ 9 tuổi (giường riêng): **{kids_over9} bé** × {pricing['adult_unit']:,.0f} ₫ = **{kids_over9 * pricing['adult_unit']:,.0f} ₫**\n"
            if kids_under9 > 0:
                summary_msg += (
                    f"• 👶 Trẻ em < 9 tuổi (Babysitter Vietnam): **{kids_under9} bé**\n"
                    f"   └ 🚌 Vé xe buýt: **100% MIỄN PHÍ (0 ₫)** (tiết kiệm {kids_under9 * 1_400_000:,.0f} ₫)\n"
                    f"   └ ⚡ E-Visa khẩn trợ giá: **{pricing['total_kids_under9_price']:,.0f} ₫**\n"
                )
            summary_msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **TỔNG CỘNG THANH TOÁN:** **{pricing['grand_total']:,.0f} VND**\n"
                f"🛏️ **Tổng số giường nằm cần giữ chỗ:** **{total_seats_needed} giường**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 **Các bước tiếp theo:**\n"
                f"1️⃣ Chuyên viên Easy Trip sẽ gửi ngay sơ đồ chỗ trống mới nhất để quý khách chọn số ghế phù hợp cho gia đình.\n"
                f"2️⃣ Vui lòng gửi ảnh Hộ chiếu của tất cả thành viên vào khung chat này để công ty làm thủ tục.\n"
                f"3️⃣ Sau khi chọn ghế xong, quý khách bấm nút bên dưới để thanh toán:"
            )
        else:
            summary_msg = (
                f"🧾 **FAMILY / GROUP BOOKING SUMMARY**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🚌 **Service Route:** {cust_data.loai_visa or 'Visarun'}\n"
                f"📅 **Departure Date:** {date_val}\n\n"
                f"👥 **Passenger Breakdown:**\n"
                f"• 👨 Adults: **{adults} pax** × {pricing['adult_unit']:,.0f} VND = **{adults * pricing['adult_unit']:,.0f} VND**\n"
            )
            if kids_over9 > 0:
                summary_msg += f"• 👦 Kids ≥ 9yo (Separate Bed): **{kids_over9} pax** × {pricing['adult_unit']:,.0f} VND = **{kids_over9 * pricing['adult_unit']:,.0f} VND**\n"
            if kids_under9 > 0:
                summary_msg += (
                    f"• 👶 Kids < 9yo (Babysitter Vietnam): **{kids_under9} pax**\n"
                    f"   └ 🚌 Bus ticket: **100% FREE (0 VND)** (Saved {kids_under9 * 1_400_000:,.0f} VND)\n"
                    f"   └ ⚡ Subsidized E-Visa: **{pricing['total_kids_under9_price']:,.0f} VND**\n"
                )
            summary_msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 **TOTAL AMOUNT:** **{pricing['grand_total']:,.0f} VND**\n"
                f"🛏️ **Total Sleeper Beds Required:** **{total_seats_needed} beds**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 **Next Steps:**\n"
                f"1️⃣ Our consultant is sending the live bus seat layout for your family to select preferred beds.\n"
                f"2️⃣ Please upload clear passport photos for all passengers in this chat.\n"
                f"3️⃣ Proceed with payment using the buttons below:"
            )
            
        action_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 " + ("Запросить проверку свободных мест в автобусе" if lang == "ru" else "Báo nhân viên kiểm tra vị trí cabin trống" if lang == "vi" else "Notify staff to check vacant cabins"), callback_data=f"step|check_cabins|{route_key}|{date_val}|{adults}|{kids_under9}|{kids_over9}")],
            [InlineKeyboardButton("🔄 " + ("Изменить состав группы" if lang == "ru" else "Thay đổi số lượng người" if lang == "vi" else "Modify party count"), callback_data=f"step|bus_date|{route_key}|{date_val}")],
            [InlineKeyboardButton("💬 " + ("Менеджер поддержки" if lang == "ru" else "Chat với nhân viên hỗ trợ" if lang == "vi" else "Support Manager"), url="https://t.me/easytripvisa_co_ltd")]
        ])
        
        await send_step_reply(update, context, summary_msg, reply_markup=action_kb, parse_mode="Markdown")
        return

    # 🟢 BƯỚC: Báo nhân viên kiểm tra vị trí cabin trống trên xe buýt
    elif step_type == "check_cabins":
        route_key = parts[2] if len(parts) > 2 else "laos_boy_90d"
        date_val = parts[3] if len(parts) > 3 else (cust_data.ngay_khoi_hanh or "")
        adults = int(parts[4]) if len(parts) > 4 else 1
        kids_under9 = int(parts[5]) if len(parts) > 5 else 0
        kids_over9 = int(parts[6]) if len(parts) > 6 else 0
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        pricing = calculate_party_pricing(route_key, adults, kids_under9, kids_over9, lang=lang, country=cust_data.quoc_tich)
        total_seats_needed = adults + kids_over9
        cust_data.ngay_khoi_hanh = date_val
        cust_data.ghe_chon = "Chờ nhân viên gửi sơ đồ ghế / Awaiting Staff Seat Map"
        
        u_name = getattr(update.effective_user, "full_name", "Easy Trip Visa")
        u_handle = getattr(update.effective_user, "username", "")
        user_disp = f"{u_name} (@{u_handle})" if u_handle and u_handle != "N/A" else u_name
        route_disp = cust_data.loai_visa or ("Nha Trang ⇄ Lào Bờ Y (90 Ngày)" if "90" in route_key else "Nha Trang ⇄ Lào Bờ Y (45 Ngày)")
        
        # Lưu thông tin pending booking vào memory_store để bot tự động nhận diện khi khách nhắn số ghế
        memory_store[f"{session_id}_pending_seats"] = {
            "route_key": route_key,
            "route_name": route_disp,
            "date_val": date_val,
            "adults": adults,
            "kids_over9": kids_over9,
            "kids_under9": kids_under9,
            "total_seats_needed": total_seats_needed,
            "grand_total": pricing["grand_total"],
            "pricing": pricing,
            "customer_name": u_name,
            "customer_handle": u_handle
        }
        
        kids_u9_str = f" + {kids_under9} EM BÉ" if kids_under9 > 0 else ""
        kids_u9_ru = f" + {kids_under9} РЕБЕНОК" if kids_under9 > 0 else ""
        kids_u9_en = f" + {kids_under9} INFANT" if kids_under9 > 0 else ""

        members_vi = f"{adults} người lớn"
        if kids_over9 > 0:
            members_vi += f" + {kids_over9} trẻ ≥ 9T"
        if kids_under9 > 0:
            members_vi += f" + {kids_under9} trẻ < 9T"

        members_ru = f"{adults} взр."
        if kids_over9 > 0:
            members_ru += f" + {kids_over9} детей ≥ 9 лет"
        if kids_under9 > 0:
            members_ru += f" + {kids_under9} детей < 9 лет"

        members_en = f"{adults} adults"
        if kids_over9 > 0:
            members_en += f" + {kids_over9} kids ≥ 9yo"
        if kids_under9 > 0:
            members_en += f" + {kids_under9} kids < 9yo"
            
        if lang == "ru":
            wait_msg = (
                f"👨‍👩‍👧 **БРОНИРОВАНИЕ ДЛЯ СЕМЬИ / ГРУППЫ ({total_seats_needed} МЕСТА{kids_u9_ru})**\n"
                f"👤 Представитель: {user_disp}\n"
                f"📍 Маршрут: {route_disp}\n"
                f"📅 Дата выезда: {date_val}\n"
                f"👥 Состав: {members_ru}\n"
                f"💰 Общая сумма: {pricing['grand_total']:,.0f} VND\n\n"
                f"👉 Xin vui lòng đợi một lát chúng tôi đang kiểm tra và sẽ quay trở lại với bạn trong vài phút nữa"
            )
        elif lang == "vi":
            wait_msg = (
                f"👨‍👩‍👧 **KHÁCH ĐẶT ĐOÀN / GIA ĐÌNH ({total_seats_needed} GIƯỜNG{kids_u9_str})**\n"
                f"👤 Đại diện: {user_disp}\n"
                f"📍 Tuyến: {route_disp}\n"
                f"📅 Ngày đi: {date_val}\n"
                f"👥 Thành viên: {members_vi}\n"
                f"💰 Tổng tiền dự kiến: {pricing['grand_total']:,.0f} VND\n\n"
                f"👉 Xin vui lòng đợi một lát chúng tôi đang kiểm tra và sẽ quay trở lại với bạn trong vài phút nữa"
            )
        else:
            wait_msg = (
                f"👨‍👩‍👧 **FAMILY / GROUP BOOKING ({total_seats_needed} BEDS{kids_u9_en})**\n"
                f"👤 Representative: {user_disp}\n"
                f"📍 Route: {route_disp}\n"
                f"📅 Date: {date_val}\n"
                f"👥 Passengers: {members_en}\n"
                f"💰 Estimated Total: {pricing['grand_total']:,.0f} VND\n\n"
                f"👉 Xin vui lòng đợi một lát chúng tôi đang kiểm tra và sẽ quay trở lại với bạn trong vài phút nữa"
            )
            
        wait_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 " + ("Менеджер поддержки" if lang == "ru" else "Chat với nhân viên hỗ trợ" if lang == "vi" else "Support Manager"), url="https://t.me/easytripvisa_co_ltd")],
            [InlineKeyboardButton("🔄 " + ("Выбрать другую дату" if lang == "ru" else "Chọn ngày khác" if lang == "vi" else "Select another date"), callback_data=f"step|bus_pkg|{route_key}")]
        ])
        await send_step_reply(update, context, wait_msg, reply_markup=wait_kb, parse_mode="Markdown")
        
        # Báo ngay vào Admin Group
        from telegram_router import send_to_admin_group
        await send_to_admin_group(
            context,
            f"👨‍👩‍👧 **KHÁCH ĐẶT ĐOÀN / GIA ĐÌNH ({total_seats_needed} GIƯỜNG{kids_u9_str})**\n"
            f"👤 Đại diện: {user_disp}\n"
            f"📍 Tuyến: {route_disp}\n"
            f"📅 Ngày đi: {date_val}\n"
            f"👥 Thành viên: {members_vi}\n"
            f"💰 Tổng tiền dự kiến: {pricing['grand_total']:,.0f} VND\n\n"
            f"👉 HÃY KIỂM TRA CABIN TRỐNG VÀ GỬI ẢNH SƠ ĐỒ GHẾ CHO KHÁCH CHỌN!"
        )
        return

    elif step_type == "bus_pkg":
        pkg_id = parts[2]
        lang = memory_store.get(f"{session_id}_lang", "en")
        
        pkg_names = {
            "laos_bus_only": ("Только билет на автобус Lào Bờ Y (1.400.000 ₫)", "Vé xe giường nằm Lào Bờ Y (1.400.000 ₫)", "Laos Bo Y Round-trip Bus Ticket (1,400,000 VND)"),
            "laos_combo_90d": ("Пакет: Bus + E-Visa 90 дней Lào Bờ Y (3.400.000 ₫)", "Trọn gói: Bus + E-Visa 90 ngày Lào Bờ Y (4.000.000 ₫)", "Combo: Bus + 90-Day E-Visa Laos Bo Y (4,000,000 VND)"),
            "mocbai_bus_only": ("Только билет на автобус Mộc Bài (1.400.000 ₫)", "Vé xe giường nằm Mộc Bài (1.400.000 ₫)", "Moc Bai Round-trip Bus Ticket (1,400,000 VND)"),
            "mocbai_combo_90d": ("Пакет: Bus + E-Visa 90 дней Mộc Bài (3.400.000 ₫)", "Trọn gói: Bus + E-Visa 90 ngày Mộc Bài (4.000.000 ₫)", "Combo: Bus + 90-Day E-Visa Moc Bai (4,000,000 VND)"),
            "mocbai_combo_24h": ("Пакет: Bus + E-Visa 24ч + виза Камбоджи (4.400.000 ₫)", "Trọn gói: Bus + E-Visa 24h + Visa Campuchia (4.400.000 ₫)", "Combo: Bus + 24h E-Visa + Cambodia Visa (4,400,000 VND)"),
            "baby_under9": ("Льготный тариф для детей до 9 лет (1.480.000 ₫ + 100% Бесплатный автобус)", "Ưu đãi trẻ em dưới 9 tuổi (1.480.000 ₫ + Miễn 100% vé xe)", "Subsidized Child Package under 9 (1,480,000 VND + 100% Free Bus)")
        }
        pkg_tuple = pkg_names.get(pkg_id, ("Dịch vụ xe buýt", "Dịch vụ xe buýt", "Bus Service"))
        pkg_name = pkg_tuple[0] if lang == "ru" else pkg_tuple[1] if lang == "vi" else pkg_tuple[2]
        cust_data.loai_visa = pkg_name
        
        now = datetime.now()
        r_key = "laos_boy_90d" if "laos" in pkg_id else "cambodia_mocbai"
        
        cal_prompt = {
            "ru": f"✅ Вы выбрали: **{pkg_name}**\n\n📅 Пожалуйста, выберите дату выезда на календаре ниже (🟢 зеленые даты — дни рейсов Вт, Чт, Вс):",
            "vi": f"✅ Bạn đã chọn: **{pkg_name}**\n\n📅 Vui lòng bấm chọn ngày đi trên lịch bên dưới (🟢 ngày có chấm xanh là ngày xe chạy T3, T5, CN):",
            "en": f"✅ You selected: **{pkg_name}**\n\n📅 Please select your departure date on the calendar below (🟢 green dates = operating days):"
        }
        kb = get_bus_integrated_calendar_keyboard(r_key, now.year, now.month, lang)
        await send_step_reply(update, context, cal_prompt.get(lang, cal_prompt["en"]), reply_markup=kb, parse_mode="Markdown")
        return

    # 🟢 ĐIỀU HƯỚNG LỊCH THÁNG CHUẨN
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
                f"📊 Результат анализа данных для визарана:\n"
                f"• Гражданство: {cname} ({'Безвизовый въезд 45 дней ✅' if exempt else 'Требуется E-Visa 90 дней 📑'})\n"
                f"• Город отправления: {city_key.upper()}\n"
                f"• Дата выезда: {date_val}\n\n"
                "👉 Рекомендованные варианты услуг (выберите подходящий пакет):"
            ),
            "en": (
                f"📊 Visa Run Advisory Summary:\n"
                f"• Nationality: {cname} ({'45-Day Visa-Free Eligible ✅' if exempt else '90-Day E-Visa Required 📑'})\n"
                f"• Departure City: {city_key.upper()}\n"
                f"• Expiry / Departure Date: {date_val}\n\n"
                "👉 Recommended packages (please choose an option):"
            ),
            "vi": (
                f"📊 Kết quả phân tích tư vấn Visarun:\n"
                f"• Quốc tịch: {cname} ({'Được Miễn thị thực 45 ngày ✅' if exempt else 'Cần đăng ký E-Visa 90 ngày 📑'})\n"
                f"• Thành phố xuất phát: {city_key.upper()}\n"
                f"• Ngày hết hạn / khởi hành: **{date_val}**\n\n"
                "👉 Các gói dịch vụ phù hợp nhất (vui lòng chọn gói):"
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
        
        # 1. Xử lý dịch vụ khẩn cấp Urgent E-Visa với Quy tắc đăng ký khoa học + Bàn phím tích hợp Lịch
        if "urgent" in svc_id or svc_id == "special_urgent_evisa":
            cust_data.loai_visa = "Urgent E-Visa"
            now = datetime.now()
            intro_msg = {
                "ru": (
                    "⚡ СИСТЕМА И ПРАВИЛА ОФОРМЛЕНИЯ СРОЧНОЙ E-VISA\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📌 ПРАВИЛА И СРОКИ РАССМОТРЕНИЯ:\n"
                    "• 🚫 Нерабочие дни: Суббота и воскресенье НЕ учитываются в сроках (по регламенту Иммиграционной службы Вьетнама).\n"
                    "• 📅 Сохранение 90 дней: Дата начала действия визы регистрируется точно в день вашего прилета во Вьетнам — вы не теряете ни одного дня пребывания!\n"
                    "• 🛡️ Безопасный буфер: Готовая E-Visa выдается в 17:30 (за 14–16 часов до вылета) для гарантированной защиты от задержек рейсов и сбоев.\n\n"
                    "📊 РЕКОМЕНДУЕМЫЕ ТАРИФЫ:\n"
                    "1. Вылет сегодня/завтра (1 ночь за рубежом) ➜ Тариф 4 часа (выдача в 17:30 сегодня).\n"
                    "2. 2 ночи за рубежом ➜ Тариф 1 рабочий день (выдача в 17:30 следующего рабочего дня).\n"
                    "3. 3 ночи за рубежом ➜ Тариф 2 рабочих дня.\n"
                    "4. 4–5+ ночей ➜ Тариф 3–5 рабочих дней.\n\n"
                    "👉 Выберите тариф вверху или нажмите дату въезда в календаре ниже:"
                ),
                "vi": (
                    "⚡ HỆ THỐNG & QUY TẮC ĐĂNG KÝ E-VISA KHẨN CẤP\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📌 QUY TẮC TÍNH TOÁN & THỜI GIAN DUYỆT:\n"
                    "• 🚫 Loại trừ ngày nghỉ: Thời gian làm việc KHÔNG tính Thứ 7 & Chủ Nhật (theo quy định của Cục Quản lý Xuất nhập cảnh).\n"
                    "• 📅 Bảo toàn đủ 90 ngày: Ngày kích hoạt E-visa được cấp đúng vào ngày chuyến bay hạ cánh nhập cảnh Việt Nam — bạn không bị mất một ngày lưu trú nào!\n"
                    "• 🛡️ Vùng đệm an toàn: E-visa luôn được trả lúc 17:30 của ngày trả (trước giờ bay từ 14–16 tiếng) nhằm đảm bảo an toàn tuyệt đối khi gặp sự cố delay hoặc nghẽn mạng.\n\n"
                    "📊 CÁC GÓI ĐĂNG KÝ PHÙ HỢP:\n"
                    "1. Ở nước ngoài 1 đêm ➜ Gói siêu khẩn 4 Giờ (nhận lúc 17:30 trong ngày).\n"
                    "2. Ở nước ngoài 2 đêm ➜ Gói khẩn 1 Ngày làm việc (nhận lúc 17:30 ngày làm việc tiếp theo).\n"
                    "3. Ở nước ngoài 3 đêm ➜ Gói khẩn 2 Ngày làm việc.\n"
                    "4. Ở nước ngoài 4–5+ đêm ➜ Gói 3–5 Ngày làm việc.\n\n"
                    "👉 Bấm chọn gói dịch vụ bên trên hoặc bấm ngày dự kiến bay vào Việt Nam trên lịch bên dưới:"
                ),
                "en": (
                    "⚡ SMART URGENT E-VISA SCHEDULE & REGISTRATION RULES\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    "📌 IMMIGRATION RULES & TIMELINES:\n"
                    "• 🚫 Weekend Exclusion: Processing time strictly EXCLUDES Saturdays & Sundays (Vietnamese Immigration regulations).\n"
                    "• 📅 Full 90-Day Stay Preserved: Your visa activation date starts exactly on your return flight arrival date — you do not lose a single day!\n"
                    "• 🛡️ Safe Buffer: Visas are delivered at 17:30 on the delivery date (14–16 hours prior to departure) to ensure complete protection against airline delays or system backlogs.\n\n"
                    "📊 RECOMMENDED PACKAGES:\n"
                    "1. 1 night abroad ➜ Super Urgent 4 Hours (delivery at 17:30 same day).\n"
                    "2. 2 nights abroad ➜ Urgent 1 Working Day (delivery at 17:30 next working day).\n"
                    "3. 3 nights abroad ➜ Urgent 2 Working Days.\n"
                    "4. 4–5+ nights ➜ Standard 3–5 Working Days.\n\n"
                    "👉 Select a package above or click your arrival date on the calendar below:"
                )
            }
            kb_integrated = get_evisa_integrated_calendar_keyboard(now.year, now.month, lang)
            await send_step_reply(update, context, intro_msg.get(lang, intro_msg["en"]), reply_markup=kb_integrated, parse_mode="Markdown")
            return
            
        # 2. Xử lý trường hợp VIP Fast Track sân bay
        elif "fasttrack" in svc_id or "fast_track" in svc_id:
            cust_data.loai_visa = "Airport VIP Fast Track"
            fasttrack_msg = {
                "ru": (
                    "✈️ Airport VIP Fast Track (встреча и проход без очередей)\n\n"
                    "💰 Стоимость: 1.200.000 VND / человек\n"
                    "📍 Доступно в аэропортах: Cam Ranh (CXR), Tân Sơn Nhất (SGN), Nội Bài (HAN), Đà Nẵng (DAD)\n\n"
                    "🌟 Привилегии сервиса:\n"
                    "• Персональный ассистент встречает вас у выхода из самолета с именной табличкой\n"
                    "• Проход паспортного контроля через дипломатический коридор (без ожидания в общей очереди)\n"
                    "• Помощь с получением багажа и сопровождение до выхода\n\n"
                    "📋 Для бронирования отправьте в этот чат:\n"
                    "1. Номер рейса и дату/время прилета\n"
                    "2. Фамилию и имя на латинице (как в паспорте)\n"
                    "3. Название аэропорта прилета"
                ),
                "vi": (
                    "✈️ Dịch vụ Airport VIP Fast Track (đón tại cửa máy bay)\n\n"
                    "💰 Chi phí: 1.200.000 ₫ / khách\n"
                    "📍 Áp dụng tại sân bay: Cam Ranh (CXR), Tân Sơn Nhất (SGN), Nội Bài (HAN), Đà Nẵng (DAD)\n\n"
                    "🌟 Quyền lợi dịch vụ:\n"
                    "• Nhân viên đón khách ngay tại cửa ra máy bay với bảng tên riêng\n"
                    "• Dẫn khách qua làn ưu tiên Ngoại Giao / Fast Track không phải xếp hàng chờ đợi\n"
                    "• Hỗ trợ nhận hành lý và dẫn ra xe riêng\n\n"
                    "📋 Thông tin cần gửi vào chat:\n"
                    "1. Số hiệu chuyến bay và ngày giờ hạ cánh\n"
                    "2. Họ tên trên hộ chiếu\n"
                    "3. Sân bay đến"
                ),
                "en": (
                    "✈️ Airport VIP Fast Track Service\n\n"
                    "💰 Price: 1,200,000 VND / pax\n"
                    "📍 Available at: Cam Ranh (CXR), Tan Son Nhat (SGN), Noi Bai (HAN), Da Nang (DAD)\n\n"
                    "🌟 VIP Benefits:\n"
                    "• Personal assistant meets you at the arrival gate with your name board\n"
                    "• Fast-track escort through Diplomatic / Priority lane (skip all queues)\n"
                    "• Baggage collection assistance and escort to exit or driver\n\n"
                    "📋 Please send in this chat:\n"
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
        
        # Lấy bản thông tin lịch trình chi tiết kèm Quy tắc đăng ký
        itin_msg = get_itinerary_message(route_key, lang)
        now = datetime.now()
        
        # Với tuyến xe buýt Nha Trang - Lào và Nha Trang - Campuchia: Sử dụng Bàn phím tích hợp (Nút gói + Lịch xe chạy T3, T5, CN)
        if route_key in ("laos_boy_90d", "cambodia_mocbai", "laos_boy_45d"):
            next_action_kb = get_bus_integrated_calendar_keyboard(route_key, now.year, now.month, lang)
        else:
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
                "⏳ Мы проверяем наличие свободных мест в автобусе...\n\n"
                "📸 Пожалуйста, отправьте фото страницы с информацией загранпаспорта и напишите желаемое место (например: **A2**, **B3**).\n\n"
                + get_payment_instruction_text(lang)
            ),
            "en": (
                "⏳ We are checking seat availability on the bus...\n\n"
                "📸 Please send a clear photo of your passport page and type your preferred seat number (e.g. **A2**, **B3**).\n\n"
                + get_payment_instruction_text(lang)
            ),
            "vi": (
                "⏳ Chúng tôi đang kiểm tra sơ đồ chỗ trống trên xe buýt...\n\n"
                "📸 Quý khách vui lòng chụp gửi ảnh mặt Hộ chiếu và nhắn lại số ghế mong muốn (ví dụ: **A2**, **B3**).\n\n"
                + get_payment_instruction_text(lang)
            )
        }
        kb_pay = get_payment_methods_keyboard(lang)
        await send_step_reply(update, context, seat_req_msg.get(lang, seat_req_msg["en"]), reply_markup=kb_pay, parse_mode="Markdown")
            
        # Ghi nhận trạng thái đang chọn ghế vào CustomerData và phiên chat
        cust_data.ghe_chon = "Chờ khách chọn ghế / Ожидание выбора места"
        memory_store[session_id].append({"role": "assistant", "content": seat_req_msg.get(lang, seat_req_msg["en"])})
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
                    "⚠️ Консультация по просрочке визы (Visa Overstay)\n\n"
                    "Мы зафиксировали ваш запрос! Наша команда помогает легально урегулировать просрочку визы во Вьетнаме, минимизировать штрафы и избежать черного списка.\n\n"
                    "📋 Пожалуйста, отправьте в этот чат:\n"
                    "1. Фото главной страницы загранпаспорта\n"
                    "2. Фото штампа последнего въезда или текущей визы\n"
                    "3. Точную дату окончания срока действия вашей визы\n\n"
                    "Наш специалист по миграционным вопросам ответит вам прямо здесь в течение нескольких минут!\n"
                    "💬 Или свяжитесь напрямую со старшим менеджером: @easytripvisa_co_ltd"
                ),
                "en": (
                    "⚠️ Visa Overstay Consultation & Legal Settlement\n\n"
                    "We have logged your request! Easy Trip Visa assists with legal overstay settlement in Vietnam, minimizing fines and preventing blacklisting.\n\n"
                    "📋 Please send in this chat:\n"
                    "1. Photo of your passport info page\n"
                    "2. Photo of your latest entry stamp or visa sticker\n"
                    "3. The exact date your visa expired\n\n"
                    "Our migration specialist will review and respond directly in this chat shortly!\n"
                    "💬 Or message senior manager directly: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "⚠️ Tư vấn & Xử lý Quá hạn Visa (Visa Overstay)\n\n"
                    "Easy Trip Visa đã tiếp nhận yêu cầu của quý khách! Chúng tôi chuyên xử lý quá hạn visa hợp pháp, giảm thiểu mức phạt và bảo vệ lịch xử xuất nhập cảnh.\n\n"
                    "📋 Quý khách vui lòng gửi vào khung chat này:\n"
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
                    "🪪 Оформление карты временного резидента (TRC на 2 года)\n\n"
                    "Мы зафиксировали ваш запрос на получение TRC (ВНЖ Вьетнама на 2 года)!\n\n"
                    "📋 Пожалуйста, укажите желаемое основание:\n"
                    "• Семейная виза / брак с гражданином Вьетнама (Thăm thân)\n"
                    "• Рабочая виза / официальный контракт с компанией (Work Permit)\n"
                    "• Инвестиции / открытие юридического лица во Вьетнаме\n\n"
                    "Отправьте фото вашего паспорта в этот чат, и юрист Easy Trip Visa подробно проконсультирует вас!\n"
                    "💬 Консультация старшего менеджера: @easytripvisa_co_ltd"
                ),
                "en": (
                    "🪪 2-Year Temporary Residence Card (TRC)\n\n"
                    "We have received your TRC inquiry! A 2-year TRC allows multiple entries and legal stay without visas.\n\n"
                    "📋 Please tell us your intended category:\n"
                    "• Family ties / Marriage with Vietnamese citizen\n"
                    "• Employment / Work Permit sponsor\n"
                    "• Business investment / Company establishment\n\n"
                    "Please send your passport photo in this chat, and our legal advisor will guide you step by step!\n"
                    "💬 Or contact manager: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "🪪 Tư vấn làm Thẻ tạm trú (TRC) thời hạn 2 năm\n\n"
                    "Chúng tôi đã tiếp nhận yêu cầu tư vấn Thẻ tạm trú (TRC 2 năm) của quý khách!\n\n"
                    "📋 Quý khách vui lòng cho biết diện làm hồ sơ:\n"
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
                    "💼 Рабочая виза и разрешение на работу (Work Permit)\n\n"
                    "Мы зафиксировали ваш запрос на оформление Work Permit и рабочей визы!\n\n"
                    "📋 Пожалуйста, уточните детали:\n"
                    "1. Есть ли у вас приглашающая компания/работодатель во Вьетнаме?\n"
                    "2. Ваша специальность, диплом и справка о несудимости?\n\n"
                    "Наш специалист визового отдела свяжется с вами прямо в этом чате в течение нескольких минут!\n"
                    "💬 Связаться с руководителем: @easytripvisa_co_ltd"
                ),
                "en": (
                    "💼 Work Visa & Work Permit\n\n"
                    "We have logged your Work Visa request! Easy Trip Visa provides full sponsorship and work permit processing.\n\n"
                    "📋 Please provide details:\n"
                    "1. Do you have a sponsoring company / employer in Vietnam?\n"
                    "2. Do you have your university degree and criminal record certificate ready?\n\n"
                    "Our corporate visa specialist will assist you directly in this chat shortly!\n"
                    "💬 Or contact manager: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "💼 Tư vấn Visa lao động & Giấy phép lao động\n\n"
                    "Easy Trip Visa đã ghi nhận yêu cầu tư vấn Giấy phép lao động (Work Permit) của quý khách!\n\n"
                    "📋 Quý khách vui lòng cho biết:\n"
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
                    "👨‍👩‍👧 Оформление визы для членов семьи (Family Visit Visa)\n\n"
                    "Мы зафиксировали ваш запрос на оформление семейной визы (TT)!\n\n"
                    "📋 Пожалуйста, подготовьте и отправьте:\n"
                    "1. Фото загранпаспорта заявителя и приглашающего лица\n"
                    "2. Документ о родстве (свидетельство о браке / о рождении с переводом и легализацией)\n\n"
                    "Наш специалист по семейным визам ответит вам в этом чате в течение нескольких минут!\n"
                    "💬 Написать менеджеру: @easytripvisa_co_ltd"
                ),
                "en": (
                    "👨‍👩‍👧 Family Visit / Visitor Visa\n\n"
                    "We have logged your Family Visa request! We assist spouses, children, and parents with family visas in Vietnam.\n\n"
                    "📋 Please prepare:\n"
                    "1. Passport photos of applicant and sponsoring family member\n"
                    "2. Proof of relationship (Marriage certificate / Birth certificate legalized and translated)\n\n"
                    "Our family visa consultant will assist you directly in this chat shortly!\n"
                    "💬 Or message manager: @easytripvisa_co_ltd"
                ),
                "vi": (
                    "👨‍👩‍👧 Tư vấn Visa Thăm thân / Gia đình\n\n"
                    "Easy Trip Visa đã ghi nhận yêu cầu làm Visa thăm thân cho thân nhân gia đình!\n\n"
                    "📋 Quý khách vui lòng chuẩn bị:\n"
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
                "💳 Выберите способ оплаты (Easy Trip & Visa):\n\n"
                "Пожалуйста, выберите подходящий банк для безналичного перевода или вариант оплаты наличными в офисе Нячанга:"
            ),
            "vi": (
                "💳 Chọn phương thức thanh toán (Easy Trip & Visa):\n\n"
                "Quý khách vui lòng chọn ngân hàng chuyển khoản phù hợp hoặc đến văn phòng nộp tiền mặt:"
            ),
            "en": (
                "💳 Select Payment Method (Easy Trip & Visa):\n\n"
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
                    f"📊 Результат подбора визарана:\n"
                    f"• Гражданство: {cname} ({'Безвизовый въезд на 45 дней ✅' if exempt else 'Требуется электронная виза 90 дней 📑'})\n"
                    f"• Город отправления: {city_key.upper()}\n"
                    f"• Дата выезда: {date_val}\n\n"
                    "👉 Доступные пакеты и услуги:"
                ),
                "en": (
                    f"📊 Visa Run Advisory Summary:\n"
                    f"• Nationality: {cname} ({'Visa-Free 45 Days Exempt ✅' if exempt else 'Requires 90-Day E-Visa 📑'})\n"
                    f"• Departure City: {city_key.upper()}\n"
                    f"• Expiry / Departure Date: {date_val}\n\n"
                    "👉 **RECOMMENDED PACKAGES (Choose an option to change):**"
                ),
                "vi": (
                    f"📊 Kết quả phân tích tư vấn Visarun:\n"
                    f"• Quốc tịch: {cname} ({'Được Miễn thị thực 45 ngày ✅' if exempt else 'Cần đăng ký E-Visa 90 ngày 📑'})\n"
                    f"• Thành phố xuất phát: {city_key.upper()}\n"
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
            await send_step_reply(update, context, "🌐 " + ("Выберите страну:" if lang == "ru" else "Chọn lại quốc tịch:" if lang == "vi" else "Choose country:"), reply_markup=keyboard)
            return
            
        # 3. Trở về chọn lại thành phố
        elif back_target == "city":
            keyboard = get_city_keyboard(lang)
            await send_step_reply(update, context, "📍 " + ("Выберите город:" if lang == "ru" else "Chọn lại thành phố:" if lang == "vi" else "Choose city:"), reply_markup=keyboard)
            return
