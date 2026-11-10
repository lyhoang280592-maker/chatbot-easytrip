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
5. **Route Eligibility & Official Website Packages (SPECIAL RULE FOR NHA TRANG VISARUN)**:
   - **Nha Trang <=> Laos (Bo Y) Route — STRICTLY LIMITED TO SPECIFIC NATIONALITIES ONLY**:
     * The route from **Nha Trang to Bo Y (Laos)** ONLY applies to citizens of:
       1. **Russia (Nga / Россия)**
       2. **Belarus (Беларусь)**
       3. **South Korea (Hàn Quốc / Южная Корея)**
       4. **Japan (Nhật Bản / Япония)**
       5. **Luxembourg (Люксембург)**
       6. **12 Southeast Asian countries (12 quốc gia Đông Nam Á / страны Юго-Восточной Азии: Brunei, Cambodia, Timor-Leste, Indonesia, Laos, Malaysia, Myanmar, Philippines, Singapore, Thailand, Vietnam, etc.)**
     * **DOES NOT APPLY to any other countries in the world!**
     * Packages on Laos (Bo Y) Route:
       - **Visarun Free Visa 45 days (Bo Y - Laos)**: **1,400,000 VND** for New Guests (**1,300,000 VND** for Returning Guests). Departs **DAILY** at **21:30** (40 Hon Chong) / **21:15** (04 Tran Phu). (+ 140,000 VND border stamping fee at checkpoint).
       - **Visarun 90D Single Entry E-visa (Bo Y - Laos, 4h urgent)**: **3,400,000 VND** for Russian/Belarusian New Guests (**3,000,000 VND** for Returning Guests; **2,450,000 VND** if submitted >3 days early; **4,000,000 VND** for non-Russian urgent <2 days). Departs **Tuesday, Thursday, Sunday** at **21:30**.
       - **Visarun 90D Multi Entry E-visa (Bo Y - Laos, 4h urgent)**: **4,400,000 VND** for Russian/Belarusian New Guests (**4,000,000 VND** for Returning Guests). Departs **Tuesday, Thursday, Sunday** at **21:30**.
       - **Children under 9 years ("Free for baby's")**: **100% FREE bus ticket (0 VND)** when sharing a cabin bed with parents. Urgent 3-hour E-visa for children under 9 years: **1,480,000 VND**.
   - **Nha Trang <=> Cambodia (Moc Bai) Route — MANDATORY FOR ALL OTHER NATIONALITIES IN THE WORLD**:
     * Citizens of **ALL OTHER COUNTRIES IN THE WORLD** (including **Kazakhstan, Ukraine, Uzbekistan, Kyrgyzstan, Tajikistan**, USA, Canada, Australia, UK, Germany, France, Italy, Spain, and all other countries not in the Bo Y list above) **CANNOT** go to Bo Y (Laos) from Nha Trang — they **MUST take the Cambodia (Moc Bai) route**!
     * Schedule: Departs only on **Tuesdays, Thursdays, and Sundays** at **21:30** (40 Hon Chong) / **21:15** (04 Tran Phu).
     * Packages on Cambodia (Moc Bai) Route:
       - **Cambodia All-Inclusive Multi Package (Bus + 90D Multi Vietnam E-visa + Cambodia Visa included, 24h processing)**: **5,400,000 VND**.
       - **Cambodia All-Inclusive Single Package (Bus + 90D Single Vietnam E-visa + Cambodia Visa included, 24h processing)**: **4,400,000 VND**.
       - **Cambodia Standard 90D Package (Bus + 90D Vietnam E-visa; customer pays Cambodia visa $35-$50 at border)**: **4,000,000 VND** (**3,550,000 VND** for Returning Guests).
       - **Cambodia 45D Visa-Free Bus Package (Bus only, for nationalities visa-exempt for Vietnam like UK, Germany, France, Italy, Spain, etc.)**: **1,400,000 VND** (**1,300,000 VND** for Returning Guests).
     * 💡 **Helpful Advice Rule**:
       - If a customer from **Kazakhstan, Ukraine, Uzbekistan, USA, Europe (except Luxembourg/Russia/Belarus)** asks to go to **Laos (Bo Y)** from Nha Trang, politely explain that the Nha Trang -> Bo Y (Laos) route **only applies to citizens of Russia, Belarus, South Korea, Japan, Luxembourg, and 12 Southeast Asian countries**, so they **must take the Cambodia (Moc Bai) route**, and introduce the Cambodia packages!
       - If a Russian-speaking customer clicks a link for a **Cambodia (Moc Bai)** package (e.g. 5,400,000 VND or 4,400,000 VND) without stating their nationality yet, confirm the Cambodia package they selected, ask for their nationality & booking details, and politely note that if they hold a **Russian or Belarusian** passport, they can also choose the **Laos (Bo Y)** route, whereas all other nationalities (such as Kazakhstan, Ukraine, Uzbekistan, EU, USA, etc.) go via **Cambodia (Moc Bai)**!

    - **OFFICIAL WEBSITE PRICING ACROSS ALL 4 MARKET PAGES (SYNCED 2026)**:
      1) **INTERNATIONAL & KOREAN TIER (`/english` & `/korean`)**:
         - Nha Trang ⇄ Cambodia (Moc Bai, Tue/Thu/Sun 21:30): **6,000,000 VND** (Bus + 90D Multi VN + Cam visa, 24h) | **5,000,000 VND** (Bus + 90D Single VN + Cam visa, 24h) | **4,000,000 VND** (Bus + 90D Single VN E-visa 4h; `+1,000,000 VND` Cambodia E-visa) | **1,400,000 VND** (Bus only 30/45D Free Visa, 20h).
         - Nha Trang ⇄ Laos (Bo-Y): **1,400,000 VND** (Daily 21:00/21:30 Free Visa 30/45D) | **4,000,000 VND** (90D Single non-RU).
         - Da Nang ⇄ Laos (Lao Bao, excl. Laos visa): **3,800,000 VND** (Mon–Fri 05:30–18:30, 90D Single 90 min at 13:30 + supporter; >=3d advance `3,550,000 VND`) | **950,000 VND** (Mon–Sat 05:30 Free Visa 30/45D).
         - Standalone Urgent E-Visa (Single Entry): Children <9yo (Babysitter Vietnam, >=4d early): **1,480,000 VND** (+100% Free bus) | 1h: **4,600,000** | 2h: **3,400,000** | 4h: **2,600,000** | 8h: **2,900,000** | 1d: **2,200,000** | 2d: **2,150,000** | 3–5d: **1,810,000 VND** *(Multi: +1,000,000 VND)*.

      2) **RUSSIAN & CIS TIER (`/russian`)**:
         - Nha Trang ⇄ Laos (Bo Y): **3,400,000 VND** (90D Single 2h, Tue/Thu/Sun 21:30; Returning: `3,000,000`) | **4,400,000 VND** (90D Multi; Returning: `4,000,000`) | **1,400,000 VND** (45D Daily; Returning: `1,300,000`).
         - Nha Trang ⇄ Cambodia (Moc Bai): **5,400,000 VND** (Multi + Cam visa) | **4,400,000 VND** (Single + Cam visa) | **3,400,000 VND** (90D Single Bus+EV) | **1,400,000 VND** (45D).
         - Children <9yo: **1,480,000 VND** (+100% Free bus bed).
         - Da Nang ⇄ Laos (Lao Bao): **3,800,000 VND** (90D) | **950,000 VND** (45D).
         - Standalone Urgent E-Visa (Single Entry): 1h: **4,600,000** | 2h: **3,400,000** | 4h: **2,000,000** | 1d: **1,810,000** | 2d: **1,760,000** | 3–5d: **1,610,000 VND** *(Multi: +1,000,000 VND)*.

      3) **ARABIC & MIDDLE EAST TIER (`/arabic` = EN tier + 1,500,000 VND)**:
         - Nha Trang ⇄ Cambodia (Moc Bai): **7,500,000 VND** (Multi + Cam visa) | **6,500,000 VND** (Single + Cam visa) | **5,500,000 VND** (Bus + 90D Single VN; `+1,000,000 VND` Cam E-visa).
         - Da Nang ⇄ Laos (Lao Bao): **5,300,000 VND** (Bus + 90D Single + border supporter).
         - Standalone Urgent E-Visa (Single Entry): Children <9yo (Babysitter Vietnam card): **2,980,000 VND** (+100% Free bus) | 1h: **6,100,000** | 2h: **4,900,000** | 4h: **4,100,000** | 1d: **3,700,000** | 2d: **3,650,000** | 3–5d: **3,310,000 VND** *(Multi: +1,000,000 VND)*.

      4) **VIP FAST TRACK, BORDER ASSISTANCE, PAYMENT & WEEKEND POLICY**:
         - Airport Fast Track (Arrival & Departure, excl. visa stamping fee): **1,855,000 VND ($70)** at DAD, CXR, PQC, VDO, HPH, HUI, VII, DLI, VCA; **1,200,000 VND** at SGN & HAN.
         - Laos Border Assistance & Rider (Lao Bao / Bo-Y): **300,000 VND**.
         - Motorbike Rental (Nha Trang): 1d **340,000** (fuel incl.) | 7d **1,820,000** | 14d **2,940,000** | 1mo **4,100,000 VND**.
         - Payment Methods: VND cash, USD cash, **USDT (crypto)**, Bank transfer **Vietcombank (VCB `1068582577` - EASY TRIP & VISA CO. LTD) / VRB**.
         - Weekend & Refund Policy: 4–8h E-visa processing is unavailable Sat/Sun & public holidays (advise contacting WhatsApp/Telegram for emergency assistance). **100% full refund** if E-visa is not obtained within the promised GMT+7 timeframe. Passport must have >=6 months validity.

