import os, httpx, asyncio
from dotenv import load_dotenv

load_dotenv()

async def push_incidents_to_lark():
    LARK_APP_ID = os.getenv("LARK_APP_ID")
    LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
    LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
    TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")

    incidents = [
        {"Q": "Khách hàng mặc cả hoặc đòi giảm giá", "A": "Giải thích đây là giá chuẩn của công ty để đảm bảo dịch vụ tốt nhất. Nếu là khách cũ đã từng đi, hãy báo nhân viên để kiểm tra chính sách Loyalty Discount (giảm ~200-300k tùy tuyến)."},
        {"Q": "Khách muốn đổi ngày đi xe buýt", "A": "Báo khách gửi lại ngày mới. Nhân viên kiểm tra sơ đồ ghế. Nếu còn chỗ, hệ thống sẽ tự động cập nhật lại lệnh đăng ký và báo cho đội xe."},
        {"Q": "Lỗi chuyển khoản hoặc chưa nhận được tiền", "A": "Yêu cầu khách gửi ảnh chụp màn hình Bill chuyển khoản thành công có mã giao dịch. Admin sẽ kiểm tra tài khoản BIDV của Ly Viet Hoang để xác nhận."},
        {"Q": "Hộ chiếu khách bị mờ hoặc thiếu thông tin", "A": "Yêu cầu khách chụp lại ảnh gốc hộ chiếu rõ nét, không bị bóng đèn hoặc mất góc để làm thủ tục biên giới chính xác."},
        {"Q": "Trường hợp khẩn cấp tại biên giới hoặc sát giờ xe", "A": "Cung cấp ngay hotline hỗ trợ 24/7 của Mr. Hoang: +84 896 916 361."}
    ]

    async with httpx.AsyncClient(timeout=30) as http:
        auth = await http.post(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
        )
        token = auth.json().get("tenant_access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        for item in incidents:
            payload = {"fields": {"Question": item["Q"], "Answer": item["A"]}}
            await http.post(
                f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records",
                json=payload,
                headers=headers
            )
    print("=== SUCCESS ===\nIncident handling rules have been uploaded to Lark.")

if __name__ == "__main__":
    asyncio.run(push_incidents_to_lark())

