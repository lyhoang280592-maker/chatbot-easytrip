import json
from datetime import datetime

# RAM storage cho session
memory_store = {}


def log_message(user_id, platform, role, content):
    """Ghi log hội thoại vào file chat_history.json để Admin truy cập"""
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_id": str(user_id),
        "platform": platform,
        "role": role,
        "content": content,
    }
    try:
        with open("chat_history.json", "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"Lỗi ghi log: {e}")


def get_recent_logs(limit=200):
    """Lấy các dòng log mới nhất"""
    logs = []
    try:
        with open("chat_history.json", "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    logs.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        pass
    return logs[::-1]
