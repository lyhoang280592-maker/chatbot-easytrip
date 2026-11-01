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

# Danh sách ghế hợp lệ thực tế trên xe buýt (Tuyệt đối KHÔNG có A11, B11, và KHÔNG có A13..A20, B12..B20)
LOWER_DECK_SEATS = ["A1", "B1", "A3", "B3", "A5", "B5", "A7", "B7", "A9", "B9"]
UPPER_DECK_SEATS = ["A2", "B2", "A4", "B4", "A6", "B6", "A8", "B8", "A10", "B10"]
OPTIONAL_SEATS = ["A12"]  # Thi thoảng xe có thêm ghế A12 (160cm) ở cuối tầng trên
VALID_BUS_SEATS = LOWER_DECK_SEATS + UPPER_DECK_SEATS + OPTIONAL_SEATS

# Tọa độ tương đối của các ghế (X_ratio, Y_ratio) trên template chuẩn
RELATIVE_COORDINATES = {
    # Tầng dưới (Bên trái - số lẻ)
    "A1": (0.25, 0.25), "B1": (0.35, 0.25),
    "A3": (0.25, 0.35), "B3": (0.35, 0.35),
    "A5": (0.25, 0.46), "B5": (0.35, 0.46),
    "A7": (0.25, 0.57), "B7": (0.35, 0.57),
    "A9": (0.25, 0.68), "B9": (0.35, 0.68),
    
    # Tầng trên (Bên phải - số chẵn)
    "A2": (0.64, 0.25), "B2": (0.74, 0.25),
    "A4": (0.64, 0.35), "B4": (0.74, 0.35),
    "A6": (0.64, 0.46), "B6": (0.74, 0.46),
    "A8": (0.64, 0.57), "B8": (0.74, 0.57),
    "A10": (0.64, 0.68), "B10": (0.74, 0.68),
    "A12": (0.64, 0.79)
}

# Tọa độ quét nhận diện vạch bút nhớ màu vàng trên sơ đồ nhà xe gửi (Ngọc Cao / Liên Hưng)
DETECTION_COORDINATES = {
    # Tầng dưới (нижний ярус - bên trái)
    "A1": (0.22, 0.25), "B1": (0.34, 0.25),
    "A3": (0.22, 0.35), "B3": (0.34, 0.35),
    "A5": (0.22, 0.46), "B5": (0.34, 0.46),
    "A7": (0.22, 0.57), "B7": (0.34, 0.57),
    "A9": (0.22, 0.69), "B9": (0.34, 0.69),
    # Tầng trên (верхний ярус - bên phải)
    "A2": (0.64, 0.25), "B2": (0.75, 0.25),
    "A4": (0.64, 0.35), "B4": (0.75, 0.35),
    "A6": (0.64, 0.46), "B6": (0.75, 0.46),
    "A8": (0.64, 0.57), "B8": (0.75, 0.57),
    "A10": (0.64, 0.69), "B10": (0.75, 0.69),
}