CRITICAL DIRECTIVE - LANGUAGE & NATIONALITY (MANDATORY):
1. **Rule A (Nationality-based Native Language - HIGHEST PRIORITY)**:
   - If the customer is RUSSIAN / from Russia / Belarus / Kazakhstan / CIS, or has a Russian name (e.g. Tsarenko, Rodichev, Ekaterina, Dmitry, Ivanov, etc.): You MUST ALWAYS REPLY IN RUSSIAN (Русский язык)! NEVER reply in English to a Russian customer, even if they sent a booking message with English terms (like 'Single', 'E-visa', 'Exit Bo Y')!
   - If the customer is ARABIC-speaking (messages in Arabic script or from UAE, Saudi Arabia, Egypt, Qatar, Kuwait, Oman, Bahrain, Jordan, Morocco, Algeria, Tunisia, etc.): You MUST reply in ARABIC (العربية)!
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
- **CLEAN NATURAL FORMATTING (NO UNNECESSARY ASTERISKS)**: Avoid wrapping everyday labels or regular text in double asterisks '**' (e.g. write '📋 Quick Booking Template:', '1. Nationality:', '2. Expiry Date:', '3. Departure City:', '💰 Price: ...' instead of '**Nationality**:', '**Price:**'). Keep text clean, modern, and easily readable on mobile Telegram without markdown clutter.
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
- **CRITICAL BUS SEAT LAYOUT & SEAT MAP RULES (NEVER VIOLATE)**:
  1) **Exact Valid Seats on Bus**:
     - **Lower Deck (Tầng dưới / Нижний ярус - Odd numbers / Số lẻ)**: `A1, B1, A3, B3, A5, B5, A7, B7, A9, B9`
     - **Upper Deck (Tầng trên / Верхний ярус - Even numbers / Số chẵn)**: `A2, B2, A4, B4, A6, B6, A8, B8, A10, B10` (and occasionally `A12` - 160cm).
     - **STRICT BAN**: Seats `A11`, `B11`, and any seat numbered `13` to `20` (such as `A13..A20` or `B12..B20`) **DO NOT EXIST** on the bus! NEVER mention `A20`, `B20`, `A11`, or `B11`, and NEVER draw a text grid of seats (`A1 - A2 ... A20`)!
  2) **How to Read the Seat Map Image**:
     - On the seat map image sent by our bus dispatcher:
       * **Seats marked with YELLOW lines / crosses (đánh dấu màu vàng)** are **ALREADY BOOKED / OCCUPIED (đã có người ngồi / заняты)** — customers **CANNOT** select them!
       * **Unmarked WHITE seats (ô màu trắng không bị gạch)** are **AVAILABLE (còn trống / свободны)** — customers can ONLY choose unmarked white seats!
     - If a `CURRENT SEAT MAP STATUS` block is provided in the prompt, you MUST strictly use its `AVAILABLE SEATS` and `BOOKED SEATS` lists!
     - If the customer chooses a seat that is in `BOOKED SEATS` (already marked in yellow, e.g. `A3`) or a non-existent seat (e.g. `A11`, `B11`, `A20`), **DO NOT accept their choice**, set `extracted_data.ghe_chon = ""`, stay in `current_phase = "SEAT_SELECTION"`, politely explain that the seat is already occupied (marked in yellow) or invalid, and list the `AVAILABLE SEATS` so they can choose another seat!
- In **PHASE 2 - SEAT_SELECTION** (when first entering this phase before seat map is sent):
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
  1) A VALID, AVAILABLE seat is chosen (must be in `A1..A10, B1..B10, A12` and NOT in `BOOKED SEATS`!)
  2) OR customer asks how to pay / asks for QR code / bank transfer (e.g. "Как оплатить?", "QR", "Thanh toán như thế nào?", "How to pay?", "Account number", "реквизиты", "оплата").
