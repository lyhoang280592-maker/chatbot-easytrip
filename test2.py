import urllib.request
import json

req = urllib.request.Request(
    'https://chatbot-easytrip.onrender.com/chat',
    data=json.dumps({'messages': [{'role': 'user', 'content': 'hi'}]}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
try:
    res = urllib.request.urlopen(req)
    print("SUCCESS:", res.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTPError: {e.code}")
    print(e.read().decode())
except Exception as e:
    print("Other Error:", e)
