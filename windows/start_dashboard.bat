@echo off
cd /d "%~dp0.."
call venv\Scripts\activate
python ui\flask_dashboard.py
pause
