import sys
import os

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from i18n import get_lang_code, get_msg

# Đảm bảo in được ký tự Unicode trên Windows console
if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

def test_i18n():
    test_cases = [
        ("Russian", "ru", "welcome", "Добро пожаловать"),
        ("Hàn Quốc", "ko", "system_busy", "죄송합니다"),
        ("Trung Quốc", "zh", "please_pay", "请在这里支付"),
        ("Vietnam", "vi", "payment_confirmed", "Đã nhận được thanh toán"),
        ("Unknown", "en", "welcome", "Welcome"),
        ("", "en", "welcome", "Welcome"),
        ("French", "en", "welcome", "Welcome"), # Not in map yet, should default to EN
    ]
    
    print("=== Testing i18n module ===")
    all_passed = True
    for nat, expected_code, key, expected_snippet in test_cases:
        code = get_lang_code(nat)
        msg = get_msg(key, code)
        
        passed = code == expected_code and expected_snippet in msg
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] Nat: {nat:12} | Lang: {code} | Snippet: {expected_snippet}")
        
        if not passed:
            print(f"      Expected code: {expected_code}, Got: {code}")
            print(f"      Message: {msg}")
            all_passed = False
            
    # Test formatting
    msg = get_msg("image_received", "ru", img_type="Passport")
    if "Получено Passport" in msg:
        print("[PASS] Formatting: ru")
    else:
        print(f"[FAIL] Formatting: ru | Got: {msg}")
        all_passed = False

    if all_passed:
        print("\n✅ ALL TESTS PASSED")
    else:
        print("\n❌ SOME TESTS FAILED")

if __name__ == "__main__":
    test_i18n()
