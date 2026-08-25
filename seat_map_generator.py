import os
import sys
from PIL import Image, ImageDraw, ImageFont

# Sửa lỗi in tiếng Việt trên Terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    getattr(sys.stdout, "reconfigure")(encoding="utf-8")

# Đảm bảo nhận dạng chính xác sơ đồ gốc của bạn
TEMPLATE_PATH = "seat_map_template.jpg"
if os.path.exists("seat_map_template.jpg.jpg"):
    TEMPLATE_PATH = "seat_map_template.jpg.jpg"
elif os.path.exists("seat_map_template.jpg"):
    TEMPLATE_PATH = "seat_map_template.jpg"
OUTPUT_PATH = "seat_map_output.jpg"

# Tọa độ tương đối của các ghế (X_ratio, Y_ratio)
# Dựa trên phân tích ảnh, tính theo % chiều rộng và chiều cao
RELATIVE_COORDINATES = {
    # Tầng dưới (Bên trái)
    "A1": (0.25, 0.25), "B1": (0.35, 0.25),
    "A3": (0.25, 0.35), "B3": (0.35, 0.35),
    "A5": (0.25, 0.46), "B5": (0.35, 0.46),
    "A7": (0.25, 0.57), "B7": (0.35, 0.57),
    "A9": (0.25, 0.68), "B9": (0.35, 0.68),
    "A11": (0.25, 0.79),
    
    # Tầng trên (Bên phải)
    "A2": (0.64, 0.25), "B2": (0.74, 0.25),
    "A4": (0.64, 0.35), "B4": (0.74, 0.35),
    "A6": (0.64, 0.46), "B6": (0.74, 0.46),
    "A8": (0.64, 0.57), "B8": (0.74, 0.57),
    "A10": (0.64, 0.68), "B10": (0.74, 0.68),
    "A12": (0.64, 0.79)
}

def generate_seat_map(booked_seats: list[str], template_path=TEMPLATE_PATH, output_path=OUTPUT_PATH):
    """
    Vẽ dấu X màu vàng lên các ghế đã được đặt
    """
    if not os.path.exists(template_path):
        print(f"Không tìm thấy file ảnh gốc: {template_path}")
        # Tạo ảnh giả định nếu chưa có file mẫu
        img = Image.new('RGB', (800, 1000), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), "Seat Map Template (Mock)", fill=(0, 0, 0))
        width, height = 800, 1000
    else:
        img = Image.open(template_path)
        draw = ImageDraw.Draw(img)
        width, height = img.size

    # Cấu hình màu và kích thước dấu X (Làm to và nét dày theo mẫu của bạn)
    cross_color = (255, 215, 0) # Màu vàng
    cross_size = int(width * 0.035) # Tăng kích thước dấu X để bao phủ hết ghế
    line_width = max(5, int(width * 0.008)) # Tăng độ dày của nét vẽ

    for seat in booked_seats:
        seat = seat.upper().strip()
        if seat in RELATIVE_COORDINATES:
            rx, ry = RELATIVE_COORDINATES[seat]
            x = int(width * rx)
            y = int(height * ry)
            # Vẽ dấu X
            draw.line((x - cross_size, y - cross_size, x + cross_size, y + cross_size), fill=cross_color, width=line_width)
            draw.line((x - cross_size, y + cross_size, x + cross_size, y - cross_size), fill=cross_color, width=line_width)
        else:
            print(f"Ghế {seat} không có trong cấu hình toạ độ.")

    img.save(output_path)
    return output_path

if __name__ == "__main__":
    # Test
    out = generate_seat_map(["A1", "B2", "C3"])
    print(f"Saved to {out}")
