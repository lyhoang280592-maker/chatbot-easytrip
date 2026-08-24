"""
google_sheet_sync.py
Tự động đồng bộ đơn hàng (sau khi PAID) vào 4 Google Sheet của đối tác.
Yêu cầu: file `gcp_service_account.json` trong thư mục backend.
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "gcp_service_account.json")

# Google Sheet IDs
SERGEI_SHEET_ID = "1qRAqNkMqS9VQRrys8jc-4MhUHebumblmIYArdwSbRNo"
BOLOT_SHEET_ID = "1mDweOPSDeoO93cL8WxAv6nUtS9kw6MXFWK42j5gPyvs"
LUAN_SHEET_ID = "1vOnA7Zqn3T4XughsDUP0dJsBjUoWCFrt6ibVGLzGWjU"
TUNG_SHEET_ID = "1-Extaar3qtMhAKIwVScBYtteqfHHtfJEskKEFo9x9wM"


def _get_client():
    """Khởi tạo Google Sheets client từ Service Account hoặc Biến môi trường."""
    # 1. Ưu tiên đọc từ biến môi trường (Cho Render production)
    json_str = os.getenv("GCP_SERVICE_ACCOUNT_JSON")
    if json_str:
        try:
            creds_info = json.loads(json_str)
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            print("Lỗi đọc GCP_SERVICE_ACCOUNT_JSON từ env:", e)

    # 2. Đọc từ file local (Cho phát triển local)
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
            return gspread.authorize(creds)
        except Exception as e:
            print("Lỗi đọc file service account local:", e)

    print("⚠️  Không tìm thấy credentials cho Google Sheets. Sync bị tắt.")
    return None


def _append_row_safe(sheet_id: str, tab_name: str, row: list, client):
    """Ghi 1 dòng vào Google Sheet, tạo tab nếu chưa có."""
    try:
        wb = client.open_by_key(sheet_id)
        try:
            ws = wb.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = wb.add_worksheet(title=tab_name, rows=1000, cols=20)
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True
    except Exception as e:
        print(f"Lỗi ghi Google Sheet ({sheet_id} / {tab_name}):", e)
        return False


def _format_weekly_tab() -> str:
    """Trả về tên tab theo tuần hiện tại: 'dd/mm-dd/mm' (Thứ 2 - Chủ nhật)"""
    now = datetime.now()
    # monday = now - weekday (0=Mon, 6=Sun)
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    return f"{monday.strftime('%d/%m')}-{sunday.strftime('%d/%m')}"


# ------------------------------------------------------------------
# Sergei & Bolot Sheet — Bus/Tour Rules
# A: Input Date | B: Travel Date | C: Name/YOB | F: Pickup | G: Seat | H: Border | ...
# ------------------------------------------------------------------
async def sync_to_sergei_bolot(order: dict, sheet_id: str, partner_name: str):
    client = _get_client()
    if not client: return
    tab = _format_weekly_tab()
    
    # Chuẩn bị dòng dữ liệu (Row 3 là header, nên append vào cuối)
    # A: NGÀY NHẬP | B: NGÀY ĐI | C: TÊN/NS | D: THANH TOÁN | E: VÉ | F: ĐIỂM ĐÓN | G: GHẾ | H: CỬA KHẨU | I: FT | J: EVISA
    row = [
        datetime.now().strftime("%d/%m/%Y"), # A
        order.get("Departure Date", ""),     # B
        order.get("Full Name", ""),          # C
        "YES" if order.get("Status") == "PAID" else "NO", # D
        "YES",                               # E (Mặc định có vé)
        order.get("Pickup Point", ""),       # F
        order.get("Seat", ""),               # G
        "Lào (Bo Y)" if "lao" in (order.get("Route") or "").lower() else "Campuchia", # H
        "NO",                                # I (Fast Track)
        "YES" if "visa" in (order.get("Route") or "").lower() else "NO", # J
        "", "", "", "",                      # K, L, M, N
        order.get("Payment Note", "")        # O (Ghi chú)
    ]
    if _append_row_safe(sheet_id, tab, row, client):
        print(f"✅ Synced order {order.get('Order ID')} → {partner_name} Sheet ({tab})")


# ------------------------------------------------------------------
# Mr. Luân Sheet — E-visa Rules
# A: Ngày | B: Tên/NS | C: SL | D: Quốc tịch | E: Nguồn | F: Loại | G: Gói | H: Chi phí
# ------------------------------------------------------------------
async def sync_to_luan(order: dict):
    client = _get_client()
    if not client: return
    tab = _format_weekly_tab()
    row = [
        datetime.now().strftime("%d/%m/%Y"), # A
        order.get("Full Name", ""),          # B
        1,                                   # C
        order.get("Nationality", ""),        # D
        order.get("Source Channel", ""),     # E
        order.get("Route", ""),              # F
        "",                                  # G
        f"{order.get('Price (VND)', 0):,}",  # H
        "Auto-synced from Bot",              # I
        "FALSE"                              # J (Checkbox DXC)
    ]
    if _append_row_safe(LUAN_SHEET_ID, tab, row, client):
        print(f"✅ Synced order {order.get('Order ID')} → Luân Sheet ({tab})")


# ------------------------------------------------------------------
# Mr. Tùng Sheet — Visa & FT Rules
# A: Ngày | B: Tên/NS | C: SL | D: Quốc tịch | F: FT | G: E-visa | M: Chi phí
# ------------------------------------------------------------------
async def sync_to_tung(order: dict):
    client = _get_client()
    if not client: return
    tab = _format_weekly_tab()
    # Header: A: Ngày | B: Tên | C: SL | D: QT | E: (Hidden) | F: FT | G: E-visa ... M: Chi phí
    row = [
        datetime.now().strftime("%d/%m/%Y"), # A
        order.get("Full Name", ""),          # B
        1,                                   # C
        order.get("Nationality", ""),        # D
        "",                                  # E
        "YES" if "track" in (order.get("Route") or "").lower() else "NO", # F
        "YES" if "visa" in (order.get("Route") or "").lower() else "NO",  # G
        "", "", "", "", "",                  # H, I, J, K, L
        f"{order.get('Price (VND)', 0):,}",  # M
    ]
    if _append_row_safe(TUNG_SHEET_ID, tab, row, client):
        print(f"✅ Synced order {order.get('Order ID')} → Tùng Sheet ({tab})")


# ------------------------------------------------------------------
# DISPATCHER
# ------------------------------------------------------------------
async def sync_order_to_sheet(order: dict):
    agent = (order.get("Agent") or "Direct").lower()
    if "sergei" in agent:
        await sync_to_sergei_bolot(order, SERGEI_SHEET_ID, "Sergei")
    elif "bolot" in agent:
        await sync_to_sergei_bolot(order, BOLOT_SHEET_ID, partner_name="Bolot")
    elif "lu" in agent or "luan" in agent:
        await sync_to_luan(order)
    elif "t" in agent and "ng" in agent:
        await sync_to_tung(order)
    else:
        print(f"ℹ️  Order {order.get('Order ID')} là Direct — không sync sheet đối tác.")
