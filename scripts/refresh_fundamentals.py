import os
import sys
import math
from datetime import datetime
from pathlib import Path
import io

import pandas as pd
import yfinance as yf
import requests

# Ensure project root is on sys.path, so 'config' and others are importable
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import settings
from data.database import init_db, get_session, Fundamentals

# ---------------------------------------------------------------------------
# NSE symbol universe (all EQ series) with local cache
# ---------------------------------------------------------------------------
NSE_SEC_LIST_URL = "https://nsearchives.nseindia.com/content/equities/sec_list.csv"
LOCAL_SEC_LIST = Path(__file__).resolve().parent.parent / "data" / "sec_list.csv"


def load_all_nse_symbols() -> list[str]:
    """
    Load all NSE symbols from official sec_list.csv.

    Strategy:
    - Try online download with proper headers + long timeout.
    - If it fails, fall back to cached local copy data/sec_list.csv (if present).
    """
    # Try online first
    try:
        print(f"[NSE] Downloading symbol list from {NSE_SEC_LIST_URL} ...")
        resp = requests.get(
            NSE_SEC_LIST_URL,
            timeout=60,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                ),
                "Accept": "text/csv,application/octet-stream;q=0.9,*/*;q=0.8",
            },
        )
        resp.raise_for_status()

        # Save a local cache so future runs can use it if NSE is down
        LOCAL_SEC_LIST.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_SEC_LIST, "w", encoding="utf-8", newline="") as f:
            f.write(resp.text)

        csv_text = resp.text
        print("[NSE] Download OK, cached to data/sec_list.csv")

    except Exception as e:
        print(f"[NSE] Online download failed: {e}")
        if not LOCAL_SEC_LIST.exists():
            raise FileNotFoundError(
                f"Could not download {NSE_SEC_LIST_URL} and "
                f"no local cache at {LOCAL_SEC_LIST}"
            )
        print(f"[NSE] Falling back to local cache: {LOCAL_SEC_LIST}")
        csv_text = LOCAL_SEC_LIST.read_text(encoding="utf-8")

    # Parse CSV (online or cached)
    df = pd.read_csv(io.StringIO(csv_text))
    df["Symbol"] = df["Symbol"].astype(str).str.upper()
    df["Series"] = df["Series"].astype(str).str.upper()

    # Main-board equities only for now (Series == 'EQ')
    eq = df[df["Series"] == "EQ"]

    symbols = sorted(eq["Symbol"].unique().tolist())
    print(f"[NSE] Loaded {len(symbols)} EQ symbols")
    return symbols


# ---------------------------------------------------------------------------
# Helpers: CAGR, FCFE, ROE, DCF
# ---------------------------------------------------------------------------
def safe_cagr(series: list[float]) -> float:
    """CAGR from first to last value in series (annualized)."""
    series = [float(x) for x in series if x is not None and x > 0]
    if len(series) < 2:
        return 0.0
    start = series[0]
    end = series[-1]
    n = len(series) - 1
    if start <= 0 or n <= 0:
        return 0.0
    return (end / start) ** (1 / n) - 1


def compute_fcfe_from_statements(t: yf.Ticker) -> tuple[float, float]:
    """
    Compute simple FCFE TTM and 3y average from Yahoo statements.

    FCFE ≈ CFO - Capex (simplified).[web:89][web:92]
    """
    try:
        cf = t.cashflow  # annual cash flow statement[web:82]
        if cf is None or cf.empty:
            return 0.0, 0.0

        # Yahoo columns: 'Total Cash From Operating Activities', 'Capital Expenditures'
        cfo = cf.loc["Total Cash From Operating Activities"].dropna()
        capex = cf.loc["Capital Expenditures"].dropna()

        # Align lengths
        n = min(len(cfo), len(capex))
        if n == 0:
            return 0.0, 0.0

        fcfe_series = (cfo.iloc[:n] + capex.iloc[:n]).astype(float)  # capex is usually negative
        fcfe_ttm = float(fcfe_series.iloc[0])
        fcfe_mean_3y = float(fcfe_series.head(3).mean())
        return fcfe_ttm, fcfe_mean_3y
    except Exception:
        return 0.0, 0.0


def compute_roe_from_statements(t: yf.Ticker) -> float:
    try:
        inc = t.financials  # annual income statement[web:82]
        bs = t.balance_sheet
        if inc is None or inc.empty or bs is None or bs.empty:
            return 0.0

        ni = inc.loc["Net Income"].dropna()
        eq = bs.loc["Total Stockholder Equity"].dropna()
        n = min(len(ni), len(eq))
        if n == 0:
            return 0.0

        roe_series = (ni.iloc[:n] / eq.iloc[:n]).astype(float)
        return float(roe_series.mean())
    except Exception:
        return 0.0


