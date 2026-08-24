import httpx
import re

url = "https://www.easytripvisa.com/"
try:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    r = httpx.get(url, headers=headers, timeout=15)
    html = r.text
    
    # Quét tất cả đường dẫn ảnh trong HTML
    img_urls = re.findall(r'src="([^"]+?\.(?:jpg|png|webp|gif|jpeg)[^"]*)"', html)
    bg_urls = re.findall(r'url\(\'?([^\'\)]+?\.(?:jpg|png|webp|gif|jpeg)[^\'\)]*)\'\)', html)
    
    all_urls = list(set(img_urls + bg_urls))
    print(f"--- FOUND {len(all_urls)} IMAGES ---")
    for u in all_urls:
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = "https://www.easytripvisa.com/" + u[1:]
        elif not u.startswith("http"):
            u = "https://www.easytripvisa.com/" + u
        print(u)
except Exception as e:
    print("Error:", e)
