import os
import asyncio
from telethon import TelegramClient, events
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Groq client cho tính năng xào bài marketing (miễn phí)
keys_str = os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY") or ""
first_key = [k.strip() for k in keys_str.split(",") if k.strip()][0] if keys_str else "dummy_key"
groq_client = AsyncGroq(api_key=first_key)

# Danh sách các kênh đối thủ cần theo dõi
TARGET_CHANNELS = [
    'sir_visaranus',
    'MrVisarunNhaLao',
    'viet_viza',
    'vizaranlaos'
]

# Khởi tạo Telegram Client (Sẽ tạo file session là scraper_v2.session)
# Nếu chưa có API_ID thì bỏ qua không chạy
if API_ID and API_HASH:
    scraper_client = TelegramClient('scraper_v2', int(API_ID), API_HASH)
else:
    scraper_client = None

# Hàm gọi Gemini xào bài
async def rewrite_content(original_text: str) -> str:
    prompt = f"""
    Bạn là một chuyên gia Marketing của công ty 'Easy Trip & Visa'.
    Dưới đây là một bài viết lấy từ kênh của đối thủ:
    ---
    {original_text}
    ---
    Hãy viết lại bài này theo chuẩn văn phong và thương hiệu của Easy Trip & Visa.
    
    YÊU CẦU QUAN TRỌNG:
    1. Giọng điệu: Chuyên nghiệp, đáng tin cậy. Dịch vụ hướng tới Expat (đặc biệt là khách Nga), do đó ưu tiên viết bằng tiếng Nga (hoặc song ngữ Anh-Nga nếu cần).
    2. Tuyệt đối loại bỏ mọi thông tin liên hệ, tên công ty của đối thủ.
    3. Luôn luôn chèn thông tin liên hệ chuẩn của công ty vào cuối bài:
       - Website: https://www.easytripvisa.com
       - Telegram: @easytripvisa_co_ltd
       - Zalo Official Account: Easy Trip Visa
    4. Sử dụng bộ Hashtag chuẩn: #Easytripvisa #visavietnam #ExpatsInVietnam #визаран #ВьетнамВиза
    """
    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1024
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        print("Gemini rewrite error:", e)
        return "Lỗi khi dùng AI xào bài."

async def notify_admin(original_text: str, rewritten_text: str, channel_name: str):
    import httpx
    if not ADMIN_TELEGRAM_ID or not BOT_TOKEN:
        return
        
    message = f"🚨 **Phát hiện bài mới từ kênh {channel_name}**\n\n"
    message += f"**Nội dung gốc:**\n{original_text[:200]}...\n\n"
    message += f"**Nội dung AI đã xào (Bản nháp):**\n{rewritten_text}\n\n"
    message += "👉 **Hành động của bạn:**\n"
    message += "Hãy gửi 1 bức ảnh vào đây để làm ảnh đăng kèm, hoặc gõ lệnh `Duyệt nháp` để hệ thống tiến hành đăng chay (không ảnh) lên các kênh của chúng ta."
    
    # Lưu nháp vào memory_store của FastAPI (vì chạy cùng tiến trình)
    from memory_store import memory_store
    memory_store["pending_marketing_post"] = rewritten_text
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_TELEGRAM_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)

async def start_scraper():
    if not scraper_client:
        print("Scraper disabled: Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in .env")
        return
        
    await scraper_client.connect()
    if not await scraper_client.is_user_authorized():
        print("⚠️ CẢNH BÁO: UserBot chưa được đăng nhập!")
        print("Tính năng tự động cào bài đối thủ đang tạm tắt.")
        print("Vui lòng mở Terminal mới và chạy: python login_scraper.py để đăng nhập.")
        await scraper_client.disconnect()  # type: ignore
        return
        
    print("🚀 Telethon Scraper Started! Đang lắng nghe 4 kênh đối thủ...")
    
    @scraper_client.on(events.NewMessage(chats=TARGET_CHANNELS))
    async def new_message_handler(event):
        text = event.message.message
        if text:
            # Lấy tên kênh
            chat = await event.get_chat()
            channel_name = chat.username or chat.title
            
            print(f"Scraped new message from {channel_name}")
            rewritten = await rewrite_content(text)
            await notify_admin(text, rewritten, channel_name)
