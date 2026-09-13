import unittest
from datetime import datetime, timedelta
from telegram_router import format_bus_booking_notification
from pydantic import BaseModel
from typing import Optional

class BookingInfoMock(BaseModel):
    ho_ten: Optional[str] = None
    nam_sinh: Optional[str] = None
    quoc_tich: Optional[str] = None
    so_dien_thoai: Optional[str] = None
    ngay_khoi_hanh: Optional[str] = None
    ghe_chon: Optional[str] = None
    diem_don: Optional[str] = None
    loai_visa: Optional[str] = None
    tuyen_duong: Optional[str] = None
    goi_dich_vu: Optional[str] = None

class TestBookingNotificationFormat(unittest.TestCase):
    def test_user_exact_example(self):
        data = BookingInfoMock(
            ho_ten="TSARENKO EKATERINA, RODICHEV DMITRY",
            ghe_chon="A2, B1",
            diem_don="40 Hon Chong",
            loai_visa="90D Laos",
            tuyen_duong="Laos",
            ngay_khoi_hanh="13/09",
            quoc_tich="Россия",
            so_dien_thoai=""
        )
        msg = format_bus_booking_notification(data, ngay_di="13/09", service_type="90D")
        
        expected = (
            "13/09-90D- Laos\n"
            "TSARENKO EKATERINA\n"
            "A2\n"
            "RODICHEV DMITRY\n"
            "B1\n"
            "40 Hon Chong - 9:30PM\n"
            "📍https://maps.app.goo.gl/LmwZhraVzHBuxoTm9\n\n"
            "Single\n"
            "E-visa 4 hour x 2 person\n"
            "14/09 - 8:00: Exit Bo Y\n"
            "14/09 - 11:30: Entry Bo Y"
        )
        self.assertEqual(msg, expected)

    def test_cambodia_single_person(self):
        data = BookingInfoMock(
            ho_ten="JOHN DOE",
            ghe_chon="B5",
            diem_don="04 Tran Phu",
            loai_visa="90D Cambodia",
            tuyen_duong="Cambodia",
            ngay_khoi_hanh="20/09"
        )
        msg = format_bus_booking_notification(data, ngay_di="20/09", service_type="Cambodia")
        
        expected = (
            "20/09-90D- Cambodia\n"
            "JOHN DOE\n"
            "B5\n"
            "04 Tran Phu - Muong Thanh - 9:15PM\n"
            "📍https://maps.app.goo.gl/hPNMWxUAmm4VcgWK9\n\n"
            "Single\n"
            "E-visa 4 hour x 1 person\n"
            "21/09 - 8:00: Exit Moc Bai\n"
            "21/09 - 11:30: Entry Moc Bai"
        )
        self.assertEqual(msg, expected)

    def test_laos_45d(self):
        data = BookingInfoMock(
            ho_ten="ANNA KARENINA",
            ghe_chon="A1",
            diem_don="New Bo Ke Bo Cat",
            loai_visa="45D Laos",
            tuyen_duong="Laos",
            ngay_khoi_hanh="15/09"
        )
        msg = format_bus_booking_notification(data, ngay_di="15/09", service_type="45D")
        
        expected = (
            "15/09-45D- Laos\n"
            "ANNA KARENINA\n"
            "A1\n"
            "New Bo Ke Bo Cat - 9:30PM\n"
            "📍https://maps.app.goo.gl/Kc6dm92VVAF1j13j9\n\n"
            "Single\n"
            "45D Visa Free x 1 person\n"
            "16/09 - 8:00: Exit Bo Y\n"
            "16/09 - 11:30: Entry Bo Y"
        )
        self.assertEqual(msg, expected)

if __name__ == "__main__":
    unittest.main()
