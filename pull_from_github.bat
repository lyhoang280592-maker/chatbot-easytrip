@echo off
chcp 65001 > nul
title Dong bo Code tu GitHub - Easy Trip
cd /d "c:\Projects\chatbot-easytrip"

echo ========================================================
echo   ĐỒNG BỘ (PULL) CODE MỚI NHẤT TỪ GITHUB VỀ MÁY
echo   Repo: https://github.com/lyhoang280592-maker/chatbot-easytrip
echo ========================================================
echo.

setlocal enabledelayedexpansion
set "GIT_CMD=C:\Users\AD\AppData\Local\Programs\MinGit\cmd\git.exe"
if not exist "%GIT_CMD%" set "GIT_CMD=git"

echo ⏳ Đang kiểm tra và kéo code mới nhất từ GitHub...
"%GIT_CMD%" pull origin main

if !ERRORLEVEL! EQU 0 (
    echo.
    echo ========================================================
    echo   🎉 ĐỒNG BỘ CODE TỪ GITHUB VỀ MÁY THÀNH CÔNG RỰC RỠ!
    echo ========================================================
) else (
    echo.
    echo ❌ Có lỗi xảy ra trong quá trình đồng bộ từ GitHub.
    echo Vui lòng kiểm tra lại kết nối mạng hoặc trạng thái Git.
)

echo.
pause
