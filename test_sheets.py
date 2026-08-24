import gspread
from google.oauth2.service_account import Credentials
import os

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_FILE = "gcp_service_account.json"

SHEETS = {
    "Sergei": "1qRAqNkMqS9VQRrys8jc-4MhUHebumblmIYArdwSbRNo",
    "Bolot": "1mDweOPSDeoO93cL8WxAv6nUtS9kw6MXFWK42j5gPyvs",
    "Luan": "1vOnA7Zqn3T4XughsDUP0dJsBjUoWCFrt6ibVGLzGWjU",
    "Tung": "1-Extaar3qtMhAKIwVScBYtteqfHHtfJEskKEFo9x9wM"
}

def test_access():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print(f"FAILED: File {SERVICE_ACCOUNT_FILE} not found!")
        return

    try:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        for name, sid in SHEETS.items():
            try:
                wb = client.open_by_key(sid)
                print(f"SUCCESS: Access to {name} sheet OK! (Title: {wb.title})")
            except Exception as e:
                print(f"FAILED: Cannot access {name} sheet. Did you share it with the service account email? Error: {e}")
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

if __name__ == "__main__":
    test_access()
