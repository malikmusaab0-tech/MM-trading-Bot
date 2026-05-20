import requests
from config import settings


class NotificationService:
    def __init__(self):
        self.telegram_enabled = bool(settings.TELEGRAM_ENABLED)
        self.telegram_token = settings.TELEGRAM_BOT_TOKEN or ""
        self.telegram_chat_id = settings.TELEGRAM_CHAT_ID or ""

    # ---------- Low-level Telegram ----------

    def _send_telegram_message(self, text: str) -> None:
        if not (
            self.telegram_enabled
            and self.telegram_token
            and self.telegram_chat_id
        ):
            print("[NOTIFY] Telegram disabled or missing token/chat_id")
            return

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        try:
            resp = requests.post(url, json=payload, timeout=5)
            if not resp.ok:
                print(f"[NOTIFY FAILED] HTTP {resp.status_code}: {resp.text}")
        except requests.exceptions.Timeout:
            print("[NOTIFY FAILED] Telegram API connection timed out.")
        except Exception as e:
            print(f"[NOTIFY FAILED] Unexpected error: {e}")

    # ---------- Generic text ----------

    def send_text(self, text: str) -> None:
        """
        Generic Telegram text sender (for startup pings, errors, etc.).
        """
        self._send_telegram_message(text)

    # ---------- Swing alerts ----------

    def send_swing_trade_alert(
        self,
        *,
        segment: str,
        symbol: str,
        side: str,
        qty: int,
        entry: float,
        stop_loss: float,
        target: float,
        timeframe: str,
        risk_value: float,
        risk_pct: float,
        profit_value: float,
        profit_pct: float,
    ) -> None:
        if not settings.SWING_NOTIFICATIONS_ENABLED:
            return

        msg_lines = [
            f"*Swing Trade Alert* ({segment})",
            "",
            f"*Symbol:* {symbol}",
            f"*Side:* {side}",
            f"*Quantity:* {qty}",
            "",
            f"*Entry:* ₹{entry:,.2f}",
            f"*Stop-loss:* ₹{stop_loss:,.2f}",
            f"*Target:* ₹{target:,.2f}",
            "",
            f"*Risk:* ₹{risk_value:,.2f} ({risk_pct:+.2f}%)",
            f"*Expected Profit:* ₹{profit_value:,.2f} ({profit_pct:+.2f}%)",
            f"*Timeframe:* {timeframe}",
        ]
        text = "\n".join(msg_lines)
        self._send_telegram_message(text)

    # ---------- Long-term alerts ----------

    def send_longterm_trade_alert(
        self,
        *,
        symbol: str,
        action: str,
        qty: int,
        entry: float,
        fair_value: float,
        timeframe: str,
        margin_of_safety_pct: float,
        risk_value: float,
        risk_pct: float,
        profit_value: float,
        profit_pct: float,
    ) -> None:
        if not settings.LONGTERM_NOTIFICATIONS_ENABLED:
            return

        msg_lines = [
            "*Long-Term Trade Alert* (LONGTERM)",
            "",
            f"*Symbol:* {symbol}",
            f"*Action:* {action}",
            f"*Quantity:* {qty}",
            "",
            f"*Entry:* ₹{entry:,.2f}",
            f"*Fair Value:* ₹{fair_value:,.2f}",
            f"*Margin of Safety:* {margin_of_safety_pct:+.1f}%",
            "",
            f"*Risk (budget):* ₹{risk_value:,.2f} ({risk_pct:+.2f}%)",
            f"*Expected Profit (to FV):* ₹{profit_value:,.2f} ({profit_pct:+.2f}%)",
            f"*Timeframe:* {timeframe}",
        ]
        text = "\n".join(msg_lines)
        self._send_telegram_message(text)