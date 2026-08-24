import os
from PIL import Image, ImageOps

def convert_all_passports_to_bw(input_dir="downloads/passports", output_dir="downloads/passports_bw"):
    """
    Chuyển đổi toàn bộ ảnh hộ chiếu thành Trắng Đen (Grayscale / Black & White)
    Giữ nguyên 100% kích thước gốc của toàn bộ trang hộ chiếu, không cắt (no crop).
    Tự động hiệu chỉnh xoay ảnh theo EXIF orientation.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(input_dir):
        print(f"❌ Không tìm thấy thư mục: {input_dir}")
        return []
    
    files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    print(f"🔄 Bắt đầu chuyển đổi {len(files)} ảnh hộ chiếu sang Trắng Đen (không cắt)...")
    
    converted = []
    for idx, filename in enumerate(files, 1):
        in_path = os.path.join(input_dir, filename)
        out_path = os.path.join(output_dir, filename)
        
        try:
            with Image.open(in_path) as img:
                # Tự động xoay đúng chiều theo thông số EXIF của máy ảnh/điện thoại
                img_transposed = ImageOps.exif_transpose(img)
                
                # Chuyển sang Grayscale (Trắng Đen)
                bw_img = ImageOps.grayscale(img_transposed)
                
                # Tăng độ tương phản nhẹ để nét chữ và hình ảnh rõ ràng như bản photocopy chuẩn
                bw_img = ImageOps.autocontrast(bw_img, cutoff=1)
                
                # Lưu dưới định dạng JPEG chất lượng cao
                bw_img.save(out_path, format="JPEG", quality=95)
                converted.append(out_path)
                
        except Exception as e:
            print(f"⚠️ Lỗi xử lý {filename}: {e}")
            
    print(f"🎉 Đã chuyển đổi thành công {len(converted)}/{len(files)} ảnh sang Trắng Đen tại: {output_dir}")
    return converted

if __name__ == "__main__":
    convert_all_passports_to_bw()
