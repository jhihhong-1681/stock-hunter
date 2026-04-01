import json
import pandas as pd
from yahooquery import Ticker

# Mock generating 1964 tickers
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
nasdaq = pd.read_csv('ftp://ftp.nasdaqtrader.com/SymbolDirectory/nasdaqtraded.txt', sep='|')
# Filter exactly as app does for Nasdaq
nasdaq = nasdaq[nasdaq['Test Issue'] == 'N']
tickers = nasdaq[nasdaq['Nasdaq Traded'] == 'Y']['Symbol'].dropna().tolist()[:1964]

print(f"Testing {len(tickers)} tickers...")
try:
    yq_tickers = Ticker(tickers, asynchronous=True)
    fin_modules_data = yq_tickers.financial_data
    if isinstance(fin_modules_data, dict):
        print(f"Total keys retrieved: {len(fin_modules_data.keys())}")
        empty_count = sum(1 for v in fin_modules_data.values() if not isinstance(v, dict))
        print(f"Non-dict values (errors): {empty_count}")
    else:
        print(f"fin_modules_data is not a dict: type={type(fin_modules_data)}")
        print(fin_modules_data)
except Exception as e:
    print(f"Error: {e}")
