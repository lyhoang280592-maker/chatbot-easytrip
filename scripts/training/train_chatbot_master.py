"""
train_chatbot_master.py - TRUNG TÂM HUẤN LUYỆN CHATBOT & QUẢN LÝ DỮ LIỆU EASYTRIP
Cung cấp menu 1 chạm để:
1. Huấn luyện toàn diện & Cập nhật chỉ mục RAG từ toàn bộ kho dữ liệu (705+ Q&A, 4.485 tin nhắn, 323 khách cũ).
2. Thêm nhanh 1 cặp Hỏi - Đáp (Q&A) mới vào kho tri thức (Tự động nạp vào RAG ngay lập tức).
3. Đồng bộ dữ liệu kiến thức 2 chiều với Lark CRM Base (Push / Pull).
4. Chạy bộ kiểm thử tự động (Auto-Benchmark & Evaluation) toàn diện hệ thống AI.
"""

import os
import sys
import json
import argparse
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts", "training"))


def print_banner():
    print("\n" + "=" * 65)
    print(" 🧠 EASYTRIP - TRUNG TÂM HUẤN LUYỆN CHATBOT & QUẢN TRỊ DỮ LIỆU")
    print("=" * 65)


def run_full_training():
    """Chạy toàn bộ quy trình import dữ liệu lịch sử & re-index RAG"""
    print("\n--- [1] BẮT ĐẦU HUẤN LUYỆN TOÀN DIỆN VÀ TÁI LẬP CHỈ MỤC RAG ---")
    
    # 1. Import Legacy Data & Contracts & Chats into SQLite DB
    print("\n🔹 Bước 1: Nạp dữ liệu khách hàng, chuyến đi và lịch sử chat vào SQLite DB...")
    import_script = os.path.join(ROOT_DIR, "scripts", "training", "import_legacy_data.py")
    if os.path.exists(import_script):
        os.system(f'"{sys.executable}" "{import_script}"')
    else:
        print(f"⚠️ Không tìm thấy script: {import_script}")

    # 2. Re-index RAG Search Engine
    print("\n🔹 Bước 2: Tái lập chỉ mục RAG TF-IDF Engine từ toàn bộ file kiến thức...")
    try:
        import knowledge_rag
        knowledge_rag.rebuild()
        total_qa = len(knowledge_rag._rag_index.qa_pairs)
        print(f"✅ RAG Engine đã nạp thành công {total_qa} cặp Q&A vào bộ nhớ!")
        
        # Test 1 câu mẫu
        test_q = "giá vé đi lào bao nhiêu"
        results = knowledge_rag.search(test_q, top_k=2)
        print(f"\n🔍 Thử nghiệm tìm kiếm mẫu cho câu hỏi: '{test_q}'")
        for idx, item in enumerate(results, 1):
            print(f"   [{idx}] (Score: {item['score']:.3f}) Q: {item['question']} -> A: {item['answer'][:70]}...")
    except Exception as e:
        print(f"⚠️ Lỗi khi nạp RAG: {e}")

    print("\n🎉 HUẤN LUYỆN HOÀN TẤT! Toàn bộ kho tri thức và bộ nhớ khách hàng đã sẵn sàng.")


