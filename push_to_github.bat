@echo off
chcp 65001 > nul
title Push Code to GitHub - Easy Trip
cd /d "c:\Projects\chatbot-easytrip"

echo ========================================================
echo   DANG DAY TOAN BO CODE LEN GITHUB
echo   Repo: https://github.com/lyhoang280592-maker/chatbot-easytrip
echo ========================================================
echo.

set "GIT_CMD=C:\Users\AD\AppData\Local\Programs\MinGit\cmd\git.exe"

if not exist "%GIT_CMD%" (
    set "GIT_CMD=git"
)

"%GIT_CMD%" remote set-url origin https://github.com/lyhoang280592-maker/chatbot-easytrip.git 2>nul || "%GIT_CMD%" remote add origin https://github.com/lyhoang280592-maker/chatbot-easytrip.git

echo Dang thuc hien git push...
echo (Neu co popup trinh duyet hien ra, ban chi can nhan 'Sign in with your browser' de xac thuc 1 lan duy nhat)
echo.

"%GIT_CMD%" push -u origin main

echo.
echo ========================================================
echo   DA HOAN TAT!
echo ========================================================
pause
