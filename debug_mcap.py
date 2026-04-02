from yahooquery import Ticker
import requests

finmind_url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
r = requests.get(finmind_url, timeout=15).json()
valid_tickers = []
for item in r.get('data', []):
    code = item.get('stock_id', '')
    ind_cat = item.get('industry_category', '其他')
    if len(code) == 4 and code.isdigit() and ind_cat != 'ETF':
        suffix = ".TW" if item.get('type') == 'twse' else ".TWO"
        valid_tickers.append(f"{code}{suffix}")

print(f"Total tickers: {len(valid_tickers)}")

# Test chunks
size_map = {}
for i in range(0, min(1000, len(valid_tickers)), 500):
    chunk = valid_tickers[i:i+500]
    print(f"Testing chunk {i} to {i+len(chunk)}")
    yq = Ticker(chunk, asynchronous=True)
    price_data = yq.price
    if isinstance(price_data, dict):
         for tkr, data in price_data.items():
              if isinstance(data, dict):
                  mcap = data.get('marketCap', 0)
                  if mcap and mcap > 0:
                       size_map[tkr] = mcap
              else:
                  pass # string error message probably

print(f"Size map contains {len(size_map)} items. First 5:", list(size_map.items())[:5])
