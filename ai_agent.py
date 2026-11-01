import os
import re
from datetime import datetime
import httpx
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
from i18n import get_lang_code, get_msg
import knowledge_rag
import customer_memory

load_dotenv()

# === CONFIGURATION ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
groq_raw_keys = f"{os.getenv('GROQ_API_KEYS', '')},{os.getenv('GROQ_API_KEY', '')}"
GROQ_API_KEYS = [
    k.strip() for k in groq_raw_keys.split(",") if k.strip()
]
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPSEEK_MODEL = "deepseek-chat"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")



# === DATA MODELS (Linh hoạt tối đa) ===
class CustomerData(BaseModel):
    model_config = ConfigDict(extra="allow")  # Cho phép mọi field lạ
    ho_ten: str | None = None
    nam_sinh: str | None = None
    quoc_tich: str | None = None
    thanh_pho: str | None = None
    ngay_het_han_visa: str | None = None
    loai_visa: str | None = None
    ngay_khoi_hanh: str | None = None
    ghe_chon: str | None = None
    diem_don: str | None = None
    so_dien_thoai: str | None = None
    agent: str | None = None


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    reply_message: str
    extracted_data: CustomerData = Field(default_factory=CustomerData)
    current_phase: str = "CONSULTING"
    is_complete: bool = False

    @classmethod
    def model_validate_json(cls, json_data: str | bytes | bytearray, *args, **kwargs):
        import json
        import re

        if isinstance(json_data, (bytes, bytearray)):
            json_str = json_data.decode("utf-8")
        else:
            json_str = str(json_data)

        clean_data = json_str.strip()

        # 1. Làm sạch Markdown nếu có
        if "```" in clean_data:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_data, re.DOTALL)
            if match:
                clean_data = match.group(1).strip()

        # 2. Trích xuất phần JSON giữa cặp ngoặc nhọn đầu tiên và cuối cùng
        match_json = re.search(r"(\{.*\})", clean_data, re.DOTALL)
        if match_json:
            clean_data = match_json.group(1).strip()

        # 3. Sửa lỗi dấu phẩy thừa trước ] hoặc }
        clean_data = re.sub(r",\s*([\]}])", r"\1", clean_data)

        data = None
        # Thử parse bằng standard json
        try:
            data = json.loads(clean_data)
        except Exception:
            # Thử parse với strict=False (cho phép newlines và ký tự điều khiển trong chuỗi)
            try:
                data = json.loads(clean_data, strict=False)
            except Exception:
                try:
                    import json_repair
                    data = json_repair.loads(clean_data)
                except Exception as e:
                    print(f"⚠️ JSON repair failed: {e}")

        if isinstance(data, dict):
            if "extracted_data" not in data or not isinstance(data["extracted_data"], dict):
                data["extracted_data"] = {}
                
            # Tự động ánh xạ các field nếu LLM đặt tên khác
            ext = data["extracted_data"]
            if not ext.get("ho_ten") and (data.get("customer_name") or data.get("name")):
                ext["ho_ten"] = str(data.get("customer_name") or data.get("name"))
            if not ext.get("nam_sinh") and (data.get("birth_year") or data.get("year_of_birth")):
                ext["nam_sinh"] = str(data.get("birth_year") or data.get("year_of_birth"))
            if not ext.get("diem_don") and (data.get("pickup_location") or data.get("pickup_address")):
                ext["diem_don"] = str(data.get("pickup_location") or data.get("pickup_address"))
            if not ext.get("loai_visa") and (data.get("visa_package") or data.get("visa_type")):
                ext["loai_visa"] = str(data.get("visa_package") or data.get("visa_type"))
            if not ext.get("ngay_khoi_hanh") and data.get("departure_date"):
                ext["ngay_khoi_hanh"] = str(data.get("departure_date"))
            if not ext.get("so_dien_thoai") and (data.get("phone") or data.get("phone_number")):
                ext["so_dien_thoai"] = str(data.get("phone") or data.get("phone_number"))

            if not data.get("reply_message"):
                data["reply_message"] = data.get("message") or data.get("text") or data.get("notes") or ""

            if data.get("reply_message"):
                return cls.model_validate(data, *args, **kwargs)

        # PHƯƠNG ÁN CỨU HỘ: Trích xuất reply_message từ chuỗi
        msg = ""
        msg_match = re.search(r'"reply_message"\s*:\s*"(.*?)(?:"\s*,\s*"extracted_data"|"\s*,\s*"current_phase"|"\s*\}|$)', json_str, re.DOTALL)
        if msg_match:
            msg = msg_match.group(1).strip()
            msg = msg.replace('\\n', '\n').replace('\\"', '"')
        
        if not msg:
            stripped = json_str.strip()
            stripped = re.sub(r"```(?:json)?|```", "", stripped).strip()
            if len(stripped) > 10:
                clean_text = re.sub(r'["\']?(?:reply_message|current_phase|extracted_data|is_complete)["\']?\s*:\s*', '', stripped)
                clean_text = re.sub(r'[{}"]', '', clean_text).strip()
                if len(clean_text) > 10 and "json_object" not in clean_text.lower():
                    msg = clean_text

        if not msg:
            if any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in json_str) or any(r in json_str.lower() for r in ["russian", "russia", "nga", "ru"]):
                msg = get_msg("processing_info", "ru")
            elif any(v in json_str.lower() for v in ["chào", "giá", "vé", "việt nam"]):
                msg = get_msg("processing_info", "vi")
            elif any(k in json_str.lower() for k in ["korea", "hàn quốc", "ko"]):
                msg = get_msg("processing_info", "ko")
            elif any(z in json_str.lower() for z in ["china", "trung quốc", "zh"]):
                msg = get_msg("processing_info", "zh")
            else:
                msg = get_msg("processing_info", "en")

        return cls(
            reply_message=msg,
            extracted_data=CustomerData(),
            current_phase="CONSULTING",
            is_complete=False,
        )


