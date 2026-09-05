import os
import re
from datetime import datetime
import httpx
from fastapi import FastAPI, Request, BackgroundTasks, Response, UploadFile, File, Depends, Header, HTTPException
import shutil
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn
from contextlib import asynccontextmanager

from ai_agent import process_chat
from lark_api import create_order, update_order_status, get_all_orders
from google_sheet_sync import sync_order_to_sheet
from telegram_router import (
    router as telegram_router,
    tg_app,
    send_to_bus_group,
    send_to_admin_group,
    get_scheme_command,
    normalize_date,
    calculate_smart_departure,
    validate_and_adjust_departure,
    latest_seat_maps,
    scheme_history,
    get_customer_service_type,
    get_or_create_seat_map,
)
from memory_store import memory_store, log_message, get_recent_logs, load_session_history
import customer_memory
from i18n import get_lang_code, get_msg

import time

def update_env_file(key: str, value: str):
    import re
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
        return
        
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    lines = content.splitlines(keepends=True)
    replaced = False
    new_lines = []
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=.*")
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key}={value}\n")
            replaced = True
        else:
            new_lines.append(line)
            
    if not replaced:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] = new_lines[-1] + "\n"
        new_lines.append(f"{key}={value}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


async def webhook_guardian():
    import asyncio
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not render_url or not token:
        return
    render_url = render_url.rstrip("/")
    webhook_url = f"{render_url}/telegram/webhook"
    print(f"🛡️ Webhook Guardian started checking: {webhook_url}")
    
    while True:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
                info = res.json()
                if info.get("ok"):
                    current_url = info.get("result", {}).get("url", "")
                    if current_url != webhook_url:
                        print(f"🛡️ Webhook mismatch! Current: '{current_url}', Expected: '{webhook_url}'. Restoring...")
                        set_res = await client.post(
                            f"https://api.telegram.org/bot{token}/setWebhook",
                            data={"url": webhook_url}
                        )
                        print(f"🛡️ Webhook restored: {set_res.json()}")
        except Exception as e:
            print(f"🛡️ Webhook Guardian check failed: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from visa_reminder import start_daily_reminder_loop
    
    await tg_app.initialize()
    await tg_app.start()
    
    # Khởi động tiến trình nhắc nhở hết hạn visa tự động hàng ngày
    reminder_task = asyncio.create_task(start_daily_reminder_loop(tg_app.bot, run_hour_utc=2))
    
    # Thiết lập webhook Telegram tự động khi chạy trên Render
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    guardian_task = None
    if render_url:
        render_url = render_url.rstrip("/")
        webhook_url = f"{render_url}/telegram/webhook"
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if token:
            print(f"Setting Telegram Webhook to: {webhook_url}")
            async with httpx.AsyncClient() as client:
                try:
                    res = await client.post(
                        f"https://api.telegram.org/bot{token}/setWebhook",
                        data={"url": webhook_url}
                    )
                    print(f"Set webhook result: {res.json()}")
                except Exception as e:
                    print(f"Failed to set Telegram webhook: {e}")
            
            # Start the Webhook Guardian background task
            guardian_task = asyncio.create_task(webhook_guardian())
    else:
        print("Running locally. Skipping Telegram Webhook registration (polling will be handled by telegram_poller.py).")
        
    yield
    if guardian_task:
        guardian_task.cancel()
        try:
            await guardian_task
        except asyncio.CancelledError:
            pass
            
    if reminder_task:
        reminder_task.cancel()
        try:
            await reminder_task
        except asyncio.CancelledError:
            pass
            
    await tg_app.stop()
    await tg_app.shutdown()


app = FastAPI(title="Easy Trip & Visa Omnichannel", lifespan=lifespan)

# Tự động tạo thư mục static nếu thiếu
if not os.path.exists("static"):
    os.makedirs("static")

# Mount thư mục static để truy cập ảnh sơ đồ ghế từ URL
app.mount("/static", StaticFiles(directory="static"), name="static")

# Mount thư mục copilot để truy cập dashboard quản lý live chat
if not os.path.exists("copilot"):
    os.makedirs("copilot")
app.mount("/copilot", StaticFiles(directory="copilot"), name="copilot")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === TRANG QUẢN TRỊ LOGS ===
@app.get("/admin/logs", response_class=HTMLResponse)
async def view_logs():
    logs = get_recent_logs(200)
    html = """<html><head><title>Admin Logs</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; padding: 30px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .item { background: white; padding: 20px; margin-bottom: 15px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 8px solid #ddd; }
        .User { border-left-color: #0084ff; }
        .Bot { border-left-color: #44bec7; }
        .meta { font-size: 0.85em; color: #999; margin-bottom: 8px; }
        .platform { background: #e4e6eb; padding: 2px 6px; border-radius: 4px; font-weight: bold; }
        .content { line-height: 1.5; color: #1c1e21; white-space: pre-wrap; }
    </style></head>
    <body><div class="container">
    <h1>📋 Lịch sử hội thoại Omnichannel</h1>
    """
    for log in logs:
        role = log.get("role", "User")
        html += f"""
        <div class="item {role}">
            <div class="meta">{log.get('timestamp')} | <span class="platform">{log.get('platform')}</span> | ID: {log.get('user_id')}</div>
            <div class="content"><b>{role}:</b> {log.get('content')}</div>
        </div>
        """
    return html + "</div></body></html>"


# === GIAO TIẾP VỚI CÁC KÊNH (ZALO, FB) ===
_zalo_access_token = None
_zalo_token_expiry = 0

async def get_zalo_access_token():
    global _zalo_access_token, _zalo_token_expiry
    now = time.time()
    if _zalo_access_token and now < _zalo_token_expiry:
        return _zalo_access_token

    app_id = os.getenv("ZALO_APP_ID")
    secret_key = os.getenv("ZALO_APP_SECRET")
    refresh_token = os.getenv("ZALO_REFRESH_TOKEN")

    if not app_id or not secret_key or not refresh_token:
        print("Thiếu cấu hình Zalo trong .env")
        return None

    url = "https://oauth.zaloapp.com/v4/oa/access_token"
    headers = {
        "secret_key": secret_key,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "app_id": app_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, data=data)
            res_data = resp.json()
            if "access_token" in res_data:
                _zalo_access_token = res_data["access_token"]
                expires_in = int(res_data.get("expires_in", 90000))
                _zalo_token_expiry = now + expires_in - 300
                new_refresh = res_data.get("refresh_token")
                if new_refresh and new_refresh != refresh_token:
                    os.environ["ZALO_REFRESH_TOKEN"] = new_refresh
                    update_env_file("ZALO_REFRESH_TOKEN", new_refresh)
                return _zalo_access_token
            else:
                print("Lỗi làm mới token Zalo:", res_data)
        except Exception as e:
            print("Exception khi refresh Zalo token:", e)
    return None

async def send_zalo_message(user_id: str, text: str):
    token = await get_zalo_access_token()
    if not token:
        print("❌ send_zalo_message: Không lấy được access token Zalo")
        return
    url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {"access_token": token, "Content-Type": "application/json"}
    payload = {"recipient": {"user_id": user_id}, "message": {"text": text}}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            print(f"Zalo send message response: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Zalo send message failed: {e}")

async def send_zalo_image(user_id: str, image_url: str):
    token = await get_zalo_access_token()
    if not token:
        print("❌ send_zalo_image: Không lấy được access token Zalo")
        return
    url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {"access_token": token, "Content-Type": "application/json"}
    payload = {
        "recipient": {"user_id": user_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "media",
                    "elements": [{"media_type": "image", "url": image_url}]
                }
            }
        }
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            print(f"Zalo send image response: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Zalo send image failed: {e}")

async def send_facebook_message(user_id: str, text: str):
    token = os.getenv("FB_PAGE_ACCESS_TOKEN")
    if not token:
        print("❌ send_facebook_message: Không cấu hình FB_PAGE_ACCESS_TOKEN")
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={token}"
    payload = {"recipient": {"id": user_id}, "message": {"text": text}}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            print(f"Facebook send message response: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Facebook send message failed: {e}")

async def send_facebook_image(user_id: str, image_url: str):
    token = os.getenv("FB_PAGE_ACCESS_TOKEN")
    if not token:
        print("❌ send_facebook_image: Không cấu hình FB_PAGE_ACCESS_TOKEN")
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={token}"
    payload = {
        "recipient": {"id": user_id},
        "message": {
            "attachment": {
                "type": "image",
                "payload": {"url": image_url, "is_reusable": True}
            }
        }
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            print(f"Facebook send image response: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Facebook send image failed: {e}")


# === LUỒNG XỬ LÝ CHUNG CHO MỌI KÊNH ===
async def process_omnichannel_logic(user_id, platform, user_text, session_id, agent="Direct"):
    # 1. Truy xuất hoặc tạo mới hồ sơ khách hàng từ SQLite
    cust_profile = customer_memory.get_or_create_customer(platform.lower(), str(user_id))
    cust_id = cust_profile.get("customer_id") if cust_profile else None

    log_message(user_id, platform, "User", user_text, customer_id=cust_id)
    load_session_history(session_id)
        
    # Lấy trạng thái trước đó để so sánh thay đổi
    prev_data = memory_store.get(f"{session_id}_data")
    prev_seat = getattr(prev_data, "ghe_chon", None) if prev_data else None

    memory_store[session_id].append({"role": "user", "content": user_text})
    memory_store[f"{session_id}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Ghi nhận tên hiển thị nếu chưa có
    if not memory_store.get(f"{session_id}_name"):
        cust_name_db = cust_profile.get("full_name") if cust_profile else None
        memory_store[f"{session_id}_name"] = cust_name_db or f"Khách {platform} ({str(user_id)[:6]})"

    # Kiểm tra chế độ Bot
    mode = memory_store.get(f"{session_id}_mode", "auto")
    if mode == "manual":
        # Chế độ thủ công hoàn toàn, không tự động trả lời
        return None, None
        
    if mode == "copilot":
        # Chế độ Co-pilot: Bot tạo tin nhắn nháp nhưng không tự động gửi
        try:
            ai_response = await process_chat(memory_store[session_id], customer_profile=cust_profile)
            reply = ai_response.reply_message
            memory_store[f"{session_id}_draft"] = reply
            memory_store[f"{session_id}_draft_data"] = ai_response.extracted_data
            memory_store[f"{session_id}_draft_phase"] = ai_response.current_phase
            
            # Gửi thông báo cho Admin Group (nếu có cấu hình)
            admin_msg = (
                f"🤖 **[Dự thảo Co-Pilot] ({platform})**\n"
                f"👤 Khách hàng: {memory_store.get(f'{session_id}_name')}\n"
                f"💬 Hỏi: \"{user_text}\"\n"
                f"📝 Dự thảo: \"{reply}\"\n"
                f"👉 Duyệt qua Live Chat Studio!"
            )
            await send_to_admin_group(None, admin_msg)
        except Exception as e:
            print(f"Lỗi tạo tin nhắn nháp Co-Pilot ({platform}):", e)
        return None, None

    try:
        # Gọi AI Agent kèm hồ sơ khách cũ để cá nhân hóa ngữ điệu
        ai_response = await process_chat(memory_store[session_id], customer_profile=cust_profile)
        reply = ai_response.reply_message
        memory_store[session_id].append({"role": "assistant", "content": reply})
        log_message(user_id, platform, "Bot", reply, customer_id=cust_id)

        data = ai_response.extracted_data
        # Inject agent from URL param if not set by AI
        if agent and agent != "Direct" and not getattr(data, "agent", None):
            data.agent = agent
        memory_store[f"{session_id}_data"] = data

        # Tự động cập nhật hồ sơ khách hàng vào Database SQLite
        if cust_id:
            profile_updates = {}
            if getattr(data, "ho_ten", None): profile_updates["full_name"] = data.ho_ten
            if getattr(data, "quoc_tich", None): profile_updates["nationality"] = data.quoc_tich
            if getattr(data, "so_dien_thoai", None):
                profile_updates["phone_number"] = str(data.so_dien_thoai)
                customer_memory.link_platform_by_phone(str(data.so_dien_thoai), platform.lower(), str(user_id))
            if getattr(data, "ghe_chon", None): profile_updates["preferred_seat"] = data.ghe_chon
            if getattr(data, "diem_don", None): profile_updates["preferred_pickup"] = data.diem_don
            if getattr(data, "ngay_het_han_visa", None): profile_updates["visa_expiry_date"] = data.ngay_het_han_visa
            if profile_updates:
                customer_memory.update_customer_profile(cust_id, **profile_updates)

        # Xác định ngày đi và loại dịch vụ của khách
        history_text = " ".join([m["content"] for m in memory_store[session_id]])
        service_type = get_customer_service_type(data, history_text)
        
        dest = "cambodia" if service_type == "Cambodia" else "laos"
        ngay_di = validate_and_adjust_departure(data.ngay_khoi_hanh or "", data.ngay_het_han_visa or "", data.loai_visa or "", dest)
        if ngay_di:
            data.ngay_khoi_hanh = ngay_di

        # 1. Gửi Scheme vào nhóm Bus (Cooldown 15p)
        if ngay_di:
            now = time.time()
            last_sent = scheme_history.get(ngay_di, 0)
            if (now - last_sent) > (15 * 60):
                cmd = get_scheme_command(ngay_di, data.loai_visa or "", history_text)
                if cmd:
                    await send_to_bus_group(None, cmd, date=ngay_di, service=service_type)
                    scheme_history[ngay_di] = now
            else:
                print(f"⏳ Omnichannel: Bỏ qua Scheme cho {ngay_di} (vừa gửi).")

        # 2. Kiểm tra/Tạo Sơ đồ tự động
        image_to_send = None
        if ngay_di:
            should_send_map = False
            if ai_response.current_phase == "SEAT_SELECTION" and not getattr(data, "ghe_chon", None):
                should_send_map = True
            
            user_text_lower = user_text.lower()
            reply_lower = reply.lower()
            map_keywords = [
                "sơ đồ", "seat map", "chờ", "ghế trống", "vị trí", "chỗ", "sơ đồ ghế", "chọn ghế",
                "map", "seat selection", "select seat", "available seats",
                "карта мест", "выбор места", "схема мест", "свободные места", "карта",
                "좌석", "좌석 배치도", "배치도"
            ]
            if any(kw in user_text_lower or kw in reply_lower for kw in map_keywords):
                should_send_map = True

            if should_send_map:
                map_data = await get_or_create_seat_map(ngay_di, service_type)
                if map_data:
                    domain = os.getenv("RENDER_EXTERNAL_URL", "https://chatbot-easytrip.onrender.com").rstrip("/")
                    image_to_send = f"{domain}{map_data['url']}"

        # 3. Gửi lệnh đặt ghế cho đối tác nếu khách vừa chọn ghế
        curr_seat = getattr(data, "ghe_chon", None)
        if curr_seat and curr_seat != prev_seat:
            notif_key = f"{session_id}_bus_notified_{curr_seat}"
            if not memory_store.get(notif_key):
                if not getattr(data, "diem_don", None):
                    data.diem_don = "Oceanus"
                
                bus_msg = (
                    f"🚌 **ĐẶT CHỖ MỚI ({platform})**\n"
                    f"👤 Khách hàng: {data.ho_ten or 'Khách'} / {data.nam_sinh or ''}\n"
                    f"🌏 Quốc tịch: {data.quoc_tich or ''}\n"
                    f"📞 SĐT: {data.so_dien_thoai or ''}\n"
                    f"💺 Ghế chọn: {curr_seat}\n"
                    f"📍 Điểm đón: {data.diem_don}\n"
                    f"⚠️ *Vui lòng đối tác đặt chỗ trên hệ thống của mình!*"
                )
                await send_to_bus_group(None, bus_msg, date=ngay_di or "", service=service_type)
                memory_store[notif_key] = True
                print(f"📢 ({platform}) Đã gửi tin nhắn đặt chỗ {curr_seat} vào topic đối tác!")

        # 4. Chốt đơn & tạo Order trong Lark + thông báo Admin
        if ai_response.is_complete or ai_response.current_phase == "COMPLETED":
            completed_key = f"{session_id}_completed"
            if not memory_store.get(completed_key):
                memory_store[completed_key] = True
                order_info = await create_order(data, channel=platform, agent=agent)
                record_id = order_info["record_id"]
                order_id = order_info["order_id"]
                price = order_info["price"]
                memory_store[f"{session_id}_record_id"] = record_id
                memory_store[f"{session_id}_order"] = {
                    **order_info,
                    "user_id": user_id,
                    "platform": platform,
                }

                # Lưu chuyến đi vào SQLite trip_history
                if cust_id:
                    try:
                        customer_memory.record_completed_trip(
                            customer_id=cust_id,
                            departure_date=ngay_di or data.ngay_khoi_hanh or datetime.now().strftime("%d/%m"),
                            route=service_type,
                            visa_type=data.loai_visa,
                            seat_number=data.ghe_chon,
                            pickup_location=data.diem_don,
                            price_paid=price,
                            order_id=record_id
                        )
                    except Exception as e_trip:
                        print(f"⚠️ Lỗi lưu trip_history vào SQLite ({platform}): {e_trip}")

                # Gửi thông báo Admin với Inline Keyboard
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✅ Đã nhận tiền",
                            callback_data=f"paid|{record_id}|{session_id}"
                        ),
                        InlineKeyboardButton(
                            "❌ Huỷ đơn",
                            callback_data=f"cancel|{record_id}|{session_id}"
                        ),
                    ]
                ])
                msg = (
                    f"🔔 ĐƠN MỚI [{order_id}]\n"
                    f"👤 {data.ho_ten or ''} / {data.nam_sinh or ''}\n"
                    f"🌏 {data.quoc_tich or ''} | {platform}\n"
                    f"🚌 {data.loai_visa or ''} — {ngay_di or ''}\n"
                    f"💺 Ghế: {data.ghe_chon or ''} | Điểm đón: {data.diem_don or ''}\n"
                    f"📞 {data.so_dien_thoai or 'Chưa có SĐT'}\n"
                    f"💰 Giá: {price:,} VND\n"
                    f"🏷️ Đại lý: {agent}"
                )
                admin_id = os.getenv("ADMIN_TELEGRAM_ID")
                if admin_id:
                    bot = tg_app.bot
                    await bot.send_message(
                        chat_id=admin_id,
                        text=msg,
                        reply_markup=keyboard
                    )

        return reply, image_to_send
    except Exception as e:
        print(f"Lỗi Omnichannel ({platform}):", e)
        # Try to get lang from existing data if possible
        data = memory_store.get(f"{session_id}_data")
        lang = get_lang_code(getattr(data, "quoc_tich", "")) if data else "en"
        return (
            get_msg("system_busy", lang),
            None,
        )


