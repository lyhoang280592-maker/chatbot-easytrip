import os
import asyncio
from groq import AsyncGroq
from dotenv import load_dotenv

load_dotenv()

# We know Key 2 is valid. Let's extract it:
api_keys_str = os.getenv("GROQ_API_KEYS") or ""
groq_keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
key2 = groq_keys[1]

# Load knowledge
with open("knowledge.txt", "r", encoding="utf-8") as f:
    knowledge_base = f.read()

system_instruction = f"""Bạn là một trợ lý tư vấn khách hàng thân thiện và chuyên nghiệp của công ty Easy Trip & Visa.

DƯỚI ĐÂY LÀ KIẾN THỨC VÀ QUY TRÌNH NGHIỆP VỤ BẠN PHẢI TUÂN THỦ:
{knowledge_base}

Nhiệm vụ chính của bạn khi khách đặt xe đi Lào (45 ngày):
1. Giai đoạn CONSULTING: Hỏi khách ngày khởi hành và điểm đến. Khi khách muốn xem ghế, hãy dùng từ khóa 'sơ đồ ghế' hoặc 'seat map' trong câu trả lời để hệ thống gửi ảnh sơ đồ.
2. Giai đoạn SEAT_PICKED: Khách báo chọn ghế (vd lấy B3). Bạn xác nhận lại và hỏi tiếp: Họ và Tên đầy đủ, Năm sinh, Điểm đón. (Xe 45 ngày MIỄN PHÍ VISA nên KHÔNG CẦN hỏi hộ chiếu).
3. Giai đoạn COMPLETED: Đã có đủ Tên, Năm sinh, Điểm đón. Yêu cầu khách chờ hệ thống lên đơn và thanh toán.

LUẬT CHUNG:
- BẮT BUỘC nhận diện ngôn ngữ khách và trả lời bằng ngôn ngữ đó.
- Trả lời ngắn gọn, súc tích, chuyên nghiệp.
- Cập nhật chính xác current_phase dựa trên diễn biến.
- ĐẶC BIỆT LƯU Ý: Nếu khách hàng yêu cầu gặp nhân viên tư vấn trực tiếp, muốn gọi điện hotline, hoặc có sự cố khẩn cấp cần hỗ trợ khẩn cấp, bạn BẮT BUỘC phải lịch sự đề xuất thông tin liên hệ trực tiếp của chủ doanh nghiệp như sau (bằng ngôn ngữ khách đang chat):
  + Số điện thoại/Zalo: +84 896 916 361
  + Người hỗ trợ: Mr. Hoang (Chủ sở hữu hợp pháp của Easy Trip & Visa)

BẮT BUỘC trả về JSON với đúng cấu trúc sau (không thêm text bên ngoài JSON):
{{
  "reply_message": "Câu trả lời cho khách",
  "extracted_data": {{
    "ho_ten": null,
    "nam_sinh": null,
    "quoc_tich": null,
    "thanh_pho": null,
    "ngay_het_han_visa": null,
    "loai_visa": null,
    "ngay_khoi_hanh": null,
    "ghe_chon": null,
    "diem_don": null
  }},
  "current_phase": "CONSULTING",
  "is_complete": false
}}"""

async def test_call():
    client = AsyncGroq(api_key=key2)
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": "tôi muốn visarun"}
    ]
    try:
        print("Calling Groq...")
        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1024
        )
        print("Response received:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_call())
