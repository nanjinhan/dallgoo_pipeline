@echo off
REM Windows Task Scheduler 가 실행하는 래퍼. 프로젝트 루트에서 모듈 실행.
cd /d "%~dp0.."
python -m scheduler.run_transfer >> "logs\scheduler.out" 2>&1
