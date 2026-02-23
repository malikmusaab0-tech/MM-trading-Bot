@echo off
cd /d "%~dp0.."
call venv\Scripts\activate
python scripts\auto_authenticate.py
pause
