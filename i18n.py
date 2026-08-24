import re

# Mapping nationality names/keywords to language codes
NATIONALITY_MAP = {
    "ru": ["russian", "russia", "nga", "ru", "rus", "belarus", "ukraine", "kazakhstan", "kyrgyzstan", "uzbekistan"],
    "ko": ["korean", "korea", "hàn quốc", "han quoc", "ko", "kor"],
    "zh": ["chinese", "china", "trung quốc", "trung quoc", "zh", "cn", "taiwan"],
    "vi": ["vietnamese", "vietnam", "việt nam", "viet nam", "vi", "vn"],
    "en": ["english", "american", "british", "australian", "canada", "en", "us", "uk", "germany", "france", "italy", "spain", "europe"]
}

MESSAGES = {
    "en": {
        "welcome": "Welcome to Easy Trip & Visa Assistant! 🚌🌏",
        "system_busy": "Sorry, our system is temporarily busy. Please leave your phone number or contact support!",
        "processing_info": "Sorry, I am processing information, please wait a moment!",
        "payment_confirmed": "✅ Payment received. Thank you! Please send your Passport photo.",
        "image_received": "Received {img_type}! Thank you.",
        "please_pay": "Please pay here ✅",
        "seat_map_caption": "🚌 Seat map for {date}.",
        "seat_map_waiting": "Please wait while we check seat availability and send you the seat map..."
    },
    "vi": {
        "welcome": "Chào mừng bạn đến với Trợ lý Easy Trip & Visa! 🚌🌏",
        "system_busy": "Xin lỗi, hệ thống đang bận. Bạn vui lòng để lại số điện thoại hoặc liên hệ hỗ trợ nhé!",
        "processing_info": "Xin lỗi, tôi đang xử lý thông tin, bạn vui lòng chờ giây lát nhé!",
        "payment_confirmed": "✅ Đã nhận được thanh toán. Cảm ơn bạn! Vui lòng gửi ảnh Hộ chiếu.",
        "image_received": "Đã nhận được {img_type}! Cảm ơn bạn.",
        "please_pay": "Vui lòng thanh toán tại đây ✅",
        "seat_map_caption": "🚌 Sơ đồ ghế cho ngày {date}.",
        "seat_map_waiting": "Vui lòng chờ giây lát để chúng tôi kiểm tra chỗ và gửi sơ đồ ghế cho bạn..."
    },
    "ru": {
        "welcome": "Добро пожаловать в Easy Trip & Visa Assistant! 🚌🌏",
        "system_busy": "Извините, наша система временно занята. Пожалуйста, оставьте свой номер телефона или обратитесь в службу поддержки!",
        "processing_info": "Извините, я обрабатываю информацию, пожалуйста, подождите немного!",
        "payment_confirmed": "✅ Платеж получен. Спасибо! Пожалуйста, пришлите фото вашего паспорта.",
        "image_received": "Получено {img_type}! Спасибо.",
        "please_pay": "Пожалуйста, оплатите здесь ✅",
        "seat_map_caption": "🚌 Схема мест на {date}.",
        "seat_map_waiting": "Пожалуйста, подождите, пока мы проверим наличие мест и вышлем вам схему..."
    },
    "ko": {
        "welcome": "이지트립 & 비자 어시스턴트에 오신 것을 환영합니다! 🚌🌏",
        "system_busy": "죄송합니다. 시스템이 일시적으로 중단되었습니다. 전화번호를 남겨주시거나 고객 센터에 문의해 주세요!",
        "processing_info": "죄송합니다. 정보를 처리 중입니다. 잠시만 기다려 주세요!",
        "payment_confirmed": "✅ 결제가 완료되었습니다. 감사합니다! 여권 사진을 보내주세요.",
        "image_received": "{img_type}을(를) 받았습니다! 감사합니다.",
        "please_pay": "여기에서 결제해 주세요 ✅",
        "seat_map_caption": "{date} 좌석 배치도입니다. 🚌",
        "seat_map_waiting": "좌석 가용성을 확인하고 좌석 배치도를 보내드릴 때까지 잠시만 기다려 주세요..."
    },
    "zh": {
        "welcome": "欢迎使用 Easy Trip & Visa 助手！ 🚌🌏",
        "system_busy": "抱歉，我们的系统暂时繁忙。请留下您的电话号码或联系客服！",
        "processing_info": "抱歉，正在处理信息，请稍候！",
        "payment_confirmed": "✅ 已收到付款。谢谢！请发送您的护照照片。",
        "image_received": "已收到 {img_type}！谢谢。",
        "please_pay": "请在这里支付 ✅",
        "seat_map_caption": "🚌 {date} 的座位图。",
        "seat_map_waiting": "请稍候，我们正在检查座位情况并为您发送座位图..."
    }
}

def get_lang_code(nationality: str) -> str:
    if not nationality:
        return "en"
    
    nat_lower = nationality.lower()
    for code, keywords in NATIONALITY_MAP.items():
        if any(kw in nat_lower for kw in keywords):
            return code
    return "en"

def get_msg(key: str, lang_code: str = "en", **kwargs) -> str:
    lang_msgs = MESSAGES.get(lang_code, MESSAGES["en"])
    msg = lang_msgs.get(key, MESSAGES["en"].get(key, ""))
    if kwargs:
        try:
            return msg.format(**kwargs)
        except Exception:
            pass
    return msg
