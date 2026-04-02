import yfinance as yf
import pandas as pd

tickers = ['2330.TW', '2317.TW', '2454.TW', '2382.TW', '0050.TW', '2303.TW', '8046.TW']

df = yf.download(tickers, period="5d", progress=False, threads=True)
size_map = {}
for t in tickers:
    v = df['Volume'][t].dropna()
    c = df['Close'][t].dropna()
    if len(v) > 0 and len(c) > 0:
        avg_trade_value = (v[-3:] * c[-3:]).mean()
        size_map[t] = float(avg_trade_value)

# sort by size
sorted_items = sorted(size_map.items(), key=lambda x: x[1], reverse=True)
print("Top stocks by 3-day average TradeValue:")
for t, size in sorted_items:
    print(f"{t}: {size:,.0f} NTD")
