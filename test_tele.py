import os
from pathlib import Path

from dotenv import load_dotenv
import requests

print("CWD:", os.getcwd())
print(".env exists here?:", Path(".env").exists())

# Try loading .env from current directory
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

print("TOKEN prefix:", (TOKEN or "")[:10])
print("CHAT_ID:", CHAT_ID)

if not TOKEN or not CHAT_ID:
    print("Missing TOKEN or CHAT_ID from env")
    raise SystemExit(1)

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "text": "PRIMA test: if you see this, Telegram wiring is OK.",
}

resp = requests.post(url, json=payload, timeout=5)
print("Status:", resp.status_code)
print("Body:", resp.text)