def dcf_fair_value_per_share(
    fcfe_base: float,
    shares_out: float,
    growth_cagr: float,
    roe: float,
    risk_free: float = 0.07,
    equity_premium: float = 0.06,
    beta: float | None = None,
    horizon_years: int = 10,
    terminal_growth: float = 0.04,
) -> float:
    """
    Simple FCFE DCF model:
    - Use fcfe_base (avg 3y) as year 0 cash flow.
    - Growth capped by both growth_cagr and a ceiling (e.g. 15%).[web:92][web:97]
    - Discount rate from CAPM if beta available, else conservative constant.
    """
    if fcfe_base <= 0 or shares_out <= 0:
        return 0.0

    # Conservative growth cap
    g = max(0.0, min(growth_cagr, 0.15))
    # Risk: if no beta, use a conservative constant
    if beta is not None and beta > 0:
        re = risk_free + beta * equity_premium
    else:
        re = max(risk_free + equity_premium, 0.14)

    if re <= terminal_growth + 0.01:
        re = terminal_growth + 0.01

    # Project FCFE and discount
    fcfe_years = []
    for t in range(1, horizon_years + 1):
        fcfe_t = fcfe_base * ((1 + g) ** t)
        disc = (1 + re) ** t
        fcfe_years.append(fcfe_t / disc)

    # Terminal value (Gordon)[web:94][web:97]
    fcfe_T = fcfe_base * ((1 + g) ** horizon_years)
    tv = (fcfe_T * (1 + terminal_growth)) / (re - terminal_growth)
    tv_disc = tv / ((1 + re) ** horizon_years)

    equity_value = sum(fcfe_years) + tv_disc
    fv_per_share = equity_value / shares_out
    return max(fv_per_share, 0.0)


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Main refresh function
# ---------------------------------------------------------------------------
def refresh_for_symbols(symbols: list[str]):
    mapping = {sym: f"{sym}.NS" for sym in symbols}
    tickers = yf.Tickers(" ".join(mapping.values()))  # batch call[web:82]

    now = datetime.utcnow()
    with get_session() as session:
        for sym, yticker in mapping.items():
            try:
                t = tickers.tickers[yticker]
            except KeyError:
                print(f"[YF] Missing ticker object for {yticker}")
                continue

            info = t.info or {}
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            market_cap = info.get("marketCap")

            trailing_pe_raw = info.get("trailingPE")
            pb_raw = info.get("priceToBook")
            ps_raw = info.get("priceToSalesTrailing12Months")
            beta = info.get("beta")

            if not price or not market_cap:
                print(f"[YF] {yticker}: missing price/market cap")
                continue

            price = float(price)
            market_cap = float(market_cap)

            trailing_pe = to_float(trailing_pe_raw)
            pb = to_float(pb_raw)
            ps = to_float(ps_raw)

            shares_out = market_cap / price if price > 0 else None

            # Revenue/EPS history for CAGR
            try:
                fin = t.financials
                rev = fin.loc["Total Revenue"].dropna().astype(float)
                ni = fin.loc["Net Income"].dropna().astype(float)
                rev_vals = list(rev.tail(5)[::-1])  # oldest -> latest
                ni_vals = list(ni.tail(5)[::-1])
                revenue_cagr_5y = safe_cagr(rev_vals)
                eps_cagr_5y = (
                    safe_cagr([n / shares_out for n in ni_vals])
                    if shares_out
                    else 0.0
                )
            except Exception:
                revenue_cagr_5y = 0.0
                eps_cagr_5y = 0.0

            # ROE and FCFE
            roe = compute_roe_from_statements(t)
            fcfe_ttm, fcfe_mean_3y = compute_fcfe_from_statements(t)

            # Basic multiples fair value heuristic:
            # Assume "normal" P/E ~ 15; if current P/E < 15 and earnings positive,
            # fair value from multiples = price * (15 / P/E). Otherwise, 0.
            fv_multiples = 0.0
            if trailing_pe is not None and 0 < trailing_pe < 30:
                target_pe = 15.0
                fv_multiples = price * min(target_pe / trailing_pe, 2.0)

            # DCF fair value
            growth_for_dcf = max(revenue_cagr_5y, eps_cagr_5y)
            fv_dcf = 0.0
            if fcfe_mean_3y > 0 and shares_out:
                fv_dcf = dcf_fair_value_per_share(
                    fcfe_base=fcfe_mean_3y,
                    shares_out=shares_out,
                    growth_cagr=growth_for_dcf,
                    roe=roe,
                    beta=beta,
                )

            # Composite fair value: conservative min of non-zero models
            candidates = [v for v in (fv_dcf, fv_multiples) if v and v > 0]
            fv_composite = min(candidates) if candidates else 0.0

            row = (
                session.query(Fundamentals)
                .filter(Fundamentals.symbol == sym)
                .one_or_none()
            )
            if row is None:
                row = Fundamentals(symbol=sym)
                session.add(row)

            row.yf_ticker = yticker
            row.updated_at = now

            row.current_price = price
            row.market_cap = market_cap

            row.pe = trailing_pe
            row.pb = pb
            row.ps = ps

            row.roe = float(roe) if roe else None
            row.revenue_cagr_5y = float(revenue_cagr_5y)
            row.eps_cagr_5y = float(eps_cagr_5y)
            row.fcfe_ttm = float(fcfe_ttm)
            row.debt_to_equity = None  # optional: derive later from balance sheet
            row.dividend_yield = (
                float(info.get("dividendYield"))
                if info.get("dividendYield")
                else None
            )

            row.fv_dcf = float(fv_dcf) if fv_dcf else None
            row.fv_multiples = float(fv_multiples) if fv_multiples else None
            row.fv_composite = float(fv_composite) if fv_composite else None

            print(
                f"[DB] {sym}: price={price:.2f}, fv_dcf={fv_dcf:.2f}, "
                f"fv_mult={fv_multiples:.2f}, fv_comp={fv_composite:.2f}"
            )


def main():
    init_db()
    symbols = load_all_nse_symbols()
    print(f"[YF] Refreshing fundamentals for {len(symbols)} NSE EQ symbols...")
    refresh_for_symbols(symbols)
    print("[YF] Done.")


if __name__ == "__main__":
    main()