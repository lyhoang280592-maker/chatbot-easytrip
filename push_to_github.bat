@echo off
chcp 65001 > nul
title Push Code to GitHub - Easy Trip
cd /d "c:\Projects\chatbot-easytrip"

echo ========================================================
echo   ĐẨY TOÀN BỘ CODE VÀ TRI THỨC LÊN GITHUB
echo   Repo: https://github.com/lyhoang280592-maker/chatbot-easytrip
echo ========================================================
echo.

setlocal enabledelayedexpansion
set "GIT_CMD=C:\Users\AD\AppData\Local\Programs\MinGit\cmd\git.exe"
if not exist "%GIT_CMD%" set "GIT_CMD=git"

"%GIT_CMD%" remote set-url origin https://github.com/lyhoang280592-maker/chatbot-easytrip.git 2>nul || "%GIT_CMD%" remote add origin https://github.com/lyhoang280592-maker/chatbot-easytrip.git

echo Đang tự động lưu các thay đổi mới...
"%GIT_CMD%" add .
"%GIT_CMD%" commit -m "update code and training materials" 2>nul

echo Đang thử đẩy code lên GitHub...
"%GIT_CMD%" push -u origin main
if !ERRORLEVEL! EQU 0 (
    echo.
    echo ========================================================
    echo   🎉 ĐẨY CODE LÊN GITHUB THÀNH CÔNG RỰC RỠ!
    echo ========================================================
    goto :end
)

echo.
echo ⚠️ GITHUB YÊU CẦU XÁC THỰC TOKEN:
echo --------------------------------------------------------
echo 1. Truy cập: https://github.com/settings/tokens/new
echo 2. Đặt tên Token (ví dụ: my-token), tích chọn ô 'repo'
echo 3. Bấm 'Generate token' ở cuối trang và copy mã (dạng ghp_xxxx...)
echo --------------------------------------------------------
echo.
set /p GH_TOKEN="👉 Dán mã Token GitHub của bạn vào đây rồi nhấn Enter: "

if not "!GH_TOKEN!"=="" (
    echo Đang đẩy lại với Token...
    "%GIT_CMD%" push https://!GH_TOKEN!@github.com/lyhoang280592-maker/chatbot-easytrip.git main
    if !ERRORLEVEL! EQU 0 (
        echo.
        echo ========================================================
        echo   🎉 ĐẨY CODE LÊN GITHUB THÀNH CÔNG RỰC RỠ!
        echo ========================================================
    ) else (
        echo.
        echo ❌ Đẩy thất bại. Vui lòng kiểm tra lại Token hoặc quyền truy cập.
    )
)

:end
echo.
pause
