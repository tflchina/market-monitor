"""Alpaca Basic IEX snapshots, during regular NYSE trading sessions only."""
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import pandas_market_calendars as mcal
import requests

GROUPS = {
    "Technology": "AAPL ADBE AMD AMZN ASML AVGO CBRS DRAM GOOG META MRVL MSFT MU NVDA ORCL SKHY SNDK SPCX TSLA TSM",
    "Other": "BRK.B CALY COST FIG OHI PSA SOFI UNH WMT",
    "ETFs": "GLD QQQ SPHD SPX SPY VOO",
}
SYMBOLS = list(dict.fromkeys(t for group in GROUPS.values() for t in group.split()))
# SPX is an index, not an IEX-traded equity. Keep its previous quote, if any.
EQUITIES = [s for s in SYMBOLS if s != "SPX"]
NOW = datetime.now(timezone.utc)
schedule = mcal.get_calendar("NYSE").schedule(start_date=NOW.date(), end_date=NOW.date())
if schedule.empty or not (schedule.iloc[0]["market_open"] <= pd.Timestamp(NOW) <= schedule.iloc[0]["market_close"]):
    print("Market closed; keeping existing quotes.")
    raise SystemExit(0)

key = os.environ.get("ALPACA_API_KEY_ID")
secret = os.environ.get("ALPACA_API_SECRET_KEY")
if not key or not secret:
    raise SystemExit("Missing Alpaca credentials in GitHub Actions secrets.")
path = Path("quotes.json")
try:
    existing = json.loads(path.read_text()) if path.exists() else {}
except (OSError, ValueError):
    existing = {}
quotes = existing.get("quotes", {})
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/snapshots",
    params={"symbols": ",".join(EQUITIES), "feed": "iex"},
    headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
    timeout=30,
)
response.raise_for_status()
snapshots = response.json()
updated = 0
for symbol in EQUITIES:
    snap = snapshots.get(symbol, {})
    trade = snap.get("latestTrade") or {}
    daily = snap.get("dailyBar") or {}
    prev = snap.get("previousDailyBar") or {}
    price = trade.get("p") or daily.get("c")
    previous = prev.get("c")
    try:
        price = float(price)
        previous = float(previous)
        if not (math.isfinite(price) and math.isfinite(previous) and price > 0 and previous > 0):
            continue
        quotes[symbol] = {
            "price": round(price, 4),
            "changePct": round((price / previous - 1) * 100, 4),
            "source": "Alpaca IEX",
            "asOf": trade.get("t") or daily.get("t"),
        }
        updated += 1
    except (TypeError, ValueError):
        continue
if not updated:
    raise SystemExit("No valid IEX quotes returned; preserving existing snapshot.")
path.write_text(json.dumps({
    "updatedAt": NOW.isoformat(),
    "quotes": quotes,
    "note": "IEX-only market data, not consolidated SIP; scheduled about every 5 minutes; quotes may be delayed or unavailable.",
}, indent=2) + "\n")
print(f"Updated {updated} of {len(EQUITIES)} eligible instruments; kept previous values for missing quotes.")