# === ENDPOINTS ===
# === ENDPOINTS ===

def verify_admin_access(authorization: str = Header(None)):
    expected_password = os.getenv("ADMIN_ACCESS_PASSWORD", "Easytrip0301!")
    if not authorization:
        raise HTTPException(status_code=401, detail="Mã truy cập bị thiếu.")
    token = authorization.split(" ")[-1] if " " in authorization else authorization
    if token != expected_password:
        raise HTTPException(status_code=403, detail="Mã truy cập không hợp lệ.")


@app.post("/api/verify_code")
async def verify_code(request: Request):
    body = await request.json()
    code = body.get("code", "")
    expected = os.getenv("ADMIN_ACCESS_PASSWORD", "Easytrip0301!")
    if code == expected:
        return {"success": True}
    return {"success": False, "message": "Mã truy cập không chính xác!"}


@app.post("/chat")  # Website Chatbox
async def web_chat(request: Request):
    data = await request.json()
    user_id = data.get("user_id", "web_user")
    agent = data.get("agent", "Direct")
    messages = data.get("messages", [])
    user_text = messages[-1].get("content", "") if messages else ""
    reply, img = await process_omnichannel_logic(
        user_id, "Website", user_text, f"web_{user_id}", agent=agent
    )
    if reply is None:
        reply = "Cảm ơn bạn đã nhắn tin. Nhân viên tư vấn đang kiểm tra thông tin và sẽ phản hồi trực tiếp cho bạn ngay ạ! 🧑‍💻"
        session_id = f"web_{user_id}"
        if session_id in memory_store:
            memory_store[session_id].append({"role": "assistant", "content": reply})
            log_message(user_id, "Website", "Bot", reply)
    elif img:
        session_id = f"web_{user_id}"
        if session_id in memory_store and memory_store[session_id]:
            if memory_store[session_id][-1]["role"] == "assistant":
                memory_store[session_id][-1]["content"] += f"\n\n![Sơ đồ ghế]({img})"
    return {"reply": reply, "image": img}


