@echo off
chcp 65001 > nul
title Cập Nhật & Huấn Luyện Dữ Liệu Mới - Easy Trip AI Chatbot
cd /d "%~dp0"

echo ========================================================
echo   TRÌNH TỰ ĐỘNG CẬP NHẬT & HUẤN LUYỆN DỮ LIỆU MỚI
echo ========================================================
echo.
echo Bạn muốn cập nhật dữ liệu từ nguồn nào?
echo   [1] Cập nhật toàn bộ tin nhắn mới từ TELEGRAM
echo   [2] Cập nhật toàn bộ tin nhắn mới từ FACEBOOK (META)
echo   [3] Cập nhật nội dung mới từ file ZALO (zalo_chat.docx)
echo   [4] Tải tri thức mới nhất từ CRM Lark Base về máy
echo   [5] Quét TẤT CẢ các nguồn và đồng bộ lên CRM Lark Base
echo   [0] Thoát
echo --------------------------------------------------------
set /p opt="👉 Nhập lựa chọn (1/2/3/4/5): "

set "PY=.\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if "%opt%"=="1" (
    echo.
    echo 🚀 [1/2] Đang quét tin nhắn mới từ Telegram...
    "%PY%" export_telegram_dialogs.py
    echo 🧠 [2/2] Đang dùng AI trích xuất Q&A từ Telegram...
    "%PY%" analyze_chat_history.py
    echo ☁️ Đang đồng bộ lên CRM...
    "%PY%" sync_knowledge_crm.py push
)

if "%opt%"=="2" (
    echo.
    echo 🚀 [1/2] Đang quét tin nhắn mới từ Meta Graph API...
    "%PY%" export_meta_chats.py
    echo 🧠 [2/2] Đang dùng AI trích xuất Q&A từ Facebook...
    "%PY%" analyze_meta_history.py
    echo ☁️ Đang đồng bộ lên CRM...
    "%PY%" sync_knowledge_crm.py push
)

if "%opt%"=="3" (
    echo.
    echo 🧠 Đang dùng AI trích xuất Q&A từ file zalo_chat.docx...
    "%PY%" analyze_zalo_docx.py
    echo ☁️ Đang đồng bộ lên CRM...
    "%PY%" sync_knowledge_crm.py push
)

if "%opt%"=="4" (
    echo.
    echo 📥 Đang tải toàn bộ tri thức mới nhất từ CRM Lark Base về máy...
    "%PY%" sync_knowledge_crm.py pull
)

if "%opt%"=="5" (
    echo.
    echo 🚀 Bắt đầu quét và đồng bộ TẤT CẢ các kênh...
    "%PY%" export_telegram_dialogs.py
    "%PY%" analyze_chat_history.py
    "%PY%" export_meta_chats.py
    "%PY%" analyze_meta_history.py
    "%PY%" analyze_zalo_docx.py
    "%PY%" sync_knowledge_crm.py push
)

echo.
echo ========================================================
echo   🎉 HOÀN TẤT CẬP NHẬT & HUẤN LUYỆN DỮ LIỆU!
echo ========================================================
pause
