import os
import re
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import httpx
from fastapi import FastAPI, Request, BackgroundTasks, Response, UploadFile, File, Depends, Header, HTTPException
import shutil
from fastapi.responses import HTMLResponse, RedirectResponse
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
    notify_admin_incoming_message,
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

async def send_zalo_message(user_id: str, text: str) -> tuple[bool, str]:
    token = await get_zalo_access_token()
    if not token:
        msg = "Không lấy được access token Zalo (Refresh Token đã hết hạn / không hợp lệ - Error -14014)"
        print(f"❌ send_zalo_message: {msg}")
        return False, msg
    url = "https://openapi.zalo.me/v3.0/oa/message/cs"
    headers = {"access_token": token, "Content-Type": "application/json"}
    payload = {"recipient": {"user_id": user_id}, "message": {"text": text}}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            print(f"Zalo send message response: {resp.status_code} - {resp.text}")
            res_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if res_data.get("error") == 0:
                return True, resp.text
            else:
                return False, f"Zalo Error {res_data.get('error')}: {res_data.get('message', resp.text)}"
        except Exception as e:
            print(f"Zalo send message failed: {e}")
            return False, str(e)

async def send_zalo_image(user_id: str, image_url: str) -> tuple[bool, str]:
    token = await get_zalo_access_token()
    if not token:
        msg = "Không lấy được access token Zalo (Refresh Token đã hết hạn / không hợp lệ - Error -14014)"
        print(f"❌ send_zalo_image: {msg}")
        return False, msg
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
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, headers=headers, json=payload)
            print(f"Zalo send image response: {resp.status_code} - {resp.text}")
            res_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if res_data.get("error") == 0:
                return True, resp.text
            else:
                return False, f"Zalo Error {res_data.get('error')}: {res_data.get('message', resp.text)}"
        except Exception as e:
            print(f"Zalo send image failed: {e}")
            return False, str(e)

def get_fb_page_token(page_id: str = None) -> str | None:
    """Lấy Page Access Token theo page_id.
    Ưu tiên: FB_PAGE_TOKEN_{PAGE_ID} → FB_PAGE_ACCESS_TOKEN (fallback)
    """
    if page_id:
        token = os.getenv(f"FB_PAGE_TOKEN_{page_id}")
        if token:
            return token
    return os.getenv("FB_PAGE_ACCESS_TOKEN")


async def send_facebook_message(user_id: str, text: str, page_id: str = None):
    token = get_fb_page_token(page_id)
    if not token:
        print(f"❌ send_facebook_message: Không cấu hình token cho page {page_id or 'default'}")
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={token}"
    payload = {"recipient": {"id": user_id}, "message": {"text": text}}
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            print(f"Facebook send message response (page={page_id}): {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Facebook send message failed: {e}")

async def send_facebook_image(user_id: str, image_url: str, page_id: str = None):
    token = get_fb_page_token(page_id)
    if not token:
        print(f"❌ send_facebook_image: Không cấu hình token cho page {page_id or 'default'}")
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
            print(f"Facebook send image response (page={page_id}): {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Facebook send image failed: {e}")

def get_whatsapp_credentials(phone_number_id: str = None) -> tuple[Optional[str], Optional[str]]:
    """Lấy Access Token và Phone Number ID của WhatsApp Cloud API"""
    token = os.getenv("WHATSAPP_ACCESS_TOKEN") or os.getenv("WHATSAPP_TOKEN")
    p_id = phone_number_id or os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    return token, p_id


async def send_whatsapp_message(to_number: str, text: str, phone_number_id: str = None) -> tuple[bool, str]:
    """Gửi tin nhắn văn bản qua WhatsApp Business Cloud API và trả về (is_success, error_or_id)"""
    token, p_id = get_whatsapp_credentials(phone_number_id)
    if not token or not p_id:
        msg = "Chưa cấu hình WHATSAPP_ACCESS_TOKEN hoặc WHATSAPP_PHONE_NUMBER_ID"
        print(f"❌ send_whatsapp_message: {msg}")
        return False, msg
    clean_to = re.sub(r"[^\d]", "", str(to_number))
    url = f"https://graph.facebook.com/v19.0/{p_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "text",
        "text": {"preview_url": False, "body": text}
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            print(f"WhatsApp send message response ({clean_to}): {resp.status_code} - {resp.text}")
            if resp.status_code in [200, 201]:
                return True, resp.text
            else:
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_data.get("error", {}).get("message", resp.text)
                return False, f"HTTP {resp.status_code}: {err_msg}"
        except Exception as e:
            print(f"WhatsApp send message failed: {e}")
            return False, str(e)


