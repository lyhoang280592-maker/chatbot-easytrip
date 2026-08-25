import os
import json
import asyncio
from docx import Document
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

GROQ_KEYS = [k.strip() for k in (os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY") or "").split(",") if k.strip()]
current_key_idx = 0

def get_client():
    return AsyncGroq(api_key=GROQ_KEYS[current_key_idx % len(GROQ_KEYS)])

def rotate_key():
    global current_key_idx
    current_key_idx = (current_key_idx + 1) % len(GROQ_KEYS)
    print(f"  -> Chuyen sang key {current_key_idx + 1}/{len(GROQ_KEYS)}")

# =====================================================================
# Trích xuất dữ liệu từ DOCX
# =====================================================================

def extract_docx_data(filepath: str):
    print(f"--- Dang doc file: {filepath} ---")
    doc = Document(filepath)
    
    # 1. Trich xuat van ban
    full_text = []
    for para in doc.paragraphs:
        if para.text.strip():
            full_text.append(para.text.strip())
    
    combined_text = "\n".join(full_text)
    print(f"  Da trich xuat {len(full_text)} doan van ban.")

    # 2. Trich xuat hinh anh (luu vao thu muc)
    img_dir = "zalo_images"
    os.makedirs(img_dir, exist_ok=True)
    img_count = 0
    
    for rel in doc.part.rels.values():
        if "image" in rel.target_ref:
            img_count += 1
            img_data = rel.target_part.blob
            img_ext = rel.target_ref.split('.')[-1]
            img_name = f"image_{img_count}.{img_ext}"
            with open(os.path.join(img_dir, img_name), "wb") as f:
                f.write(img_data)
    
    print(f"  Da trich xuat {img_count} hinh anh vao thu muc '{img_dir}'.")
    return combined_text

# =====================================================================
# AI Trich xuat Q&A
# =====================================================================

EXTRACT_PROMPT = """You are an expert at analyzing customer conversations for "Easy Trip & Visa".

From the text below, extract REAL and USEFUL question-answer pairs for a chatbot.
Focus on:
- Visarun logic (dates, borders, nationality rules)
- Prices, schedules, booking flow
- How staff handles customer concerns naturally

Return JSON:
{
  "qa_pairs": [
    {"question": "...", "answer": "..."}
  ]
}"""

async def analyze_text_chunk(text: str, idx: int, total_chunks: int):
    client = get_client()
    try:
        response = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"Text chunk {idx}:\n\n{text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        pairs = data.get("qa_pairs", [])
        print(f"  Batch {idx}/{total_chunks}: {len(pairs)} Q&A")
        return pairs
    except Exception as e:
        if "rate_limit" in str(e).lower():
            rotate_key()
            await asyncio.sleep(10)
            return await analyze_text_chunk(text, idx, total_chunks)
        print(f"  Batch {idx} LOI: {e}")
        return []

async def main():
    docx_path = "zalo_chat.docx"
    if not os.path.exists(docx_path):
        print(f"Khong tim thay file {docx_path}")
        return

    # Buoc 1: Trich xuat
    text = extract_docx_data(docx_path)
    
    # Buoc 2: Chia nho text de AI xu ly (moi batch ~4000 ky tu)
    chunk_size = 4000
    chunks = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
    print(f"\nChia du lieu thanh {len(chunks)} batch de AI phan tich...")

    # Buoc 3: AI xu ly batch
    all_qa = []
    for i, chunk in enumerate(chunks, 1):
        pairs = await analyze_text_chunk(chunk, i, len(chunks))
        all_qa.extend(pairs)
        await asyncio.sleep(2) # Tranh spam API

    # Buoc 4: Luu ket qua
    output_file = "extracted_qa_zalo_docx.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_qa, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== HOAN THANH ===")
    print(f"Tong cong trich xuat duoc {len(all_qa)} cap Q&A tu Zalo Docx.")
    print(f"Ket qua luu tai: {output_file}")
    print(f"Anh da duoc trich xuat vao thu muc 'zalo_images'.")

if __name__ == "__main__":
    asyncio.run(main())
