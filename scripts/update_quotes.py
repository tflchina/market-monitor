import json
from datetime import datetime, timezone
from pathlib import Path
import yfinance as yf

groups = {
  "Technology": "CBRS AAPL NVDA MSFT GOOG META AVGO AMD MU MRVL ASML TSM SNDK ADBE ORCL DRAM SKHY SPCX AMZN TSLA",
  "Other": "COST WMT BRK.B SOFI FIG UNH OHI PSA CALY",
  "ETFs": "SPY VOO SPHD SLV SPX"
}
aliases = {"BRK.B":"BRK-B","SPX":"^GSPC","USD.CNH":"CNH=X","USD.HKD":"HKD=X","EUR.USD":"EURUSD=X","GBP.USD":"GBPUSD=X","USD.JPY":"JPY=X"}
symbols = list(dict.fromkeys(s for group in groups.values() for s in group.split()))
quotes = {}
for symbol in symbols:
    ticker = aliases.get(symbol, symbol)
    try:
        daily = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
        intraday = yf.Ticker(ticker).history(period="1d", interval="5m", auto_adjust=False)
        if len(daily) < 2:
            continue
        last = float(intraday["Close"].iloc[-1]) if len(intraday) else float(daily["Close"].iloc[-1])
        prev = float(daily["Close"].iloc[-2]) if not len(intraday) else float(daily["Close"].iloc[-2] if len(daily) == 2 else daily["Close"].iloc[-2])
        if last > 0 and prev > 0:
            quotes[symbol] = {"price": round(last, 4), "changePct": round((last/prev-1)*100, 4)}
    except Exception as exc:
        print(f"{symbol}: {exc}")
output = {"updatedAt": datetime.now(timezone.utc).isoformat(), "quotes": quotes, "note": "Latest available 5-minute bar, compared with prior daily close; may be delayed"}
Path("quotes.json").write_text(json.dumps(output, indent=2)+"\n")
print(f"Retrieved {len(quotes)} of {len(symbols)} symbols")
