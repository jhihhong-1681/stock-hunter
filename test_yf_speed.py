import yfinance as yf
import time
import requests

# Get TWSE tickers
url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
data = requests.get(url, verify=False).json()
tickers = [item['Code'] + '.TW' for item in data if len(item['Code']) == 4][:300] # test 300

start = time.time()
df = yf.download(tickers, period="3mo", progress=False)['Close']
end = time.time()
print(f"Downloaded 300 tickers in {end-start:.2f} seconds")
