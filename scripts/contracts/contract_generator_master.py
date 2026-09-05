"""
contract_generator_master.py - TRUNG TÂM QUẢN LÝ VÀ TẠO HỢP ĐỒNG KHÁCH HÀNG EASYTRIP
Cung cấp menu điều khiển 1 chạm để:
1. Tạo 1 hợp đồng nhanh cho khách hàng (xuất file DOCX / PDF có dấu đỏ & chữ ký).
2. Tạo hợp đồng hàng loạt từ file Excel CRM.
3. Xử lý ảnh hộ chiếu sang đen trắng (B&W Passport Processing).
"""

import os
import sys
import argparse
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "scripts", "contracts"))


def print_banner():
    print("\n" + "=" * 65)
    print(" 📄 EASYTRIP & VISA - TRUNG TÂM TẠO HỢP ĐỒNG KHÁCH HÀNG")
    print("=" * 65)


def create_single_contract_interactive():
    """Tạo hợp đồng cho 1 khách hàng thông qua nhập liệu nhanh"""
    print("\n--- [1] TẠO HỢP ĐỒNG ĐƠN LẺ NHANH ---")
    
    full_name = input("👤 Họ và tên khách hàng (VD: ALEXEY SMIRNOV): ").strip()
    if not full_name:
        print("⚠️ Tên khách hàng không được để trống!")
        return

    nationality = input("🌍 Quốc tịch (VD: Russian / Hàn Quốc / Vietnam): ").strip() or "Russian"
    passport_number = input("🛂 Số hộ chiếu (VD: 75N1234567): ").strip() or "N/A"
    phone_number = input("📞 Số điện thoại / Zalo (VD: +84988776655): ").strip() or "N/A"
    
    print("\nChọn tuyến dịch vụ:")
    print("  1. Nha Trang ↔ Bo Y (Lào 45 ngày Miễn Thị Thực)")
    print("  2. Nha Trang ↔ Mộc Bài (Campuchia 90 ngày E-visa)")
    print("  3. Nha Trang ↔ Bo Y (Lào 90 ngày)")
    print("  4. Dịch vụ E-visa Việt Nam")
    svc_choice = input("👉 Chọn (1-4, mặc định 1): ").strip() or "1"
    
    services_map = {
        "1": ("Nha Trang - Cửa khẩu Bờ Y (Lào)", "Lào 45 Ngày Miễn Thị Thực", 3300000),
        "2": ("Nha Trang - Mộc Bài (Campuchia)", "Campuchia 90 Ngày E-visa", 4000000),
        "3": ("Nha Trang - Cửa khẩu Bờ Y (Lào)", "Lào 90 Ngày E-visa", 4200000),
        "4": ("Dịch vụ E-visa Việt Nam", "E-visa 90 Ngày", 1500000),
    }
    route, visa_type, default_price = services_map.get(svc_choice, services_map["1"])
    
    dep_date_input = input(f"📅 Ngày khởi hành (DD/MM/YYYY, mặc định hôm nay {datetime.now().strftime('%d/%m/%Y')}): ").strip()
    departure_date = dep_date_input or datetime.now().strftime("%d/%m/%Y")
    
    price_input = input(f"💰 Giá dịch vụ VNĐ (mặc định {default_price:,} VNĐ): ").strip()
    price = int(price_input.replace(",", "").replace(".", "")) if price_input.isdigit() else default_price
    
    tier = input("🏢 Loại khách (1: Khách lẻ - Retail, 2: Đại lý - Agency, mặc định 1): ").strip() or "1"
    is_agency = (tier == "2")
    
    now = datetime.now()
    contract_data = {
        "contract_no": datetime.now().strftime("%y%m%d%H%M"),
        "date_vi": f"ngày {now.day:02d} tháng {now.month:02d} năm {now.year}",
        "date_en": now.strftime("%B %d, %Y"),
        "customer_name": full_name.upper(),
        "passport_no": passport_number,
        "date_of_issue": "20/05/2022",
        "nationality": nationality,
        "service_fee": price,
        "state_fee": 0,
        "signature_image_path": None
    }
    
    output_dir = os.path.join(ROOT_DIR, "output_contracts")
    os.makedirs(output_dir, exist_ok=True)
    
    file_name = f"HopDong_{contract_data['contract_no']}_{full_name.replace(' ', '_')}.docx"
    file_path = os.path.join(output_dir, file_name)
    
    print(f"\n⏳ Đang khởi tạo hợp đồng cho {full_name}...")
    try:
        from generate_docx_contracts import build_contract_docx
        build_contract_docx(file_path, contract_data)
        print(f"✅ ĐÃ TẠO THÀNH CÔNG HỢP ĐỒNG!")
        print(f"📁 Đường dẫn file: {file_path}")
    except Exception as e:
        print(f"⚠️ Lỗi khi tạo file hợp đồng: {e}")


