import httpx
import os

def download_drive_file():
    # ID file Google Drive của sếp
    file_id = "1Q-1OH9gOIWyPNzLIlZ-1Wdd0zRZYxwO2"
    # Đường dẫn tải trực tiếp không cần đăng nhập
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
    
    out_path = "fleet_video.mov"
    print("Đang tải video thực tế đoàn xe từ Google Drive về máy chủ...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    try:
        with httpx.Client(follow_redirects=True) as client:
            response = client.get(download_url, headers=headers, timeout=60.0)
            if response.status_code == 200:
                with open(out_path, "wb") as f:
                    f.write(response.content)
                size_mb = os.path.getsize(out_path) / (1024 * 1024)
                print(f"🎉 TẢI THÀNH CÔNG! Đã lưu video thành '{out_path}' | Kích thước: {size_mb:.2f} MB")
                return True
            else:
                print(f"Lỗi tải video (Status code: {response.status_code}): {response.text}")
                return False
    except Exception as e:
        print("Lỗi hệ thống khi tải video:", e)
        return False

if __name__ == "__main__":
    download_drive_file()
