import os
import httpx
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

LARK_APP_ID = os.getenv("LARK_APP_ID")
LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
KNOWLEDGE_TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")
CUSTOMER_TABLE_ID = os.getenv("LARK_CUSTOMER_TABLE_ID", "tblXJ8vF7vXvXvXv")
ORDERS_TABLE_ID = os.getenv("LARK_ORDERS_TABLE_ID", "tblr83gYCyGnYybF")


async def get_tenant_access_token():
    url = "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            url, json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
        )
        return r.json().get("tenant_access_token")


# ============================================================
# HÀM CŨ - Dùng cho /chat (Web) và Zalo/Facebook
# ============================================================
async def add_record(data: dict):
    """Thêm bản ghi vào bảng chính của Lark Base (dùng cho Web/Zalo/Facebook)"""
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{KNOWLEDGE_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json={"fields": data}, headers=headers)
        return r.json()


# ============================================================
# HÀM MỚI - Dùng cho Telegram (Tạo hồ sơ khách hàng đầy đủ)
# ============================================================
async def create_customer_record(data) -> str | None:
    """
    Tạo bản ghi khách hàng mới trên Lark và trả về record_id
    để bot có thể cập nhật ảnh (Passport/Face/Exit stamp) vào đúng dòng sau này
    """
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{CUSTOMER_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    fields = {}
    if hasattr(data, "ho_ten") and data.ho_ten:
        fields["Full Name"] = data.ho_ten
    if hasattr(data, "nam_sinh") and data.nam_sinh:
        fields["YOB"] = data.nam_sinh
    if hasattr(data, "quoc_tich") and data.quoc_tich:
        fields["Nationality"] = data.quoc_tich
    if hasattr(data, "loai_visa") and data.loai_visa:
        route = data.loai_visa
        if hasattr(data, "ngay_khoi_hanh") and data.ngay_khoi_hanh:
            route = f"{data.ngay_khoi_hanh} - {data.loai_visa}"
        fields["Route"] = route
    if hasattr(data, "diem_don") and data.diem_don:
        fields["Pickup"] = data.diem_don
    if hasattr(data, "ghe_chon") and data.ghe_chon:
        fields["Seat"] = data.ghe_chon

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={"fields": fields}, headers=headers)
            res = r.json()
            return res.get("data", {}).get("record", {}).get("record_id")
    except Exception as e:
        print("Lỗi tạo Lark record:", e)
        return None


async def upload_image_to_lark(file_path: str) -> str | None:
    """Upload file ảnh lên Lark và trả về file_token để gán vào cột ảnh"""
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/media/upload"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "image/jpeg")}
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(url, files=files, headers=headers)
                return r.json().get("data", {}).get("file_token")
    except Exception as e:
        print("Lỗi upload ảnh Lark:", e)
        return None


async def update_customer_image(record_id: str, field_name: str, file_token: str):
    """Cập nhật ảnh vào đúng cột (Passport / Face / Exit stamp) của bản ghi"""
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{CUSTOMER_TABLE_ID}/records/{record_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"fields": {field_name: [{"file_token": file_token}]}}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(url, json=payload, headers=headers)
            print(f"✅ Cập nhật ảnh [{field_name}] lên Lark:", r.status_code)
    except Exception as e:
        print("Lỗi cập nhật ảnh Lark:", e)


async def get_knowledge_records():
    """Lấy toàn bộ tri thức từ Lark Base để bot học hỏi"""
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{KNOWLEDGE_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=headers)
            items = r.json().get("data", {}).get("items", [])
            return [
                {
                    "cau_hoi": i["fields"].get("Question"),
                    "cau_tra_loi": i["fields"].get("Answer"),
                }
                for i in items
                if i["fields"].get("Question") and i["fields"].get("Answer")
            ]
    except Exception as e:
        print("Lỗi lấy tri thức Lark:", e)
        return []


# ============================================================
# ORDER MANAGEMENT
# ============================================================
_order_counter = {}


def _generate_order_id() -> str:
    today = datetime.now().strftime("%d%m%y")
    _order_counter[today] = _order_counter.get(today, 0) + 1
    return f"{today}-{_order_counter[today]:04d}"


