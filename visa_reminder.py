"""
Module Quản lý & Tự Động Nhắc Nhở Hết Hạn Visa (Automated Visa Expiry Reminder System)
Chức năng:
1. Quét danh sách khách hàng có visa sắp hết hạn (trước 10 ngày).
2. Tự động soạn tin nhắn nhắc nhở cá nhân hóa bằng tiếng bản địa (Nga, Hàn, Anh, Pháp, Việt).
3. Gửi tin nhắn chủ động qua Telegram Bot / Zalo / Meta và lưu vào lịch sử hội thoại (chat_messages).
4. Đồng bộ ngữ cảnh: Khi khách trả lời, AI Agent tự động hiểu và tiếp tục tư vấn đặt chuyến mới.
5. Thông báo báo cáo cho Admin Group trên Telegram.
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional

import customer_memory
from customer_memory import (
    get_db_connection,
    get_customers_needing_visa_reminder,
    mark_reminder_sent,
    save_chat_message
)

# Admin Chat ID để gửi báo cáo
ADMIN_GROUP_CHAT_ID = os.getenv("ADMIN_GROUP_CHAT_ID", "-1003884841968")


def format_display_date(date_str: str) -> str:
    """Chuyển định dạng YYYY-MM-DD sang DD/MM/YYYY để hiển thị cho khách"""
    if not date_str:
        return ""
    try:
        parts = date_str.split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    except:
        pass
    return date_str


def generate_reminder_message(customer: Dict[str, Any], days_left: int = 10) -> str:
    """
    Tạo tin nhắn nhắc nhở hết hạn visa được cá nhân hóa theo ngôn ngữ và thói quen của khách.
    Hỗ trợ: Tiếng Nga (ru), Tiếng Hàn (ko), Tiếng Anh (en), Tiếng Việt (vi), Tiếng Pháp (fr).
    """
    name = customer.get("full_name") or ""
    lang = (customer.get("preferred_lang") or "en").lower()
    raw_exp = customer.get("visa_expiry_date") or ""
    exp_date = format_display_date(raw_exp)
    pref_seat = customer.get("preferred_seat")
    pref_pickup = customer.get("preferred_pickup")
    
    # 1. TIẾNG NGA (ru)
    if lang == "ru":
        name_str = f", {name}" if name else ""
        if pref_seat and pref_pickup:
            addon = f" Мы с радостью заранее забронируем ваше привычное место {pref_seat} и организуем трансфер от {pref_pickup}."
        elif pref_seat:
            addon = f" Мы с радостью заранее забронируем ваше привычное место {pref_seat}."
        elif pref_pickup:
            addon = f" Мы можем организовать трансфер от {pref_pickup}."
        else:
            addon = ""
        
        return (
            f"Здравствуйте{name_str}! 👋\n\n"
            f"Напоминаем, что срок действия вашей визы/пребывания во Вьетнаме истекает через {days_left} дней — {exp_date}. ⏳\n\n"
            f"Планируете ли вы поехать на очередной визаран с EasyTrip или продлить визу, чтобы избежать штрафов за просрочку?\n"
            f"Автобусы в Камбоджу (Мок Бай) и Лаос отправляются регулярно.{addon}\n\n"
            f"👉 Желаете забронировать место на ближайший удобный рейс?"
        )

    # 2. TIẾNG HÀN (ko)
    elif lang == "ko":
        name_str = f"{name}님, " if name else ""
        seat_mention = f" 선호하시는 좌석({pref_seat})으로 미리 지정 가능합니다." if pref_seat else ""
        return (
            f"안녕하세요 {name_str}EasyTrip입니다! 😊\n\n"
            f"고객님의 베트남 비자/체류 기간 만료일이 {days_left}일 후({exp_date})로 다가왔습니다. ⏳\n\n"
            f"비자 만료 전 비자런(Visa Run) 또는 비자 연장 신청을 진행하시겠습니까?{seat_mention}\n"
            f"캄보디아/라오스행 정기 셔틀버스가 매주 운행 중입니다.\n\n"
            f"👉 이번에도 안전하고 편안하게 예약 도와드릴까요?"
        )

    # 3. TIẾNG VIỆT (vi)
    elif lang == "vi":
        name_str = f" {name}" if name else ""
        seat_mention = f" EasyTrip có thể ưu tiên giữ ghế quen {pref_seat} cho bạn." if pref_seat else ""
        return (
            f"Chào bạn{name_str}! 😊\n\n"
            f"EasyTrip xin nhắc nhở lịch trình: Visa/thời hạn lưu trú của bạn sẽ hết hạn sau {days_left} ngày nữa (vào ngày {exp_date}). ⏳\n\n"
            f"Bạn có dự định đăng ký chuyến visarun tiếp theo hoặc gia hạn visa để đảm bảo đúng hạn không?{seat_mention}\n\n"
            f"👉 Hãy nhắn lại để EasyTrip hỗ trợ giữ chỗ và sắp xếp lịch trình sớm nhất cho bạn nhé!"
        )

    # 4. TIẾNG PHÁP (fr)
    elif lang == "fr":
        name_str = f" {name}" if name else ""
        seat_mention = f" Nous pouvons pré-réserver votre siège favori {pref_seat}." if pref_seat else ""
        return (
            f"Bonjour{name_str}! 👋\n\n"
            f"Un petit rappel amical d'EasyTrip: votre visa/séjour au Vietnam expire dans {days_left} jours, le {exp_date}. ⏳\n\n"
            f"Prévoyez-vous de renouveler votre visa ou d'effectuer un visa run pour éviter tout dépassement?{seat_mention}\n\n"
            f"👉 Souhaitez-vous que nous vous réservions une place sur notre prochain départ?"
        )

    # 5. TIẾNG ANH (en - Mặc định cho khách quốc tế)
    else:
        name_str = f" {name}" if name else ""
        if pref_seat and pref_pickup:
            addon = f" We can hold your preferred seat {pref_seat} and arrange pickup at {pref_pickup}."
        elif pref_seat:
            addon = f" We can hold your preferred seat {pref_seat}."
        elif pref_pickup:
            addon = f" We can arrange pickup at {pref_pickup}."
        else:
            addon = ""
            
        return (
            f"Hello{name_str}! 👋\n\n"
            f"This is a friendly reminder from EasyTrip: Your Vietnam visa/stay is set to expire in {days_left} days on {exp_date}. ⏳\n\n"
            f"Are you planning to renew your visa or take a visa run to ensure you stay compliant without penalties?{addon}\n"
            f"We have regular bus departures from Nha Trang.\n\n"
            f"👉 Would you like us to assist you with reserving a seat on the upcoming departure?"
        )


async def send_visa_reminder_to_customer(
    customer: Dict[str, Any],
    bot = None,
    days_left: int = 10
) -> Dict[str, Any]:
    """
    Gửi tin nhắn nhắc nhở tới khách hàng qua Telegram Bot (hoặc log nếu chưa có Telegram ID)
    và lưu vào chat_messages để AI tiếp tục hỗ trợ khi khách phản hồi.
    """
    customer_id = customer["customer_id"]
    tg_id = customer.get("telegram_id")
    full_name = customer.get("full_name") or f"Customer #{customer_id}"
    phone = customer.get("phone_number") or "N/A"
    exp_date = customer.get("visa_expiry_date")
    
    # Tạo nội dung nhắc nhở
    msg_text = generate_reminder_message(customer, days_left=days_left)
    
    sent_success = False
    delivery_channel = "NONE"
    
    # 1. Gửi qua Telegram Bot nếu có telegram_id
    if tg_id and bot:
        try:
            target_chat_id = int(tg_id) if str(tg_id).lstrip("-").isdigit() else str(tg_id)
            await bot.send_message(
                chat_id=target_chat_id,
                text=msg_text
            )
            sent_success = True
            delivery_channel = "TELEGRAM"
            print(f"✅ Đã gửi nhắc nhở Visa thành công tới {full_name} (TG: {tg_id})")
        except Exception as e:
            print(f"⚠️ Không thể gửi Telegram tới {tg_id} ({full_name}): {e}")
            delivery_channel = f"TELEGRAM_ERROR ({e})"
            
    # 2. Lưu vào lịch sử chat_messages (để AI đọc được ngữ cảnh khi khách reply)
    session_id = f"telegram_{tg_id}" if tg_id else f"cust_{customer_id}"
    save_chat_message(
        session_id=session_id,
        platform="telegram" if tg_id else "system_reminder",
        role="assistant",
        content=msg_text,
        customer_id=customer_id
    )
    
    # 3. Đánh dấu trạng thái đã gửi trong Database
    mark_reminder_sent(customer_id, reminder_type="10_DAYS")
    
    return {
        "customer_id": customer_id,
        "full_name": full_name,
        "phone": phone,
        "telegram_id": tg_id,
        "visa_expiry_date": exp_date,
        "sent_success": sent_success,
        "delivery_channel": delivery_channel,
        "message": msg_text
    }


async def check_and_send_daily_reminders(bot = None) -> Dict[str, Any]:
    """
    Tiến trình quét và gửi nhắc nhở tự động hàng ngày:
    1. Tìm tất cả khách hàng có visa_expiry_date trong khoảng 9-11 ngày tới.
    2. Gửi tin nhắn trực tiếp qua Bot.
    3. Gửi thông báo tổng hợp tới Admin Telegram Group.
    """
    print("⏰ [VISA REMINDER] Bắt đầu quét danh sách khách hàng cần nhắc nhở...")
    needing_reminders = get_customers_needing_visa_reminder(days_before=10, window_days=2)
    
    total_found = len(needing_reminders)
    print(f"🔍 [VISA REMINDER] Tìm thấy {total_found} khách hàng cần gửi nhắc nhở.")
    
    if total_found == 0:
        return {
            "total_found": 0,
            "reminders_sent": 0,
            "details": []
        }
        
    results = []
    sent_count = 0
    non_tg_customers = []
    
    for cust in needing_reminders:
        res = await send_visa_reminder_to_customer(cust, bot=bot, days_left=10)
        results.append(res)
        if res["sent_success"]:
            sent_count += 1
        else:
            non_tg_customers.append(res)
            
    # Gửi báo cáo vào Admin Group Telegram
    if bot and ADMIN_GROUP_CHAT_ID:
        try:
            report_lines = [
                f"🔔 <b>[BÁO CÁO TỰ ĐỘNG] NHẮC NHỞ HẾT HẠN VISA (TRƯỚC 10 NGÀY)</b>",
                f"📅 Ngày quét: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                f"📊 Tổng số khách tìm thấy: <b>{total_found}</b>",
                f"✅ Đã gửi trực tiếp qua Telegram: <b>{sent_count}</b>\n"
            ]
            
            if sent_count > 0:
                report_lines.append("<b>Danh sách đã gửi qua Bot:</b>")
                for r in [x for x in results if x["sent_success"]][:10]:
                    report_lines.append(f"• {r['full_name']} (Hạn: {format_display_date(r['visa_expiry_date'])})")
                report_lines.append("")
                
            if non_tg_customers:
                report_lines.append("⚠️ <b>Khách cần Sales liên hệ Zalo/SĐT:</b>")
                for r in non_tg_customers[:10]:
                    report_lines.append(f"• {r['full_name']} | SĐT: {r['phone']} (Hạn: {format_display_date(r['visa_expiry_date'])})")
                    
            await bot.send_message(
                chat_id=int(ADMIN_GROUP_CHAT_ID),
                text="\n".join(report_lines),
                parse_mode="HTML"
            )
            print("📢 Đã gửi báo cáo nhắc nhở Visa tới Admin Group Telegram")
        except Exception as e:
            print(f"⚠️ Lỗi gửi báo cáo nhắc nhở tới Admin Group: {e}")

    return {
        "total_found": total_found,
        "reminders_sent": sent_count,
        "details": results
    }


async def start_daily_reminder_loop(bot, run_hour_utc: int = 2):
    """
    Vòng lặp chạy ngầm mỗi ngày 1 lần vào giờ cố định (02:00 UTC = 09:00 Sáng giờ Việt Nam).
    """
    print(f"🚀 [VISA REMINDER LOOP] Khởi động tiến trình nhắc nhở tự động (Chạy lúc {run_hour_utc + 7}:00 Sáng VN hàng ngày)")
    while True:
        try:
            now = datetime.utcnow()
            # Nếu đến đúng giờ chạy (hoặc khi vừa bật server)
            if now.hour == run_hour_utc and now.minute == 0:
                await check_and_send_daily_reminders(bot=bot)
                await asyncio.sleep(70) # Tránh chạy 2 lần trong cùng 1 phút
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            print("🛑 [VISA REMINDER LOOP] Tiến trình đã dừng.")
            break
        except Exception as e:
            print(f"⚠️ [VISA REMINDER LOOP] Lỗi vòng lặp: {e}")
            await asyncio.sleep(60)
