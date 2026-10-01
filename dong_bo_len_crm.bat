@echo off
chcp 65001 > nul
title Đẩy Tri Thức Lên CRM Lark Base - Easy Trip
cd /d "%~dp0"

echo ========================================================
echo   ĐANG ĐẨY TOÀN BỘ TRI THỨC Q&A TỪ MÁY LÊN CRM LARK BASE
echo ========================================================
echo.

if exist ".\venv\Scripts\python.exe" (
    ".\venv\Scripts\python.exe" sync_knowledge_crm.py push
) else (
    python sync_knowledge_crm.py push
)

echo.
echo ========================================================
echo   HOÀN TẤT ĐỒNG BỘ!
echo ========================================================
pause
