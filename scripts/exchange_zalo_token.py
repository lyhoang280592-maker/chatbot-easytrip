import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv(".env")

def update_env(key: str, value: str):
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
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{key}={value}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def exchange_code(code: str, code_verifier: str = None):
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
    if code_verifier:
        data["code_verifier"] = code_verifier

    print(f"⏳ Đang gửi mã xác thực tới Zalo OAuth (App ID: {app_id})...")
    res = httpx.post(url, headers=headers, data=data, timeout=10.0)
    print(f"Status: {res.status_code}")
    res_data = res.json()
    print("Response:", res_data)
    
    if "access_token" in res_data and "refresh_token" in res_data:
        new_refresh = res_data["refresh_token"]
        update_env("ZALO_REFRESH_TOKEN", new_refresh)
        print(f"\n🎉 CẬP NHẬT THÀNH CÔNG! Refresh Token mới đã được lưu vào .env.")
        print(f"Access Token: {res_data['access_token'][:20]}...")
    else:
        print("\n❌ Thất bại. Vui lòng kiểm tra lại mã authorization code hoặc cấu hình App ID/Secret.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        code = sys.argv[1].strip()
        verifier = sys.argv[2].strip() if len(sys.argv) > 2 else None
        exchange_code(code, verifier)
    else:
        print("Sử dụng: python scripts/exchange_zalo_token.py <MÃ_AUTHORIZATION_CODE> [CODE_VERIFIER]")
