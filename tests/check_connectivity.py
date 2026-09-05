"""
Script kiểm tra kết nối toàn diện hệ thống Easy Trip & Visa:
- Telegram Bot
- Gemini AI (Google Generative AI)
- DeepSeek AI (Bộ não AI tư vấn chính)
- Groq AI (Bộ não AI tốc độ cao)
- Lark Base (Cloud Database)
- Render Server (Backend Cloud Hosting)
- Zalo OA
"""
import asyncio
import httpx
import os
import sys
import json
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        getattr(sys.stdout, "reconfigure")(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ZALO_APP_ID = os.getenv("ZALO_APP_ID")
ZALO_APP_SECRET = os.getenv("ZALO_APP_SECRET")
ZALO_REFRESH_TOKEN = os.getenv("ZALO_REFRESH_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
GROQ_API_KEYS = os.getenv("GROQ_API_KEYS")

RENDER_URL = "https://chatbot-easytrip.onrender.com"

async def check_telegram():
    print("\n📱 [1. TELEGRAM BOT] Đang kiểm tra...")
    if not TELEGRAM_BOT_TOKEN:
        print("  ⚠️  Chưa cấu hình TELEGRAM_BOT_TOKEN trong .env")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe")
            data = r.json()
            if data.get("ok"):
                bot = data["result"]
                wh = await client.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo")
                wh_data = wh.json().get("result", {})
                webhook_url = wh_data.get("url", "Chưa cài đặt")
                print(f"  ✅ Bot: @{bot.get('username')} (ID: {bot.get('id')})")
                print(f"  🔗 Webhook: {webhook_url}")
                return True
            else:
                print(f"  ❌ Lỗi Telegram: {data.get('description')}")
                return False
    except Exception as e:
        print(f"  ❌ Không kết nối được Telegram: {e}")
        return False

async def check_gemini():
    print("\n🤖 [2. GEMINI AI] Đang kiểm tra...")
    if not GEMINI_API_KEY:
        print("  ⚠️  Chưa có GEMINI_API_KEY trong .env (hoặc để trống)")
        return False
    try:
        import google.generativeai as genai  # type: ignore
        genai.configure(api_key=GEMINI_API_KEY.strip())  # type: ignore
        model = genai.GenerativeModel("gemini-3.6-flash")  # type: ignore
        response = await model.generate_content_async("Trả lời: OK")
        reply = response.text.strip()
        print(f"  ✅ Gemini AI (gemini-3.6-flash): HOẠT ĐỘNG TỐT (Phản hồi: '{reply}')")
        return True
    except Exception as e:
        print(f"  ❌ Lỗi kết nối Gemini: {e}")
        return False

async def check_deepseek():
    print("\n🧠 [3. DEEPSEEK AI - ENGINE CHÍNH] Đang kiểm tra...")
    if not DEEPSEEK_API_KEY:
        print("  ⚠️  Chưa cấu hình DEEPSEEK_API_KEY trong .env")
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            url = "https://api.deepseek.com/chat/completions"
            headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY.strip()}", "Content-Type": "application/json"}
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 10
            }
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code == 200:
                reply = r.json()["choices"][0]["message"]["content"].strip()
                print(f"  ✅ DeepSeek AI (deepseek-chat): HOẠT ĐỘNG TỐT (Phản hồi: '{reply}')")
                return True
            else:
                print(f"  ⚠️  DeepSeek phản hồi mã {r.status_code}: {r.text[:100]}")
                return False
    except Exception as e:
        print(f"  ❌ Không kết nối được DeepSeek: {e}")
        return False

async def check_groq():
    print("\n⚡ [4. GROQ AI - TỐC ĐỘ CAO] Đang kiểm tra...")
    if not GROQ_API_KEYS:
        print("  ⚠️  Chưa cấu hình GROQ_API_KEYS")
        return False
    keys = [k.strip() for k in GROQ_API_KEYS.split(",") if k.strip()]
    valid = 0
    async with httpx.AsyncClient(timeout=10) as client:
        for k in keys:
            try:
                r = await client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {k}"})
                if r.status_code == 200:
                    valid += 1
            except Exception:
                pass
    if valid > 0:
        print(f"  ✅ Groq AI: {valid}/{len(keys)} API Keys SẴN SÀNG")
        return True
    else:
        print("  ❌ Không có API Key Groq nào khả dụng.")
        return False