@app.get("/chat/{user_id}/history")
async def get_web_chat_history(user_id: str):
    session_id = f"web_{user_id}"
    history = memory_store.get(session_id, [])
    is_complete = memory_store.get(f"{session_id}_completed", False)
    return {
        "success": True,
        "history": history,
        "is_complete": is_complete
    }



@app.post("/zalo/webhook")
async def zalo_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        if data.get("event_name") == "user_send_text":
            u_id = data.get("sender", {}).get("id")
            text = data.get("message", {}).get("text")
            background_tasks.add_task(handle_zalo_flow, u_id, text)
    except Exception as e:
        print(f"❌ Zalo Webhook Error: {e}")
    return Response(status_code=200)


async def handle_zalo_flow(u_id, text):
    reply, img = await process_omnichannel_logic(u_id, "Zalo", text, f"zalo_{u_id}")
    if reply:
        await send_zalo_message(u_id, reply)
        if img:
            await send_zalo_image(u_id, img)


async def handle_fb_flow(u_id, text):
    reply, img = await process_omnichannel_logic(u_id, "Facebook", text, f"fb_{u_id}")
    if reply:
        await send_facebook_message(u_id, reply)
        if img:
            await send_facebook_image(u_id, img)


# === ADMIN PAYMENT CONFIRMATION (Telegram callback) ===
@app.post("/admin/order/{record_id}/paid")
async def admin_confirm_paid(record_id: str, request: Request):
    """HTTP fallback nếu cần confirm qua API thay vì Telegram button"""
    body = await request.json()
    note = body.get("note", "")
    ok = await update_order_status(record_id, "PAID", note)
    return {"success": ok}


