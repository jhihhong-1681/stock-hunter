import time
from yahooquery import Ticker
import requests

finmind_url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
r = requests.get(finmind_url, timeout=15).json()
valid_tickers = []
for item in r.get('data', []):
    code = item.get('stock_id', '')
    if len(code) == 4 and code.isdigit():
        suffix = ".TW" if item.get('type') == 'twse' else ".TWO"
        valid_tickers.append(f"{code}{suffix}")

print(f"Total valid tickers: {len(valid_tickers)}")

# Keep only 500 to test speed, or all 1700
valid_tickers = valid_tickers[:1700]

start = time.time()
yq = Ticker(valid_tickers, asynchronous=True)
data = yq.price
end = time.time()
print(f"yq.price took {end-start:.2f} seconds")
# check if data has 'regularMarketVolume' and 'regularMarketPrice'
count = 0
for t, d in data.items():
    if isinstance(d, dict) and 'regularMarketVolume' in d:
        count += 1
print(f"Valid data count: {count}")
