@echo off
REM ============================================================
REM  recording-pipeline 종료
REM  go2rtc + 백엔드(uvicorn/python) 프로세스를 모두 끈다.
REM ============================================================
echo go2rtc 종료...
taskkill /IM go2rtc.exe /F >nul 2>&1

echo 백엔드(python/uvicorn) 종료...
REM 8000 포트를 쓰는 python 프로세스만 골라 종료
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr LISTENING') do taskkill /PID %%p /F >nul 2>&1

echo === 종료 완료 ===
pause
