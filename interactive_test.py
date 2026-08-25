"""
interactive_test.py - Công cụ test trực tiếp AI Chatbot Easy Trip & Visa
Chạy trực tiếp: python interactive_test.py
"""

import sys
import asyncio
import os
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

load_dotenv()

from ai_agent import process_chat, process_staff_chat
import knowledge_rag

async def main():
    knowledge_rag.rebuild()
    print("=" * 65)
    print("🤖 CHƯƠNG TRÌNH TEST TRỰC TIẾP AI CHATBOT EASY TRIP & VISA")
    print(f"📚 Kho tri thức hiện tại: {len(knowledge_rag._rag_index.qa_pairs)} cặp Q&A (Tele + Zalo + Meta + Excel)")
    print("=" * 65)
    print("Chọn chế độ test:")
    print("  [1] Chat thử vai Khách Hàng (Tự động nhận diện Tiếng Việt, Nga, Anh, Hàn...)")
    print("  [2] Chat thử vai Nhân Viên (Hỏi nghiệp vụ, nhờ AI soạn tin nhắn trả lời khách)")
    print("  [3] Chạy bộ test tự động (4 kịch bản: Khách Nga, Mỹ, Hàn, Việt)")
    print("  [0] Thoát")
    print("-" * 65)

    choice = input("👉 Nhập lựa chọn của bạn (1/2/3): ").strip()

    if choice == "1":
        print("\n💬 [CHẾ ĐỘ KHÁCH HÀNG] - Nhập câu hỏi (Gõ 'exit' để dừng, 'reset' để xóa lịch sử):")
        history = []
        while True:
            try:
                user_msg = input("\n👤 Bạn (Khách hàng): ").strip()
                if not user_msg:
                    continue
                if user_msg.lower() in ["exit", "quit", "q"]:
                    break
                if user_msg.lower() == "reset":
                    history = []
                    print("🔄 Đã reset lịch sử trò chuyện.")
                    continue

                history.append({"role": "user", "content": user_msg})
                print("⏳ AI đang suy nghĩ và tra cứu dữ liệu...", end="\r")
                
                resp = await process_chat(history)
                
                print(f"\n🤖 EasyTrip AI:\n{resp.reply_message}\n")
                
                # In thông tin trích xuất
                data = {k: v for k, v in resp.extracted_data.model_dump().items() if v}
                if data:
                    print(f"📊 [Dữ liệu AI đã trích xuất]: {data}")
                print(f"📍 [Giai đoạn hiện tại]: {resp.current_phase}")
                
                history.append({"role": "assistant", "content": resp.reply_message})
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Lỗi: {e}")

    elif choice == "2":
        print("\n💼 [CHẾ ĐỘ NHÂN VIÊN] - Nhập câu hỏi nghiệp vụ hoặc dán tin nhắn khách (Gõ 'exit' để dừng):")
        while True:
            try:
                msg = input("\n👔 Nhân viên: ").strip()
                if not msg or msg.lower() in ["exit", "quit", "q"]:
                    break
                print("⏳ AI đang tra cứu...", end="\r")
                reply = await process_staff_chat(msg)
                print(f"\n🤖 AI Hỗ Trợ:\n{reply}\n")
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\n❌ Lỗi: {e}")

    elif choice == "3":
        print("\n🧪 ĐANG CHẠY BỘ TEST TỰ ĐỘNG...\n")
        scenarios = [
            ("Khách Việt Nam", "Chào bạn, mình muốn hỏi thủ tục và giá vé đi visarun cửa khẩu Mộc Bài từ Nha Trang."),
            ("Khách Mỹ (English)", "Hello! I am a US citizen in Nha Trang. My visa expires on 15/09. How much is Cambodia visa run?"),
            ("Khách Nga (Russian)", "Здравствуйте! Я гражданин РФ, нахожусь в Нячанге. Виза заканчивается 20/09. Сколько стоит визаран в Лаос?"),
            ("Khách Hàn Quốc (Korean)", "안녕하세요! 저는 한국인입니다. 나트랑에서 라오스 비자런 가격이 얼마인가요?"),
        ]
        for name, msg in scenarios:
            print(f"--- [Test: {name}] ---")
            print(f"👤 Khách: {msg}")
            resp = await process_chat([{"role": "user", "content": msg}])
            print(f"🤖 AI:\n{resp.reply_message}\n")
            data = {k: v for k, v in resp.extracted_data.model_dump().items() if v}
            if data:
                print(f"📊 Extracted: {data}")
            print("-" * 60)

    print("\n👋 Đã kết thúc chương trình test.")

if __name__ == "__main__":
    asyncio.run(main())
