@echo off
REM Wrapper run by Windows Task Scheduler. Runs the module from project root.
REM (ASCII only: Korean text breaks .bat on double-click / cp949)
chcp 65001 >nul
cd /d "%~dp0.."
python -m scheduler.run_transfer >> "logs\scheduler.out" 2>&1
