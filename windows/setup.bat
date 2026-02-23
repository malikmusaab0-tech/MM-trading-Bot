@echo off
cd /d "%~dp0.."
echo Creating virtual environment...
python -m venv venv
call venv\Scripts\activate
echo Installing requirements...
pip install --upgrade pip
pip install -r requirements.txt
echo Setup complete.
pause