@app.get("/admin/orders")
async def list_orders(status: str | None = None):
    """Xem toàn bộ đơn hàng, có thể lọc: ?status=PENDING"""
    orders = await get_all_orders(status_filter=status)
    return {"orders": orders, "total": len(orders)}


@app.get("/facebook/webhook")
async def verify_facebook_webhook(request: Request):
    if request.query_params.get("hub.mode") == "subscribe" and request.query_params.get("hub.verify_token") == os.getenv("FB_VERIFY_TOKEN"):
        return Response(content=request.query_params.get("hub.challenge"), status_code=200)
    return Response(status_code=403)


@app.post("/facebook/webhook")
async def facebook_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for event in entry.get("messaging", []):
                    if "message" in event and "text" in event["message"]:
                        if event["message"].get("is_echo"):
                            continue
                        u_id = event["sender"]["id"]
                        text = event["message"]["text"]
                        background_tasks.add_task(handle_fb_flow, u_id, text)
    except Exception as e:
        print(f"❌ Facebook Webhook Error: {e}")
    return Response(status_code=200)


# === API CHO CO-PILOT CHAT STUDIO ===

def get_active_sessions():
    sessions = []
    for key in list(memory_store.keys()):
        # Loại trừ các hậu tố quản lý trạng thái
        if "_" in key and not any(key.endswith(suffix) for suffix in [
            "_data", "_completed", "_mode", "_draft", "_name", "_last_update", 
            "_draft_data", "_draft_phase", "_bus_notified", "_record_id", "_order"
        ]):
            if isinstance(memory_store[key], list):
                session_id = key
                parts = session_id.split("_", 1)
                platform = parts[0].capitalize()
                user_id = parts[1]
                
                history = memory_store[session_id]
                last_msg = history[-1]["content"] if history else ""
                
                name = memory_store.get(f"{session_id}_name")
                if not name:
                    data = memory_store.get(f"{session_id}_data")
                    name = getattr(data, "ho_ten", None) if data else None
                if not name:
                    name = f"Khách {platform} ({user_id[:6]})"
                    
                sessions.append({
                    "session_id": session_id,
                    "platform": platform,
                    "user_id": user_id,
                    "mode": memory_store.get(f"{session_id}_mode", "auto"),
                    "last_message": last_msg,
                    "last_update": memory_store.get(f"{session_id}_last_update", ""),
                    "customer_name": name,
                    "pending_draft": memory_store.get(f"{session_id}_draft", "")
                })
    sessions.sort(key=lambda s: s["last_update"], reverse=True)
    return sessions


