@echo off
REM ============================================================
REM  recording-pipeline 원클릭 시작
REM  더블클릭하면: go2rtc(영상) + 백엔드(녹화제어) 실행 후 브라우저 자동 열기
REM ============================================================
cd /d "%~dp0"

echo [1/3] go2rtc(영상 서버) 시작...
start "go2rtc" /min go2rtc.exe -config go2rtc.yaml

echo [2/3] 백엔드(녹화 제어) 시작...
start "backend" /min python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

echo [3/3] 서버 뜰 때까지 5초 대기 후 브라우저 열기...
timeout /t 5 /nobreak >nul
start "" http://127.0.0.1:8000/

echo.
echo === 실행 완료 ===
echo  - 영상/녹화 화면:  http://127.0.0.1:8000/
echo  - go2rtc 대시보드: http://127.0.0.1:1984/
echo  이 창은 닫아도 됩니다. 서버는 각자 최소화된 창에서 계속 돕니다.
echo  (종료하려면 stop.bat 실행)
pause
