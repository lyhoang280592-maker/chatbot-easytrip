import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

# Thêm đường dẫn hiện tại vào sys.path để import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram_router import (
    parse_topic_name,
    get_customer_service_type,
    get_or_create_seat_map,
    normalize_date,
    validate_and_adjust_departure
)

class TestCompoundBookingLogic(unittest.TestCase):

    def test_parse_topic_name(self):
        cases = [
            ("20/05 - 45D laos", ("20/05", "45D")),
            ("20/05 Cambodia", ("20/05", "Cambodia")),
            ("20/05 - 90D laos", ("20/05", "90D")),
            ("20-05 Cambodia", ("20/05", "Cambodia")),
            ("20.05 campuchia", ("20/05", "Cambodia")),
            ("Mộc Bài 20/05", ("20/05", "Cambodia")),
            ("laos 45d 20/5", ("20/05", "45D")),
            ("05/12 - 90D", ("05/12", "90D")),
        ]
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(parse_topic_name(name), expected)

    def test_get_customer_service_type(self):
        class MockData:
            def __init__(self, loai_visa):
                self.loai_visa = loai_visa

        cases = [
            (MockData("45 ngày"), "đi lào", "45D"),
            (MockData("90 ngày"), "visa 90d", "90D"),
            (MockData(""), "Tôi muốn đi campuchia", "Cambodia"),
            (MockData("45"), "chạy mộc bài", "Cambodia"),
            (MockData("90D"), "laos", "90D"),
            (MockData(None), "lào 45 ngày", "45D"),
        ]
        for data, history, expected in cases:
            with self.subTest(history=history):
                self.assertEqual(get_customer_service_type(data, history), expected)

    def test_normalize_date(self):
        self.assertEqual(normalize_date("20/5"), "20/05")
        self.assertEqual(normalize_date("20-5"), "20/05")
        self.assertEqual(normalize_date("2026-05-20"), "20/05")

    def test_validate_and_adjust_departure(self):
        # 1. Laos 45D (Daily): Should accept any date <= expiry - 1
        res = validate_and_adjust_departure("", "28/05/2026", "45 ngày", "laos")
        self.assertEqual(res, "27/05")

        # 2. Laos 90D (Tue, Thu, Sun): Expiry 29/05/2026 (Friday).
        # latest possible is 28/05/2026 (Thursday), which is a running day.
        res = validate_and_adjust_departure("", "29/05/2026", "90 ngày", "laos")
        self.assertEqual(res, "28/05")

        # 3. Laos 90D: Expiry 30/05/2026 (Saturday).
        # latest possible is 29/05/2026 (Friday), which is NOT a running day.
        # Nearest valid running day on or before Friday is Thursday (28/05/2026).
        res = validate_and_adjust_departure("", "30/05/2026", "90 ngày", "laos")
        self.assertEqual(res, "28/05")

        # 4. If customer requested a non-running day (e.g., Wednesday 27/05/2026 for Cambodia),
        # it should automatically adjust to Tuesday (26/05).
        res = validate_and_adjust_departure("27/05/2026", "30/05/2026", "90 ngày", "cambodia")
        self.assertEqual(res, "26/05")


class TestSeatMapGeneration(unittest.IsolatedAsyncioTestCase):

    @patch("lark_api.get_all_orders", new_callable=AsyncMock)
    async def test_get_or_create_seat_map_dynamic(self, mock_get_all_orders):
        # Thiết lập dữ liệu đơn hàng giả lập trong Lark Base
        mock_get_all_orders.return_value = [
            {
                "Departure Date": "20/05",
                "Status": "PAID",
                "Route": "45-day Visa Free (Laos)",
                "Seat": "A1, B1"
            },
            {
                "Departure Date": "20/05",
                "Status": "PAID",
                "Route": "Cambodia Mộc Bài",
                "Seat": "A3, B3"
            },
            {
                "Departure Date": "20/05",
                "Status": "CANCELLED",
                "Route": "Cambodia Mộc Bài",
                "Seat": "A4"
            }
        ]

        # Xóa các file cũ nếu có để kiểm tra
        file_45d = "static/map_20_05_45D.jpg"
        file_cambodia = "static/map_20_05_Cambodia.jpg"
        for f in [file_45d, file_cambodia]:
            if os.path.exists(f):
                os.remove(f)

        # 1. Gọi khi chưa có sơ đồ chính thức trên đĩa -> tự động tạo sơ đồ trống
        res_45d = await get_or_create_seat_map("20/05", "45D")
        self.assertIsNotNone(res_45d)

        # 2. Giả lập đối tác đã tải lên sơ đồ bằng cách tạo file trống trên đĩa
        os.makedirs(os.path.dirname(file_45d), exist_ok=True)
        with open(file_45d, "w") as f:
            f.write("mock content")

        # Gọi lại get_or_create_seat_map -> phải trả về thông tin sơ đồ
        res_45d_after = await get_or_create_seat_map("20/05", "45D")
        self.assertIsNotNone(res_45d_after)
        self.assertEqual(res_45d_after["url"], f"/static/map_20_05_45D.jpg")

        # Dọn dẹp
        for f in [file_45d, file_cambodia]:
            if os.path.exists(f):
                os.remove(f)


if __name__ == "__main__":
    unittest.main()
