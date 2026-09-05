import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
LARK_KNOWLEDGE_TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")

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

async def add_lark_records(records_list: list):
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
        response = await client.post(url, headers=headers, json=payload, timeout=20.0)
        return response.status_code == 200

# 4 FAQs đa phương tiện VIP nhất
media_faqs = [
    {
        "Question": "Sơ đồ hành trình Visarun chi tiết và hình ảnh thực tế",
        "Answer": "Dưới đây là sơ đồ hành trình Visarun chi tiết từ Nha Trang đến cửa khẩu (Mộc Bài / Bờ Y):\n📍 Link sơ đồ chi tiết & ảnh xe: https://www.easytripvisa.com/\n\nHành trình bao gồm xe buýt giường nằm cao cấp khứ hồi 2 chiều, hướng dẫn viên hỗ trợ thủ tục xuất nhập cảnh tại cả 2 đầu cửa khẩu, nước uống miễn phí và dừng chân nghỉ ngơi tại các trạm dừng thoải mái."
    },
    {
        "Question": "Video giới thiệu chính thức về Easy Trip & Visa",
        "Answer": "Chào bạn! Mời bạn xem video giới thiệu ngắn cực kỳ sinh động về Easy Trip & Visa để hiểu rõ hơn về dịch vụ uy tín của chúng tôi tại đây nhé:\n🎥 Xem Video giới thiệu: https://www.youtube.com/shorts/8lcvXFHSYsc"
    },
    {
        "Question": "Hình ảnh và Video thực tế về dàn xe buýt giường nằm cao cấp",
        "Answer": "Easy Trip & Visa sở hữu dàn xe buýt giường nằm cao cấp đời mới (quy mô 9 xe hiện đại) với đầy đủ tiện nghi: điều hòa mát lạnh, ổ cắm sạc điện thoại tại giường, nước uống đóng chai miễn phí, wifi tốc độ cao và nhà vệ sinh sạch sẽ trên xe.\n🎥 Xem Video giới thiệu dàn xe của chúng tôi: https://www.youtube.com/shorts/4iZLyd_qkm8"
    },
    {
        "Question": "Video thực tế chuyến đi Visarun sang Lào như thế nào?",
        "Answer": "Để giúp bạn hình dung rõ nét nhất về chuyến đi Visarun sang Lào (cửa khẩu Bờ Y), mời bạn xem video thực tế hành trình được ghi lại tại đây:\n🎥 Xem Video hành trình đi Lào thực tế: https://www.youtube.com/shorts/z_3fCc1NWyA"
    }
]

async def main():
    print("Đang tải 4 bộ câu hỏi Đa phương tiện lên Lark Base...")
    success = await add_lark_records(media_faqs)
    if success:
        print("🎉 HOÀN THÀNH THÀNH CÔNG! Đã nạp đầy đủ Sơ đồ hành trình, Video giới thiệu, Video đội xe và Video thực cảnh lên Lark Base!")
    else:
        print("Lỗi khi tải dữ liệu lên Lark Base.")

if __name__ == "__main__":
    asyncio.run(main())