# === KNOWLEDGE BASE ===
def load_knowledge():
    candidates = [
        os.path.join(os.path.dirname(__file__), "data", "training_knowledge", "knowledge.txt"),
        os.path.join(os.path.dirname(__file__), "knowledge.txt"),
        "data/training_knowledge/knowledge.txt",
        "knowledge.txt",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass
    return ""


KNOWLEDGE_BASE = load_knowledge()

SYSTEM_PROMPT = f"""You are the professional, friendly, and expert AI Assistant for 'Easy Trip & Visa Co. Ltd' (Nha Trang & Da Nang's premier Visarun and Bus service).

CRITICAL OPERATIONS DIRECTIVES (NEVER DEVIATE OR INVENT):
1. **Visa Run Pick-up & Schedule**:
   - The bus to Laos (Bo Y) or Cambodia (Moc Bai) departures are ALWAYS overnight. Departure time from Nha Trang is **21:30** (from 40 Hon Chong) or **21:15** (from No. 4 Tran Phu). We do **NOT** pick up customers in the morning or at 5:00 AM.
   - The bus arrives at the Moc Bai border around **06:00 - 06:30 AM** the next morning.
2. **No Border Guides**:
   - We do **NOT** have guides at the border. Customers must go through the exit/entry gates themselves. The driver will only help collect passports for the Bo Y (Laos) route, but for Cambodia (Moc Bai), the passengers must do it themselves.
3. **Moc Bai Visa Run Process**:
   - Passengers cross into Cambodia around 7:30 - 8:00 AM.
   - Passengers **MUST** take a photo of their Vietnam exit stamp and send it to EasyTrip before **08:00 AM**.
   - We process the emergency e-visa in 4 hours while they wait at a café in Cambodia.
   - The new e-visa is delivered via message/email between **11:30 AM and 12:00 PM**.
4. **Visa Extension (Inside Vietnam)**:
   - Vietnam does **NOT** allow extensions for tourist visas inside the country. Extension is impossible (0 VND / Not available). The customer MUST do a visarun.
5. **Route Eligibility & Official Website Packages (https://www.easytripvisa.com/russian)**:
   - **Laos (Bo Y) Route**: Specifically for citizens EXEMPT from Laos visa (Russia, Belarus, Kazakhstan, South Korea, Japan, ASEAN, etc.). Russian citizens normally take the Laos (Bo Y) route to save costs:
     * **Visarun Free Visa 45 days (Bo Y - Laos)**: **1,400,000 VND** for New Guests (**1,300,000 VND** for Returning Guests). Departs **DAILY** at **21:30** (40 Hon Chong) / **21:15** (04 Tran Phu). (+ 140,000 VND border stamping fee at checkpoint).
     * **Visarun 90D Single Entry E-visa (Bo Y - Laos, 4h urgent)**: **3,400,000 VND** for Russian New Guests (**3,000,000 VND** for Returning Guests; **2,450,000 VND** if submitted >3 days early; **4,000,000 VND** for non-Russian urgent <2 days). Departs **Tuesday, Thursday, Sunday** at **21:30**.
     * **Visarun 90D Multi Entry E-visa (Bo Y - Laos, 4h urgent)**: **4,400,000 VND** for Russian New Guests (**4,000,000 VND** for Returning Guests). Departs **Tuesday, Thursday, Sunday** at **21:30**.
     * **Children under 9 years ("Free for baby's")**: **100% FREE bus ticket (0 VND)** when sharing a cabin bed with parents. Urgent 3-hour E-visa for children under 9 years: **1,480,000 VND**.
   - **Cambodia (Moc Bai) Route**: Departs only on **Tuesdays, Thursdays, and Sundays** at **21:30** (40 Hon Chong) / **21:15** (04 Tran Phu). Required for nationalities NOT exempt from Laos visa (e.g. USA, Canada, Australia, UK, EU, Ukraine, etc.), or available as an all-inclusive package on our website:
     * **Cambodia All-Inclusive Multi Package (Bus + 90D Multi Vietnam E-visa + Cambodia Visa included, 24h processing)**: **5,400,000 VND**.
     * **Cambodia All-Inclusive Single Package (Bus + 90D Single Vietnam E-visa + Cambodia Visa included, 24h processing)**: **4,400,000 VND**.
     * **Cambodia Standard 90D Package (Bus + 90D Vietnam E-visa; customer pays Cambodia visa $35-$50 at border)**: **4,000,000 VND** (**3,550,000 VND** for Returning Guests).
     * **Cambodia 45D Visa-Free Bus Package (Bus only)**: **1,400,000 VND** (**1,300,000 VND** for Returning Guests).
     * 💡 **Helpful Advice Rule**: If a Russian-speaking customer clicks a link for a **Cambodia (Moc Bai)** package (e.g. 5,400,000 VND or 4,400,000 VND), ALWAYS confirm the exact Cambodia package and price they selected first, AND politely inform them that if they hold a **Russian / Belarusian / Kazakh** passport, they are visa-exempt for Laos and can also choose the **Laos (Bo Y)** route which is cheaper (**3,400,000 VND** Single / **4,400,000 VND** Multi / **1,400,000 VND** 45D stamp), or proceed with **Cambodia (Moc Bai)** if they hold another passport (e.g. Ukraine, EU, USA) or prefer Moc Bai!

CRITICAL DIRECTIVE - LANGUAGE & NATIONALITY (MANDATORY):
1. **Rule A (Nationality-based Native Language - HIGHEST PRIORITY)**:
   - If the customer is RUSSIAN / from Russia / Belarus / Kazakhstan / CIS, or has a Russian name (e.g. Tsarenko, Rodichev, Ekaterina, Dmitry, Ivanov, etc.): You MUST ALWAYS REPLY IN RUSSIAN (Русский язык)! NEVER reply in English to a Russian customer, even if they sent a booking message with English terms (like 'Single', 'E-visa', 'Exit Bo Y')!
   - If the customer is VIETNAMESE: You MUST reply in VIETNAMESE (Tiếng Việt)!
   - If the customer is KOREAN: You MUST reply in KOREAN (한국어)!
   - If the customer is CHINESE: You MUST reply in CHINESE (中文)!
2. **Rule B (Default Language for International Guests)**:
   - For all other nationalities (USA, UK, Australia, Germany, France, Canada, Europe, etc.) or when nationality is international: Reply in clear, professional ENGLISH.
3. **RAG Context Language Warning**: You will see 'RELEVANT PAST EXPERIENCE FROM REAL CUSTOMER CHATS' in the prompt, which may be in Vietnamese or Russian. DO NOT copy their language if it differs from the customer's nationality! Always follow Rule A and Rule B.

CRITICAL DIRECTIVE - BUS DEPARTURE SCHEDULING (MANDATORY):
1. **Rule A (Calculated Calendar Priority)**: If the system prompt contains a 'CRITICAL CALENDAR DIRECTIVE' with a 'Calculated correct bus departure date' (e.g. 31/05), you MUST ABSOLUTELY use that exact calculated date as the departure date in your response! Do NOT calculate or suggest any other date (such as 1 day before, or 01/06). The calendar system has calculated the actual bus schedule day, so its output is absolute and overrides all general rules.
2. **Rule B (Weekday Matching)**: You MUST match the weekday name provided in the directive (e.g. Sunday). Do NOT hallucinate weekday names. Do NOT say '01/06 is Sunday' (June 1st is Monday in 2026). Always match the calendar system's provided weekday name.
3. **Rule C (Historical Consistency Override)**: If the customer changes details or you realize you proposed a wrong/hallucinated date earlier, you MUST immediately switch to the new calculated date in the current system prompt. Prioritize current system prompt parameters above all conversation history!

CRITICAL DIRECTIVE - CHAT FORMATTING, SPACING & EMOJIS (MANDATORY TO PREVENT WALLS OF TEXT):
1. **NO WALLS OF TEXT**: NEVER write long, dense, or cluttered paragraphs. A single paragraph MUST NOT exceed 2 short sentences!
2. **CLEAN SPACING**: You MUST use double newlines (\\n\\n) to create clear, spacious spacing between different ideas and sections of your reply.
3. **SPACIOUS ITINERARIES & OPTIONS**: When presenting options, prices, routes, or instructions, you MUST place each detail on a SEPARATE NEW LINE and start with a single appropriate emoji. Never write them in a continuous block of text!
4. **BOLD FOR KEY INFORMATION**: Always use bold markdown (`**bold**`) to highlight key prices, times, dates, and borders (e.g., `**4,000,000 VND**`, `**Cambodia**`, `**31/05 (Sunday)**`).
5. **PROFESSIONAL EMOJI BRANDING**: Use warm and professional emojis (🚌, 💰, 📍, ⏰, 📞, ✅, 📘, 🗺️) to visually structure the text. Avoid using too many random emojis that clutter the screen.

{KNOWLEDGE_BASE}

CORE COMMUNICATION PHILOSOPHY:
- **ALWAYS REPLY IN THE CUSTOMER'S NATIVE LANGUAGE** as defined in the CRITICAL DIRECTIVE above.
- **OFFICIAL PERSONAL SUPPORT CONTACTS (AUTO-SEND WHEN REQUESTED)**: If the customer asks to speak with a human agent/manager, requests direct support, wants manual payment confirmation, or asks for Zalo/WhatsApp/Telegram contact info, you MUST automatically provide these two links and encourage them to click to contact our official support team directly:
  - Telegram Support: https://t.me/easytripvisa_co_ltd
  - WhatsApp Support: https://wa.me/84853201277
  - Zalo Support: https://zalo.me/84853201277
- **INTERACTIVE ONBOARDING TEMPLATE (ONLY FOR BLANK GREETINGS WITHOUT DETAILS)**:
  When a customer sends ONLY a blank greeting (like 'hi', 'hello', 'chào', 'здравствуйте') or asks generally how to book without providing ANY details, warmly introduce our services and provide this easy-to-fill **5-point template** in their native language:
  
  📋 **Quick Booking Template (Mẫu thông tin tư vấn nhanh)**:
  1️⃣ **Nationality (Quốc tịch)**: (e.g. Russia, Vietnam, Korea, USA, Germany...)
  2️⃣ **Visa Expiry Date (Ngày hết hạn visa)**: (e.g. 15/09)
  3️⃣ **Departure City (Thành phố)**: Nha Trang or Da Nang
  4️⃣ **Desired Service (Dịch vụ cần làm)**:
     • Visarun 45-day Visa Free (Laos Bo Y)
     • Visarun 90-day E-visa (Laos Bo Y / Cambodia Moc Bai)
     • Emergency E-visa online (4h / 1-3 days)
     • Airport Fast Track (Cam Ranh / SGN / DAD)
  5️⃣ **Phone / Zalo / WhatsApp (SĐT liên hệ)**
  
  💡 *Example one-line format (Ví dụ gửi 1 dòng):*
  👉 `[Nationality] - [Expiry Date] - [City] - [Service] - [Phone]`

  ⚠️ **CRITICAL RULE**: DO NOT send this 5-point template if the customer has ALREADY stated their needs, answered booking questions, provided their name/year/pickup point, or sent passport/photos!

- **VALUE-FIRST (ADVISE FIRST, PROCEDURES LATER)**: If the customer asks a question (such as prices, schedules, routes, border fees, visa requirements), **immediately and directly answer their question first** clearly, politely, and professionally. Do NOT withhold prices or information until they answer a checklist. Provide value first to build trust!
- **CONTACT NUMBER REQUEST FORMAT (CONCISE & FRIENDLY - NEVER MANDATORY)**:
  When asking the customer for their phone number / contact info, you can politely include:
  • In English: "Could you please share your Phone number / WhatsApp?"
  • In Russian: "Пожалуйста, отправьте ваш контактный номер (WhatsApp / Telegram) 😊"
  • In Vietnamese: "Cho mình xin Số điện thoại / Zalo để liên hệ khi đón xe nhé!"
  • In Korean: "연락 가능한 전화번호 / 카카오톡을 알려주시겠어요? 😊"
  • In Chinese: "请留下您的联系电话 / 微信 / WhatsApp 😊"

- **MANDATORY 2-STEP CONSULTATION & BOOKING WORKFLOW (COLLECT CUSTOMER INFO FIRST -> THEN SEAT MAP)**:
  - **CRITICAL BAN ON HALLUCINATION**: NEVER invent, guess, or assume any customer information! NEVER output placeholder names like `Дмитрий`, placeholder birth years like `1995`, or fake departure dates if the customer has not explicitly provided them!
  - When a customer first messages or clicks a pre-filled service button from our website (e.g. asking to book/consult a Visarun package, E-visa, Fast Track, Motorbike rental, etc.), they have ONLY selected the service name — they have **NOT** provided their personal booking details yet!
  - Therefore, you MUST stay in **PHASE 1 - CONSULTING** (`current_phase = "CONSULTING"`), confirm the service/package details accurately, **send the questions asking for the customer's information, and WAIT for the customer to reply** before moving to `SEAT_SELECTION`!

CONVERSATION PHASES (TECHNICAL STATE MANAGEMENT):

PHASE 1 - CONSULTING (DEFAULT INITIAL PHASE - COLLECT CUSTOMER DETAILS & WAIT FOR REPLY):
- Stay in `current_phase = "CONSULTING"` whenever the customer has NOT yet provided their personal booking details (specifically: **Nationality**, **Visa Expiry Date / Desired Departure Date**, and **Full Name / Year of Birth**).
- In **PHASE 1 - CONSULTING**, your response MUST:
  1. Warmly greet the customer and confirm the exact service/package they asked about (with accurate price, route, and schedule from the website/SOP).
  2. Politely ask the customer to send their information so you can check the schedule / bus seat map or process their booking, and **wait for their reply**:
     • **For Visarun / Bus packages (Laos Bo Y, Cambodia Moc Bai, Da Nang Lao Bao)**, ask for:
       1️⃣ **Гражданство** *(Nationality / Quốc tịch)*
       2️⃣ **Дата окончания текущей визы (или желаемая дата выезда)** *(Current visa expiry date or desired departure date / Ngày hết hạn visa hoặc ngày muốn khởi hành)*
       3️⃣ **Имя и Фамилия (как в загранпаспорте) + Год рождения** *(Full Name + Year of Birth / Họ tên hộ chiếu & Năm sinh)*
       4️⃣ **Точка посадки в Нячанге**: **40 Hon Chong (21:30)** или **04 Tran Phu (21:15)** *(Pickup point / Điểm đón)*
       5️⃣ **Контактный номер телефона (WhatsApp / Telegram)** *(Contact phone number / SĐT liên hệ)*
       *(Note: If the package includes a 90-day E-visa, also mention that they will need to send a clear photo of their passport data page and a portrait photo).*
     • **For Standalone Urgent E-visa (without bus) or Children under 9 E-visa (1,480,000 VND)**, ask for:
       1️⃣ **Гражданство** *(Nationality)*
       2️⃣ **Желаемая дата въезда (или дата окончания текущей визы) и пункт въезда** *(Desired entry date & checkpoint/airport)*
       3️⃣ **Фото паспорта (разворот с данными) и портретное фото** *(Passport data page photo & portrait photo)*
       4️⃣ **Контактный номер телефона / Email**
     • **For Airport Fast Track / Transfer / Motorbike Rental / Other Services**, confirm the exact website price and ask for the relevant details (e.g. Flight number, Arrival/Departure date & time, and Full Name for Fast Track; Rental duration, Start date, and Hotel address for Motorbike Rental).
- Do NOT say you are checking the bus seat map in `PHASE 1 - CONSULTING`! Wait for the customer to reply with their details first.

PHASE 2 - SEAT_SELECTION (ONLY AFTER CUSTOMER REPLIES WITH THEIR BOOKING DETAILS):
- Move to `current_phase = "SEAT_SELECTION"` ONLY AFTER the customer has replied to your questions and provided:
  1) Their **Visa Expiry Date or Desired Departure Date** (so a real departure date `DD/MM` is known), AND
  2) Their **Full Name / Year of Birth** (or passport photo / explicit confirmation of the proposed departure date).
- Never use `SEAT_SELECTION` for non-bus services (like standalone E-visa, Fast Track, or Motorbike rental).
- In **PHASE 2 - SEAT_SELECTION**:
  - Warmly acknowledge the customer's actual details.
  - Present the confirmed booking summary using ONLY the real details provided by the customer:
    - 👤 Full Name & Year of Birth (from customer's reply)
    - 📍 Pickup Location & Departure Time (`40 Hon Chong - 21:30` or `04 Tran Phu - 21:15`)
    - 🚌 Route & Departure Date (format `DD/MM`)
    - 💰 Total Price (accurate price in VND for their selected package)
  - End your reply with the seat map waiting message with the departure date:
    • In Russian: "Пожалуйста, подождите немного — я проверю свободные места в автобусе на **[дата выезда]** и отправлю вам схему свободных мест для выбора через несколько минут! 🚌"
    • In Vietnamese: "Anh/chị vui lòng đợi một chút, em sẽ kiểm tra chỗ trống trên xe buýt vào ngày **[ngày khởi hành]** và gửi cho anh/chị sơ đồ chỗ trống để chọn trong vài phút nữa ạ! 🚌"
    • In English: "Please wait a moment, I will check seat availability on the bus for **[departure date]** and send you the seat map to choose your seat in a few minutes! 🚌"
    • In Korean: "잠시만 기다려 주시면 **[출발일]** 버스의 잔여 좌석을 확인하여 몇 분 내로 좌석 배치도를 보내드리겠습니다! 🚌"
    • In Chinese: "请稍等片刻，我将查询 **[出发日期]** 大巴的空余座位，并在几分钟内为您发送座位图以便您选座！🚌"
  - Set `current_phase = "SEAT_SELECTION"`.
  - Crucial: Populate `extracted_data.ngay_khoi_hanh` with the real departure date (format `DD/MM`, e.g., `"15/11"`) so the system can automatically request the seat map (`Scheme`).

PHASE 3 - PAYMENT:
- Triggered when:
  1) A seat is chosen (e.g. A1, B1, A10, etc.)
  2) OR customer asks how to pay / asks for QR code / bank transfer (e.g. "Как оплатить?", "QR", "Thanh toán như thế nào?", "How to pay?", "Account number", "реквизиты", "оплата").
- Set `current_phase = "PAYMENT"`.
- Provide the official company payment details (translated to the customer's language):
  • In Russian:
    "Пожалуйста, выберите удобный способ оплаты:

    💳 **Банковский перевод / QR-код (VCB OneQR)**:
    🏦 Банк: **Vietcombank (Акционерный коммерческий банк внешней торговли Вьетнама)**
    👤 Получатель: **EASY TRIP & VISA CO. LTD**
    🔢 Номер счета: **1068582577**
    📱 **Оплата по QR-коду**: Официальный QR-код для быстрой оплаты прикреплен ниже. Вы можете просто отсканировать его в банковском приложении!
    📝 Назначение платежа (комментарий): **[Имя_ГодРождения_Место]** (например: `Dmitriy_1995_B1`)

    🏢 **Оплата в офисе**:
    📍 Адрес: 21 Phan Vinh, South Nha Trang
    🗺 Карта: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9

    После совершения оплаты, пожалуйста, пришлите нам квитанцию или скриншот для подтверждения бронирования! 😊"

  • In Vietnamese:
    "Quý khách vui lòng chọn phương thức thanh toán:

    💳 **Chuyển khoản Ngân hàng / Quét mã QR (VCB OneQR)**:
    🏦 Ngân hàng: **Vietcombank**
    👤 Chủ tài khoản: **EASY TRIP & VISA CO. LTD**
    🔢 Số tài khoản: **1068582577**
    📱 **Mã QR**: Mã QR thanh toán chính thức đã được gửi đính kèm bên dưới, quý khách có thể quét trực tiếp trên App ngân hàng.
    📝 Nội dung chuyển khoản: **[Tên_NămSinh_SốGhế]** (Ví dụ: `Hoang_1992_A1`)

    🏢 **Thanh toán trực tiếp tại văn phòng**:
    📍 Địa chỉ: 21 Phan Vinh, Vĩnh Nguyên, Nha Trang
    🗺 Bản đồ: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9

    Sau khi chuyển khoản, quý khách vui lòng gửi ảnh chụp biên lai/bill để em xác nhận và xuất vé nhé! 😊"

  • In English:
    "Please choose your payment method:

    💳 **Bank Transfer / QR Code (VCB OneQR)**:
    🏦 Bank: **Vietcombank (Joint Stock Commercial Bank for Foreign Trade of Viet Nam)**
    👤 Account Name: **EASY TRIP & VISA CO. LTD**
    🔢 Account Number: **1068582577**
    📱 **QR Code**: The official payment QR code is attached below for instant scanning with your banking app.
    📝 Transfer memo / Note: **[Name_BirthYear_Seat]** (e.g. `John_1990_A1`)

    🏢 **Pay in cash at our office**:
    📍 Address: 21 Phan Vinh, South Nha Trang
    🗺 Google Maps: https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9

    After completing payment, please send us the transfer screenshot/receipt so we can confirm your booking immediately! 😊"

- CRITICAL BAN: NEVER output fake URLs (such as https://example.com/qr.png) or fake dummy account numbers (such as 0123456789). Always use the exact Account Number 1068582577.

PHASE 4 - COMPLETED:
- Set when the payment is confirmed and all booking details are complete.

FORMATTING RULES:
- You MUST follow the 'CRITICAL DIRECTIVE - CHAT FORMATTING, SPACING & EMOJIS' strictly.
- Every key detail (Price, Departure, Pickup) MUST have its own line, preceded by an emoji.
- Never merge distinct thoughts into a single dense block of text. Use spacious double newlines.
- Keep responses warm, encouraging, helpful, and highly professional.

OUTPUT: Return ONLY a valid JSON object. No markdown wrapping or conversational text outside the JSON.
{{
  "reply_message": "your warm and helpful response (translated to the customer's language)",
  "extracted_data": {{
    "ho_ten": "...",
    "nam_sinh": "...",
    "quoc_tich": "...",
    "thanh_pho": "...",
    "ngay_het_han_visa": "...",
    "loai_visa": "...",
    "ngay_khoi_hanh": "...",
    "ghe_chon": "...",
    "diem_don": "...",
    "so_dien_thoai": "..."
  }},
  "current_phase": "CONSULTING|SEAT_SELECTION|PAYMENT|COMPLETED",
  "is_complete": false
}}"""


# === AI PROCESSING ===
async def call_deepseek(messages):
    if not DEEPSEEK_API_KEY:
        return None
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.5,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"]
                if raw and raw.strip():
                    return raw
            return None
        except Exception:
            return None


async def call_groq_fallback(messages):
    if not GROQ_API_KEYS:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    SCHEMA_DIRECTIVE = """
CRITICAL BOOKING DIRECTIVE:
- NEVER invent or hallucinate customer names (like Дмитрий), birth years (like 1995), or dates!
- When a customer first clicks a website link or asks about a package without providing their Visa Expiry Date / Departure Date and Full Name, stay in current_phase = "CONSULTING", confirm the package & price, and ask them for their booking details (1. Nationality, 2. Visa expiry date or desired departure date, 3. Full Name & Year of birth, 4. Pickup point: 40 Hon Chong 21:30 or 04 Tran Phu 21:15, 5. Contact phone number).
- ONLY set current_phase = "SEAT_SELECTION" AFTER the customer has replied with their departure/expiry date and name for a bus/visarun trip!
- In SEAT_SELECTION, end your response with: "Пожалуйста, подождите немного — я проверю свободные места в автобусе на [дата] и отправлю вам схему свободных мест для выбора через несколько минут! 🚌" (or translated to customer's language).

OUTPUT SCHEMA: You MUST return strictly a JSON object with these EXACT keys:
{
  "reply_message": "your warm, helpful response in the customer's language",
  "extracted_data": {
    "ho_ten": "...",
    "nam_sinh": "...",
    "quoc_tich": "...",
    "thanh_pho": "...",
    "ngay_het_han_visa": "...",
    "loai_visa": "...",
    "ngay_khoi_hanh": "...",
    "ghe_chon": "...",
    "diem_don": "...",
    "so_dien_thoai": "..."
  },
  "current_phase": "CONSULTING|SEAT_SELECTION|PAYMENT|COMPLETED",
  "is_complete": false
}
"""
    groq_messages = []
    for m in messages:
        if m.get("role") == "system":
            sys_txt = m.get("content", "")
            if len(sys_txt) > 3500:
                sys_txt = sys_txt[:3500]
            sys_txt += "\n\n" + SCHEMA_DIRECTIVE
            groq_messages.append({"role": "system", "content": sys_txt})
        else:
            groq_messages.append(m)

    payload = {
        "model": GROQ_MODEL,
        "messages": groq_messages,
        "response_format": {"type": "json_object"},
        "max_tokens": 800,
    }
    
    # Try each available API key to handle rate limits or transient errors
    for idx, key in enumerate(GROQ_API_KEYS):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            try:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"]
                    if raw and raw.strip():
                        return raw
                else:
                    print(f"⚠️ Groq key {idx+1} failed with status {r.status_code}: {r.text}")
            except Exception as e:
                print(f"⚠️ Groq key {idx+1} exception: {e}")
    return None


async def call_gemini_fallback(messages):
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY.strip())
        model = genai.GenerativeModel(
            "gemini-3.6-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        system_content = ""
        conversation_history = []
        for m in messages:
            if m["role"] == "system":
                system_content += m["content"] + "\n\n"
            elif m["role"] == "assistant":
                conversation_history.append(f"Assistant: {m['content']}")
            elif m["role"] == "user":
                conversation_history.append(f"Customer: {m['content']}")
        
        full_prompt = f"{system_content}CONVERSATION HISTORY:\n" + "\n".join(conversation_history) + "\n\nRespond with ONLY a valid JSON object matching the schema:"
        response = await model.generate_content_async(full_prompt)
        if response and response.text and response.text.strip():
            return response.text.strip()
        return None
    except Exception as e:
        print(f"⚠️ Gemini fallback exception: {e}")
        return None


def calculate_smart_departure_local(ngay_het_han: str, loai_visa: str = "", destination: str = "laos") -> str | None:
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

        latest = exp_dt - timedelta(days=1)
        loai_lower = (loai_visa or "").lower()
        dest_lower = (destination or "").lower()

        # Quy tắc lịch xe:
        # - Chỉ duy nhất tuyến Lào 45 Ngày (Laos 45D) chạy HÀNG NGÀY.
        # - Tuyến 90D/Mộc Bài, 45D/Mộc Bài (Campuchia) và 90D/Lào chỉ chạy tối Thứ 3, Thứ 5, Chủ Nhật.
        is_cambodia = any(k in dest_lower or k in loai_lower for k in ["cambodia", "campuchia", "mộc bài", "moc bai", "mbi", "cam"])
        is_daily = ("45" in loai_lower or "free" in loai_lower) and not is_cambodia and ("90" not in loai_lower)
        if is_daily:
            return latest.strftime("%d/%m")

        valid_days = {1, 3, 6} # Tue=1, Thu=3, Sun=6
        for i in range(7):
            check = latest - timedelta(days=i)
            if check.weekday() in valid_days:
                return check.strftime("%d/%m")
        return latest.strftime("%d/%m")
    except Exception:
        return None

def _is_valid_calendar_date(day_str: str, month_str: str, year_str: str | None = None) -> tuple[bool, str]:
    try:
        d = int(day_str)
        m = int(month_str)
        y = int(year_str) if year_str else datetime.now().year
        if y < 100:
            y += 2000
        if not (1 <= d <= 31 and 1 <= m <= 12 and 2024 <= y <= 2030):
            return False, ""
        # Ignore common non-date ratios like 24/7
        if d == 24 and m == 7 and not year_str:
            return False, ""
        datetime(y, m, d)
        return True, f"{d:02d}/{m:02d}/{y}"
    except Exception:
        return False, ""


def extract_date_and_nationality_from_history(history_messages: list[dict]):
    user_messages = [re.sub(r'\[.*?\]', '', m.get("content", "")) for m in history_messages if m.get("role") == "user"]
    clean_user_text = " ".join(user_messages)
    clean_user_text_lower = clean_user_text.lower()
    full_text = " ".join([m.get("content", "") for m in history_messages])
    full_text_lower = full_text.lower()
    
    # 1. Extract valid expiry/departure date from user messages (search newest first)
    expiry_date = None
    for u_msg in reversed(user_messages):
        for match in re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", u_msg):
            ok, formatted = _is_valid_calendar_date(match.group(1), match.group(2), match.group(3))
            if ok:
                expiry_date = formatted
                break
        if expiry_date:
            break
        
    # 2. Extract destination based on explicit route mentions and nationality
    destination = "laos"
    user_explicit_cambodia = any(
        k in clean_user_text_lower
        for k in ["камбодж", "cambodia", "campuchia", "мокбай", "мок бай", "moc bai", "mộc bài"]
    )
    user_explicit_laos = any(
        k in clean_user_text_lower
        for k in ["лаос", "laos", "lào", "бо й", "bo y", "bờ y", "лаобао", "lao bao", "lao bảo"]
    )
    
    # Russian, CIS, Belarusian, Korean, ASEAN citizens are exempt from Laos visa
    is_laos_exempt = (
        bool(re.search(r'\b(ru|russia|russian|россия|рф|nga|belarus|беларусь|kazakh|kazakhstan|казахстан|cis|kr|korea|korean|hàn quốc)\b', clean_user_text_lower))
        or any(re.search(r'\b' + re.escape(rn) + r'\b', clean_user_text_lower) for rn in [
            "dmitry", "dimitry", "dmitrii", "ivan", "alexey", "sergei", "vladimir", "ekaterina", 
            "elena", "olga", "tatiana", "roman", "andrei", "nikita", "timofei", "tsarenko", "rodichev"
        ])
    )
    
    if user_explicit_cambodia and not user_explicit_laos:
        destination = "cambodia"
    elif not is_laos_exempt:
        cambodia_keywords = [
            "us", "usa", "american", "uk", "british", "germany", "german", "france", "french", 
            "canada", "canadian", "australia", "australian", "india", "indian", "ukraine", "ukrainian",
            "украин", "сша", "великобритан", "герман", "франц", "канад", "австрал",
            "mỹ", "nước anh", "quốc tịch anh", "nước pháp", "nước đức"
        ]
        
        has_cambodia_keyword = False
        for kw in cambodia_keywords:
            if kw in ["us", "uk", "mỹ"]:
                if re.search(r"\b" + re.escape(kw) + r"\b", clean_user_text_lower):
                    has_cambodia_keyword = True
                    break
            else:
                if kw in clean_user_text_lower:
                    has_cambodia_keyword = True
                    break
                    
        if has_cambodia_keyword:
            destination = "cambodia"
        
    # 3. Extract visa type (45D vs 90D)
    visa_type = "90D"  # Default is 90D
    if destination == "laos":
        if "45" in full_text_lower or "free" in full_text_lower or "miễn" in full_text_lower or "безвиз" in full_text_lower:
            visa_type = "45D"
            
    return expiry_date, destination, visa_type


async def process_chat(history_messages: list[dict], customer_profile: dict | None = None) -> ChatResponse:
    recent_history = history_messages[-8:]

    # 1. Tìm ngày hết hạn visa và tính ngày đi bằng Python
    expiry_date, destination, visa_type = extract_date_and_nationality_from_history(history_messages)
    smart_dep = None
    
    # Kế thừa thông tin từ hồ sơ khách cũ nếu tin nhắn hiện tại chưa đề cập
    if customer_profile:
        prof_nat = (customer_profile.get("nationality") or "").lower()
        if not destination or destination == "laos":
            if any(k in prof_nat for k in ["us", "uk", "american", "british", "french", "german", "canadian", "australian", "mỹ", "anh", "pháp", "đức"]):
                destination = "cambodia"
    
    smart_departure_context = ""
    route_directive_context = ""
    
    user_text_all = " ".join([re.sub(r'\[.*?\]', '', m.get("content", "")) for m in history_messages if m.get("role") == "user"]).lower()
    user_explicit_cambodia = any(k in user_text_all for k in ["камбодж", "cambodia", "campuchia", "мокбай", "мок бай", "moc bai", "mộc bài"])

    # Route directives to guide the LLM accurately without overriding explicit customer package requests
    if destination == "cambodia" and user_explicit_cambodia:
        route_directive_context = (
            f"\nCRITICAL ROUTE & PACKAGE DIRECTIVE:\n"
            f"- The customer explicitly asked about the **CAMBODIA (Moc Bai border)** visarun package.\n"
            f"- Confirm the exact Cambodia (Moc Bai) package and price they asked about:\n"
            f"  + **5,400,000 VND**: Bus + 90-day Multi Vietnam E-visa + Cambodia Visa included (24h processing).\n"
            f"  + **4,400,000 VND**: Bus + 90-day Single Vietnam E-visa + Cambodia Visa included (24h processing).\n"
            f"  + **4,000,000 VND**: Bus + 90-day Vietnam E-visa (customer pays Cambodia visa $35-$50 at border).\n"
            f"  + **1,400,000 VND**: Bus only for 45-day Visa-Free stamp.\n"
            f"  + Schedule: Departs Tuesday, Thursday, and Sunday at 21:30 (40 Hon Chong) / 21:15 (04 Tran Phu).\n"
            f"- If they are chatting in Russian and have not stated their nationality yet, also politely add a brief note that if they have a **Russian / Belarusian / Kazakh** passport, they are visa-exempt for Laos and can alternatively choose the **Laos (Bo Y)** route (3,400,000 VND for 90D Single / 4,400,000 VND for 90D Multi / 1,400,000 VND for 45D stamp), or stay with the Cambodia (Moc Bai) package as selected!\n"
            f"- Ask the customer for their booking details (1. Nationality, 2. Current visa expiry date or desired departure date, 3. Full Name + Year of birth, 4. Pickup point in Nha Trang, 5. Contact phone number) and WAIT for their reply!"
        )
    elif destination == "cambodia":
        route_directive_context = (
            f"\nCRITICAL ROUTE DIRECTIVE:\n"
            f"- Customer's nationality requires the **CAMBODIA route (Moc Bai border)** because they are not exempt from Laos visa at Bo Y border.\n"
            f"- Recommend the CAMBODIA route (Moc Bai border) and ask for their booking details if not yet provided."
        )
    else:
        route_directive_context = (
            f"\nCRITICAL ROUTE DIRECTIVE:\n"
            f"- For citizens exempt from Laos visa (Russia, Belarus, Kazakhstan, South Korea, ASEAN), the **LAOS route (Bo Y border)** is the most popular and economical route (1,400,000 VND for 45D Visa-Free; 3,400,000 VND for 90D Single E-visa; 4,400,000 VND for 90D Multi E-visa)."
        )

    if expiry_date:
        smart_dep = calculate_smart_departure_local(expiry_date, visa_type, destination)
        if smart_dep:
            dep_date_parsed = None
            try:
                for fmt in ["%d/%m/%Y", "%d/%m/%y", "%d/%m"]:
                    try:
                        dep_date_parsed = datetime.strptime(f"{smart_dep}/{datetime.now().year}", f"%d/%m/%Y")
                        break
                    except: pass
            except: pass
            
            day_name_en = ""
            day_name_vi = ""
            if dep_date_parsed:
                wd = dep_date_parsed.weekday()
                days_en = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                days_vi = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
                day_name_en = days_en[wd]
                day_name_vi = days_vi[wd]

            smart_departure_context = (
                f"\nCRITICAL CALENDAR DIRECTIVE:\n"
                f"- Customer's visa expiry date is: {expiry_date[:5]}\n"
                f"- Calculated correct bus departure date: {smart_dep} ({day_name_en} / {day_name_vi})\n"
                f"- Operating Schedule Rules:\n"
                f"  + Laos 45D: runs DAILY every night.\n"
                f"  + Laos 90D, Cambodia/Moc Bai 90D, and Cambodia/Moc Bai 45D: run ONLY on Tuesday, Thursday, and Sunday nights.\n"
                f"- To avoid overstaying, the bus departure date must be exactly {smart_dep} ({day_name_en}).\n"
                f"- YOU MUST propose exactly the date '{smart_dep}' ({day_name_en}) as their departure date in your response! Do NOT suggest any other date. Clearly state this date to the customer and explain that the bus departs on this day."
            )

    # 2. Đoán ngôn ngữ đích bằng Python dựa trên quốc tịch / tin nhắn / tên / hồ sơ khách cũ
    user_text = " ".join([m["content"] for m in history_messages if m.get("role") == "user"])
    # Loại bỏ các tag hệ thống trong ngoặc vuông trước khi nhận diện ngôn ngữ
    clean_user_text = re.sub(r'\[.*?\]', '', user_text)
    clean_user_text_lower = clean_user_text.lower()
    
    # Check Russian indicators:
    # 1. Cyrillic characters
    # 2. Russian nationality keywords
    # 3. Common Russian/Slavic names
    russian_name_keywords = [
        "dmitry", "dimitry", "dmitrii", "dmitri", "ivan", "alexey", "aleksei", "alexander", 
        "sergei", "sergey", "vladimir", "ekaterina", "elena", "olga", "tatiana", "tatyana", 
        "roman", "andrei", "andrey", "nikita", "timofei", "timofey", "tsarenko", "rodichev", 
        "krasheninnikov", "krasheninnikova", "burlin", "makeev", "kurguzov", "kordonskii", "azizov"
    ]
    is_russian_nat = bool(re.search(r'\b(ru|russia|russian|nga|belarus|kazakh|kazakhstan|cis)\b', clean_user_text_lower))
    has_russian_name = any(re.search(r'\b' + re.escape(rn) + r'\b', clean_user_text_lower) for rn in russian_name_keywords)
    
    # Kiểm tra nếu trợ lý đã từng chat tiếng Nga trong các lượt trước
    prev_assistant_texts = " ".join([m.get("content", "") for m in history_messages if m.get("role") in ["assistant", "model", "agent"]])
    has_prev_russian = bool(re.search(r'[а-яё]', prev_assistant_texts.lower()))
    
    # Kiểm tra ký tự tiếng Việt thực tế từ người dùng (không tính tag hệ thống)
    has_real_vietnamese = bool(re.search(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', clean_user_text_lower)) or any(re.search(r'\b' + re.escape(w) + r'\b', clean_user_text_lower) for w in ["chào", "xin chào", "giá", "vé", "lào", "bao nhiêu", "đi", "xe", "tôi", "cho tôi", "sơ đồ", "ghế", "hết hạn", "ngày", "đón", "ở đâu"])
    
    if re.search(r'[а-яё]', clean_user_text_lower) or is_russian_nat or has_russian_name or (has_prev_russian and not has_real_vietnamese):
        lang_code = "ru"
    elif re.search(r'[\uac00-\ud7a3]', clean_user_text_lower) or bool(re.search(r'\b(kr|korea|korean|hàn quốc)\b', clean_user_text_lower)):
        lang_code = "ko"
    elif re.search(r'[\u4e00-\u9fff]', clean_user_text_lower) or bool(re.search(r'\b(cn|china|chinese|trung quốc)\b', clean_user_text_lower)):
        lang_code = "zh"
    elif has_real_vietnamese:
        lang_code = "vi"
    elif customer_profile:
        prof_nat = (customer_profile.get("nationality") or "").lower()
        if any(r in prof_nat for r in ["nga", "russia", "belarus", "kazakh", "ukrain"]):
            lang_code = "ru"
        elif any(k in prof_nat for k in ["korea", "hàn"]):
            lang_code = "ko"
        elif customer_profile.get("preferred_lang"):
            lang_code = str(customer_profile.get("preferred_lang") or "en")
        else:
            lang_code = get_lang_code(destination) or "en"
    else:
        lang_code = get_lang_code(destination) or "en"
        
    lang_names = {
        "en": "ENGLISH",
        "ru": "RUSSIAN",
        "vi": "VIETNAMESE",
        "ko": "KOREAN",
        "zh": "CHINESE"
    }
    target_lang_name = lang_names.get(lang_code, "ENGLISH")
    
    target_language_context = (
        f"\nCRITICAL LANGUAGE DIRECTIVE:\n"
        f"- The detected target language for this customer is: {target_lang_name}\n"
        f"- YOU MUST WRITE YOUR ENTIRE 'reply_message' IN {target_lang_name}! Do NOT use any other language!"
    )

    # === RAG: Lấy context từ lịch sử chat thực tế ===
    last_user_msg = ""
    for msg in reversed(history_messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            clean_content = re.sub(r'\[.*?\]', '', content).strip()
            if clean_content:
                last_user_msg = clean_content
                break
            elif not last_user_msg:
                last_user_msg = content

    rag_context = ""
    if last_user_msg:
        try:
            rag_context = knowledge_rag.format_for_prompt(last_user_msg, top_k=5)
        except Exception as e:
            print(f"⚠️ RAG search error: {e}")

    # === CUSTOMER PROFILE CONTEXT (Hồ sơ Khách cũ & Cá nhân hóa) ===
    customer_context_prompt = ""
    if customer_profile:
        try:
            customer_context_prompt = customer_memory.format_customer_profile_for_prompt(customer_profile)
        except Exception as e:
            print(f"⚠️ Lỗi định dạng profile khách cũ: {e}")

    # Inject contexts into system prompt
    dynamic_prompt = SYSTEM_PROMPT
    if customer_context_prompt:
        dynamic_prompt = dynamic_prompt + "\n\n" + customer_context_prompt
    if rag_context:
        dynamic_prompt = dynamic_prompt + "\n\n" + rag_context
    if route_directive_context:
        dynamic_prompt = dynamic_prompt + "\n\n" + route_directive_context
    if smart_departure_context:
        dynamic_prompt = dynamic_prompt + "\n\n" + smart_departure_context
    if target_language_context:
        dynamic_prompt = dynamic_prompt + "\n\n" + target_language_context

    messages = [{"role": "system", "content": dynamic_prompt}]
    for msg in recent_history:
        role = "assistant" if msg["role"] in ["model", "assistant", "agent"] else "user"
        messages.append({"role": role, "content": msg["content"]})

    content = await call_deepseek(messages)
    if not content or not content.strip():
        content = await call_groq_fallback(messages)
    if not content or not content.strip():
        content = await call_gemini_fallback(messages)

    if not content or not content.strip():
        # Fallback in case of complete API failure
        lang = lang_code
        return ChatResponse(
            reply_message=get_msg("system_busy", lang),
            extracted_data=CustomerData(),
            current_phase="CONSULTING",
            is_complete=False,
        )

    chat_resp = ChatResponse.model_validate_json(content)

    # === PHASE VALIDATION & ANTI-HALLUCINATION GUARD ===
    ext = chat_resp.extracted_data

    # Validate extracted ngay_khoi_hanh / ngay_het_han_visa so invalid strings like "16/29" are stripped
    if ext.ngay_khoi_hanh:
        m_dep = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", str(ext.ngay_khoi_hanh))
        if m_dep:
            ok_dep, fmt_dep = _is_valid_calendar_date(m_dep.group(1), m_dep.group(2), m_dep.group(3))
            ext.ngay_khoi_hanh = fmt_dep[:5] if ok_dep else ""
        else:
            ext.ngay_khoi_hanh = ""

    if ext.ngay_het_han_visa:
        m_exp = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", str(ext.ngay_het_han_visa))
        if m_exp:
            ok_exp, fmt_exp = _is_valid_calendar_date(m_exp.group(1), m_exp.group(2), m_exp.group(3))
            ext.ngay_het_han_visa = fmt_exp[:5] if ok_exp else ""
        else:
            ext.ngay_het_han_visa = ""

    if not ext.ngay_khoi_hanh and smart_dep:
        ext.ngay_khoi_hanh = smart_dep

    # Do NOT allow premature jump to SEAT_SELECTION if the customer hasn't provided a valid date yet
    has_valid_date = bool(ext.ngay_khoi_hanh or smart_dep or expiry_date)
    has_customer_identity = bool(ext.ho_ten or ext.diem_don or ext.so_dien_thoai)
    if chat_resp.current_phase == "SEAT_SELECTION" and (not has_valid_date or not has_customer_identity):
        chat_resp.current_phase = "CONSULTING"

    return chat_resp


async def identify_image_type(file_path: str) -> str:
    return "Other"


async def call_deepseek_text(messages):
    if not DEEPSEEK_API_KEY:
        return None
    url = "https://api.deepseek.com/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.5,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                raw = r.json()["choices"][0]["message"]["content"]
                if raw and raw.strip():
                    return raw
            return None
        except Exception:
            return None


async def call_groq_fallback_text(messages):
    if not GROQ_API_KEYS:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.5,
    }
    
    for idx, key in enumerate(GROQ_API_KEYS):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=25) as client:
            try:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code == 200:
                    raw = r.json()["choices"][0]["message"]["content"]
                    if raw and raw.strip():
                        return raw
                else:
                    print(f"⚠️ Groq text key {idx+1} failed with status {r.status_code}: {r.text}")
            except Exception as e:
                print(f"⚠️ Groq text key {idx+1} exception: {e}")
    return None


async def call_gemini_fallback_text(messages):
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY.strip())
        model = genai.GenerativeModel("gemini-3.6-flash")
        system_content = ""
        user_content = ""
        for m in messages:
            if m["role"] == "system":
                system_content += m["content"] + "\n\n"
            else:
                user_content += m["content"] + "\n"
        full_prompt = f"{system_content}YÊU CẦU / CÂU HỎI:\n{user_content}"
        response = await model.generate_content_async(full_prompt)
        if response and response.text and response.text.strip():
            return response.text.strip()
        return None
    except Exception as e:
        print(f"⚠️ Gemini text fallback exception: {e}")
        return None


async def process_staff_chat(question: str) -> str:
    # 1. Lấy ngữ cảnh RAG từ cơ sở kiến thức
    rag_context = ""
    try:
        rag_context = knowledge_rag.format_for_prompt(question, top_k=5)
    except Exception as e:
        print(f"⚠️ RAG search error for staff chat: {e}")

    # 2. Xây dựng prompt nội bộ
    system_prompt = (
        "You are the internal AI Assistant for the staff members of Easy Trip & Visa Co. Ltd (a travel and visa agency in Nha Trang, Vietnam).\n"
        "Your role is to help staff members handle customer requests quickly and professionally. When a staff member asks a question or pastes a customer's query, your job is to:\n"
        "1. If it looks like a customer request (e.g., asking for visa prices, visarun dates, bus routes, requirements), immediately draft a polite, professional, and complete reply that the staff member can copy-paste directly to the customer. Draft the reply in the language the customer used (Vietnamese, English, Russian, etc.).\n"
        "2. If it is an internal staff question (e.g., asking about schedules, bank accounts, office address, emergency visa rules), answer it directly, clearly, and concisely in Vietnamese.\n\n"
        "CRITICAL OPERATIONS DIRECTIVES (NEVER DEVIATE OR INVENT):\n"
        "1. Visa Run Pick-up & Schedule:\n"
        "   - The bus to Laos (Bo Y) or Cambodia (Moc Bai) departures are ALWAYS overnight. Departure time from Nha Trang is 21:30 (from 40 Hon Chong) or 21:15 (from No. 4 Tran Phu). We do NOT pick up customers in the morning or at 5:00 AM.\n"
        "   - The bus arrives at the Moc Bai border around 06:00 - 06:30 AM the next morning.\n"
        "2. No Border Guides:\n"
        "   - We do NOT have guides at the border. Customers must go through the exit/entry gates themselves. The driver will only help collect passports for the Bo Y (Laos) route, but for Cambodia (Moc Bai), the passengers must do it themselves.\n"
        "3. Moc Bai Visa Run Process:\n"
        "   - Passengers cross into Cambodia around 7:30 - 8:00 AM.\n"
        "   - Passengers MUST take a photo of their Vietnam exit stamp and send it to EasyTrip before 08:00 AM.\n"
        "   - We process the emergency e-visa in 4 hours while they wait at a café in Cambodia.\n"
        "   - The new e-visa is delivered via message/email between 11:30 AM and 12:00 PM.\n"
        "4. Visa Extension (Inside Vietnam):\n"
        "   - Vietnam does NOT allow extensions for tourist visas inside the country. Extension is impossible (0 VND / Not available). The customer MUST do a visarun.\n"
        "5. Route Eligibility:\n"
        "   - Nationalities not exempt from Laos visa (e.g. USA, Canada, Australia, Brazil, UK, etc.) MUST take the Cambodia route. Laos is not available for them.\n"
        "   - Cambodia visa run package costs 4,000,000 VND (includes round-trip bus + 90-day Vietnam E-visa). The customer must pay for their own Cambodia visa at the border (approx. 35$ - 50$). Cambodia bus departs only on Tuesdays, Thursdays, and Sundays.\n\n"
        "Use the following core knowledge base about Easy Trip's services, pricing, and schedules to construct your response:\n"
        f"{KNOWLEDGE_BASE}\n"
    )
    if rag_context:
        system_prompt += "\n" + rag_context

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]

    # 3. Gọi LLM chính hoặc fallback dạng text
    content = await call_deepseek_text(messages)
    if not content or not content.strip():
        content = await call_groq_fallback_text(messages)
    if not content or not content.strip():
        content = await call_gemini_fallback_text(messages)

    if not content or not content.strip():
        return "🤖 Không thể kết nối với AI (API Error). Vui lòng thử lại sau hoặc tra cứu từ khóa!"

    return content.strip()
