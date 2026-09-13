@echo off
chcp 65001 > nul
title Xuất Hợp Đồng & Bảng Kê Đối Soát (01/08 - 24/08/2026) - EasyTrip
cd /d "%~dp0"

echo ========================================================
echo   TRÌNH TẠO HỢP ĐỒNG (DOCX/PDF) & ĐỐI SOÁT TỰ ĐỘNG
echo   Kỳ hạch toán: 01/08/2026 - 24/08/2026
echo ========================================================
echo.

set "PY=.\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" batch_generate_by_accounting_date.py

echo.
echo ========================================================
echo   🎉 HOÀN TẤT XUẤT HỢP ĐỒNG VÀ ĐỐI SOÁT!
echo ========================================================
pause
