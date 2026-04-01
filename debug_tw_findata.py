import json
from yahooquery import Ticker

tickers = ['2330.TW', '1256.TW', '2317.TW', '2454.TW']
t = Ticker(tickers, asynchronous=True)
fin = t.financial_data

print("Keys:", list(fin.keys()) if isinstance(fin, dict) else type(fin))
for k, v in fin.items():
    if isinstance(v, dict):
        print(f"[{k}] rev: {v.get('revenueGrowth')}, pm: {v.get('profitMargins')}")
    else:
        print(f"[{k}] is {type(v)}: {v}")