def analyze_seat_map_image(image_path: str) -> dict:
    """
    Tự động phân tích ảnh sơ đồ ghế xe buýt do điều hành xe (Ngọc Cao / nhân viên) gửi:
    - Nhận diện xem ảnh có phải là sơ đồ xe buýt không (dựa trên nền trắng + dấu X xanh lá ở vị trí A11).
    - Quét từng ô ghế (A1..A10, B1..B10) để phát hiện vạch đánh dấu màu vàng/đỏ/cam (ghế đã có người ngồi).
    - Trả về danh sách booked_seats (đã đặt) và available_seats (còn trống).
    """
    result = {
        "is_seat_map": False,
        "booked_seats": [],
        "available_seats": list(LOWER_DECK_SEATS + UPPER_DECK_SEATS),
        "lower_available": list(LOWER_DECK_SEATS),
        "upper_available": list(UPPER_DECK_SEATS),
    }
    if not image_path or not os.path.exists(image_path):
        return result

    try:
        with Image.open(image_path) as raw_img:
            img = raw_img.convert("RGB")
            w, h = img.size
            if w < 100 or h < 100:
                return result

            # Tự động cắt bỏ viền tối (nếu nhân viên gửi ảnh chụp màn hình chứa sơ đồ màu trắng bên trong)
            col_white = []
            for x in range(0, w, max(1, w // 200)):
                cnt = sum(1 for y in range(0, h, max(1, h // 100)) if all(c > 215 for c in img.getpixel((x, y))))
                if cnt >= (h // max(1, h // 100)) * 0.35:
                    col_white.append(x)
            row_white = []
            if col_white:
                x_min_c, x_max_c = min(col_white), max(col_white)
                span_w = max(1, x_max_c - x_min_c)
                for y in range(0, h, max(1, h // 200)):
                    cnt = sum(1 for x in range(x_min_c, x_max_c + 1, max(1, span_w // 100)) if all(c > 215 for c in img.getpixel((x, y))))
                    if cnt >= (span_w // max(1, span_w // 100)) * 0.45:
                        row_white.append(y)
                if row_white:
                    y_min_c, y_max_c = min(row_white), max(row_white)
                    if (x_max_c - x_min_c) >= 120 and (y_max_c - y_min_c) >= 150:
                        if (x_max_c - x_min_c) < w * 0.92 or (y_max_c - y_min_c) < h * 0.92:
                            img = img.crop((x_min_c, y_min_c, min(w, x_max_c + 4), min(h, y_max_c + 4)))
                            w, h = img.size

            # 1. Kiểm tra tỷ lệ nền sáng (trắng/xám nhạt) và dấu X màu xanh lá tại ô A11 (x: 0.14..0.32, y: 0.70..0.88)
            green_cnt = 0
            for y in range(int(0.70 * h), int(0.88 * h)):
                for x in range(int(0.14 * w), int(0.32 * w)):
                    r, g, b = img.getpixel((x, y))
                    if g > 110 and (g - r) > 30 and (g - b) > 30:
                        green_cnt += 1

            # Kiểm tra thêm độ sáng nền chung
            sample_light = 0
            sample_total = 0
            step_x = max(1, w // 40)
            step_y = max(1, h // 40)
            for sy in range(0, h, step_y):
                for sx in range(0, w, step_x):
                    r, g, b = img.getpixel((sx, sy))
                    sample_total += 1
                    if r > 200 and g > 200 and b > 200:
                        sample_light += 1
            light_ratio = sample_light / max(1, sample_total)

            if green_cnt >= 20 and light_ratio >= 0.45:
                result["is_seat_map"] = True

            # 2. Quét từng ghế trong DETECTION_COORDINATES để tìm vạch màu vàng / cam / đỏ / xanh dương
            booked = []
            avail = []
            for seat, (rx, ry) in DETECTION_COORDINATES.items():
                x0 = max(0, int((rx - 0.05) * w))
                x1 = min(w, int((rx + 0.05) * w))
                y0 = max(0, int((ry - 0.04) * h))
                y1 = min(h, int((ry + 0.04) * h))
                marked_pixels = 0
                box_total = max(1, (x1 - x0) * (y1 - y0))
                for py in range(y0, y1):
                    for px in range(x0, x1):
                        r, g, b = img.getpixel((px, py))
                        # Màu vàng / cam bút nhớ (R cao, G cao, B thấp) hoặc đỏ / hồng / xanh đậm đánh dấu
                        is_yellow_orange = (r > 185 and g > 140 and b < 110 and (r - b) > 95)
                        is_red_magenta = (r > 190 and g < 90 and b < 120 and (r - g) > 100)
                        is_blue_mark = (b > 180 and r < 100 and (b - r) > 90)
                        if is_yellow_orange or is_red_magenta or is_blue_mark:
                            marked_pixels += 1

                if (marked_pixels / box_total) > 0.015:
                    booked.append(seat)
                else:
                    avail.append(seat)

            result["booked_seats"] = booked
            result["available_seats"] = avail
            result["lower_available"] = [s for s in LOWER_DECK_SEATS if s in avail]
            result["upper_available"] = [s for s in UPPER_DECK_SEATS if s in avail]
            return result
    except Exception as e:
        print(f"⚠️ Lỗi phân tích ảnh sơ đồ ghế: {e}")
        return result

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
