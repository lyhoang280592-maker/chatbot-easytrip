import urllib.request
import json
import sys

def main():
    url = "http://localhost:8000/facebook/webhook"
    
    # Kịch bản gửi tin nhắn giả lập
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page_id_123",
                "time": 1719040000,
                "messaging": [
                    {
                        "sender": {"id": "fb_test_user_999"},
                        "recipient": {"id": "page_id_123"},
                        "timestamp": 1719040000,
                        "message": {
                            "mid": "mid.1457764197618:cf3749a37ad058a5e7",
                            "text": "tôi muốn visa run lào"
                        }
                    }
                ]
            }
        ]
    }
    
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        url, 
        data=data, 
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Sending mock FB webhook request to: {url} ...")
    try:
        with urllib.request.urlopen(req) as response:
            status = response.getcode()
            body = response.read().decode("utf-8")
            print(f"Status Code: {status}")
            print(f"Response: {body}")
            print("Webhook request sent successfully!")
    except Exception as e:
        print(f"❌ Error sending webhook request: {e}")
        print("Please make sure your local server is running (e.g. at http://localhost:8000)")
        sys.exit(1)

if __name__ == "__main__":
    main()
