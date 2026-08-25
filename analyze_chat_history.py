"""
Phiên bản trích xuất Q&A từ lịch sử chat Telegram tối ưu cho Easy Trip & Visa
Sử dụng mô hình OpenAI GPT-OSS-120B / 20B trên Groq.
"""

import os
import sys
import json
import re
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from groq import AsyncGroq

# Reconfigure stdout for Windows UTF-8
if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

load_dotenv()

GROQ_KEYS = [k.strip() for k in (os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY") or "").split(",") if k.strip()]
current_key_idx = 0

def get_client():
    return AsyncGroq(api_key=GROQ_KEYS[current_key_idx % len(GROQ_KEYS)])

def rotate_key():
    global current_key_idx
    current_key_idx = (current_key_idx + 1) % len(GROQ_KEYS)
    print(f"  -> Chuyển sang key {current_key_idx + 1}/{len(GROQ_KEYS)}")

# =====================================================================
# Lọc và đọc chat
# =====================================================================

SKIP_NAMES = {
    "N/A", "Bus VietNam", "Easytrip Operation Chat",
    "Easy Trip & Visa Operation", "Booking e-visa",
    "Easy Trip - Da Nang", "Visa Run - Operations Team",
    "Russians / Ukranians - Visa Run", "easytrip & Mr.Bolot",
}

def extract_text(msg) -> str:
    t = msg.get("text", "")
    if isinstance(t, list):
        t = " ".join([x if isinstance(x, str) else x.get("text", "") for x in t])
    return str(t).strip()

def build_full_conversation(messages: list) -> str:
    """Ghép toàn bộ tin nhắn của 1 cuộc chat thành 1 chuỗi text."""
    lines = []
    for m in messages:
        if m.get("type") != "message":
            continue
        text = extract_text(m)
        if len(text) < 3:
            continue
        sender = m.get("from", "?")
        lines.append(f"{sender}: {text}")
    return "\n".join(lines)

def load_customer_chats(filepath: str) -> list[dict]:
    """Trả về list of {name, type, conversation_text}."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    chats_list = data.get("chats", {}).get("list", [])
    result = []
    
    for chat in chats_list:
        name = chat.get("name") or "Unknown"
        ctype = chat.get("type", "")
        messages = chat.get("messages", [])
        
        if name in SKIP_NAMES:
            continue
        if ctype == "public_channel":
            continue
        if ctype == "personal_chat" and len(messages) < 5:
            continue
        if ctype in ("private_supergroup", "private_group") and len(messages) < 10:
            continue
        
        conv_text = build_full_conversation(messages)
        if len(conv_text) < 50:
            continue
        
        # Giới hạn 7000 ký tự mỗi cuộc chat (để vừa context window)
        if len(conv_text) > 7000:
            conv_text = conv_text[:7000] + "\n...[truncated]"
        
        result.append({"name": name, "type": ctype, "text": conv_text, "msg_count": len(messages)})
    
    return result

# =====================================================================
# AI Trích xuất
# =====================================================================

EXTRACT_PROMPT = """You are an expert analyzing REAL customer service conversations for "Easy Trip & Visa" - a Vietnam-based visa run (Laos Bo Y border, Cambodia Moc Bai border, eVisa, bus services, airport fast-track).

From the conversation below, extract high-quality, practical Question-Answer pairs for training a customer service AI chatbot.

WHAT TO EXTRACT:
1. Pricing, bus schedules, departure locations (Nha Trang, Da Nang, Ho Chi Minh).
2. Visa run procedures for Laos (Bo Y border) & Cambodia (Moc Bai), requirements for nationalities (Russia, Kazakhstan, UK, USA, Korea, etc.).
3. E-visa processing times (emergency 4h, 1 day, standard), passport validity requirements (6+ months).
4. Staff explanations, solutions for delays, border fees, seat bookings, baggage, special requests.

RULES:
- Keep the Question and Answer in the ORIGINAL language (Vietnamese, Russian, English, Korean, etc.).
- The question must be clear and self-contained.
- The answer must be informative and accurate based on what the staff answered.
- Return ONLY valid JSON format:
{
  "qa_pairs": [
    {"question": "...", "answer": "..."}
  ]
}
"""

async def extract_qa_from_chat(chat: dict, idx: int, total: int, retry: int = 0) -> list[dict]:
    client = get_client()
    name = chat["name"]
    model_name = "openai/gpt-oss-120b" if retry % 2 == 0 else "openai/gpt-oss-20b"
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"Customer Chat Name: {name}\n\n{chat['text']}"}
            ],
            temperature=0.1,
            max_tokens=2500
        )
        content = response.choices[0].message.content or ""
        
        # Parse JSON robustly
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            data = json.loads(json_match.group(0))
            pairs = data.get("qa_pairs", [])
            print(f"  [{idx}/{total}] {name[:40]:40s} -> {len(pairs)} Q&A")
            return pairs
        else:
            print(f"  [{idx}/{total}] {name[:40]:40s} -> 0 Q&A (No JSON)")
            return []

    except Exception as e:
        err = str(e)
        if ("rate_limit" in err.lower() or "429" in err) and retry < 5:
            rotate_key()
            wait = 5 * (retry + 1)
            print(f"  [{idx}/{total}] Rate limit -> chờ {wait}s (lần {retry+1})...")
            await asyncio.sleep(wait)
            return await extract_qa_from_chat(chat, idx, total, retry + 1)
        print(f"  [{idx}/{total}] LỖI ({name[:30]}): {err[:80]}")
        return []

async def process_all(chats: list[dict]) -> list[dict]:
    all_qa = []
    total = len(chats)
    sem = asyncio.Semaphore(3)  # 3 concurrent requests to respect rate limits smoothly

    async def worker(chat, idx):
        async with sem:
            pairs = await extract_qa_from_chat(chat, idx, total)
            await asyncio.sleep(1.0)  # Smooth delay between requests
            return pairs

    tasks = [worker(chat, idx) for idx, chat in enumerate(chats, 1)]
    results = await asyncio.gather(*tasks)
    
    for pairs in results:
        all_qa.extend(pairs)
        
    return all_qa

# =====================================================================
# Dedup
# =====================================================================

def deduplicate(qa_list: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for qa in qa_list:
        q = qa.get("question", "").strip().lower()[:120]
        a = qa.get("answer", "").strip()
        if q and len(q) > 6 and len(a) > 5 and q not in seen:
            seen.add(q)
            unique.append(qa)
    return unique

# =====================================================================
# MAIN
# =====================================================================

async def main():
    print("=" * 60)
    print("EASY TRIP - TRÍCH XUẤT TRI THỨC Q&A TELEGRAM (GPT-OSS-120B)")
    print("=" * 60)
    
    if not os.path.exists("telegram_chat.json"):
        print("LỖI: Không tìm thấy file telegram_chat.json!")
        return
    
    print("\n[1/3] Đọc và lọc các cuộc trò chuyện khách hàng...")
    chats = load_customer_chats("telegram_chat.json")
    print(f"  -> Đã lọc được {len(chats)} cuộc trò chuyện có nội dung thực tế")
    
    print(f"\n[2/3] Dùng AI phân tích trích xuất Q&A từ {len(chats)} cuộc trò chuyện...\n")
    all_qa = await process_all(chats)
    
    unique_qa = deduplicate(all_qa)
    print(f"\n[3/3] Kết quả phân tích:")
    print(f"  - Tổng số cặp Q&A trích xuất thô: {len(all_qa)}")
    print(f"  - Sau khi lọc trùng lặp & chuẩn hóa: {len(unique_qa)} cặp Q&A chất lượng cao")
    
    output_file = "extracted_qa_telegram.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(unique_qa, f, ensure_ascii=False, indent=2)
    print(f"  -> Đã lưu dữ liệu tri thức vào file: {output_file}")
    
    print("\n" + "=" * 60)
    print(f"🎉 HOÀN THÀNH! {len(unique_qa)} cặp Q&A đã sẵn sàng nạp vào bộ não Chatbot!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
