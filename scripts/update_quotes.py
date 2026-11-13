"""Alpaca IEX snapshots during regular and extended US trading sessions."""
import json
import math
import os
from datetime import datetime, timezone, time
from pathlib import Path
from zoneinfo import ZoneInfo
import pandas as pd
import pandas_market_calendars as mcal
import requests

GROUPS = {
    "Technology": "AAPL ADBE AMD AMZN ASML AVGO CBRS DRAM GOOG META MRVL MSFT MU NVDA ORCL SKHY SNDK SPCX TSLA TSM",
    "Other": "BRK.B COST OHI UNH WMT",
    "ETFs": "GLD QQQ SPHD SPY VOO",
}
SYMBOLS = list(dict.fromkeys(t for group in GROUPS.values() for t in group.split()))
# SPX is an index, not an IEX-traded equity. Keep its previous quote, if any.
EQUITIES = [s for s in SYMBOLS if s != "SPX"]
NOW = datetime.now(timezone.utc)
ET = NOW.astimezone(ZoneInfo("America/New_York"))
schedule = mcal.get_calendar("NYSE").schedule(start_date=ET.date(), end_date=ET.date())
if schedule.empty:
    print("NYSE holiday/weekend; no snapshot.")
    raise SystemExit(0)
market_open = schedule.iloc[0]["market_open"].to_pydatetime()
market_close = schedule.iloc[0]["market_close"].to_pydatetime()
if market_open <= NOW <= market_close:
    session = "REG"
    interval = 5
elif ET.time() >= time(4, 0) and NOW < market_open:
    session = "PRE"
    interval = 15
elif NOW > market_close and ET.time() < time(20, 0):
    session = "POST"
    interval = 15
else:
    print("Outside US stock extended trading hours; no snapshot.")
    raise SystemExit(0)
if ET.minute % interval:
    print(f"Skipping {session} snapshot: scheduled every {interval} minutes.")
    raise SystemExit(0)
print(f"{session} snapshot at {ET.isoformat()} (target every {interval} min)")

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
    "session": session,
    "quotes": quotes,
    "note": f"IEX-only market data, not consolidated SIP; {session} target refresh every {interval} minutes; extended-hours liquidity may be sparse.",
}, indent=2) + "\n")
print(f"Updated {updated} of {len(EQUITIES)} eligible instruments; kept previous values for missing quotes.")
