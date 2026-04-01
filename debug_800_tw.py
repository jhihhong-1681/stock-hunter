import json
from yahooquery import Ticker
import pandas as pd
import requests

url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
import urllib3
urllib3.disable_warnings()
data = requests.get(url, verify=False).json()
tickers = [item['Code'] + '.TW' for item in data if len(item['Code']) == 4][:800] # bulk test

yq_tickers = Ticker(tickers, asynchronous=True)
modules_data = yq_tickers.get_modules('price financialData assetProfile cashflowStatementHistoryQuarterly')

print(f"modules_data type: {type(modules_data)}")
if isinstance(modules_data, dict):
    print(f"Number of keys: {len(modules_data.keys())}")
    empty_count = sum(1 for v in modules_data.values() if isinstance(v, str))
    print(f"String responses (errors): {empty_count}")
