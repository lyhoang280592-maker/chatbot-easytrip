import json
from collections import Counter

with open('telegram_chat.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=== TOP-LEVEL KEYS ===")
for k, v in data.items():
    if isinstance(v, list):
        print(f"  '{k}': list of {len(v)} items")
    elif isinstance(v, dict):
        print(f"  '{k}': dict with keys {list(v.keys())[:5]}")
    else:
        print(f"  '{k}': {str(v)[:80]}")

# Dig into 'chats'
chats_section = data.get('chats', {})
print()
print("=== CHATS SECTION ===")
if isinstance(chats_section, dict):
    print("Chats keys:", list(chats_section.keys()))
    chat_list = chats_section.get('list', [])
    print(f"Total chats: {len(chat_list)}")
    print()
    total_msgs = 0
    for i, chat in enumerate(chat_list):
        name = chat.get('name', 'N/A')
        ctype = chat.get('type', '?')
        msgs = chat.get('messages', [])
        total_msgs += len(msgs)
        print(f"  [{i+1}] {name} ({ctype}) - {len(msgs)} messages")
    print()
    print(f"=== TONG SO TIN NHAN: {total_msgs} ===")

# Also check left_chats
left = data.get('left_chats', {})
if isinstance(left, dict):
    left_list = left.get('list', [])
    print(f"\nLeft chats: {len(left_list)} chats")
    for chat in left_list[:5]:
        msgs = chat.get('messages', [])
        print(f"  {chat.get('name','?')} - {len(msgs)} messages")
