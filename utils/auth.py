import json
from pathlib import Path
from kiteconnect import KiteConnect
from config import settings

TOKEN_PATH = settings.BASE_DIR / "token.json"


def get_kite_client(access_token: str | None = None) -> KiteConnect:
    kite = KiteConnect(api_key=settings.KITE_API_KEY)
    if access_token:
        kite.set_access_token(access_token)
    return kite


def load_access_token() -> str | None:
    if TOKEN_PATH.exists():
        data = json.loads(TOKEN_PATH.read_text())
        return data.get("access_token")
    return None


def save_access_token(access_token: str):
    TOKEN_PATH.write_text(json.dumps({"access_token": access_token}, indent=2))


def generate_access_token_from_request_token(request_token: str) -> str:
    kite = KiteConnect(api_key=settings.KITE_API_KEY)
    data = kite.generate_session(request_token, api_secret=settings.KITE_API_SECRET)
    access_token = data["access_token"]
    save_access_token(access_token)
    return access_token
