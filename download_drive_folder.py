import os
import time
import gdown

def download_folder_with_retry(url, output_dir="HD_Khach_le", max_retries=5):
    """
    Tải toàn bộ thư mục Google Drive về với cơ chế tự động thử lại khi mất kết nối
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for attempt in range(1, max_retries + 1):
        print(f"📡 Đang tải thư mục Google Drive (Lần thử {attempt}/{max_retries})...")
        try:
            res = gdown.download_folder(url=url, output=output_dir, quiet=False, use_cookies=False)
            if res:
                print(f"🎉 Tải thành công toàn bộ thư mục về: {output_dir}")
                return True
        except Exception as e:
            print(f"⚠️ Lỗi kết nối (Lần {attempt}): {e}")
            time.sleep(3)
            
    print("❌ Đã thử tải nhiều lần nhưng chưa hoàn tất.")
    return False

if __name__ == "__main__":
    folder_url = "https://drive.google.com/drive/folders/1t5m89waYfWJKY4tPIFg_tzinSWsGWPOe"
    download_folder_with_retry(folder_url)