async def check_lark():
    print("\n📊 [5. LARK BASE - CLOUD DATABASE] Đang kiểm tra...")
    if not LARK_APP_ID or not LARK_APP_SECRET or not LARK_APP_TOKEN:
        print("  ⚠️  Chưa cấu hình đủ thông tin Lark Base trong .env")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
            )
            data = r.json()
            if data.get("code") == 0:
                token = data["tenant_access_token"]
                kb = await client.get(
                    f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/tbl6cnBVolclQp9v/records",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"page_size": 1}
                )
                kb_data = kb.json()
                total = kb_data.get("data", {}).get("total", 0)
                print(f"  ✅ Lark Authentication: XÁC THỰC THÀNH CÔNG")
                print(f"  ✅ Bảng Tri Thức (Knowledge Base): {total} bản ghi đang hoạt động")
                return True
            else:
                print(f"  ❌ Lark Auth lỗi: {data.get('msg')}")
                return False
    except Exception as e:
        print(f"  ❌ Không kết nối được Lark: {e}")
        return False

async def check_render():
    print("\n🌐 [6. RENDER SERVER - BACKEND HOSTING] Đang kiểm tra...")
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{RENDER_URL}/docs")
            if r.status_code == 200:
                print(f"  ✅ Server Render: ĐANG ONLINE ({RENDER_URL})")
                return True
            else:
                print(f"  ⚠️  Render trả về status code: {r.status_code}")
                return False
    except Exception as e:
        print(f"  ❌ Server Render không phản hồi: {e}")
        return False

async def check_zalo():
    print("\n💬 [7. ZALO OA] Đang kiểm tra...")
    if not ZALO_APP_ID or not ZALO_APP_SECRET or not ZALO_REFRESH_TOKEN:
        print("  ⚠️  Chưa cấu hình đủ thông tin Zalo trong .env")
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = "https://oauth.zaloapp.com/v4/oa/access_token"
            headers = {"secret_key": ZALO_APP_SECRET, "Content-Type": "application/x-www-form-urlencoded"}
            data = {"app_id": ZALO_APP_ID, "grant_type": "refresh_token", "refresh_token": ZALO_REFRESH_TOKEN}
            resp = await client.post(url, headers=headers, data=data)
            res_data = resp.json()
            if "access_token" in res_data:
                print("  ✅ Zalo OA: XÁC THỰC VÀ TOKEN HỢP LỆ")
                return True
            else:
                err_desc = res_data.get("error_description") or res_data.get("error_name")
                print(f"  ⚠️  Zalo Token: {err_desc} (Mã: {res_data.get('error')}) - [Hết hạn 90 ngày của Zalo]")
                return False
    except Exception as e:
        print(f"  ❌ Lỗi kết nối Zalo: {e}")
        return False

async def main():
    print("=" * 60)
    print("  🔍 KIỂM TRA ĐỒNG BỘ TOÀN DIỆN HỆ THỐNG (BẠN & TRỢ LÝ)")
    print("=" * 60)
    
    results = await asyncio.gather(
        check_telegram(),
        check_gemini(),
        check_deepseek(),
        check_groq(),
        check_lark(),
        check_render(),
        check_zalo(),
        return_exceptions=True
    )
    
    checks = [
        "Telegram Bot",
        "Gemini AI (Google)",
        "DeepSeek AI (Engine chính)",
        "Groq AI (Tốc độ cao)",
        "Lark Base (Database)",
        "Render Server",
        "Zalo OA"
    ]
    
    print("\n" + "=" * 60)
    print("  📋 BÁO CÁO TỔNG KẾT HỆ THỐNG")
    print("=" * 60)
    ok_count = 0
    for name, result in zip(checks, results):
        if result is True:
            print(f"  ✅ {name:30}: HOẠT ĐỘNG TỐT")
            ok_count += 1
        elif result is False:
            print(f"  ⚠️  {name:30}: CẦN CHÚ Ý / CHƯA KÍCH HOẠT")
        else:
            print(f"  ❌ {name:30}: LỖI NGOẠI LỆ - {result}")
    print(f"\n  🏆 Điểm hệ thống: {ok_count}/{len(checks)} dịch vụ đã sẵn sàng.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
