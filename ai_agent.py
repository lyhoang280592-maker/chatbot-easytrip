import os
import re
from datetime import datetime
import httpx
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv
from i18n import get_lang_code, get_msg
import knowledge_rag

load_dotenv()

# === CONFIGURATION ===
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GROQ_API_KEYS = [
    k.strip() for k in os.getenv("GROQ_API_KEYS", "").split(",") if k.strip()
]
DEEPSEEK_MODEL = "deepseek-chat"
GROQ_MODEL = "llama-3.1-8b-instant"


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
            json_str = json_data

        try:
            # 1. Trích xuất phần JSON giữa cặp ngoặc nhọn đầu tiên và cuối cùng
            match_json = re.search(r"(\{.*\})", json_str, re.DOTALL)
            if match_json:
                clean_data = match_json.group(1).strip()
            else:
                clean_data = json_str.strip()

            # 2. Làm sạch Markdown nếu vẫn còn
            if "```" in clean_data:
                match = re.search(r"```(?:json)?\s*(.*?)\s*```", clean_data, re.DOTALL)
                if match:
                    clean_data = match.group(1)

            # 3. Sửa lỗi dấu phẩy thừa
            clean_data = re.sub(r",\s*([\]}])", r"\1", clean_data)

            # 4. Parse JSON
            data = json.loads(clean_data)

            # 5. Đảm bảo extracted_data luôn là dict
            if "extracted_data" not in data or not isinstance(
                data["extracted_data"], dict
            ):
                data["extracted_data"] = {}

            return cls.model_validate(data, *args, **kwargs)
        except Exception as e:
            print(f"⚠️ JSON Parse Fallback triggered: {e}")
            # PHƯƠNG ÁN CỨU HỘ CUỐI CÙNG: Nếu JSON lỗi hoàn toàn, lấy text thô làm reply_message
            msg_match = re.search(
                r'"reply_message"\s*:\s*"(.*?)"', json_str, re.DOTALL
            )
            if msg_match:
                msg = msg_match.group(1)
            else:
                # Nếu không tìm thấy trường reply_message nhưng có chữ thô, lấy chữ thô đó
                stripped = json_str.strip()
                if len(stripped) > 10 and not stripped.startswith("{"):
                    msg = stripped
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
    try:
        with open("knowledge.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
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
5. **Route Eligibility**:
   - Nationalities not exempt from Laos visa (e.g. USA, Canada, Australia, Brazil, UK, etc.) **MUST** take the Cambodia route. Laos is not available for them.
   - Cambodia visa run package costs **4,000,000 VND** (includes round-trip bus + 90-day Vietnam E-visa). The customer must pay for their own Cambodia visa at the border (approx. 35$ - 50$). Cambodia bus departs only on **Tuesdays, Thursdays, and Sundays**.

CRITICAL DIRECTIVE - LANGUAGE SWITCHING (MANDATORY):
1. **Rule A (Input Message Language)**: Respond IMMEDIATELY in the language used by the customer. If the user messages in English, reply in English. If in Russian, reply in Russian. If in Vietnamese, reply in Vietnamese. If in Korean, reply in Korean.
2. **Rule B (Nationality-based Language)**: The moment you realize or extract that the customer is Russian (or Belarus, Kazakh, Ukrainian, Russian speaker), you MUST IMMEDIATELY switch the conversation to RUSSIAN, even if the customer started the conversation in English or Vietnamese!
   - Example: Customer says "Hello, I want to book a visa run. I am Russian." -> Your reply MUST be in RUSSIAN (e.g., "Привет! Рад помочь вам с визараном...").
   - Example: Customer says "Hello, I'm Korean." -> Your reply MUST be in KOREAN (e.g., "안녕하세요! ...").
3. Do NOT default to English or Vietnamese if the customer's nationality or language is different.
4. **RAG Context Language Warning**: You will see 'RELEVANT PAST EXPERIENCE FROM REAL CUSTOMER CHATS' in the prompt, which may be in Vietnamese or Russian. DO NOT copy or switch to their languages! You MUST strictly follow Rule A and Rule B. If the customer chats in English and is a US/UK citizen, you MUST reply in English, even if the RAG examples are in Vietnamese!

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
  - WhatsApp Support: https://wa.me/84868462071
- **VALUE-FIRST (ADVISE FIRST, PROCEDURES LATER)**: If the customer asks a question (such as prices, schedules, routes, border fees, visa requirements), **immediately and directly answer their question first** clearly, politely, and professionally. Do NOT withhold prices or information until they answer a checklist. Provide value first to build trust!
- **GENTLE INFORMATION GATHERING**: After answering their questions, naturally and politely ask for the next piece of information needed to check availability and arrange their trip:
  1. Nationality - to recommend the correct border (Laos Bo Y for RU/KR/BY/ASEAN; Cambodia Moc Bai for others).
  2. Visa Expiry Date - to calculate the exact departure date (1 day before expiry).
  3. Current City - to match the starting point (Nha Trang or Da Nang).
  4. Desired Visa Type (45-day Visa Free or 90-day E-visa).
  5. Contact Phone Number / Zalo / WhatsApp (Số điện thoại).
  *Ask for these details naturally in conversation, rather than a rigid list, to maintain a warm and friendly tone.*

CONVERSATION PHASES (TECHNICAL STATE MANAGEMENT):

PHASE 1 - CONSULTING:
- Answer all inquiries, explain packages, and collect the 5 key booking details naturally.
- Switch to PHASE 2 once the customer agrees to proceed with booking/selecting a seat (or after you've proposed a departure date and they are ready to proceed).
- Provide the service registration form link to the customer during consultation so they can fill out their details: https://ejpiqmzrvkf1.jp.larksuite.com/share/base/form/shrjpsFK9frTbNtt85sCXlx3b3c

PHASE 2 - SEAT_SELECTION:
- Move to this phase when the customer is ready to select a seat.
- Present the final selected package details:
  - 🚌 Route & Departure Date (calculated dynamically as 1 day before visa expiry, format DD/MM).
  - 💰 Total Price (in VND).
  - 📍 Pickup Location (default Oceanus Nha Trang or River Station in Nha Trang, or Da Nang office).
  - ⏰ Departure Time.
- End your reply with: "Please wait a moment while we check seat availability and send you the seat map..." (translated to the customer's language).
- Set `current_phase = "SEAT_SELECTION"`.
- Crucial: Populate `extracted_data.ngay_khoi_hanh` with the calculated departure date (format DD/MM, e.g., "05/06") so the system can retrieve the correct seat map.

PHASE 3 - PAYMENT:
- After a seat is chosen, provide the payment instructions (translated to the customer's language):
  "Please select your payment method. You can transfer the funds to our company's bank account or purchase the tickets directly at our office at the address provided below!
  Thank you!

  Bank Transfer (To a Vietnamese Account)
  🏦 Bank: Joint Stock Commercial Bank for Foreign Trade of Viet Nam (Vietcombank)
  👤 Account Holder: EASY TRIP & VISA CO. LTD
  🔢 Account Number: 1068582577

  Alternatively, you can pay directly at our office: 21 Phan Vinh, South Nha Trang.
  https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9"

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
        "temperature": 0.3,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"]
            return None
        except Exception:
            return None


async def call_groq_fallback(messages):
    if not GROQ_API_KEYS:
        return None
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    
    # Try each available API key to handle rate limits or transient errors
    for idx, key in enumerate(GROQ_API_KEYS):
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=25) as client:
            try:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"]
                else:
                    print(f"⚠️ Groq key {idx+1} failed with status {r.status_code}: {r.text}")
            except Exception as e:
                print(f"⚠️ Groq key {idx+1} exception: {e}")
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

        # Only Laos 45D runs daily. Cambodia (all) and Laos 90D run on Tue/Thu/Sun
        is_daily = "45" in loai_lower and "cambodia" not in dest_lower and "campuchia" not in dest_lower
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

def extract_date_and_nationality_from_history(history_messages: list[dict]):
    user_text = " ".join([m["content"] for m in history_messages if m.get("role") == "user"])
    full_text = " ".join([m["content"] for m in history_messages])
    user_text_lower = user_text.lower()
    full_text_lower = full_text.lower()
    
    # 1. Extract expiry date
    date_match = re.search(r"\b(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?\b", user_text)
    expiry_date = None
    if date_match:
        day = date_match.group(1)
        month = date_match.group(2)
        year = date_match.group(3) or str(datetime.now().year)
        if len(day) == 1: day = "0" + day
        if len(month) == 1: month = "0" + month
        if len(year) == 2: year = "20" + year
        expiry_date = f"{day}/{month}/{year}"
        
    # 2. Extract destination based on whole-word or keyword matches
    destination = "laos"
    cambodia_keywords = [
        "us", "usa", "american", "uk", "british", "germany", "german", "france", "french", 
        "canada", "canadian", "australia", "australian", "india", "indian", "mỹ", "anh", "pháp", "đức"
    ]
    
    has_cambodia_keyword = False
    for kw in cambodia_keywords:
        if kw in ["us", "uk", "mỹ", "anh", "đức"]:
            # Strict whole-word matching to avoid matching substrings like "bus" or "status"
            if re.search(r"\b" + re.escape(kw) + r"\b", user_text_lower):
                has_cambodia_keyword = True
                break
        else:
            if kw in user_text_lower:
                has_cambodia_keyword = True
                break
                
    if has_cambodia_keyword or "cambodia" in user_text_lower or "campuchia" in user_text_lower or "mộc bài" in user_text_lower or "moc bai" in user_text_lower:
        destination = "cambodia"
        
    # 3. Extract visa type (45D vs 90D)
    visa_type = "90D"  # Default is 90D
    if destination == "laos":
        if "45" in full_text_lower or "free" in full_text_lower or "miễn" in full_text_lower:
            visa_type = "45D"
            
    return expiry_date, destination, visa_type


async def process_chat(history_messages: list[dict]) -> ChatResponse:
    recent_history = history_messages[-8:]

    # 1. Tìm ngày hết hạn visa và tính ngày đi bằng Python
    expiry_date, destination, visa_type = extract_date_and_nationality_from_history(history_messages)
    
    smart_departure_context = ""
    route_directive_context = ""
    
    # Force route directives to ensure LLM doesn't get confused by RAG examples
    if destination == "cambodia":
        route_directive_context = (
            f"\nCRITICAL ROUTE DIRECTIVE:\n"
            f"- Customer MUST take the CAMBODIA route (Moc Bai border) because their nationality requires a pre-arranged visa or Bo Y border (Laos) is not suitable.\n"
            f"- YOU MUST recommend ONLY the CAMBODIA route (Moc Bai border) for their visarun! Do NOT suggest or offer Laos! "
            f"Explicitly inform them that they need to take the Cambodia route (Moc Bai border)."
        )
    else:
        route_directive_context = (
            f"\nCRITICAL ROUTE DIRECTIVE:\n"
            f"- Customer is from a country exempt from Laos visa (like Russia, Belarus, South Korea, ASEAN). They MUST take the LAOS route (Bo Y border) to save costs!\n"
            f"- YOU MUST recommend ONLY the LAOS route (Bo Y border) for their visarun! Do NOT suggest Cambodia!"
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
                f"- Since our bus to Cambodia/90D Laos only runs on Tuesday, Thursday, and Sunday nights, the departure date must be {smart_dep} ({day_name_en}) to avoid overstaying.\n"
                f"- YOU MUST propose exactly the date '{smart_dep}' ({day_name_en}) as their departure date in your response! Do NOT suggest any other date. Clearly state this date to the customer and explain that the bus departs on this day."
            )

    # 2. Đoán ngôn ngữ đích bằng Python dựa trên quốc tịch / tin nhắn
    lang_code = get_lang_code(destination)
    user_text = " ".join([m["content"] for m in history_messages if m.get("role") == "user"])
    user_text_lower = user_text.lower()
    
    # Kiểm tra xem khách có sử dụng bảng chữ cái tiếng Nga hoặc gõ tiếng Việt hay không
    if re.search(r'[а-яё]', user_text_lower):
        lang_code = "ru"
    elif any(w in user_text_lower for w in ["chào", "xin chào", "giá", "vé", "lào", "bao nhiêu", "đi", "xe"]):
        lang_code = "vi"
    elif "kor" in user_text_lower or "hàn" in user_text_lower:
        lang_code = "ko"
        
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
            last_user_msg = msg.get("content", "")
            break

    rag_context = ""
    if last_user_msg:
        try:
            rag_context = knowledge_rag.format_for_prompt(last_user_msg, top_k=5)
        except Exception as e:
            print(f"⚠️ RAG search error: {e}")

    # Inject contexts into system prompt
    dynamic_prompt = SYSTEM_PROMPT
    if rag_context:
        dynamic_prompt = SYSTEM_PROMPT + "\n\n" + rag_context
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
    if not content:
        content = await call_groq_fallback(messages)

    if not content:
        # Fallback in case of complete API failure
        lang = lang_code
        return ChatResponse(
            reply_message=get_msg("system_busy", lang),
            extracted_data=CustomerData(),
            current_phase="CONSULTING",
            is_complete=False,
        )

    return ChatResponse.model_validate_json(content)


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
                return r.json()["choices"][0]["message"]["content"]
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
                    return r.json()["choices"][0]["message"]["content"]
                else:
                    print(f"⚠️ Groq text key {idx+1} failed with status {r.status_code}: {r.text}")
            except Exception as e:
                print(f"⚠️ Groq text key {idx+1} exception: {e}")
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
    if not content:
        content = await call_groq_fallback_text(messages)

    if not content:
        return "🤖 Không thể kết nối với AI (API Error). Vui lòng thử lại sau hoặc tra cứu từ khóa!"

    return content.strip()
