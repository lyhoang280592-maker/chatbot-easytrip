import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

# Khởi tạo Groq và cấu hình Lark
groq_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
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

# Đọc file content cào từ website sếp
def load_website_content():
    # Sử dụng đúng đường dẫn tuyệt đối của file lưu trữ trang web
    path = r"C:\Users\Admin\.gemini\antigravity\brain\af36cb5a-3073-4153-a344-63a8469bfc3f\.system_generated\steps\491\content.md"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# Trích xuất dữ liệu website thành Q&As bằng Groq AI
async def extract_website_faqs(web_text: str):
    print("Đang gửi nội dung Website tới Groq AI để phân tích...")
    
    system_prompt = """Bạn là một chuyên gia phân tích dữ liệu chuyên nghiệp. 
Nhiệm vụ của bạn là đọc toàn bộ nội dung website của công ty Easy Trip & Visa dưới đây và lọc ra danh sách các dịch vụ kèm câu hỏi đáp (FAQs) cực kỳ đầy đủ.

BẠN CẦN TẬP TRUNG TRÍCH XUẤT CÁC CÂU HỎI ĐÁP TIẾNG VIỆT SAU:
1. Dịch vụ VIP Fast Track tại sân bay (Mức giá 1.200.000đ / 70$, các đặc quyền VIP như đón ở cửa máy bay, đi cổng ưu tiên, lấy thẻ lên tàu nhanh, qua an ninh siêu tốc 5-10 phút).
2. Dịch vụ Visa khẩn (làm e-visa trong 1 giờ, 4 giờ, 8 giờ, 2 ngày, sửa lỗi sai thông tin e-visa).
3. Miễn thị thực 5 năm (kể cả trường hợp chưa kết hôn chính thức nhưng có con chung).
4. Dịch vụ làm phiếu Lý lịch tư pháp (cho tất cả quốc tịch để làm GPLĐ, thẻ tạm trú).
5. Tuyến Visarun từ ĐÀ NẴNG đi Lào (Giá vé các gói 2.150.000đ, 2.200.000đ, 2.600.000đ, 3.400.000đ, 4.600.000đ tùy thuộc vào thời gian xử lý e-visa khẩn; xe chạy lúc 5:30 sáng hằng ngày từ thứ 2 đến thứ 6/thứ 7).
6. Dịch vụ cho thuê xe máy tại Nha Trang (xe mới, tiết kiệm xăng, giao tận nơi, có mũ bảo hiểm).
7. Thông tin liên hệ của Easy Trip & Visa (Tên công ty, địa chỉ văn phòng tại 21 Phan Vinh, số Zalo/Whatsapp +84 868 462 071, Telegram @easytripvisa).

Hãy biên soạn thành các câu hỏi (Question) và câu trả lời (Answer) bằng TIẾNG VIỆT thật súc tích, đầy đủ và chuyên nghiệp.
Yêu cầu trả về kết quả dưới dạng JSON chuẩn xác 100% như sau:
{
  "faqs": [
    {
      "Question": "Câu hỏi cụ thể về dịch vụ",
      "Answer": "Câu trả lời đầy đủ, chi tiết kèm bảng giá"
    }
  ]
}"""

    response = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": web_text}
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=3000
    )
    
    raw_json = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw_json)
        return data.get("faqs", [])
    except Exception as e:
        print("Lỗi parse JSON từ Groq:", e)
        return []

async def main():
    try:
        web_text = load_website_content()
        faqs = await extract_website_faqs(web_text)
        
        if not faqs:
            print("Không trích xuất được câu hỏi nào từ website.")
            return
            
        print(f"🎉 Đã trích xuất thành công {len(faqs)} câu hỏi & trả lời VIP từ website!")
        print("Bắt đầu đẩy lên Lark Base...")
        
        success = await batch_add_lark_records(faqs)
        if success:
            print(f"🔥 THÀNH CÔNG! Đã đẩy thành công toàn bộ {len(faqs)} câu hỏi từ website lên Lark Base!")
        else:
            print("Lỗi khi đẩy dữ liệu lên Lark Base.")
    except Exception as e:
        print("Lỗi hệ thống:", e)

if __name__ == "__main__":
    asyncio.run(main())
