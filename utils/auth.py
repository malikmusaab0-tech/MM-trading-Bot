import json
from pathlib import Path
from dhanhq import dhanhq
from config import settings

TOKEN_PATH = settings.BASE_DIR / "token.json"


def get_dhan_client(access_token: str | None = None) -> dhanhq:
    """Returns an authenticated DhanHQ client instance."""
    from utils.rate_limiter import retry_with_backoff
    from dhanhq import DhanContext
    client_id = settings.DHAN_CLIENT_ID
    # Use provided access token or fallback to settings
    token = access_token if access_token else settings.DHAN_ACCESS_TOKEN

    ctx = DhanContext(client_id=client_id, access_token=token)
    dhan = dhanhq(ctx)

    # Wrap dhan API calls that are prone to rate limits with retry backoff logic
    if hasattr(dhan, 'get_positions'):
        original_get_positions = dhan.get_positions
        dhan.get_positions = retry_with_backoff(retries=3)(original_get_positions)

    if hasattr(dhan, 'get_order_list'):
        original_get_order_list = dhan.get_order_list
        dhan.get_order_list = retry_with_backoff(retries=3)(original_get_order_list)

    if hasattr(dhan, 'place_order'):
        original_place_order = dhan.place_order
        dhan.place_order = retry_with_backoff(retries=3)(original_place_order)

    return dhan


def load_access_token() -> str | None:
    """Load access token from file, or settings if not found."""
    if TOKEN_PATH.exists():
        try:
            data = json.loads(TOKEN_PATH.read_text())
            return data.get("access_token", settings.DHAN_ACCESS_TOKEN)
        except Exception:
            pass
    return settings.DHAN_ACCESS_TOKEN


def save_access_token(access_token: str):
    TOKEN_PATH.write_text(json.dumps({"access_token": access_token}, indent=2))

