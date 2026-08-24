import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

# Khởi tạo Groq và các cấu hình Lark
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEYS", "").split(",")[0].strip())
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
LARK_KNOWLEDGE_TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")

# Hàm lấy token kết nối Lark
async def get_tenant_access_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    data = {
        "app_id": LARK_APP_ID,
        "app_secret": LARK_APP_SECRET
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("tenant_access_token")

# Hàm đẩy dữ liệu hàng loạt lên Lark Base
async def batch_add_lark_records(records_list: list):
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{LARK_KNOWLEDGE_TABLE_ID}/records/batch_create"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    payload = {
        "records": [
            {
                "fields": {
                    "Question": item["Question"],
                    "Answer": item["Answer"]
                }
            }
            for item in records_list
        ]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload, timeout=30.0)
        if response.status_code != 200:
            print("Lark Batch Create Error:", response.text)
            return False
        return True

# Hàm đọc và chia file làm 4 phần
def load_and_split_4_parts():
    with open("knowledge.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
    n = len(lines)
    chunk_size = n // 4
    
    part1 = "".join(lines[:chunk_size])
    part2 = "".join(lines[chunk_size:chunk_size*2])
    part3 = "".join(lines[chunk_size*2:chunk_size*3])
    part4 = "".join(lines[chunk_size*3:])
    
    return [part1, part2, part3, part4]

# Trích xuất FAQs bằng Groq AI cho từng phần
async def extract_faqs_chunk(text_content: str, chunk_name: str):
    print(f"Đang gửi {chunk_name} tới Groq để sàng lọc...")
    
    system_prompt = """You are a data analyst and FAQ documentation expert for Visarun tour bus company.
Your task is to read the provided knowledge content, extract customer real-life questions/scenarios (Question) and the corresponding answers/procedures (Answer).

EXTREMELY IMPORTANT REQUIREMENTS:
1. Remove repetitive or redundant parts.
2. Write questions and answers in natural, concise, easy to understand, and professional ENGLISH.
3. If there is highly specific information such as bus ticket prices, Laos itineraries, Cambodia itineraries, departure dates, and visa regulations, compile them into clear Q&A pairs.
4. Return the result in JSON format with the exact structure below:
{
  "faqs": [
    {
      "Question": "Question/Scenario",
      "Answer": "Standard answer"
    }
  ]
}"""

    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=1500
        )
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        return data.get("faqs", [])
    except Exception as e:
        print(f"Lỗi khi xử lý {chunk_name}: {e}")
        return []

async def main():
    try:
        parts = load_and_split_4_parts()
        all_faqs = []
        
        for idx, part in enumerate(parts, 1):
            faqs = await extract_faqs_chunk(part, f"Phần {idx}/4")
            print(f"-> Đã lọc xong Phần {idx}: Lấy được {len(faqs)} câu hỏi.")
            all_faqs.extend(faqs)
            
            # Chờ 4 giây giữa các yêu cầu để tránh giới hạn TPM của tài khoản Free
            if idx < 4:
                print("Chờ 4 giây trước khi xử lý phần tiếp theo...")
                await asyncio.sleep(4)
        
        if not all_faqs:
            print("Không trích xuất được câu hỏi nào từ file.")
            return
            
        print(f"\n🎉 TỔNG CỘNG ĐÃ TRÍCH XUẤT THÀNH CÔNG: {len(all_faqs)} cặp câu hỏi & câu trả lời chuẩn!")
        print("Bắt đầu đẩy dữ liệu lên Lark Base...")
        
        # Đẩy dữ liệu lên Lark theo lô
        batch_size = 100
        for i in range(0, len(all_faqs), batch_size):
            chunk = all_faqs[i:i+batch_size]
            success = await batch_add_lark_records(chunk)
            if success:
                print(f"Đã đẩy thành công lô {i//batch_size + 1} ({len(chunk)} dòng) lên Lark Base!")
            else:
                print(f"Lỗi khi đẩy lô {i//batch_size + 1}!")
                
        print("\n🏆 HOÀN THÀNH RỰC RỠ! Toàn bộ kho tri thức của sếp đã được sàng lọc thông minh bằng AI và đồng bộ hóa thành công lên Lark Base!")
    except Exception as e:
        print("Lỗi hệ thống:", e)

if __name__ == "__main__":
    asyncio.run(main())
