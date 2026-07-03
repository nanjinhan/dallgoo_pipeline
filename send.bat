@echo off
REM ============================================================
REM  NAS transfer (manual). Double-click to send all pending sessions.
REM  Requires: OpenVPN Connect must be connected first.
REM  Flow: check VPN -> compress -> SFTP upload -> checksum -> move to sent
REM  (ASCII only on purpose: Korean text breaks .bat on double-click / cp949)
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   NAS transfer start (VPN must be connected)
echo ============================================
echo.

python -m scheduler.run_transfer

echo.
echo ============================================
echo   Done. Sent sessions moved to recordings\sent\
echo   (this window closes automatically in 5s)
echo ============================================
REM wait ~5s without needing a keypress (ping works in any context)
ping -n 6 127.0.0.1 >nul
