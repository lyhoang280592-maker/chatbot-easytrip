@echo off
chcp 65001 > nul
title Easy Trip AI Chatbot - Interactive Tester
cd /d "c:\Projects\chatbot-easytrip"

echo ========================================================
echo   KHOI DONG TRINH TEST AI CHATBOT EASY TRIP ^& VISA
echo ========================================================
echo.

if exist ".\venv\Scripts\python.exe" (
    ".\venv\Scripts\python.exe" interactive_test.py
) else (
    python interactive_test.py
)

pause