# Auto-pricing table
PRICE_TABLE = {
    ("laos", "45"): 1_400_000,
    ("laos", "90"): 3_400_000,
    ("cambodia", "45"): 1_400_000,
    ("cambodia", "90"): 4_000_000,
}

VISAFREE_NATIONALITIES = [
    "russia", "russian", "nga",
    "korea", "korean", "han quoc", "south korea",
    "belarus", "belarusian",
    "thailand", "thai", "singapore", "malaysia", "indonesia",
    "philippines", "vietnam", "cambodia", "laos", "myanmar",
    "brunei",
]


def auto_price(nationality: str, route: str) -> int:
    nat = (nationality or "").lower()
    route_lower = (route or "").lower()
    dest = "laos" if any(k in route_lower for k in ["laos", "lào", "45d", "90d"]) else "cambodia"
    if "cambodia" in route_lower or "campuchia" in route_lower:
        dest = "cambodia"
    days = "90" if "90" in route_lower else "45"
    return PRICE_TABLE.get((dest, days), 1_400_000)


async def create_order(data, channel: str = "Website", agent: str = "Direct") -> dict:
    """Tạo đơn hàng mới trong bảng Orders, trả về {order_id, record_id}"""
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{ORDERS_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    order_id = _generate_order_id()
    route = ""
    if hasattr(data, "loai_visa") and data.loai_visa:
        route = data.loai_visa
    dep_date = ""
    if hasattr(data, "ngay_khoi_hanh") and data.ngay_khoi_hanh:
        dep_date = data.ngay_khoi_hanh
    price = auto_price(
        getattr(data, "quoc_tich", "") or "",
        route
    )

    # Build display name: "Abramov Aleksandr / 1990"
    name_parts = []
    if hasattr(data, "ho_ten") and data.ho_ten:
        name_parts.append(data.ho_ten)
    if hasattr(data, "nam_sinh") and data.nam_sinh:
        name_parts.append(data.nam_sinh)
    full_name = " / ".join(name_parts) if name_parts else ""

    fields = {
        "Order ID": order_id,
        "Full Name": full_name,
        "Nationality": getattr(data, "quoc_tich", "") or "",
        "Route": route,
        "Departure Date": dep_date,
        "Pickup Point": getattr(data, "diem_don", "") or "",
        "Seat": getattr(data, "ghe_chon", "") or "",
        "Phone": getattr(data, "so_dien_thoai", "") or "",
        "Price (VND)": price,
        "Status": "PENDING",
        "Source Channel": channel,
        "Agent": agent or "Direct",
        "Created At": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(url, json={"fields": fields}, headers=headers)
            res = r.json()
            record_id = res.get("data", {}).get("record", {}).get("record_id", "")
            return {"order_id": order_id, "record_id": record_id, "price": price, "data": data}
    except Exception as e:
        print("Lỗi tạo Order Lark:", e)
        return {"order_id": order_id, "record_id": None, "price": price, "data": data}


async def update_order_status(
    record_id: str,
    status: str,
    payment_note: str = ""
) -> bool:
    """Cập nhật trạng thái đơn hàng (PAID / CONFIRMED / CANCELLED)"""
    token = await get_tenant_access_token()
    url = (
        f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}"
        f"/tables/{ORDERS_TABLE_ID}/records/{record_id}"
    )
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    fields = {"Status": status}
    if payment_note:
        fields["Payment Note"] = payment_note
    if status in ("PAID", "CONFIRMED"):
        fields["Confirmed At"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(url, json={"fields": fields}, headers=headers)
            return r.status_code == 200
    except Exception as e:
        print("Lỗi update Order status:", e)
        return False


async def get_all_orders(status_filter: str | None = None) -> list:
    """Lấy danh sách đơn hàng từ Lark, có thể lọc theo status"""
    token = await get_tenant_access_token()
    url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{ORDERS_TABLE_ID}/records"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=headers)
            items = r.json().get("data", {}).get("items", [])
            orders = []
            for item in items:
                f = item.get("fields", {})
                f["_record_id"] = item.get("record_id", "")
                if status_filter and f.get("Status") != status_filter:
                    continue
                orders.append(f)
            return orders
    except Exception as e:
        print("Lỗi get_all_orders:", e)
        return []