def batch_generate_from_excel():
    """Tạo hợp đồng hàng loạt từ Excel CRM"""
    print("\n--- [2] TẠO HỢP ĐỒNG HÀNG LOẠT TỪ EXCEL ---")
    excel_candidates = [
        os.path.join(ROOT_DIR, "data", "contracts_and_crm", "danh_sach_hop_dong_01_08_den_24_08.xlsx"),
        os.path.join(ROOT_DIR, "data", "contracts_and_crm", "danh_sach_khach_hang_co_evisa_01_08_den_19_08.xlsx"),
    ]
    
    valid_files = [f for f in excel_candidates if os.path.exists(f)]
    if not valid_files:
        print("⚠️ Không tìm thấy file Excel nào trong data/contracts_and_crm/")
        return
        
    print("Danh sách file Excel có sẵn:")
    for idx, f in enumerate(valid_files, 1):
        print(f"  {idx}. {os.path.basename(f)}")
        
    choice = input("👉 Chọn file cần tạo (1-N): ").strip() or "1"
    try:
        selected_file = valid_files[int(choice) - 1]
    except Exception:
        selected_file = valid_files[0]
        
    print(f"\n⏳ Đang tiến hành tạo hợp đồng từ file: {os.path.basename(selected_file)}...")
    cmd = f'"{sys.executable}" "{os.path.join(ROOT_DIR, "scripts", "contracts", "batch_process_contracts.py")}"'
    os.system(cmd)
    print("✅ Hoàn tất tiến trình tạo hợp đồng hàng loạt!")


def process_passports_bw():
    """Chuyển đổi ảnh hộ chiếu sang trắng đen"""
    print("\n--- [3] XỬ LÝ ẢNH HỘ CHIẾU SANG TRẮNG ĐEN (B&W) ---")
    script_path = os.path.join(ROOT_DIR, "scripts", "contracts", "convert_passports_to_bw.py")
    if os.path.exists(script_path):
        os.system(f'"{sys.executable}" "{script_path}"')
    else:
        print("⚠️ Không tìm thấy script convert_passports_to_bw.py")


def main():
    parser = argparse.ArgumentParser(description="EasyTrip Contract Generator Master")
    parser.add_argument("--single", action="store_true", help="Tạo 1 hợp đồng lẻ")
    parser.add_argument("--batch", action="store_true", help="Tạo hàng loạt từ Excel")
    parser.add_argument("--bw-passports", dest="bw_passports", action="store_true", help="Xử lý ảnh hộ chiếu trắng đen")
    args = parser.parse_args()
    
    if args.single:
        create_single_contract_interactive()
        return
    if args.batch:
        batch_generate_from_excel()
        return
    if args.bw_passports:
        process_passports_bw()
        return

    while True:
        print_banner()
        print("1. ✍️  Tạo 1 hợp đồng lẻ nhanh (Word DOCX có dấu đỏ & chữ ký)")
        print("2. 📑  Tạo hợp đồng hàng loạt từ Excel CRM")
        print("3. 🖼️   Xử lý ảnh hộ chiếu sang đen trắng sắc nét (B&W)")
        print("4. 🚪  Thoát")
        
        choice = input("\n👉 Vui lòng chọn chức năng (1-4): ").strip()
        if choice == "1":
            create_single_contract_interactive()
        elif choice == "2":
            batch_generate_from_excel()
        elif choice == "3":
            process_passports_bw()
        elif choice == "4":
            print("\n👋 Tạm biệt!")
            break
        else:
            print("⚠️ Lựa chọn không hợp lệ, vui lòng chọn từ 1 đến 4.")


if __name__ == "__main__":
    main()
