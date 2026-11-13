"""Batch Yahoo Finance snapshot during regular NYSE trading hours only."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf

GROUPS = {
    "Technology": "CBRS AAPL NVDA MSFT GOOG META AVGO AMD MU MRVL ASML TSM SNDK ADBE ORCL DRAM SKHY SPCX AMZN TSLA",
    "Other": "COST WMT BRK.B SOFI FIG UNH OHI PSA CALY",
    "ETFs": "SPY VOO SPHD SLV SPX",
}
ALIASES = {"BRK.B": "BRK-B", "SPX": "^GSPC"}
SYMBOLS = list(dict.fromkeys(s for group in GROUPS.values() for s in group.split()))
REVERSE = {ALIASES.get(s, s): s for s in SYMBOLS}
NOW = datetime.now(timezone.utc)
calendar = mcal.get_calendar("NYSE")
session = calendar.schedule(start_date=NOW.date(), end_date=NOW.date())
if session.empty or not (session.iloc[0]["market_open"] <= pd.Timestamp(NOW) <= session.iloc[0]["market_close"]):
    print("Outside regular NYSE hours or market holiday: no fetch.")
    raise SystemExit(0)

existing_path = Path("quotes.json")
try:
    existing = json.loads(existing_path.read_text()) if existing_path.exists() else {}
except (OSError, ValueError):
    existing = {}
quotes = existing.get("quotes", {})
tickers = list(REVERSE)
print(f"Batch fetching {len(tickers)} instruments")
try:
    daily = yf.download(tickers, period="7d", interval="1d", auto_adjust=False, progress=False, threads=True, group_by="ticker")
    minute = yf.download(tickers, period="1d", interval="1m", auto_adjust=False, progress=False, threads=True, group_by="ticker")
except Exception as exc:
    print("Batch fetch failed:", exc)
    raise SystemExit(1)

updated = 0
local_date = NOW.astimezone(ZoneInfo("America/New_York")).date()
for ticker in tickers:
    symbol = REVERSE[ticker]
    try:
        d = daily[ticker]["Close"].dropna()
        m = minute[ticker]["Close"].dropna()
        if len(d) < 2 or m.empty:
            continue
        # Last completed daily bar may be today's partial bar.
        dates = [pd.Timestamp(t).date() for t in d.index]
        previous = [float(value) for date, value in zip(dates, d.values) if date < local_date]
        if not previous:
            continue
        prior_close = previous[-1]
        price = float(m.iloc[-1])
        if not (math.isfinite(price) and math.isfinite(prior_close) and price > 0 and prior_close > 0):
            continue
        quotes[symbol] = {"price": round(price, 4), "changePct": round((price / prior_close - 1) * 100, 4), "source": "Yahoo Finance (unofficial)", "asOf": pd.Timestamp(m.index[-1]).isoformat()}
        updated += 1
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"{symbol}: {exc}")
if updated == 0:
    print("No valid updated quotes; keeping existing snapshot.")
    raise SystemExit(1)
output = {"updatedAt": NOW.isoformat(), "quotes": quotes, "note": "Yahoo Finance unofficial 1-minute bars, refreshed by GitHub Actions approximately every 5 minutes; may be delayed."}
existing_path.write_text(json.dumps(output, indent=2) + "\n")
print(f"Updated {updated}/{len(SYMBOLS)} symbols; kept prior values for missing symbols")
