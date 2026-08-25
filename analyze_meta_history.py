"""
Trích xuất Q&A từ dữ liệu chat Meta Business / Facebook Fanpage
Sử dụng mô hình GPT-OSS-120B trên Groq.
"""

import os
import sys
import json
import re
import asyncio
from dotenv import load_dotenv
from groq import AsyncGroq

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

def build_conversation_text(messages: list) -> str:
    lines = []
    for m in messages:
        sender = m.get("from", "?")
        text = str(m.get("text", "")).strip()
        if len(text) >= 2:
            lines.append(f"{sender}: {text}")
    return "\n".join(lines)

def load_meta_chats(filepath: str = "meta_chat.json") -> list[dict]:
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    chats_list = data.get("chats", {}).get("list", [])
    valid_chats = []
    for c in chats_list:
        name = c.get("name", "Unknown")
        messages = c.get("messages", [])
        if len(messages) < 2:
            continue
        conv_text = build_conversation_text(messages)
        if len(conv_text) < 40:
            continue
        if len(conv_text) > 7000:
            conv_text = conv_text[:7000] + "\n...[truncated]"
        valid_chats.append({"name": name, "text": conv_text, "msg_count": len(messages)})
    return valid_chats

EXTRACT_PROMPT = """You are an expert analyzing REAL customer service conversations from Facebook/Meta for "Easy Trip & Visa" (Vietnam visa run, Bo Y, Moc Bai, E-visa, Fast-Track, bus booking).

From the conversation below, extract high-quality, practical Question-Answer pairs for training a customer service AI chatbot.

WHAT TO EXTRACT:
1. Prices, departure times, pickup locations, routes.
2. Border visa run policies (Laos, Cambodia), visa requirements for various nationalities.
3. Fast-Track procedures, airport meet-and-greet, VIP assistance.
4. How staff answers customer inquiries, objections, and solutions provided.

RULES:
- Keep the Question and Answer in the ORIGINAL language (Vietnamese, Russian, English, Korean, etc.).
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
    model_name = "openai/gpt-oss-120b"
    try:
        response = await client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"Customer: {name}\n\n{chat['text']}"}
            ],
            temperature=0.1,
            max_tokens=2500
        )
        content = response.choices[0].message.content or ""
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            data = json.loads(json_match.group(0))
            pairs = data.get("qa_pairs", [])
            print(f"  [{idx}/{total}] {name[:35]:35s} -> {len(pairs)} Q&A")
            return pairs
        else:
            print(f"  [{idx}/{total}] {name[:35]:35s} -> 0 Q&A")
            return []
    except Exception as e:
        err = str(e)
        if ("rate_limit" in err.lower() or "429" in err) and retry < 5:
            rotate_key()
            await asyncio.sleep(5 * (retry + 1))
            return await extract_qa_from_chat(chat, idx, total, retry + 1)
        print(f"  [{idx}/{total}] LỖI ({name[:25]}): {err[:60]}")
        return []

async def process_all(chats: list[dict]) -> list[dict]:
    all_qa = []
    sem = asyncio.Semaphore(3)
    async def worker(chat, idx):
        async with sem:
            pairs = await extract_qa_from_chat(chat, idx, len(chats))
            await asyncio.sleep(1.0)
            return pairs
    tasks = [worker(chat, idx) for idx, chat in enumerate(chats, 1)]
    results = await asyncio.gather(*tasks)
    for p in results:
        all_qa.extend(p)
    return all_qa

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

async def main():
    print("=" * 60)
    print("TRÍCH XUẤT TRI THỨC TỪ META BUSINESS / FACEBOOK CHAT")
    print("=" * 60)
    chats = load_meta_chats("meta_chat.json")
    if not chats:
        print("❌ Không tìm thấy dữ liệu trong file meta_chat.json!")
        return

    print(f"-> Đã lọc được {len(chats)} cuộc trò chuyện Meta có nội dung")
    all_qa = await process_all(chats)
    unique_qa = deduplicate(all_qa)

    output_file = "extracted_qa_meta.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(unique_qa, f, ensure_ascii=False, indent=2)

    print(f"\n🎉 HOÀN THÀNH! Đã lưu {len(unique_qa)} cặp Q&A Meta vào file: {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
