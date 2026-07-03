@echo off
REM ============================================================
REM  recording-pipeline stop
REM  Kills go2rtc + backend (uvicorn/python on port 8000).
REM ============================================================
chcp 65001 >nul

echo stopping go2rtc...
taskkill /IM go2rtc.exe /F >nul 2>&1

echo stopping backend (python on port 8000)...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1

echo === stopped ===
pause
