@echo off
chcp 65001 > nul
title Tải Tri Thức Từ CRM Lark Base - Easy Trip
cd /d "%~dp0"

echo ========================================================
echo   ĐANG TẢI TOÀN BỘ TRI THỨC Q&A TỪ CRM LARK BASE VỀ MÁY NÀY
echo ========================================================
echo.

if exist ".\venv\Scripts\python.exe" (
    ".\venv\Scripts\python.exe" sync_knowledge_crm.py pull
) else (
    python sync_knowledge_crm.py pull
)

echo.
echo ========================================================
echo   HOÀN TẤT! BOT ĐÃ ĐƯỢC CẬP NHẬT ĐẦY ĐỦ TRI THỨC MỚI NHẤT!
echo ========================================================
pause