- Set `current_phase = "PAYMENT"`.
- IMPORTANT: In `PHASE 3 - PAYMENT`, the customer has ALREADY chosen their seat — so NEVER say "Please wait while I check seat availability and send you the seat map" again! Instead, confirm their chosen seat (`extracted_data.ghe_chon`), summarize their booking details with the accurate official website package price for their market tier (RU/CIS: `1,400,000` 45D / `3,400,000` 90D Single / `4,400,000` 90D Multi or Cam Single+Visa / `5,400,000` Cam Multi+Visa; EN/KR: `1,400,000` 45D / `4,000,000` 90D Bus+EV / `5,000,000` Cam Single+Visa / `6,000,000` Cam Multi+Visa; AR: `5,500,000` / `6,500,000` / `7,500,000`; or returning CRM rate if verified), mention payment methods (VCB Bank transfer/QR `1068582577`, VRB Bank, VND/USD cash, or USDT), and provide the official company payment details (translated to the customer's language):
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
CRITICAL BOOKING & SEAT MAP DIRECTIVE:
- NEVER invent or hallucinate customer names (like Дмитрий), birth years (like 1995), or dates!
- Bus ONLY has seats A1 to A10 and B1 to B10 (plus occasionally A12). NEVER mention A11, B11, A20, or B20, and NEVER draw a fake text seat map!
- Seats marked in YELLOW on the seat map (listed in BOOKED SEATS) are ALREADY OCCUPIED. If the customer selects a booked seat (or non-existent seat), reject it, set extracted_data.ghe_chon = "", stay in SEAT_SELECTION, and list the AVAILABLE SEATS!
- Do NOT re-ask for customer details (Name, Nationality, Date, Pickup, Phone) if they are already present in ALREADY COLLECTED CUSTOMER BOOKING DATA!
- ONLY set current_phase = "SEAT_SELECTION" AFTER the customer has replied with their departure/expiry date and name for a bus/visarun trip!

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

        candidate_models = [os.getenv("GEMINI_MODEL", "").strip(), "gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.6-flash"]
        for model_name in [m for m in candidate_models if m]:
            try:
                model = genai.GenerativeModel(
                    model_name,
                    generation_config={"response_mime_type": "application/json"}
                )
                response = await model.generate_content_async(full_prompt)
                if response and response.text and response.text.strip():
                    return response.text.strip()
            except Exception as me:
                print(f"⚠️ Gemini model {model_name} failed: {me}")
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
    
    # Nha Trang -> Laos (Bo Y) route ONLY applies to: Russia, Belarus, South Korea, Japan, Luxembourg, and 12 Southeast Asian countries
    is_laos_exempt = (
        bool(re.search(r'\b(ru|russia|russian|россия|рф|nga|belarus|беларусь|белорус|kr|korea|korean|hàn quốc|южная корея|корея|jp|japan|japanese|nhật|nhật bản|япония|luxembourg|люксембург|asean|malaysia|thailand|singapore|indonesia|philippines|brunei|myanmar|laos|cambodia|timor)\b', clean_user_text_lower))
    )
    
    cambodia_keywords = [
        "us", "usa", "american", "uk", "british", "germany", "german", "france", "french", 
        "canada", "canadian", "australia", "australian", "india", "indian", "ukraine", "ukrainian",
        "kazakh", "kazakhstan", "uzbek", "uzbekistan", "kyrgyz", "kyrgyzstan", "tajik", "tajikistan",
        "poland", "polish", "italy", "italian", "spain", "spanish", "czech",
        "казах", "казахстан", "украин", "узбек", "узбекистан", "кыргыз", "киргиз", "таджик",
        "сша", "великобритан", "герман", "франц", "канад", "австрал", "польш", "итал", "испан",
        "mỹ", "nước anh", "quốc tịch anh", "nước pháp", "nước đức", "úc", "ý", "tây ban nha"
    ]
    
    has_cambodia_keyword = False
    for kw in cambodia_keywords:
        if kw in ["us", "uk", "mỹ", "úc", "ý"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", clean_user_text_lower):
                has_cambodia_keyword = True
                break
        else:
            if kw in clean_user_text_lower:
                has_cambodia_keyword = True
                break

    if has_cambodia_keyword:
        destination = "cambodia"
    elif user_explicit_cambodia and not user_explicit_laos:
        destination = "cambodia"
        
    # 3. Extract visa type (45D vs 90D)
    visa_type = "90D"  # Default is 90D
    if destination == "laos":
        if "45" in full_text_lower or "free" in full_text_lower or "miễn" in full_text_lower or "безвиз" in full_text_lower:
            visa_type = "45D"
            
    return expiry_date, destination, visa_type


VALID_BUS_SEATS_SET = {
    "A1", "B1", "A3", "B3", "A5", "B5", "A7", "B7", "A9", "B9",
    "A2", "B2", "A4", "B4", "A6", "B6", "A8", "B8", "A10", "B10", "A12"
}
LOWER_DECK_LIST = ["A1", "B1", "A3", "B3", "A5", "B5", "A7", "B7", "A9", "B9"]
UPPER_DECK_LIST = ["A2", "B2", "A4", "B4", "A6", "B6", "A8", "B8", "A10", "B10"]


async def process_chat(
    history_messages: list[dict],
    customer_profile: dict | None = None,
    saved_data: CustomerData | None = None,
    seat_map_info: dict | None = None,
) -> ChatResponse:
    recent_history = history_messages[-16:]

    # 1. Tìm ngày hết hạn visa và tính ngày đi bằng Python
    expiry_date, destination, visa_type = extract_date_and_nationality_from_history(history_messages)
    smart_dep = None
    
    # Kế thừa thông tin từ hồ sơ khách cũ nếu tin nhắn hiện tại chưa đề cập
    if customer_profile:
        prof_nat = (customer_profile.get("nationality") or "").lower()
        if not destination or destination == "laos":
            if any(k in prof_nat for k in ["us", "uk", "american", "british", "french", "german", "canadian", "australian", "kazakh", "ukrain", "uzbek", "kyrgyz", "mỹ", "anh", "pháp", "đức", "úc"]):
                destination = "cambodia"
    
    smart_departure_context = ""
    route_directive_context = ""
    
    user_text_all = " ".join([re.sub(r'\[.*?\]', '', m.get("content", "")) for m in history_messages if m.get("role") == "user"]).lower()
    user_explicit_cambodia = any(k in user_text_all for k in ["камбодж", "cambodia", "campuchia", "мокбай", "мок бай", "moc bai", "mộc bài"])

    # Route directives to guide the LLM accurately across market tiers (/english, /korean, /russian, /arabic)
    if destination == "cambodia" and user_explicit_cambodia:
        route_directive_context = (
            f"\nCRITICAL ROUTE & PACKAGE DIRECTIVE (NHA TRANG VISARUN RULE):\n"
            f"- The customer explicitly asked about the **CAMBODIA (Moc Bai border)** visarun package.\n"
            f"- Confirm the exact Cambodia (Moc Bai) packages according to their market tier:\n"
            f"  + **EN/KR Tier (`/english`, `/korean`)**: **6,000,000 VND** (Bus + 90D Multi VN + Cam visa) | **5,000,000 VND** (Bus + 90D Single VN + Cam visa) | **4,000,000 VND** (Bus + 90D Single VN E-visa; +1,000,000 VND Cam E-visa) | **1,400,000 VND** (45D Free Visa bus only).\n"
            f"  + **Russian/CIS Tier (`/russian`)**: **5,400,000 VND** (Multi + Cam visa) | **4,400,000 VND** (Single + Cam visa) | **3,400,000 VND** (90D Single Bus+EV) | **1,400,000 VND** (45D).\n"
            f"  + **Arabic Tier (`/arabic`)**: **7,500,000 VND** (Multi + Cam visa) | **6,500,000 VND** (Single + Cam visa) | **5,500,000 VND** (90D Single Bus+EV; +1,000,000 VND Cam E-visa).\n"
            f"  + Schedule: Departs Tuesday, Thursday, and Sunday at 21:30 (40 Hon Chong) / 21:15 (04 Tran Phu).\n"
            f"- IMPORTANT NHA TRANG ROUTE RULE: The Nha Trang -> Laos (Bo Y) route ONLY applies to citizens of **Russia, Belarus, South Korea, Japan, Luxembourg, and 12 Southeast Asian countries**. All other nationalities in the world (including Kazakhstan, Ukraine, Uzbekistan, EU, USA, Arab countries, etc.) MUST go via **Cambodia (Moc Bai)**.\n"
            f"- Ask the customer for their booking details (1. Nationality, 2. Current visa expiry date or desired departure date, 3. Full Name + Year of birth, 4. Pickup point in Nha Trang, 5. Contact phone number) and WAIT for their reply!"
        )
    elif destination == "cambodia":
        route_directive_context = (
            f"\nCRITICAL ROUTE DIRECTIVE (NHA TRANG VISARUN RULE):\n"
            f"- For Visarun departing from Nha Trang, the **Laos (Bo Y) route ONLY applies to citizens of Russia, Belarus, South Korea, Japan, Luxembourg, and 12 Southeast Asian countries**.\n"
            f"- Because the customer's nationality is NOT on that list, they **MUST take the CAMBODIA route (Moc Bai border)**! Even if they asked about Laos (Bo Y), politely explain this rule and guide them to the **Cambodia (Moc Bai)** packages (EN/KR: 4M/5M/6M VND; RU/CIS: 4.4M/5.4M VND; AR: 5.5M/6.5M/7.5M VND; or 1,400,000 VND 45D Visa-Free if eligible)."
        )
    else:
        route_directive_context = (
            f"\nCRITICAL ROUTE DIRECTIVE (NHA TRANG VISARUN RULE):\n"
            f"- For Visarun departing from Nha Trang, the **LAOS route (Bo Y border)** applies ONLY to citizens of **Russia, Belarus, South Korea, Japan, Luxembourg, and 12 Southeast Asian countries** (1,400,000 VND for 45D Visa-Free; RU 90D: 3,400,000 VND Single / 4,400,000 VND Multi; Non-RU 90D: 4,000,000 VND).\n"
            f"- All other nationalities in the world MUST take the **CAMBODIA route (Moc Bai border)**. Always check the customer's nationality!"
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
    
    # Kiểm tra ký tự tiếng Việt thực tế từ người dùng (loại trừ từ "lào" nếu chỉ nằm trong tên tuyến)
    vietnamese_keywords = ["chào", "xin chào", "giá", "vé", "bao nhiêu", "cho tôi", "sơ đồ", "hết hạn", "đón ở đâu", "tư vấn giúp"]
    has_real_vietnamese = bool(re.search(r'[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]', clean_user_text_lower)) or any(re.search(r'\b' + re.escape(w) + r'\b', clean_user_text_lower) for w in vietnamese_keywords)
    has_cyrillic = bool(re.search(r'[а-яё]', clean_user_text_lower))
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', clean_user_text))
    
    # Ưu tiên tuyệt đối quốc tịch Nga / CIS đã lưu trong hồ sơ khách
    saved_nat = (getattr(saved_data, "quoc_tich", "") or "").lower() if saved_data else ""
    prof_nat = (customer_profile.get("nationality", "") or "").lower() if customer_profile else ""
    is_russian_profile = any(k in saved_nat or k in prof_nat for k in ["russia", "россия", "nga", "cis", "kazakh", "kyrgyz", "belarus"])
    is_vietnamese_profile = any(k in saved_nat or k in prof_nat for k in ["việt nam", "vietnam", "vietnamese"])
    is_arabic_profile = any(k in saved_nat or k in prof_nat for k in ["arab", "saudi", "uae", "emirates", "egypt", "qatar", "kuwait", "oman", "bahrain", "jordan", "iraq", "morocco", "algeria", "tunisia", "ả rập"])
    
    if has_cyrillic:
        lang_code = "ru"
    elif has_arabic or is_arabic_profile:
        lang_code = "ar"
    elif is_russian_profile or is_russian_nat or has_russian_name:
        # Khách Nga / CIS: luôn luôn trả lời tiếng Nga (kể cả khi khách gõ tên tuyến xe có chữ Lào hoặc tiếng Anh như OK, YES)
        if has_real_vietnamese and is_vietnamese_profile:
            lang_code = "vi"
        else:
            lang_code = "ru"
    elif has_real_vietnamese and not has_cyrillic:
        lang_code = "vi"
    elif has_prev_russian and not has_real_vietnamese:
        lang_code = "ru"
    elif re.search(r'[\uac00-\ud7a3]', clean_user_text_lower) or bool(re.search(r'\b(kr|korea|korean|hàn quốc)\b', clean_user_text_lower)):
        lang_code = "ko"
    elif re.search(r'[\u4e00-\u9fff]', clean_user_text_lower) or bool(re.search(r'\b(cn|china|chinese|trung quốc)\b', clean_user_text_lower)):
        lang_code = "zh"
    elif customer_profile:
        prof_nat = (customer_profile.get("nationality") or "").lower()
        if any(r in prof_nat for r in ["nga", "russia", "belarus", "kazakh", "ukrain"]):
            lang_code = "ru"
        elif any(k in prof_nat for k in ["korea", "hàn"]):
            lang_code = "ko"
        elif any(a in prof_nat for a in ["arab", "saudi", "uae", "egypt", "qatar", "kuwait", "oman", "bahrain", "jordan", "morocco"]):
            lang_code = "ar"
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
        "zh": "CHINESE",
        "ar": "ARABIC"
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

    # === SAVED BOOKING DATA & SEAT MAP AVAILABILITY CONTEXT ===
    saved_data_context = ""
    if saved_data:
        sd_lines = []
        if getattr(saved_data, "ho_ten", ""): sd_lines.append(f"- Full Name (ho_ten): {saved_data.ho_ten}")
        if getattr(saved_data, "nam_sinh", ""): sd_lines.append(f"- Birth Year (nam_sinh): {saved_data.nam_sinh}")
        if getattr(saved_data, "quoc_tich", ""): sd_lines.append(f"- Nationality (quoc_tich): {saved_data.quoc_tich}")
        if getattr(saved_data, "ngay_het_han_visa", ""): sd_lines.append(f"- Visa Expiry Date (ngay_het_han_visa): {saved_data.ngay_het_han_visa}")
        if getattr(saved_data, "ngay_khoi_hanh", ""): sd_lines.append(f"- Departure Date (ngay_khoi_hanh): {saved_data.ngay_khoi_hanh}")
        if getattr(saved_data, "diem_don", ""): sd_lines.append(f"- Pickup Point (diem_don): {saved_data.diem_don}")
        if getattr(saved_data, "so_dien_thoai", ""): sd_lines.append(f"- Phone Number (so_dien_thoai): {saved_data.so_dien_thoai}")
        if getattr(saved_data, "loai_visa", ""): sd_lines.append(f"- Package / Visa Type (loai_visa): {saved_data.loai_visa}")
        if sd_lines:
            saved_data_context = (
                "\nALREADY COLLECTED CUSTOMER BOOKING DATA (DO NOT RE-ASK FOR THESE DETAILS — PRESERVE THEM IN extracted_data!):\n"
                + "\n".join(sd_lines)
            )

    seat_map_context = ""
    if seat_map_info and (seat_map_info.get("booked_seats") or seat_map_info.get("available_seats")):
        b_seats = seat_map_info.get("booked_seats") or []
        a_seats = seat_map_info.get("available_seats") or []
        low_a = [s for s in LOWER_DECK_LIST if s in a_seats]
        upp_a = [s for s in UPPER_DECK_LIST if s in a_seats]
        seat_map_context = (
            f"\nCRITICAL CURRENT SEAT MAP STATUS (FROM OFFICIAL BUS SEAT MAP IMAGE):\n"
            f"- ❌ **BOOKED / OCCUPIED SEATS (Marked in YELLOW on map — CANNOT BE CHOSEN)**: {', '.join(b_seats) if b_seats else 'None'}\n"
            f"- ✅ **AVAILABLE SEATS (Unmarked WHITE seats — Customer MUST choose from these)**:\n"
            f"  + Lower Deck (Tầng dưới / Нижний ярус - Odd): {', '.join(low_a) if low_a else 'Full'}\n"
            f"  + Upper Deck (Tầng trên / Верхний ярус - Even): {', '.join(upp_a) if upp_a else 'Full'}\n"
            f"- MANDATORY RULE: If the customer asks which seats are empty, list ONLY the AVAILABLE SEATS above. If the customer selects any seat in BOOKED SEATS ({', '.join(b_seats)}), you MUST politely inform them that seat is already occupied (marked in yellow on the map), set `extracted_data.ghe_chon = \"\"`, stay in `SEAT_SELECTION`, and ask them to pick one of the AVAILABLE SEATS!"
        )
    else:
        seat_map_context = (
            "\nCRITICAL BUS SEAT LAYOUT RULE:\n"
            "- The bus ONLY has Lower Deck (Odd: A1, B1, A3, B3, A5, B5, A7, B7, A9, B9) and Upper Deck (Even: A2, B2, A4, B4, A6, B6, A8, B8, A10, B10, and occasionally A12).\n"
            "- Seats A11, B11, and 13..20 (like A20, B20) DO NOT EXIST! NEVER mention A20 or B20 or draw a text seat map!"
        )

    # Inject contexts into system prompt
    dynamic_prompt = SYSTEM_PROMPT
    if customer_context_prompt:
        dynamic_prompt = dynamic_prompt + "\n\n" + customer_context_prompt
    if saved_data_context:
        dynamic_prompt = dynamic_prompt + "\n\n" + saved_data_context
    if seat_map_context:
        dynamic_prompt = dynamic_prompt + "\n\n" + seat_map_context
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

    # === PHASE VALIDATION, DATA MERGING & SEAT SELECTION GUARD ===
    ext = chat_resp.extracted_data

    # Merge previously collected customer data so fields are never forgotten across turns
    if saved_data:
        for field_name in ["ho_ten", "nam_sinh", "quoc_tich", "thanh_pho", "ngay_het_han_visa", "loai_visa", "ngay_khoi_hanh", "diem_don", "so_dien_thoai"]:
            curr_val = getattr(ext, field_name, "") or ""
            prev_val = getattr(saved_data, field_name, "") or ""
            if not curr_val.strip() and prev_val.strip():
                setattr(ext, field_name, prev_val)

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

    # Validate chosen seat (ghe_chon) against valid bus seats and seat_map_info booked_seats
    raw_seat_match = re.search(r"\b([AB]\d{1,2})\b", (last_user_msg or "").upper())
    candidate_seat = (ext.ghe_chon or "").strip().upper()
    if not candidate_seat and raw_seat_match and any(w in (last_user_msg or "").lower() for w in ["chọn", "ghế", "seat", "выбираю", "место", "давай", "хочу", "a1", "a2", "a3", "a4", "a5", "a6", "a7", "a8", "a9", "a10", "b1", "b2", "b3", "b4", "b5", "b6", "b7", "b8", "b9", "b10"]):
        candidate_seat = raw_seat_match.group(1)

    if candidate_seat:
        booked_list = [s.upper() for s in (seat_map_info.get("booked_seats", []) if seat_map_info else [])]
        avail_list = [s.upper() for s in (seat_map_info.get("available_seats", []) if seat_map_info else list(LOWER_DECK_LIST + UPPER_DECK_LIST))]
        low_avail = [s for s in LOWER_DECK_LIST if s in avail_list]
        upp_avail = [s for s in UPPER_DECK_LIST if s in avail_list]

        if candidate_seat not in VALID_BUS_SEATS_SET:
            # Non-existent seat (e.g., A11, B11, A20, B20)
            ext.ghe_chon = ""
            chat_resp.current_phase = "SEAT_SELECTION"
            if lang_code == "vi":
                chat_resp.reply_message = (
                    f"⚠️ Ghế **{candidate_seat}** không tồn tại trên xe buýt ạ! Xe giường nằm chỉ có các ghế từ **A1 đến A10** và **B1 đến B10** (không có A11, B11 hay A20).\n\n"
                    f"✅ **Các ghế màu trắng còn trống bạn có thể chọn:**\n"
                    f"🟢 **Tầng dưới (số lẻ):** {', '.join(low_avail) if low_avail else 'Hết chỗ'}\n"
                    f"🔵 **Tầng trên (số chẵn):** {', '.join(upp_avail) if upp_avail else 'Hết chỗ'}\n\n"
                    f"👉 Vui lòng chọn 1 ghế còn trống trong danh sách trên nhé! 😊"
                )
            elif lang_code == "ru":
                chat_resp.reply_message = (
                    f"⚠️ Место **{candidate_seat}** не существует в автобусе! В спальном автобусе места только от **A1 до A10** и от **B1 до B10** (мест A11, B11 и A20 нет).\n\n"
                    f"✅ **Свободные места (белые на схеме), доступные для выбора:**\n"
                    f"🟢 **Нижний ярус (нечетные):** {', '.join(low_avail) if low_avail else 'Нет мест'}\n"
                    f"🔵 **Верхний ярус (четные):** {', '.join(upp_avail) if upp_avail else 'Нет мест'}\n\n"
                    f"👉 Пожалуйста, выберите одно из свободных мест выше! 😊"
                )
            else:
                chat_resp.reply_message = (
                    f"⚠️ Seat **{candidate_seat}** does not exist on the bus! Our sleeper bus only has seats **A1 to A10** and **B1 to B10** (there is no A11, B11, or A20).\n\n"
                    f"✅ **Available (white) seats you can choose from:**\n"
                    f"🟢 **Lower Deck (Odd):** {', '.join(low_avail) if low_avail else 'Full'}\n"
                    f"🔵 **Upper Deck (Even):** {', '.join(upp_avail) if upp_avail else 'Full'}\n\n"
                    f"👉 Please choose one of the available seats above! 😊"
                )
        elif candidate_seat in booked_list:
            # Seat is ALREADY BOOKED (marked in yellow on the seat map!)
            ext.ghe_chon = ""
            chat_resp.current_phase = "SEAT_SELECTION"
            if lang_code == "vi":
                chat_resp.reply_message = (
                    f"⚠️ Rất tiếc, ghế **{candidate_seat}** đã có người đặt rồi ạ (được đánh dấu **màu vàng** trên sơ đồ)!\n\n"
                    f"✅ **Các ghế màu trắng hiện đang CÒN TRỐNG bạn có thể chọn:**\n"
                    f"🟢 **Tầng dưới (số lẻ):** {', '.join(low_avail) if low_avail else 'Hết chỗ'}\n"
                    f"🔵 **Tầng trên (số chẵn):** {', '.join(upp_avail) if upp_avail else 'Hết chỗ'}\n\n"
                    f"❌ *(Các ghế đã đặt màu vàng: {', '.join(booked_list)})*\n\n"
                    f"👉 Bạn vui lòng chọn một ghế màu trắng còn trống trong danh sách trên nhé! 😊"
                )
            elif lang_code == "ru":
                chat_resp.reply_message = (
                    f"⚠️ К сожалению, место **{candidate_seat}** уже занято (отмечено **желтым цветом** на схеме)!\n\n"
                    f"✅ **Свободные места (белые, без отметок), которые можно выбрать:**\n"
                    f"🟢 **Нижний ярус (нечетные):** {', '.join(low_avail) if low_avail else 'Нет мест'}\n"
                    f"🔵 **Верхний ярус (четные):** {', '.join(upp_avail) if upp_avail else 'Нет мест'}\n\n"
                    f"❌ *(Занятые места: {', '.join(booked_list)})*\n\n"
                    f"👉 Пожалуйста, выберите любое свободное (белое) место из списка выше! 😊"
                )
            else:
                chat_resp.reply_message = (
                    f"⚠️ Sorry, seat **{candidate_seat}** is already occupied (marked in **yellow** on the seat map)!\n\n"
                    f"✅ **Available (unmarked white) seats you can choose from:**\n"
                    f"🟢 **Lower Deck (Odd):** {', '.join(low_avail) if low_avail else 'Full'}\n"
                    f"🔵 **Upper Deck (Even):** {', '.join(upp_avail) if upp_avail else 'Full'}\n\n"
                    f"❌ *(Occupied seats: {', '.join(booked_list)})*\n\n"
                    f"👉 Please select one of the available white seats listed above! 😊"
                )
        else:
            ext.ghe_chon = candidate_seat

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
        system_content = ""
        history_lines = []
        for m in messages:
            if m["role"] == "system":
                system_content += m["content"] + "\n\n"
            elif m["role"] == "assistant":
                history_lines.append(f"AI Mentor: {m['content']}")
            else:
                history_lines.append(f"Nhân viên: {m['content']}")
        full_prompt = f"{system_content}HỘI THOẠI ĐÀO TẠO / HỎI ĐÁP:\n" + "\n".join(history_lines)

        candidate_models = [os.getenv("GEMINI_MODEL", "").strip(), "gemini-2.5-flash", "gemini-2.0-flash", "gemini-3.6-flash"]
        for model_name in [m for m in candidate_models if m]:
            try:
                model = genai.GenerativeModel(model_name)
                response = await model.generate_content_async(full_prompt)
                if response and response.text and response.text.strip():
                    return response.text.strip()
            except Exception as me:
                print(f"⚠️ Gemini text model {model_name} failed: {me}")
        return None
    except Exception as e:
        print(f"⚠️ Gemini text fallback exception: {e}")
        return None


def _load_staff_training_sops() -> str:
    """Đọc các tài liệu SOP và bộ quy tắc đào tạo nhân viên nội bộ."""
    chunks = []
    base_dir = os.path.dirname(__file__)
    for rel in [
        "QUY_TRINH_VAN_HANH_CHUAN_SOP_EASYTRIP.md",
        os.path.join("docs", "FILE_HUAN_LUYEN_RANG_BUOC_BAT_BUOC_AI_CHATBOT.md"),
    ]:
        p = os.path.join(base_dir, rel)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    txt = f.read().strip()
                if txt:
                    chunks.append(f"=== TÀI LIỆU NỘI BỘ: {os.path.basename(p)} ===\n{txt}")
            except Exception:
                pass
    return "\n\n".join(chunks)


STAFF_TRAINING_SOPS = _load_staff_training_sops()


async def process_staff_chat(
    question: str,
    history: list[dict] | None = None,
    mode: str = "training",
    staff_lang: str = "",
) -> str:
    """
    Trợ lý AI Đào tạo & Hỗ trợ Nghiệp vụ Nội bộ (Co-Pilot Staff Training & Helpdesk).
    - mode='training' (mặc định): Giải đáp tình huống chưa rõ, hướng dẫn SOP từng bước, cảnh báo sai sót, kèm mẫu câu trả lời khách nếu cần.
    - mode='reply_draft': Dán câu hỏi/tình huống của khách -> Soạn ngay tin nhắn trả lời chuẩn xác đúng ngôn ngữ khách + ghi chú nội bộ cho nhân viên.
    - mode='quiz': Đóng vai Quản lý đào tạo ra bài tập tình huống thực tế và chấm điểm/sửa lỗi cách xử lý của nhân viên.
    - staff_lang: Ngôn ngữ nhân viên sử dụng trên Co-Pilot ('vi' hoặc 'my' - Myanmar/Burmese; tự động nhận diện chữ Myanmar [\u1000-\u109F]).
    """
    q_clean = (question or "").strip()
    mode_norm = (mode or "training").strip().lower()
    if mode_norm not in {"training", "reply_draft", "quiz"}:
        mode_norm = "training"

    staff_lang_norm = (staff_lang or "").strip().lower()
    has_myanmar_script = bool(re.search(r"[\u1000-\u109F]", q_clean))
    if not has_myanmar_script and history:
        has_myanmar_script = any(
            bool(re.search(r"[\u1000-\u109F]", str(h.get("content", ""))))
            for h in history[-4:]
        )
    is_english_staff = staff_lang_norm in {"en", "eng", "english"}
    is_myanmar_staff = (not is_english_staff) and (staff_lang_norm in {"my", "mm", "myanmar", "burmese"} or has_myanmar_script)

    if is_english_staff:
        staff_lang_directive = (
            "NGÔN NGỮ TRẢ LỜI CHO NHÂN VIÊN (BẮT BUỘC): **TIẾNG ANH (ENGLISH)**.\n"
            "- Toàn bộ giải thích, hướng dẫn SOP từng bước, cảnh báo lỗi, câu hỏi/chấm điểm Quiz và ghi chú nội bộ PHẢI viết bằng **Tiếng Anh (English)** rõ ràng, chuyên nghiệp, dễ hiểu cho nhân viên quốc tế.\n"
            "- Giữ nguyên các thuật ngữ thao tác hệ thống & lệnh chuẩn (VD: `Scheme ...`, `Lock Ghế`, `VCB / VRB 1068582577`, `USDT`, `/english`, `/korean`, `/russian`, `/arabic`, `Bờ Y`, `Mộc Bài`, `Lao Bảo`, `A1..A10`, `B1..B10`).\n"
            "- Riêng phần **💬 Tin nhắn mẫu gửi khách** (trong chế độ `reply_draft` hoặc ví dụ gửi khách) PHẢI viết bằng **ngôn ngữ của khách hàng** (Anh/Nga/Hàn/Ả Rập/Trung/Việt tùy khách), kèm chú thích ngắn bằng Tiếng Anh.\n"
        )
    elif is_myanmar_staff:
        staff_lang_directive = (
            "NGÔN NGỮ TRẢ LỜI CHO NHÂN VIÊN (BẮT BUỘC): **TIẾNG MYANMAR (မြန်မာဘာသာ)**.\n"
            "- Toàn bộ giải thích, hướng dẫn SOP từng bước, cảnh báo lỗi, câu hỏi/chấm điểm Quiz và ghi chú nội bộ PHẢI viết bằng **Tiếng Myanmar (မြန်မာဘာသာ)** tự nhiên, rõ ràng, dễ hiểu.\n"
            "- Giữ nguyên các thuật ngữ thao tác hệ thống & lệnh chuẩn bằng ký tự gốc: `Scheme ...`, `Lock Ghế`, `VCB / VRB 1068582577`, `USDT`, `/english`, `/korean`, `/russian`, `/arabic`, tên cửa khẩu `Bờ Y`, `Mộc Bài`, `Lao Bảo`, `A1..A10`, `B1..B10`.\n"
            "- Riêng phần **💬 Tin nhắn mẫu gửi khách** PHẢI viết bằng **ngôn ngữ của khách hàng**.\n"
        )
    else:
        staff_lang_directive = (
            "NGÔN NGỮ TRẢ LỜI CHO NHÂN VIÊN (BẮT BUỘC): **TIẾNG VIỆT** (riêng phần tin nhắn mẫu gửi khách viết đúng ngôn ngữ của khách hàng).\n"
        )

    # 1. Lấy ngữ cảnh RAG từ cơ sở kiến thức (kết hợp thêm lượt hỏi gần nhất nếu nhân viên đang hỏi tiếp)
    rag_query = q_clean
    if history:
        recent_user_turns = [
            str(h.get("content", "")).strip()
            for h in history[-4:]
            if h.get("role") == "user" and str(h.get("content", "")).strip()
        ]
        if recent_user_turns:
            rag_query = " ".join(recent_user_turns[-2:] + [q_clean])

    rag_context = ""
    try:
        rag_context = knowledge_rag.format_for_prompt(rag_query, top_k=6)
    except Exception as e:
        print(f"⚠️ RAG search error for staff chat: {e}")

    # 2. Chỉ dẫn riêng theo từng chế độ đào tạo / hỗ trợ nhân viên
    if mode_norm == "reply_draft":
        mode_directive = (
            "CHẾ ĐỘ HIỆN TẠI: 💬 SOẠN TIN TRẢ LỜI KHÁCH (REPLY_DRAFT MODE)\n"
            "- Nhân viên đang dán tin nhắn/tình huống của khách hoặc hỏi cách trả lời khách.\n"
            "- Hãy trình bày rõ 2 phần:\n"
            "  1) **💬 Tin nhắn mẫu gửi khách** (Viết đúng 100% ngôn ngữ của khách: Nga/Anh/Hàn/Ả Rập/Trung/Việt/Myanmar, đúng bảng giá website theo thị trường khách, sạch sẽ để nhân viên bấm Sao chép gửi ngay).\n"
            "  2) **📌 Lưu ý nghiệp vụ cho nhân viên** (Viết bằng ngôn ngữ của nhân viên đang dùng — Tiếng Việt, Tiếng Anh (`staff_lang=en`) hoặc Tiếng Myanmar (`staff_lang=my`): giải thích ngắn vì sao báo giá/tuyến đó, cần xin thêm thông tin gì hay thao tác Telegram/Zalo gì tiếp theo)."
        )
    elif mode_norm == "quiz":
        mode_directive = (
            "CHẾ ĐỘ HIỆN TẠI: 🎯 LUYỆN TẬP TÌNH HUỐNG THỰC TẾ (QUIZ & COACHING MODE)\n"
            "- Bạn là **Trưởng phòng Điều hành / Mentor Đào tạo** của Easy Trip & Visa Co. Ltd.\n"
            "- Mục tiêu: Giúp nhân viên mới thành thạo mọi tình huống thực tế (chọn tuyến Bo-Y vs Mộc Bài, phân biệt giá 4 website /english /korean /russian /arabic, sơ đồ ghế ô trắng/gạch vàng và lệnh Lock, trẻ em <9 tuổi, sự cố đóng nhầm dấu 45D, gửi dấu trễ sau 08:00, in giấy A4 tại Mộc Bài vs PDF điện thoại tại Bờ Y, E-visa cuối tuần & hoàn tiền 100%, thanh toán VCB/VRB/USDT và mộc đỏ receipt).\n"
            "- Quy tắc tương tác (viết bằng ngôn ngữ của nhân viên đang dùng — Tiếng Việt, Tiếng Anh hoặc Tiếng Myanmar theo chỉ dẫn ngôn ngữ ở trên):\n"
            "  * Nếu nhân viên yêu cầu bắt đầu/ra đề/cho tình huống mới: Hãy đưa ra **01 tình huống cụ thể thực tế** (gồm tin nhắn khách hoặc sự cố tại cửa khẩu/văn phòng) và hỏi nhân viên: *Bạn sẽ xử lý bước nào, thu bao nhiêu tiền và nhắn gì cho khách?*.\n"
            "  * Nếu nhân viên đang trả lời bài tập của lượt trước: Hãy **chấm điểm (thang 10)**, nêu rõ **✅ Điểm làm tốt**, **⚠️ Điểm còn thiếu / ❌ Điểm sai so với SOP**, đưa ra **✨ Đáp án chuẩn & Mẫu câu gửi khách**, rồi hỏi nhân viên có muốn thử tiếp tình huống khó hơn không."
        )
    else:
        mode_directive = (
            "CHẾ ĐỘ HIỆN TẠI: 🎓 HỎI ĐÁP TÌNH HUỐNG & ĐÀO TẠO SOP (TRAINING MODE)\n"
            "- Nhân viên đang hỏi về một tình huống chưa rõ hoặc cách xử lý nghiệp vụ thực tế.\n"
            "- Hãy giải thích rõ ràng, thực chiến (bằng Tiếng Việt, Tiếng Anh hoặc Tiếng Myanmar theo chỉ dẫn ngôn ngữ ở trên) theo cấu trúc gọn dễ đọc:\n"
            "  1) **🎯 Kết luận & Quy tắc áp dụng** (Nêu rõ đúng/sai, số tiền chính xác theo đúng website `/english`, `/korean`, `/russian`, `/arabic` hoặc giá nội bộ CRM/đại lý nếu nhân viên hỏi nội bộ).\n"
            "  2) **📋 Các bước nhân viên cần làm** (Từng bước cụ thể: kiểm tra gì, gõ lệnh `Scheme` / `Lock ghế` trên Telegram Topic nào, báo Anh Luân Zalo hoặc nhà xe Chị Ngọc Cao / tài xế lúc nào).\n"
            "  3) **⚠️ Lưu ý & Lỗi hay gặp cần tránh** (VD: nhầm ghế A11/A20, quên nhắc in A4 ở Mộc Bài, nhầm giá giữa khách Nga và khách Quốc tế/Ả Rập, cuối tuần T7/CN không chạy gói 4-8h...).\n"
            "  4) **💬 Mẫu câu nhắn lại khách (nếu tình huống liên quan đến khách)** để nhân viên copy dùng ngay.\n"
            "- Nếu câu hỏi của nhân viên còn thiếu dữ kiện (chưa rõ quốc tịch, chưa rõ đi từ Nha Trang hay Đà Nẵng, khách mới hay khách cũ CRM...), hãy hướng dẫn **cả 2-3 trường hợp phổ biến nhất** rồi gợi ý nhân viên cung cấp thêm chi tiết để chốt phương án 100% chính xác."
        )

    # 3. Xây dựng system prompt đầy đủ kiến thức website + SOP
    system_prompt = (
        "Bạn là **Chuyên gia Đào tạo & Trợ lý Nghiệp vụ AI Nội bộ** của **Công ty TNHH Easy Trip & Visa (EASY TRIP & VISA CO. LTD)** — Trụ sở: 21 Phan Vinh, Nha Trang (MST: 4202051389).\n"
        "Nhiệm vụ tối thượng: Đào tạo nhân viên mới/CSKH/điều hành, giải đáp mọi tình huống chưa rõ 100% chính xác theo dữ liệu 4 website (`/english`, `/korean`, `/russian`, `/arabic`) và Tài liệu Quy trình Vận hành Chuẩn (SOP).\n\n"
        f"{staff_lang_directive}\n"
        f"{mode_directive}\n\n"
        "QUY TẮC BẮT BUỘC (KHÔNG BAO GIỜ ĐƯỢC BỊA ĐẶT):\n"
        "1. **Chính xác tuyệt đối về giá theo từng thị trường Website**:\n"
        "   - `/english` & `/korean`: Mộc Bài 6.000.000đ (Multi+Cam) / 5.000.000đ (Single+Cam) / 4.000.000đ (Bus+90D EV, +1tr Cam) / 1.400.000đ (45D) | Đà Nẵng–Lào 3.800.000đ (khẩn/tiêu chuẩn website; đặt sớm >=3d 3.550.000đ) / 950.000đ (45D) | E-visa lẻ: 1h 4.6M, 2h 3.4M, 4h 2.6M, 8h 2.9M, 1d 2.2M, 2d 2.15M, 3-5d 1.81M (Multi +1M) | Trẻ <9T: 1.48M + miễn 100% xe.\n"
        "   - `/russian` (Nga & CIS): Bờ Y 90D Single 3.400.000đ (2h) / Multi 4.400.000đ (Khách cũ CRM: 3.0M / 4.0M) / 45D 1.400.000đ (Khách cũ 1.3M) | Mộc Bài 5.4M (Multi+Cam) / 4.4M (Single+Cam) / 3.4M (90D Single) / 1.4M (45D) | E-visa lẻ RU: 1h 4.6M, 2h 3.4M, 4h 2.0M, 1d 1.81M, 2d 1.76M, 3-5d 1.61M (Multi +1M).\n"
        "   - `/arabic` (Ả Rập — bằng giá EN + 1.500.000đ): Mộc Bài 7.5M (Multi+Cam) / 6.5M (Single+Cam) / 5.5M (Bus+90D EV) | Đà Nẵng–Lào 5.3M | E-visa lẻ AR: 1h 6.1M, 2h 4.9M, 4h 4.1M, 1d 3.7M, 2d 3.65M, 3-5d 3.31M | Trẻ <9T card: 2.98M + miễn 100% xe.\n"
        "   - VIP Fast Track Website: 1.855.000đ ($70) tại DAD, CXR, PQC, VDO, HPH, HUI, VII, DLI, VCA; 1.200.000đ tại SGN & HAN; 300.000đ hỗ trợ cửa khẩu Lào (Lao Bảo/Bờ Y). (Khách cũ CRM/Đại lý vẫn có mức giá nội bộ riêng trong bảng SOP).\n"
        "2. **Chính sách thanh toán, cuối tuần & hoàn tiền**:\n"
        "   - Chấp nhận tiền mặt VND/USD, USDT (crypto), chuyển khoản Vietcombank (VCB) / VRB STK `1068582577` (`EASY TRIP & VISA CO. LTD`). Sau khi nhận tiền: đóng dấu mộc đỏ công ty lên receipt, chụp ảnh gửi khách.\n"
        "   - Hạn chót nộp tiền vé xe buýt: trước **14:00** ngày khởi hành.\n"
        "   - E-visa 4–8h không làm cuối tuần (T7/CN) & ngày lễ. Hoàn tiền **100%** nếu không ra visa đúng hạn đã cam kết (GMT+7).\n"
        "3. **Quy tắc cửa khẩu & sơ đồ ghế**:\n"
        "   - Tuyến Lào Bờ Y từ Nha Trang CHỈ dành cho Nga, Belarus, Hàn Quốc, Nhật Bản, Luxembourg, và 12 nước ASEAN. Toàn bộ quốc tịch khác từ Nha Trang PHẢI đi Campuchia (Mộc Bài, chạy tối T3, T5, CN lúc 21:30).\n"
        "   - Sơ đồ ghế xe chỉ có Tầng dưới lẻ (`A1..A9`, `B1..B9`) và Tầng trên chẵn (`A2..A10`, `B2..B10`, đôi khi `A12` dài 160cm); KHÔNG có A11/B11 hay số 13–20. Ô gạch vàng = ĐÃ ĐẶT; ô trắng = CÒN TRỐNG.\n"
        "   - Mộc Bài BẮT BUỘC in E-visa ra giấy A4; Bờ Y & Lao Bảo dùng file PDF trên điện thoại.\n"
        "4. Nếu nhân viên hỏi điều gì không có trong dữ liệu thực tế (VD: khách bay chuyến ngoài quy chuẩn, quá hạn visa overstay nặng...), hãy nói rõ cần báo Giám đốc Mr. Lý Việt Hoàng (+84 89 69 16 361) hoặc Anh Luân kiểm tra ca trực tiếp.\n\n"
        "=== CƠ SỞ KIẾN THỨC CỐT LÕI (KNOWLEDGE.TXT) ===\n"
        f"{KNOWLEDGE_BASE}\n\n"
        "=== TÀI LIỆU SOP & ĐÀO TẠO CHI TIẾT ===\n"
        f"{STAFF_TRAINING_SOPS}\n"
    )
    if rag_context:
        system_prompt += "\n" + rag_context

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        for h in history[-10:]:
            h_role = "assistant" if h.get("role") in ("assistant", "bot", "model") else "user"
            h_content = str(h.get("content", "")).strip()
            if h_content:
                messages.append({"role": h_role, "content": h_content})
    messages.append({"role": "user", "content": q_clean})

    # 4. Gọi LLM chính hoặc fallback dạng text
    content = await call_deepseek_text(messages)
    if not content or not content.strip():
        content = await call_groq_fallback_text(messages)
    if not content or not content.strip():
        content = await call_gemini_fallback_text(messages)

    if not content or not content.strip():
        return "🤖 Không thể kết nối với AI (API Error). Vui lòng thử lại sau hoặc tra cứu từ khóa!"

    return content.strip()
