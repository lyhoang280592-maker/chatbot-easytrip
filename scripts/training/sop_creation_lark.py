import os, httpx, asyncio
from dotenv import load_dotenv

load_dotenv()

async def create_sop_on_lark():
    LARK_APP_ID = os.getenv("LARK_APP_ID")
    LARK_APP_SECRET = os.getenv("LARK_APP_SECRET")
    LARK_APP_TOKEN = os.getenv("LARK_APP_TOKEN")
    
    # Chúng ta sẽ đẩy vào một bảng mới hoặc Record mới trong Bitable cho dễ quản lý
    # Hoặc nếu anh chị có ID của một thư mục (Folder Token), tôi có thể tạo Docx.
    # Ở đây tôi sẽ đẩy vào bảng KHO_TRI_THUC với tiêu đề là "OFFICIAL SOP"
    TABLE_ID = os.getenv("LARK_KNOWLEDGE_TABLE_ID", "tbl6cnBVolclQp9v")

    sop_content = """
# EASY TRIP & VISA - STANDARD OPERATING PROCEDURE (SOP)
## Subject: Automated Visarun & Booking Workflow

1. STAGE 1: INITIAL CONSULTATION (AI-DRIVEN)
   - Objective: Filter customers and determine the route.
   - Key Questions: Nationality? Current Visa Expiry Date?
   - Routing Logic:
     * Laos Border (Bo Y): For Russia, Korea, Belarus, and ASEAN citizens (Visa-free).
     * Cambodia Border (Moc Bai): For all other nationalities.

2. STAGE 2: BOOKING & LOGISTICS
   - Departure Date: Automatically calculated as 1 day BEFORE visa expiry.
   - Seat Selection: AI provides the latest Seat Map. Staff must update the seat map in the Bus Group whenever a seat is taken.
   - Command: Use "lock [Seat ID]" to reserve.

3. STAGE 3: DATA ENTRY
   - Required Info: Full Name (as per Passport), Year of Birth, and Pickup Point (Oceanus or River Station).
   - Validation: AI extracts this data into the system.

4. STAGE 4: PAYMENT & CONFIRMATION
   - Payment Method: Bank Transfer to LY VIET HOANG (BIDV - 8836142054).
   - Verification: Customer must send a screenshot of the receipt.
   - Admin Action: Confirm payment and change status to "PAID" in Lark Base.

5. STAGE 5: OPERATION HANDOVER
   - AI generates the final registration format:
     [Date] - [Visa Type] - [Destination]
     Name: [Full Name] [YOB]
     Seat: [Seat ID]
     Pickup: [Point]
   - This message is automatically sent to the "Operation Group" for bus arrangements.

6. STAGE 6: CUSTOMER SUPPORT
   - Emergency Contact: Mr. Hoang (+84 896 916 361) for immediate assistance at the border.
    """

    async with httpx.AsyncClient(timeout=30) as http:
        # Get Token
        auth = await http.post(
            "https://open.larksuite.com/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": LARK_APP_ID, "app_secret": LARK_APP_SECRET}
        )
        token = auth.json().get("tenant_access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create Record in Knowledge Table
        url = f"https://open.larksuite.com/open-apis/bitable/v1/apps/{LARK_APP_TOKEN}/tables/{TABLE_ID}/records"
        payload = {
            "fields": {
                "Question": "OFFICIAL BUSINESS SOP (ENGLISH)",
                "Answer": sop_content
            }
        }
        
        r = await http.post(url, json=payload, headers=headers)
        if r.status_code == 200:
            print("=== SUCCESS ===\nSOP has been uploaded to Lark Knowledge Base.")
        else:
            print(f"FAILED: {r.text}")

if __name__ == "__main__":
    asyncio.run(create_sop_on_lark())