async def send_whatsapp_image(to_number: str, image_url: str, phone_number_id: str = None) -> tuple[bool, str]:
    """Gửi hình ảnh qua WhatsApp Business Cloud API và trả về (is_success, error_or_id)"""
    token, p_id = get_whatsapp_credentials(phone_number_id)
    if not token or not p_id:
        msg = "Chưa cấu hình WHATSAPP_ACCESS_TOKEN hoặc WHATSAPP_PHONE_NUMBER_ID"
        print(f"❌ send_whatsapp_image: {msg}")
        return False, msg
    clean_to = re.sub(r"[^\d]", "", str(to_number))
    url = f"https://graph.facebook.com/v19.0/{p_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_to,
        "type": "image",
        "image": {"link": image_url}
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, json=payload, headers=headers)
            print(f"WhatsApp send image response ({clean_to}): {resp.status_code} - {resp.text}")
            if resp.status_code in [200, 201]:
                return True, resp.text
            else:
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_data.get("error", {}).get("message", resp.text)
                return False, f"HTTP {resp.status_code}: {err_msg}"
        except Exception as e:
            print(f"WhatsApp send image failed: {e}")
            return False, str(e)


async def get_facebook_user_profile(user_id: str, page_id: str = None) -> Optional[str]:
    """Lấy tên khách hàng từ Facebook: Thử endpoint Conversations của Page trước, sau đó fallback sang PSID direct"""
    candidate_pages = [page_id] if page_id else ["1244422022092408", "944798045391211"]
    
    for pid in candidate_pages:
        token = get_fb_page_token(pid)
        if not token:
            continue
            
        # Cách 1: Truy vấn qua endpoint Conversations của Page (chính xác 100% và không bị chặn bởi User Profile API)
        url_conv = f"https://graph.facebook.com/v19.0/{pid}/conversations"
        params = {
            "user_id": str(user_id),
            "fields": "participants,senders",
            "access_token": token
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url_conv, params=params)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for conv in data:
                        for p in conv.get("participants", {}).get("data", []):
                            if str(p.get("id")) == str(user_id) and p.get("name"):
                                name = p["name"].strip()
                                print(f"👤 Facebook Conversations API lấy được tên khách {user_id}: {name}")
                                return name
                        for s in conv.get("senders", {}).get("data", []):
                            if str(s.get("id")) == str(user_id) and s.get("name"):
                                name = s["name"].strip()
                                print(f"👤 Facebook Conversations API lấy được tên khách {user_id}: {name}")
                                return name
        except Exception as e:
            print(f"⚠️ Lỗi Facebook Conversations API {user_id}: {e}")

    # Cách 2: Fallback trực tiếp qua PSID nếu Cách 1 không có kết quả
    token = get_fb_page_token(page_id)
    if token:
        url_direct = f"https://graph.facebook.com/v19.0/{user_id}?fields=first_name,last_name,name&access_token={token}"
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(url_direct)
                if resp.status_code == 200:
                    data = resp.json()
                    name = data.get("name")
                    if not name:
                        first = data.get("first_name", "").strip()
                        last = data.get("last_name", "").strip()
                        if first or last:
                            name = f"{first} {last}".strip()
                    if name:
                        print(f"👤 Facebook PSID API lấy được tên khách {user_id}: {name}")
                        return name
        except Exception as e:
            print(f"⚠️ Lỗi Facebook PSID API {user_id}: {e}")

    return None


async def get_zalo_user_profile(user_id: str) -> Optional[str]:
    """Lấy tên hiển thị của khách hàng từ Zalo OA API"""
    token = await get_zalo_access_token()
    if not token:
        return None
    url = "https://openapi.zalo.me/v3.0/oa/user/detail"
    headers = {"access_token": token}
    params = {"data": json.dumps({"user_id": str(user_id)})}
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                res_data = resp.json()
                if res_data.get("error") == 0:
                    display_name = res_data.get("data", {}).get("display_name")
                    if display_name:
                        print(f"👤 Zalo API lấy được tên khách {user_id}: {display_name}")
                        return display_name
            else:
                print(f"ℹ️ Zalo API profile ({user_id}) trả về {resp.status_code}: {resp.text[:120]}")
    except Exception as e:
        print(f"⚠️ Lỗi Zalo API get profile {user_id}: {e}")
    return None


# === LUỒNG XỬ LÝ CHUNG CHO MỌI KÊNH ===
# ─── SESSION TTL ─────────────────────────────────────────────────
# Nếu khách im lặng quá thời gian này thì reset context hội thoại
# (giữ nguyên hồ sơ khách: tên, sơ điện thoại, tier trong SQLite)
SESSION_TTL_HOURS = 8


