"""
Execute approved long-term ideas using PaperTradingEngine.

- Processes only ideas where approved=True and executed=False
- Runs in order of multibagger_score DESC (prioritize high-upside ideas)
"""

from datetime import datetime

from config import settings
from data.database import get_session, LongTermIdea, Position
from utils.paper_trading import PaperTradingEngine
from utils.auth import get_kite_client, load_access_token


def get_open_lt_exposure(engine: PaperTradingEngine):
    """
    Optional: you can compute LT-specific exposure here later.
    For now, just return engine.cash to let PositionSizer do its job.
    """
    return engine.cash


def main():
    # Kite client only needed if your PaperTradingEngine depends on it; else skip.
    access_token = load_access_token()
    if not access_token:
        print("No access_token. Run scripts/auto_authenticate.py first.")
        return

    kite = get_kite_client(access_token)
    engine = PaperTradingEngine()

    with get_session() as session:
        ideas = (
            session.query(LongTermIdea)
            .filter(
                LongTermIdea.approved == True,   # noqa: E712
                LongTermIdea.executed == False,  # noqa: E712
            )
            .order_by(LongTermIdea.multibagger_score.desc())
            .all()
        )

        if not ideas:
            print("No approved long-term ideas to execute.")
            return

        print(f"Executing {len(ideas)} approved ideas...")
        for idea in ideas:
            sym = idea.symbol
            qty = idea.qty
            action = idea.action.upper()
            price = idea.entry_price

            print(
                f"[EXEC] Idea #{idea.id}: {action} {sym} x{qty} @ ~₹{price:.2f} "
                f"(target ₹{idea.target_price:.2f})"
            )

            # You can plug in more LT capital checks here if needed.
            trade = None
            if action == "BUY":
                trade = engine.buy(
                    symbol=sym,
                    quantity=qty,
                    price=price,
                    segment=settings.SEGMENT_LONGTERM,
                )
            elif action == "SELL":
                trade = engine.sell(
                    symbol=sym,
                    quantity=qty,
                    price=price,
                    segment=settings.SEGMENT_LONGTERM,
                )

            if trade is None:
                print(f"[EXEC] Idea #{idea.id}: blocked by risk/margin engine")
                continue

            idea.executed = True
            print(
                f"[EXEC] Idea #{idea.id} executed. "
                f"P&L so far: {trade.pnl if hasattr(trade, 'pnl') else 0.0:.2f}"
            )


if __name__ == "__main__":
    main()