def add_quick_qa():
    """Thêm nhanh 1 cặp câu hỏi - câu trả lời mới vào kho tri thức"""
    print("\n--- [2] THÊM NHANH CÂU HỎI & CÂU TRẢ LỜI MỚI VÀO KHO TRI THỨC ---")
    
    question = input("❓ Nhập câu hỏi của khách hàng: ").strip()
    if not question:
        print("⚠️ Câu hỏi không được để trống!")
        return

    answer = input("💡 Nhập câu trả lời chuẩn xác của Bot: ").strip()
    if not answer:
        print("⚠️ Câu trả lời không được để trống!")
        return

    category = input("🏷️ Danh mục (VD: Giá vé, Lịch xe, Quy định visa, Mộc Bài, Bờ Y) [Mặc định: Chung]: ").strip() or "Chung"
    
    manual_qa_path = os.path.join(ROOT_DIR, "data", "training_knowledge", "manual_qa.json")
    if not os.path.exists(manual_qa_path):
        manual_qa_path = os.path.join(ROOT_DIR, "manual_qa.json")

    existing_qa = []
    if os.path.exists(manual_qa_path):
        try:
            with open(manual_qa_path, "r", encoding="utf-8") as f:
                existing_qa = json.load(f)
        except Exception:
            existing_qa = []

    new_entry = {
        "question": question,
        "answer": answer,
        "category": category,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    existing_qa.append(new_entry)

    with open(manual_qa_path, "w", encoding="utf-8") as f:
        json.dump(existing_qa, f, ensure_ascii=False, indent=2)

    print(f"✅ Đã thêm câu hỏi vào: {manual_qa_path}")
    
    # Tự động reload RAG
    print("⏳ Đang cập nhật lại bộ nhớ RAG...")
    try:
        import knowledge_rag
        knowledge_rag.rebuild()
        total_qa = len(knowledge_rag._rag_index.qa_pairs)
        print(f"🚀 Thành công! RAG Engine hiện có tổng cộng {total_qa} cặp Q&A.")
    except Exception as e:
        print(f"⚠️ Lỗi cập nhật RAG: {e}")


def sync_crm_knowledge():
    """Đồng bộ với Lark Base CRM"""
    print("\n--- [3] ĐỒNG BỘ TRI THỨC VỚI LARK BASE CRM ---")
    print("  1. ⬆️  Push: Đẩy toàn bộ Q&A từ máy tính lên CRM Lark Base")
    print("  2. ⬇️  Pull: Tải toàn bộ Q&A mới nhất từ CRM Lark Base về máy tính")
    
    choice = input("👉 Chọn thao tác (1/2): ").strip()
    sync_script = os.path.join(ROOT_DIR, "scripts", "training", "sync_knowledge_crm.py")
    if not os.path.exists(sync_script):
        print("⚠️ Không tìm thấy sync_knowledge_crm.py")
        return
        
    if choice == "1":
        os.system(f'"{sys.executable}" "{sync_script}" push')
    elif choice == "2":
        os.system(f'"{sys.executable}" "{sync_script}" pull')
    else:
        print("⚠️ Lựa chọn không hợp lệ.")


def run_benchmark_and_eval():
    """Chạy toàn bộ bài test kiểm thử chất lượng AI"""
    print("\n--- [4] CHẠY KIỂM THỬ ĐÁNH GIÁ CHẤT LƯỢNG AI (BENCHMARK) ---")
    tests_cmd = (
        f'"{sys.executable}" "{os.path.join(ROOT_DIR, "tests", "test_returning_customer.py")}" && '
        f'"{sys.executable}" "{os.path.join(ROOT_DIR, "tests", "test_visa_reminder.py")}" && '
        f'"{sys.executable}" "{os.path.join(ROOT_DIR, "tests", "test_compound_logic.py")}" && '
        f'"{sys.executable}" "{os.path.join(ROOT_DIR, "tests", "test_i18n.py")}"'
    )
    res = os.system(tests_cmd)
    if res == 0:
        print("\n🎉 TẤT CẢ CÁC BÀI KIỂM THỬ ĐẠT ĐIỂM TUYỆT ĐỐI (100% PASSED)!")
    else:
        print("\n⚠️ Có bài kiểm thử chưa đạt, vui lòng kiểm tra lại log.")


def main():
    parser = argparse.ArgumentParser(description="EasyTrip Chatbot Training & Data Master")
    parser.add_argument("--train", action="store_true", help="Chạy toàn bộ quy trình huấn luyện")
    parser.add_argument("--add-qa", action="store_true", help="Thêm nhanh 1 cặp Q&A mới")
    parser.add_argument("--sync-crm", action="store_true", help="Đồng bộ với Lark CRM")
    parser.add_argument("--eval", action="store_true", help="Chạy kiểm thử đánh giá AI")
    args = parser.parse_args()

    if args.train:
        run_full_training()
        return
    if args.add_qa:
        add_quick_qa()
        return
    if args.sync_crm:
        sync_crm_knowledge()
        return
    if args.eval:
        run_benchmark_and_eval()
        return

    while True:
        print_banner()
        print("1. 🚀  Huấn luyện toàn diện & Cập nhật chỉ mục RAG (705+ Q&A, 4.485 chat, 323 khách cũ)")
        print("2. 💡  Thêm nhanh 1 cặp Hỏi - Đáp (Q&A) mới vào kho tri thức (Tự động nạp ngay)")
        print("3. 🔄  Đồng bộ 2 chiều với CRM Lark Base (Push / Pull)")
        print("4. 🧪  Chạy kiểm thử đánh giá chất lượng AI toàn diện (Auto-Benchmark)")
        print("5. 🚪  Thoát")

        choice = input("\n👉 Vui lòng chọn chức năng (1-5): ").strip()
        if choice == "1":
            run_full_training()
        elif choice == "2":
            add_quick_qa()
        elif choice == "3":
            sync_crm_knowledge()
        elif choice == "4":
            run_benchmark_and_eval()
        elif choice == "5":
            print("\n👋 Tạm biệt!")
            break
        else:
            print("⚠️ Lựa chọn không hợp lệ, vui lòng chọn từ 1 đến 5.")


if __name__ == "__main__":
    main()