def reset_session_if_expired(session_id: str) -> bool:
    """
    Kiểm tra xẻ phiên đã hết hiệu lực chưa (im lặng > SESSION_TTL_HOURS).
    Nếu hết TTL:
      - Xóa messages + draft + data + phase + completed khỏi RAM
      - Xóa messages trong SQLite (giữ nguyên bảng customers)
    Trả về True nếu đã reset.
    """
    last_update_str = memory_store.get(f"{session_id}_last_update")
    if not last_update_str:
        return False  # Chưa có tương tác nào, không cần reset

    try:
        last_update = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return False

    elapsed = datetime.now() - last_update
    if elapsed < timedelta(hours=SESSION_TTL_HOURS):
        return False  # Chưa hết TTL

    # ─── Đã hết TTL → xóa context cũ ───
    # 1. Xóa messages trong RAM
    if session_id in memory_store:
        del memory_store[session_id]

    # 2. Xóa các keys phụ của session (data, phase, draft, completed, order...)
    keys_to_clear = [k for k in list(memory_store.keys())
                     if k.startswith(session_id + "_") and k not in (
                         f"{session_id}_mode",      # giữ chế độ bot
                         f"{session_id}_name",      # giữ tên hiển thị
                     )]
    for k in keys_to_clear:
        del memory_store[k]

    # 3. Xóa messages phên này trong SQLite (để không nạp lại context cũ)
    try:
        customer_memory.clear_session_messages(session_id)
    except Exception as e:
        print(f"⚠️ Không thể xóa session messages SQLite ({session_id}): {e}")

    hours = round(elapsed.total_seconds() / 3600, 1)
    print(f"🔄 [SESSION RESET] {session_id} — Đã im lặng {hours}h (> {SESSION_TTL_HOURS}h). Bắt đầu phiên mới.")
    return True