async def save_teach_knowledge(question: str, answer: str):
    import json
    question = question.strip()
    answer = answer.strip()
    if not question or not answer:
        return False
    base_dir = os.path.dirname(__file__)
    kb_dir = os.path.join(base_dir, "data", "training_knowledge")
    os.makedirs(kb_dir, exist_ok=True)
    filepath = os.path.join(kb_dir, "manual_qa.json")
    if not os.path.exists(filepath) and os.path.exists(os.path.join(base_dir, "manual_qa.json")):
        filepath = os.path.join(base_dir, "manual_qa.json")
        
    data = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    data.append({"question": question, "answer": answer})
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Rebuild RAG index
    try:
        import knowledge_rag
        knowledge_rag.rebuild()
    except Exception as e:
        print("Lỗi rebuild RAG:", e)
    return True


@app.get("/api/sessions", dependencies=[Depends(verify_admin_access)])
async def list_active_sessions():
    """Lấy danh sách các phiên chat thực tế đang hoạt động"""
    return get_active_sessions()


@app.get("/api/session/{session_id}", dependencies=[Depends(verify_admin_access)])
async def get_session_detail(session_id: str):
    """Lấy chi tiết lịch sử và thông tin trích xuất của phiên chat"""
    if session_id not in memory_store:
        return {"success": False, "message": "Không tìm thấy session."}
    
    history = memory_store[session_id]
    data = memory_store.get(f"{session_id}_data")
    data_dict = {}
    if data:
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump()
        else:
            data_dict = vars(data)
            
    return {
        "success": True,
        "session_id": session_id,
        "history": history,
        "extracted_data": data_dict,
        "mode": memory_store.get(f"{session_id}_mode", "auto"),
        "pending_draft": memory_store.get(f"{session_id}_draft", ""),
        "customer_name": memory_store.get(f"{session_id}_name", "Khách hàng")
    }


