import os
import sys
from seat_map_generator import generate_seat_map

VALID_SEATS = [
    "A1", "B1", "A3", "B3", "A5", "B5", "A7", "B7", "A9", "B9",
    "A2", "B2", "A4", "B4", "A6", "B6", "A8", "B8", "A10", "B10", "A12"
]

# Giả sử Ngọc Cao nhắn: "A1, B2, B3, A5" là các ghế còn trống
empty_seats = ["A1", "B2", "B3", "A5"]

# Ghế đã đặt = 21 ghế - ghế trống
booked_seats = [s for s in VALID_SEATS if s not in empty_seats]

print(f"Tổng số ghế khả dụng: {len(VALID_SEATS)}")
print(f"Ghế trống: {empty_seats}")
print(f"Ghế cần gạch chéo (đã đặt): {booked_seats}")

output_file = "test_seat_map_output.jpg"
out_path = generate_seat_map(booked_seats, output_path=output_file)

if os.path.exists(out_path):
    print(f"✅ Tạo ảnh sơ đồ thành công! Ảnh được lưu tại: {out_path}")
else:
    print("❌ Lỗi: Không tìm thấy ảnh sơ đồ đầu ra.")