async def process_omnichannel_logic(user_id, platform, user_text, session_id, agent="Direct", customer_name: Optional[str] = None):
    # 1. Truy xuất hoặc tạo mới hồ sơ khách hàng từ SQLite
    cust_profile = customer_memory.get_or_create_customer(platform.lower(), str(user_id), full_name=customer_name)
    cust_id = cust_profile.get("customer_id") if cust_profile else None

    log_message(user_id, platform, "User", user_text, customer_id=cust_id)

    # 2. Kiểm tra và reset phiên nếu khách im lặng quá SESSION_TTL_HOURS
    was_reset = reset_session_if_expired(session_id)

    load_session_history(session_id)
        
    # Lấy trạng thái trước đó để so sánh thay đổi
    prev_data = memory_store.get(f"{session_id}_data")
    prev_seat = getattr(prev_data, "ghe_chon", None) if prev_data else None

    memory_store[session_id].append({"role": "user", "content": user_text})
    memory_store[f"{session_id}_last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Ghi nhận tên hiển thị nếu chưa có hoặc cập nhật tên thật
    existing_name = memory_store.get(f"{session_id}_name")
    cust_name_db = cust_profile.get("full_name") if cust_profile else None
    
    if customer_name and customer_name.strip() and not customer_name.startswith("Khách "):
        memory_store[f"{session_id}_name"] = customer_name.strip()
    elif cust_name_db and cust_name_db.strip() and not cust_name_db.startswith("Khách "):
        memory_store[f"{session_id}_name"] = cust_name_db.strip()
    elif not existing_name:
        memory_store[f"{session_id}_name"] = f"Khách {platform} ({str(user_id)[:6]})"

    # Kiểm tra chế độ Bot (Ưu tiên chế độ riêng của phiên, nếu chưa đặt thì lấy chế độ toàn hệ thống)
    global_mode = memory_store.get("GLOBAL_BOT_MODE", os.getenv("DEFAULT_BOT_MODE", "auto"))
    session_mode = memory_store.get(f"{session_id}_mode")
    mode = session_mode if session_mode is not None else global_mode
    if mode in ["manual", "off"]:
        # Chế độ thủ công hoàn toàn / tắt bot, không tự động trả lời
        print(f"⏸️ [Bot Paused/Manual] Bỏ qua tự động trả lời cho {session_id} (Mode: {mode})")
        await notify_admin_incoming_message(
            platform=platform,
            user_id=str(user_id),
            user_text=user_text,
            session_id=session_id,
            user_name=memory_store.get(f"{session_id}_name"),
            agent=agent,
            mode=mode
        )
        return None, None
        
    if mode == "copilot":
        # Chế độ Co-pilot: Bot tạo tin nhắn nháp nhưng không tự động gửi
        try:
            ai_response = await process_chat(memory_store[session_id], customer_profile=cust_profile)
            reply = ai_response.reply_message
            memory_store[f"{session_id}_draft"] = reply
            memory_store[f"{session_id}_draft_data"] = ai_response.extracted_data
            memory_store[f"{session_id}_draft_phase"] = ai_response.current_phase
            
            # Cập nhật hồ sơ khách hàng nếu AI trích xuất được thông tin
            extracted_data = ai_response.extracted_data
            if extracted_data and cust_id:
                profile_updates = {}
                if getattr(extracted_data, "ho_ten", None):
                    profile_updates["full_name"] = extracted_data.ho_ten
                    memory_store[f"{session_id}_name"] = extracted_data.ho_ten
                if getattr(extracted_data, "quoc_tich", None):
                    profile_updates["nationality"] = extracted_data.quoc_tich
                if getattr(extracted_data, "so_dien_thoai", None):
                    profile_updates["phone_number"] = str(extracted_data.so_dien_thoai)
                    customer_memory.link_platform_by_phone(str(extracted_data.so_dien_thoai), platform.lower(), str(user_id))
                if profile_updates:
                    customer_memory.update_customer_profile(cust_id, **profile_updates)

            # Gửi thông báo tức thì cho Admin kèm dự thảo AI
            await notify_admin_incoming_message(
                platform=platform,
                user_id=str(user_id),
                user_text=user_text,
                session_id=session_id,
                user_name=memory_store.get(f"{session_id}_name"),
                agent=agent,
                bot_reply=reply,
                mode=mode
            )
        except Exception as e:
            print(f"Lỗi tạo tin nhắn nháp Co-Pilot ({platform}):", e)
            await notify_admin_incoming_message(
                platform=platform,
                user_id=str(user_id),
                user_text=user_text,
                session_id=session_id,
                user_name=memory_store.get(f"{session_id}_name"),
                agent=agent,
                mode=mode
            )
        return None, None

    try:
        # Gọi AI Agent kèm hồ sơ khách cũ để cá nhân hóa ngữ điệu
        ai_response = await process_chat(memory_store[session_id], customer_profile=cust_profile)
        reply = ai_response.reply_message
        memory_store[session_id].append({"role": "assistant", "content": reply})
        log_message(user_id, platform, "Bot", reply, customer_id=cust_id)

        # Gửi thông báo cho Admin về tin nhắn mới của khách và phản hồi tự động
        await notify_admin_incoming_message(
            platform=platform,
            user_id=str(user_id),
            user_text=user_text,
            session_id=session_id,
            user_name=memory_store.get(f"{session_id}_name"),
            agent=agent,
            bot_reply=reply,
            mode=mode
        )


        data = ai_response.extracted_data
        # Inject agent from URL param if not set by AI
        if agent and agent != "Direct" and not getattr(data, "agent", None):
            data.agent = agent
        memory_store[f"{session_id}_data"] = data

        # Tự động cập nhật hồ sơ khách hàng vào Database SQLite
        if cust_id:
            profile_updates = {}
            if getattr(data, "ho_ten", None):
                profile_updates["full_name"] = data.ho_ten
                memory_store[f"{session_id}_name"] = data.ho_ten
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
        user_only_text = " ".join([m.get("content", "") for m in memory_store.get(session_id, []) if isinstance(m, dict) and m.get("role") == "user"])
        service_type = get_customer_service_type(data, user_only_text=user_only_text)
        
        dest = "cambodia" if service_type == "Cambodia" else "laos"
        ngay_di = validate_and_adjust_departure(data.ngay_khoi_hanh or "", data.ngay_het_han_visa or "", data.loai_visa or "", dest)
        if ngay_di:
            data.ngay_khoi_hanh = ngay_di

        # 1. GỬI SCHEME VÀO NHÓM BUS (CHỈ GỬI KHI KHÁCH ĐÃ CHỐT TUYẾN XE VÀ ĐẾN BƯỚC CHỌN GHẾ)
        if ai_response.current_phase == "SEAT_SELECTION" and ngay_di and service_type in ["45D", "90D", "Cambodia"]:
            now = time.time()
            last_sent = scheme_history.get(f"{ngay_di}_{service_type}", 0)
            if (now - last_sent) > (15 * 60):
                cmd = get_scheme_command(ngay_di, service_type)
                if cmd:
                    await send_to_bus_group(None, cmd, date=ngay_di, service=service_type)
                    scheme_history[f"{ngay_di}_{service_type}"] = now
                    print(f"🚀 Omnichannel Scheme sent: {cmd} (phase=SEAT_SELECTION, service={service_type})")
            else:
                print(f"⏳ Omnichannel: Bỏ qua Scheme cho {ngay_di}_{service_type} (vừa gửi).")

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
                import random
                ORDER_GREETINGS = [
                    "🎉 <b>NỔ ĐƠN KÌA BẠN ƠI! TING TING!</b> 💸",
                    "🚀 <b>BÙM! LẠI NỔ ĐƠN MỚI RỒI BẠN ÊI!</b> 🔥",
                    "🔥 <b>LÚA VỀ LÚA VỀ! CÓ ĐƠN MỚI TOANH NÈ!</b> 💰"
                ]
                order_head = random.choice(ORDER_GREETINGS)
                msg = (
                    f"{order_head}\n\n"
                    f"📦 <b>Mã đơn:</b> <code>[{order_id}]</code>\n"
                    f"👤 <b>Khách iu:</b> {data.ho_ten or 'Khách hàng'} / {data.nam_sinh or ''}\n"
                    f"🌏 <b>Quốc tịch:</b> {data.quoc_tich or 'Chưa rõ'} | <b>Kênh:</b> {platform}\n"
                    f"🚌 <b>Chuyến đi:</b> {data.loai_visa or ''} — {ngay_di or ''}\n"
                    f"💺 <b>Ghế & Đón:</b> Ghế {data.ghe_chon or ''} | Điểm đón: {data.diem_don or 'Oceanus'}\n"
                    f"📞 <b>SĐT:</b> {data.so_dien_thoai or 'Chưa có SĐT'}\n"
                    f"💰 <b>Tổng lúa:</b> <b>{price:,} VND</b>\n"
                    f"🏷️ <b>Đại lý / Nguồn:</b> {agent or 'Trực tiếp'}\n\n"
                    f"👉 <i>Mau check tài khoản xem lúa về chưa rồi bấm xác nhận bên dưới nhé bạn iu!</i>"
                )
                admin_id = os.getenv("ADMIN_TELEGRAM_ID")
                admin_group = os.getenv("ADMIN_GROUP_CHAT_ID")
                topic_id = os.getenv("ADMIN_GROUP_TOPIC_ID", "")
                bot = tg_app.bot
                if admin_id:
                    try:
                        await bot.send_message(
                            chat_id=int(admin_id),
                            text=msg,
                            parse_mode="HTML",
                            reply_markup=keyboard
                        )
                    except Exception as e_adm:
                        print(f"⚠️ Gửi thông báo đơn mới tới Admin cá nhân lỗi:", e_adm)

                if admin_group and str(admin_group) != str(admin_id):
                    try:
                        t_id = int(topic_id) if topic_id else None
                        await bot.send_message(
                            chat_id=int(admin_group),
                            message_thread_id=t_id,
                            text=msg,
                            parse_mode="HTML",
                            reply_markup=keyboard
                        )
                    except Exception as e_grp:
                        print(f"⚠️ Gửi thông báo đơn mới vào nhóm Admin lỗi:", e_grp)

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
    session_id = f"web_{user_id}"

    reply, img = await process_omnichannel_logic(
        user_id, "Website", user_text, f"web_{user_id}", agent=agent
    )

    # Kiểm tra seat map đến từ nhà xe (được ghi vào memory khi Bus Topic nhận ảnh)
    pending_map = memory_store.pop(f"{session_id}_pending_seat_map", None)
    if pending_map and not img:
        img = pending_map

    if reply is None:
        reply = "Cảm ơn bạn đã nhắn tin. Nhân viên tư vấn đang kiểm tra thông tin và sẽ phản hồi trực tiếp cho bạn ngay ạ! 🧑‍💻"
        if session_id in memory_store:
            memory_store[session_id].append({"role": "assistant", "content": reply})
            log_message(user_id, "Website", "Bot", reply)
    elif img:
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


@app.get("/zalo/login")
async def zalo_login_redirect():
    """Tự động chuyển hướng đến link cấp quyền Zalo OA"""
    app_id = os.getenv("ZALO_APP_ID", "4566290251866781404")
    render_url = os.getenv("RENDER_EXTERNAL_URL", "https://chatbot-easytrip.onrender.com").rstrip("/")
    redirect_uri = f"{render_url}/zalo/callback"
    import urllib.parse
    encoded_redirect = urllib.parse.quote(redirect_uri, safe="")
    auth_url = f"https://oauth.zaloapp.com/v4/oa/permission?app_id={app_id}&redirect_uri={encoded_redirect}"
    return RedirectResponse(auth_url)


@app.get("/zalo/callback")
async def zalo_oauth_callback(request: Request):
    """Tiếp nhận OAuth callback từ Zalo khi cấp quyền OA"""
    code = request.query_params.get("code") or request.query_params.get("oa_code")
    oa_id = request.query_params.get("oa_id")
    error = request.query_params.get("error")
    error_desc = request.query_params.get("error_description")
    
    if error:
        return HTMLResponse(content=f"""
        <html><body style="font-family: Arial; text-align: center; padding: 50px; background: #0f172a; color: white;">
            <h1 style="color: #ef4444;">❌ Xác thực Zalo OA Thất Bại</h1>
            <p>Lỗi: {error} - {error_desc}</p>
        </body></html>
        """, status_code=400)
        
    if not code:
        return HTMLResponse(content="""
        <html><body style="font-family: Arial; text-align: center; padding: 50px; background: #0f172a; color: white;">
            <h1 style="color: #f59e0b;">⚠️ Thiếu mã Authorization Code</h1>
            <p>Không tìm thấy tham số code trong URL callback.</p>
        </body></html>
        """, status_code=400)
        
    app_id = os.getenv("ZALO_APP_ID")
    secret_key = os.getenv("ZALO_APP_SECRET")
    
    url = "https://oauth.zaloapp.com/v4/oa/access_token"
    headers = {
        "secret_key": secret_key,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "app_id": app_id,
        "grant_type": "authorization_code",
        "code": code
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(url, headers=headers, data=data)
            res_data = resp.json()
            if "access_token" in res_data and "refresh_token" in res_data:
                global _zalo_access_token, _zalo_token_expiry
                _zalo_access_token = res_data["access_token"]
                expires_in = int(res_data.get("expires_in", 90000))
                _zalo_token_expiry = time.time() + expires_in - 300
                new_refresh = res_data["refresh_token"]
                
                os.environ["ZALO_REFRESH_TOKEN"] = new_refresh
                update_env_file("ZALO_REFRESH_TOKEN", new_refresh)
                
                # Báo Telegram Admin
                try:
                    await send_to_admin_group(None, f"🎉 **XÁC THỰC ZALO OA THÀNH CÔNG!**\nĐã nạp và kích hoạt Access Token & Refresh Token mới cho OA (ID: {oa_id or 'Easy Trip'}).")
                except:
                    pass
                    
                return HTMLResponse(content="""
                <html>
                <head>
                    <title>Zalo OA Connected</title>
                    <meta charset="utf-8">
                    <style>
                        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #060913; color: white; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                        .card { background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.1); padding: 40px 50px; border-radius: 20px; text-align: center; box-shadow: 0 20px 40px rgba(0,0,0,0.5); backdrop-filter: blur(10px); max-width: 500px; }
                        .icon { font-size: 60px; margin-bottom: 20px; }
                        h1 { color: #10b981; margin: 0 0 10px 0; font-size: 24px; }
                        p { color: #94a3b8; font-size: 16px; line-height: 1.6; margin-bottom: 25px; }
                        .btn { display: inline-block; background: #2563eb; color: white; text-decoration: none; padding: 12px 28px; border-radius: 12px; font-weight: 600; transition: 0.2s; }
                        .btn:hover { background: #1d4ed8; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="icon">🎉</div>
                        <h1>XÁC THỰC ZALO OA THÀNH CÔNG!</h1>
                        <p>Hệ thống AI Chatbot đã tự động nạp Token mới và kết nối hoàn tất với Zalo OA của <b>Easy Trip & Visa</b>. Bạn có thể đóng tab này và bắt đầu nhận tin nhắn từ khách hàng.</p>
                        <a href="/copilot/index.html" class="btn">Mở Co-Pilot Studio</a>
                    </div>
                </body>
                </html>
                """)
            else:
                return HTMLResponse(content=f"""
                <html><body style="font-family: Arial; text-align: center; padding: 50px; background: #0f172a; color: white;">
                    <h1 style="color: #ef4444;">❌ Lỗi Đổi Token Zalo</h1>
                    <p>{res_data}</p>
                </body></html>
                """, status_code=400)
        except Exception as e:
            return HTMLResponse(content=f"""
            <html><body style="font-family: Arial; text-align: center; padding: 50px; background: #0f172a; color: white;">
                <h1 style="color: #ef4444;">❌ Lỗi Kết Nối Máy Chủ Zalo</h1>
                <p>{str(e)}</p>
            </body></html>
            """, status_code=500)


@app.post("/zalo/webhook")
async def zalo_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        event_name = data.get("event_name", "")
        if event_name.startswith("user_send_"):
            u_id = data.get("sender", {}).get("id")
            msg_obj = data.get("message", {})
            text = msg_obj.get("text", "")
            if not text:
                if event_name == "user_send_image":
                    text = "[Khách gửi hình ảnh]"
                elif event_name == "user_send_sticker":
                    text = "[Khách gửi sticker]"
                elif event_name == "user_send_file":
                    text = "[Khách gửi tệp đính kèm]"
                else:
                    text = f"[{event_name}]"
            background_tasks.add_task(handle_zalo_flow, u_id, text)
    except Exception as e:
        print(f"❌ Zalo Webhook Error: {e}")
    return Response(status_code=200)


async def handle_zalo_flow(u_id, text):
    session_id = f"zalo_{u_id}"
    cust_name = memory_store.get(f"{session_id}_name")
    if not cust_name or cust_name.startswith("Khách "):
        real_zalo_name = await get_zalo_user_profile(u_id)
        if real_zalo_name:
            cust_name = real_zalo_name
            memory_store[f"{session_id}_name"] = cust_name

    reply, img = await process_omnichannel_logic(u_id, "Zalo", text, session_id, customer_name=cust_name)
    if reply:
        await send_zalo_message(u_id, reply)
        if img:
            await send_zalo_image(u_id, img)


async def handle_fb_flow(u_id, text, page_id: str = None):
    # Xác định Fanpage chi tiết
    if str(page_id) == "1244422022092408":
        fb_platform = "Facebook (Fanpage Tích Xanh)"
    elif str(page_id) == "944798045391211":
        fb_platform = "Facebook (Fanpage Phụ)"
    elif page_id:
        fb_platform = f"Facebook (Page {page_id})"
    else:
        fb_platform = "Facebook"

    session_id = f"fb_{u_id}"

    # Lấy tên khách từ Graph API nếu chưa có
    cust_name = memory_store.get(f"{session_id}_name")
    if not cust_name or cust_name.startswith("Khách "):
        real_fb_name = await get_facebook_user_profile(u_id, page_id=page_id)
        if real_fb_name:
            cust_name = real_fb_name
            memory_store[f"{session_id}_name"] = cust_name

    enable_meta = os.getenv("ENABLE_META_BOT", "true").lower() in ["true", "1", "yes"]
    if not enable_meta:
        # Nếu bot Meta bị tắt, đặt phiên sang chế độ thủ công để lưu tin nhắn vào Studio nhưng không tự động gửi trả lời
        memory_store[f"{session_id}_mode"] = "manual"
        print(f"⏸️ [{fb_platform}] Chatbot AI đang tạm dừng (Chế độ thủ công). Tin nhắn từ {cust_name or u_id}: {text[:60]}")
    else:
        print(f"📨 [{fb_platform}] Tin nhắn từ {cust_name or u_id}: {text[:60]}")

    reply, img = await process_omnichannel_logic(u_id, fb_platform, text, session_id, customer_name=cust_name)
    if reply:
        await send_facebook_message(u_id, reply, page_id=page_id)
        if img:
            await send_facebook_image(u_id, img, page_id=page_id)


async def handle_ig_flow(u_id, text):
    reply, img = await process_omnichannel_logic(u_id, "Instagram", text, f"ig_{u_id}")
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
    if request.query_params.get("hub.mode") == "subscribe" and request.query_params.get("hub.verify_token") == os.getenv("FB_VERIFY_TOKEN", "EasytripMessengerWebhook2026"):
        return Response(content=request.query_params.get("hub.challenge"), status_code=200)
    return Response(status_code=403)


@app.post("/facebook/webhook")
async def facebook_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        obj = data.get("object")
        if obj in ("page", "instagram"):
            for entry in data.get("entry", []):
                page_id = entry.get("id")  # ID của Page nhận tin nhắn
                for event in entry.get("messaging", []):
                    if "message" in event:
                        if event["message"].get("is_echo"):
                            continue
                        u_id = event["sender"]["id"]
                        text = event["message"].get("text")
                        if not text:
                            attachments = event["message"].get("attachments", [])
                            if attachments:
                                att_type = attachments[0].get("type", "tệp")
                                text = f"[Khách gửi {att_type}]"
                            else:
                                text = "[Khách gửi tệp/hình ảnh]"
                        background_tasks.add_task(handle_fb_flow, u_id, text, page_id)
    except Exception as e:
        print(f"❌ Facebook/Instagram Webhook Error: {e}")
    return Response(status_code=200)


@app.get("/instagram/webhook")
async def verify_instagram_webhook(request: Request):
    if request.query_params.get("hub.mode") == "subscribe" and request.query_params.get("hub.verify_token") in [
        os.getenv("FB_VERIFY_TOKEN"),
        "EasytripMessengerWebhook2026"
    ]:
        return Response(content=request.query_params.get("hub.challenge"), status_code=200)
    return Response(status_code=403)


@app.post("/instagram/webhook")
async def instagram_webhook(request: Request, background_tasks: BackgroundTasks):
    return await facebook_webhook(request, background_tasks)


async def handle_whatsapp_flow(wa_id: str, text: str, contact_name: Optional[str] = None, phone_number_id: Optional[str] = None):
    session_id = f"whatsapp_{wa_id}"

    # Lấy tên khách từ profile WhatsApp
    cust_name = memory_store.get(f"{session_id}_name")
    if not cust_name or cust_name.startswith("Khách "):
        if contact_name:
            cust_name = contact_name
            memory_store[f"{session_id}_name"] = cust_name

    # Lưu phone_number_id vào session để khi trả lời thủ công hoặc duyệt nháp sẽ gọi đúng phone_number_id
    if phone_number_id:
        memory_store[f"{session_id}_phone_number_id"] = phone_number_id

    # WhatsApp ID chính là số điện thoại quốc tế (ví dụ: 84868462071)
    clean_digits = re.sub(r"[^\d]", "", str(wa_id))
    phone_formatted = f"+{clean_digits}" if clean_digits else None

    # Tự động cập nhật / tạo hồ sơ khách hàng vào SQLite
    try:
        customer_memory.get_or_create_customer(
            platform="whatsapp",
            user_id=str(wa_id),
            full_name=cust_name,
            phone_number=phone_formatted
        )
    except Exception as e_cust:
        print(f"⚠️ Lưu customer memory cho WhatsApp thất bại: {e_cust}")

    enable_meta = os.getenv("ENABLE_META_BOT", "true").lower() in ["true", "1", "yes"]
    if not enable_meta:
        memory_store[f"{session_id}_mode"] = "manual"
        print(f"⏸️ [WhatsApp] Chatbot AI đang tạm dừng (Chế độ thủ công). Tin nhắn từ {cust_name or wa_id}: {text[:60]}")
    else:
        print(f"📨 [WhatsApp] Tin nhắn từ {cust_name or wa_id} ({phone_formatted}): {text[:60]}")

    reply, img = await process_omnichannel_logic(wa_id, "WhatsApp", text, session_id, customer_name=cust_name)
    if reply:
        await send_whatsapp_message(wa_id, reply, phone_number_id=phone_number_id)
        if img:
            await send_whatsapp_image(wa_id, img, phone_number_id=phone_number_id)


@app.get("/whatsapp/webhook")
async def verify_whatsapp_webhook(request: Request):
    """Xác thực Webhook với Meta Developer Portal"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected_tokens = {
        os.getenv("WHATSAPP_VERIFY_TOKEN"),
        os.getenv("FB_VERIFY_TOKEN"),
        "EasytripWhatsAppWebhook2026",
        "EasytripMessengerWebhook2026"
    }
    expected_tokens = {t for t in expected_tokens if t}
    if mode == "subscribe" and token in expected_tokens:
        print(f"✅ WhatsApp Webhook verified successfully with token: {token}")
        return Response(content=challenge, status_code=200)
    print(f"⚠️ WhatsApp Webhook verification failed. Token received: {token}, expected one of: {expected_tokens}")
    return Response(status_code=403)


@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """Tiếp nhận tin nhắn mới từ khách hàng qua WhatsApp Cloud API"""
    try:
        data = await request.json()
        if data.get("object") == "whatsapp_business_account":
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    metadata = value.get("metadata", {})
                    phone_number_id = metadata.get("phone_number_id")

                    # Lấy danh bạ (contacts) có sẵn tên hiển thị profile WhatsApp
                    contacts = value.get("contacts", [])
                    contact_map = {}
                    for c in contacts:
                        c_wa_id = c.get("wa_id")
                        c_name = c.get("profile", {}).get("name")
                        if c_wa_id and c_name:
                            contact_map[c_wa_id] = c_name

                    for msg in value.get("messages", []):
                        sender_wa_id = msg.get("from")
                        msg_type = msg.get("type")
                        text = ""
                        if msg_type == "text":
                            text = msg.get("text", {}).get("body", "")
                        elif msg_type == "image":
                            caption = msg.get("image", {}).get("caption", "")
                            text = f"[Khách gửi hình ảnh WhatsApp]{(': ' + caption) if caption else ''}"
                        elif msg_type == "document":
                            caption = msg.get("document", {}).get("caption", "")
                            text = f"[Khách gửi tài liệu WhatsApp]{(': ' + caption) if caption else ''}"
                        elif msg_type in ["audio", "voice"]:
                            text = "[Khách gửi tin nhắn thoại WhatsApp]"
                        elif msg_type == "location":
                            loc = msg.get("location", {})
                            text = f"[Khách chia sẻ vị trí: Lat {loc.get('latitude')}, Long {loc.get('longitude')}]"
                        else:
                            text = f"[Khách gửi tin nhắn {msg_type}]"

                        contact_name = contact_map.get(sender_wa_id)
                        background_tasks.add_task(
                            handle_whatsapp_flow,
                            sender_wa_id,
                            text,
                            contact_name,
                            phone_number_id
                        )
    except Exception as e:
        print(f"❌ WhatsApp Webhook Error: {e}")
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


@app.get("/")
async def root_index_redirect():
    """Chuyển hướng trang chủ sang giao diện Live Chat Studio"""
    return RedirectResponse(url="/copilot/index.html")


@app.get("/api/system/bot-mode")
async def get_system_bot_mode():
    """Lấy trạng thái hoạt động của Bot toàn hệ thống"""
    global_mode = memory_store.get("GLOBAL_BOT_MODE", os.getenv("DEFAULT_BOT_MODE", "auto"))
    enable_meta = os.getenv("ENABLE_META_BOT", "true").lower() in ["true", "1", "yes"]
    return {
        "success": True,
        "global_mode": global_mode,
        "enable_meta": enable_meta
    }


@app.post("/api/system/bot-mode", dependencies=[Depends(verify_admin_access)])
async def set_system_bot_mode(request: Request):
    """Thay đổi chế độ của Bot toàn hệ thống: auto | copilot | off"""
    body = await request.json()
    mode = body.get("mode", "auto")
    if mode not in ["auto", "copilot", "off", "manual"]:
        return {"success": False, "message": "Chế độ không hợp lệ."}
    
    normalized_mode = "off" if mode == "manual" else mode
    memory_store["GLOBAL_BOT_MODE"] = normalized_mode
    print(f"🔄 Đã cập nhật chế độ Bot toàn hệ thống sang: {normalized_mode.upper()}")
    return {"success": True, "global_mode": normalized_mode}


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
        elif platform == "whatsapp":
            p_id = memory_store.get(f"{session_id}_phone_number_id")
            await send_whatsapp_message(user_id, content, phone_number_id=p_id)
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
                
        elif platform == "whatsapp":
            p_id = memory_store.get(f"{session_id}_phone_number_id")
            if is_image:
                await send_whatsapp_image(user_id, file_url, phone_number_id=p_id)
                success = True
            else:
                wa_text = f"Gửi bạn tài liệu đính kèm: {filename}\nTải tại đây: {file_url}"
                await send_whatsapp_message(user_id, wa_text, phone_number_id=p_id)
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
        elif platform == "whatsapp":
            p_id = memory_store.get(f"{session_id}_phone_number_id")
            await send_whatsapp_message(user_id, draft, phone_number_id=p_id)
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
        elif platform == "whatsapp":
            p_id = memory_store.get(f"{session_id}_phone_number_id")
            await send_whatsapp_message(user_id, edited_reply, phone_number_id=p_id)
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
