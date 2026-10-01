@echo off
chcp 65001 > nul
title EasyTrip - Tu dong dong bo Hop Dong hang ngay (23:00)
cd /d "%~dp0..\.."

if not exist "logs" mkdir "logs"

set "PY=.\venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo [%date% %time%] Bat dau chay dong bo hop dong... >> logs\contract_sync.log
"%PY%" scripts\contracts\daily_contract_sync.py >> logs\contract_sync.log 2>&1
echo [%date% %time%] Hoan tat chay dong bo hop dong. >> logs\contract_sync.log
