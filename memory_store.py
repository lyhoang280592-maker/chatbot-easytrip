import json
from datetime import datetime
from typing import Any, Dict, List
import customer_memory

# RAM cache storage cho session thao tác siêu tốc
memory_store: Dict[str, Any] = {}


def load_session_history(session_id: str, limit: int = 20) -> List[Dict[str, str]]:
    """Tải lịch sử phiên trò chuyện từ SQLite vào memory_store nếu chưa có trong RAM"""
    if session_id in memory_store and isinstance(memory_store[session_id], list) and memory_store[session_id]:
        return memory_store[session_id]
        
    db_messages = customer_memory.get_session_messages(session_id, limit=limit)
    if db_messages:
        memory_store[session_id] = db_messages
    else:
        if session_id not in memory_store:
            memory_store[session_id] = []
            
    return memory_store[session_id]


def log_message(user_id, platform, role, content, customer_id=None):
    """Ghi log hội thoại đồng thời vào SQLite và file chat_history.json"""
    session_id = f"{platform.lower()}_{user_id}"
    
    # 1. Lưu vào SQLite Database bền vững
    try:
        customer_memory.save_chat_message(
            session_id=session_id,
            platform=platform,
            role=role,
            content=content,
            customer_id=customer_id
        )
    except Exception as e:
        print(f"⚠️ Lỗi lưu chat message vào SQLite: {e}")

    # 2. Ghi log JSON (giữ tương thích)
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
        print(f"Lỗi ghi log file: {e}")


def get_recent_logs(limit=200):
    """Lấy các dòng log mới nhất từ SQLite, fallback file json"""
    try:
        db_logs = customer_memory.get_recent_logs_from_db(limit=limit)
        if db_logs:
            return db_logs
    except Exception:
        pass

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