@app.post("/api/session/{session_id}/mode", dependencies=[Depends(verify_admin_access)])
async def set_session_mode(session_id: str, request: Request):
    """Thay đổi chế độ của phiên chat: auto | copilot | manual"""
    body = await request.json()
    mode = body.get("mode", "auto")
    if mode not in ["auto", "copilot", "manual"]:
        return {"success": False, "message": "Chế độ không hợp lệ."}
    
    memory_store[f"{session_id}_mode"] = mode
    # Reset nháp nếu quay lại auto hoặc chuyển sang manual
    if mode != "copilot":
        memory_store[f"{session_id}_draft"] = ""
    return {"success": True, "mode": mode}


@app.post("/api/session/{session_id}/message", dependencies=[Depends(verify_admin_access)])
async def send_manual_message(session_id: str, request: Request):
    """Admin gửi tin nhắn tay trực tiếp cho khách hàng (Agent Takeover)"""
    body = await request.json()
    content = body.get("message", "").strip()
    if not content:
        return {"success": False, "message": "Nội dung tin nhắn trống."}
        
    parts = session_id.split("_", 1)
    platform = parts[0]
    user_id = parts[1]
    
    success = False
    error_msg = ""
    try:
        if platform == "telegram":
            conn_id = memory_store.get(f"{session_id}_business_connection_id")
            await tg_app.bot.send_message(chat_id=int(user_id), text=content, business_connection_id=conn_id)
            success = True
        elif platform == "zalo":
            await send_zalo_message(user_id, content)
            success = True
        elif platform == "facebook":
            await send_facebook_message(user_id, content)
            success = True
        elif platform == "web":
            # Webchat kéo tin nhắn từ history nên chỉ cần append vào là thành công
            success = True
        else:
            error_msg = f"Nền tảng {platform} chưa hỗ trợ gửi trực tiếp."
    except Exception as e:
        error_msg = str(e)
        
    if success:
        if session_id not in memory_store:
            memory_store[session_id] = []
        memory_store[session_id].append({"role": "agent", "content": content})
        log_message(user_id, platform.capitalize(), "Agent", content)
        memory_store[f"{session_id}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Tiếp quản trực tiếp thì chuyển chế độ sang manual để Bot không tự động chen ngang
        memory_store[f"{session_id}_mode"] = "manual"
        return {"success": True}
    else:
        return {"success": False, "message": f"Không gửi được tin nhắn: {error_msg}"}


@app.post("/api/session/{session_id}/media", dependencies=[Depends(verify_admin_access)])
async def send_manual_media(session_id: str, file: UploadFile = File(...)):
    """Admin gửi ảnh hoặc file trực tiếp cho khách hàng (Agent Takeover)"""
    if session_id not in memory_store:
        return {"success": False, "message": "Không tìm thấy session."}

    parts = session_id.split("_", 1)
    platform = parts[0]
    user_id = parts[1]
    
    # Tạo thư mục static/uploads nếu chưa có
    upload_dir = "static/uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    filename = file.filename or "upload_file"
    # Clean filename
    filename_clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
    file_path = f"{upload_dir}/{int(time.time())}_{filename_clean}"
    
    # Lưu file cục bộ
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return {"success": False, "message": f"Không thể lưu file: {str(e)}"}
        
    is_image = bool(file.content_type and file.content_type.startswith("image/"))
    
    domain = os.getenv("RENDER_EXTERNAL_URL", "https://chatbot-easytrip.onrender.com").rstrip("/")
    file_url = f"{domain}/static/uploads/{os.path.basename(file_path)}"
    
    success = False
    error_msg = ""
    
    try:
        if platform == "telegram":
            bot = tg_app.bot
            chat_id = int(user_id)
            conn_id = memory_store.get(f"{session_id}_business_connection_id")
            if is_image:
                with open(file_path, "rb") as f:
                    await bot.send_photo(chat_id=chat_id, photo=f, business_connection_id=conn_id)
                success = True
            else:
                with open(file_path, "rb") as f:
                    await bot.send_document(chat_id=chat_id, document=f, filename=filename, business_connection_id=conn_id)
                success = True
                
        elif platform == "zalo":
            if is_image:
                await send_zalo_image(user_id, file_url)
                success = True
            else:
                zalo_text = f"Gửi bạn file đính kèm: {filename}\nTải tại đây: {file_url}"
                await send_zalo_message(user_id, zalo_text)
                success = True
                
        elif platform == "facebook":
            if is_image:
                await send_facebook_image(user_id, file_url)
                success = True
            else:
                fb_text = f"Gửi bạn file đính kèm: {filename}\nTải tại đây: {file_url}"
                await send_facebook_message(user_id, fb_text)
                success = True
                
        elif platform == "web":
            success = True
        else:
            error_msg = f"Nền tảng {platform} chưa hỗ trợ gửi file trực tiếp."
            
    except Exception as e:
        error_msg = str(e)
        
    if success:
        if is_image:
            msg_content = f"![{filename}]({file_url})"
        else:
            msg_content = f"[{filename}]({file_url})"
            
        memory_store[session_id].append({"role": "agent", "content": msg_content})
        log_message(user_id, platform.capitalize(), "Agent (File)", msg_content)
        memory_store[f"{session_id}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memory_store[f"{session_id}_mode"] = "manual"
        return {"success": True, "url": file_url}
    else:
        return {"success": False, "message": f"Không gửi được file: {error_msg}"}


@app.post("/api/session/{session_id}/approve", dependencies=[Depends(verify_admin_access)])
async def approve_session_draft(session_id: str):
    """Duyệt tin nhắn nháp của Bot và gửi đi cho khách hàng"""
    draft = memory_store.get(f"{session_id}_draft")
    if not draft:
        return {"success": False, "message": "Không có tin nhắn nháp để duyệt."}
        
    parts = session_id.split("_", 1)
    platform = parts[0]
    user_id = parts[1]
    
    success = False
    error_msg = ""
    try:
        if platform == "telegram":
            conn_id = memory_store.get(f"{session_id}_business_connection_id")
            await tg_app.bot.send_message(chat_id=int(user_id), text=draft, business_connection_id=conn_id)
            success = True
        elif platform == "zalo":
            await send_zalo_message(user_id, draft)
            success = True
        elif platform == "facebook":
            await send_facebook_message(user_id, draft)
            success = True
        elif platform == "web":
            success = True
    except Exception as e:
        error_msg = str(e)
        
    if success:
        memory_store[session_id].append({"role": "assistant", "content": draft})
        log_message(user_id, platform.capitalize(), "Bot", draft)
        memory_store[f"{session_id}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Áp dụng dữ liệu trích xuất từ bản nháp
        draft_data = memory_store.get(f"{session_id}_draft_data")
        if draft_data:
            memory_store[f"{session_id}_data"] = draft_data
            
        # Xóa nháp
        memory_store[f"{session_id}_draft"] = ""
        memory_store[f"{session_id}_draft_data"] = None
        return {"success": True}
    else:
        return {"success": False, "message": f"Không gửi được tin nhắn: {error_msg}"}


@app.post("/api/session/{session_id}/edit_send", dependencies=[Depends(verify_admin_access)])
async def edit_send_session_draft(session_id: str, request: Request):
    """Sửa tin nhắn nháp của Bot, gửi cho khách hàng và dạy Bot bài học đó"""
    body = await request.json()
    edited_reply = body.get("message", "").strip()
    if not edited_reply:
        return {"success": False, "message": "Nội dung chỉnh sửa trống."}
        
    parts = session_id.split("_", 1)
    platform = parts[0]
    user_id = parts[1]
    
    success = False
    error_msg = ""
    try:
        if platform == "telegram":
            conn_id = memory_store.get(f"{session_id}_business_connection_id")
            await tg_app.bot.send_message(chat_id=int(user_id), text=edited_reply, business_connection_id=conn_id)
            success = True
        elif platform == "zalo":
            await send_zalo_message(user_id, edited_reply)
            success = True
        elif platform == "facebook":
            await send_facebook_message(user_id, edited_reply)
            success = True
        elif platform == "web":
            success = True
    except Exception as e:
        error_msg = str(e)
        
    if success:
        memory_store[session_id].append({"role": "assistant", "content": edited_reply})
        log_message(user_id, platform.capitalize(), "Bot (Edited)", edited_reply)
        memory_store[f"{session_id}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Tìm tin nhắn khách hàng cuối cùng để lưu cặp Q&A học tập
        last_customer_msg = ""
        for msg in reversed(memory_store[session_id][:-1]):
            if msg["role"] == "user":
                last_customer_msg = msg["content"]
                break
                
        if last_customer_msg:
            await save_teach_knowledge(last_customer_msg, edited_reply)
            
        # Xóa nháp
        memory_store[f"{session_id}_draft"] = ""
        memory_store[f"{session_id}_draft_data"] = None
        return {"success": True}
    else:
        return {"success": False, "message": f"Không gửi được tin nhắn: {error_msg}"}


@app.get("/api/knowledge", dependencies=[Depends(verify_admin_access)])
async def get_knowledge():
    """Lấy danh sách tri thức gốc và thủ công đã được dạy"""
    import json
    manual_data = []
    filepath = os.path.join(os.path.dirname(__file__), "manual_qa.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                manual_data = json.load(f)
        except Exception:
            pass
            
    return {
        "success": True,
        "manual": manual_data,
        "original": [
            {"question": "Đi visarun theo quốc tịch (Nga/Hàn/ASEAN)", "answer": "Người Nga/Hàn/ASEAN đi visarun Lào (Bờ Y) để được miễn visa. Các nước khác đi Campuchia (Mộc Bài)."},
            {"question": "Giá làm E-visa Việt Nam chuẩn 3-5 ngày", "answer": "Giá E-visa 3-5 ngày là 2.150.000đ. Khách loyalty ưu đãi 1.810.000đ."},
            {"question": "Thuê xe máy Nha Trang", "answer": "Dịch vụ thuê xe máy 24/7 giao tận nơi đầy đủ mũ bảo hiểm xe ga/số."}
        ]
    }


@app.delete("/api/knowledge", dependencies=[Depends(verify_admin_access)])
async def delete_knowledge(request: Request):
    """Xoá tri thức thủ công theo index"""
    body = await request.json()
    index = body.get("index")
    if index is None:
        return {"success": False, "message": "Thiếu index tri thức cần xoá."}
        
    filepath = os.path.join(os.path.dirname(__file__), "manual_qa.json")
    if os.path.exists(filepath):
        try:
            import json
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if 0 <= index < len(data):
                del data[index]
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # Rebuild RAG index
                try:
                    import knowledge_rag
                    knowledge_rag.rebuild()
                except:
                    pass
                return {"success": True}
            else:
                return {"success": False, "message": "Index ngoài phạm vi."}
        except Exception as e:
            return {"success": False, "message": str(e)}
    return {"success": False, "message": "Không tìm thấy dữ liệu tri thức thủ công."}


@app.post("/api/teach", dependencies=[Depends(verify_admin_access)])
async def api_teach_bot(request: Request):
    """API thủ công giúp Agent dạy Bot qua câu hỏi trực tiếp"""
    body = await request.json()
    question = body.get("question", "").strip()
    answer = body.get("answer", "").strip()
    
    if not question or not answer:
        return {"success": False, "message": "Câu hỏi và câu trả lời không được để trống!"}
    
    success = await save_teach_knowledge(question, answer)
    if success:
        return {"success": True, "message": "Đã đồng bộ trực tiếp vào Tri thức thực tế!"}
    else:
        return {"success": False, "message": "Lỗi lưu tri thức."}


@app.post("/api/sync-excel", dependencies=[Depends(verify_admin_access)])
async def api_sync_excel():
    """API kích hoạt đồng bộ hóa dữ liệu Hỏi-Đáp từ file Excel Master vào RAG"""
    import subprocess
    import sys
    try:
        base_dir = os.path.dirname(__file__)
        script_path = os.path.join(base_dir, "scripts", "training", "sync_excel_kb.py")
        if not os.path.exists(script_path):
            script_path = os.path.join(base_dir, "sync_excel_kb.py")
            
        if not os.path.exists(script_path):
            return {"success": False, "message": f"Không tìm thấy file kịch bản đồng bộ tại {script_path}."}
            
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        if result.returncode == 0:
            return {"success": True, "message": "Đã đồng bộ thành công từ Excel Master vào RAG!", "log": result.stdout}
        else:
            return {"success": False, "message": f"Đồng bộ thất bại: {result.stderr}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/staff/media", dependencies=[Depends(verify_admin_access)])
async def upload_staff_media(file: UploadFile = File(...)):
    """API upload tệp và ảnh dành riêng cho trợ lý nghiệp vụ nhân viên"""
    upload_dir = "static/uploads/staff"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    filename = file.filename or "upload_file"
    # Clean filename
    filename_clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
    file_path = f"{upload_dir}/{int(time.time())}_{filename_clean}"
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        return {"success": False, "message": f"Không thể lưu file: {str(e)}"}
        
    domain = os.getenv("RENDER_EXTERNAL_URL", "https://chatbot-easytrip.onrender.com").rstrip("/")
    file_url = f"{domain}/static/uploads/staff/{os.path.basename(file_path)}"
    
    return {
        "success": True, 
        "url": file_url, 
        "filename": filename,
        "content_type": file.content_type
    }


@app.post("/api/staff/chat", dependencies=[Depends(verify_admin_access)])
async def api_staff_chat(request: Request):
    """API trợ lý AI nghiệp vụ nội bộ dành cho nhân viên (Staff AI Chatbot)"""
    body = await request.json()
    question = body.get("question", "").strip()
    attachments = body.get("attachments", [])  # Danh sách tệp đính kèm: {"url": "...", "filename": "...", "content_type": "..."}
    
    if not question and not attachments:
        return {"success": False, "message": "Câu hỏi hoặc tệp đính kèm không được để trống."}
        
    if attachments:
        attachment_notes = []
        for att in attachments:
            name = att.get("filename", "file")
            url = att.get("url", "")
            c_type = att.get("content_type", "")
            if c_type and c_type.startswith("image/"):
                attachment_notes.append(f"[Nhân viên đã đính kèm ảnh: {name} (Link: {url})]")
            else:
                attachment_notes.append(f"[Nhân viên đã đính kèm tệp: {name} (Link: {url})]")
        
        notes_str = "\n".join(attachment_notes)
        if question:
            question = f"{question}\n\n{notes_str}"
        else:
            question = f"Vui lòng kiểm tra và xử lý thông tin tệp/ảnh sau đây:\n{notes_str}"
            
    try:
        from ai_agent import process_staff_chat
        answer = await process_staff_chat(question)
        return {"success": True, "answer": answer}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/admin/trigger-visa-reminders")
async def trigger_visa_reminders_api():
    """API kích hoạt quét và gửi nhắc nhở hết hạn visa trước 10 ngày"""
    try:
        from visa_reminder import check_and_send_daily_reminders
        report = await check_and_send_daily_reminders(bot=tg_app.bot)
        return {"success": True, "report": report}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/admin/visa-reminders-preview")
async def preview_visa_reminders_api():
    """API xem trước danh sách khách hàng sắp hết hạn visa trong 10 ngày tới"""
    from customer_memory import get_customers_needing_visa_reminder
    from visa_reminder import generate_reminder_message, format_display_date
    
    customers = get_customers_needing_visa_reminder(days_before=10, window_days=2)
    preview_list = []
    for c in customers:
        preview_list.append({
            "customer_id": c["customer_id"],
            "full_name": c["full_name"],
            "nationality": c["nationality"],
            "preferred_lang": c["preferred_lang"],
            "visa_expiry_date": format_display_date(c["visa_expiry_date"]),
            "telegram_id": c["telegram_id"],
            "phone_number": c["phone_number"],
            "sample_message": generate_reminder_message(c, days_left=10)
        })
    return {"total": len(preview_list), "customers": preview_list}


app.include_router(telegram_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
