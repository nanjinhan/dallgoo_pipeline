@echo off
REM ============================================================
REM  recording-pipeline one-click start
REM  Double-click to run go2rtc + backend, then open the browser.
REM  (ASCII only: Korean text breaks .bat on double-click / cp949)
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo [1/3] starting go2rtc (video server)...
start "go2rtc" /min go2rtc.exe -config go2rtc.yaml

echo [2/3] starting backend (recording control)...
start "backend" /min python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

echo [3/3] waiting 5s then opening browser...
timeout /t 5 /nobreak >nul
start "" http://127.0.0.1:8000/

echo.
echo === started ===
echo   recording page:   http://127.0.0.1:8000/
echo   go2rtc dashboard: http://127.0.0.1:1984/
echo   You can close this window. Servers keep running (minimized).
echo   To stop everything: run stop.bat
pause
