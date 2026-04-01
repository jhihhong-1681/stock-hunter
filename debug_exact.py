import json
from yahooquery import Ticker
import pandas as pd
import numpy as np

# Mock 785 surviving tickers (TWSE)
import requests
import urllib3
urllib3.disable_warnings()
url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
data = requests.get(url, verify=False).json()
surviving_tickers = [item['Code'] + '.TW' for item in data if len(item['Code']) == 4][:785]

# Using EXACT same code as app.py
yq_tickers = Ticker(surviving_tickers, asynchronous=True)
modules_data = yq_tickers.get_modules('price financialData assetProfile cashflowStatementHistoryQuarterly')

final_results = []
for ticker in surviving_tickers:
    data = modules_data.get(ticker, {})
    if not isinstance(data, dict):
        continue
        
    f_data = data.get('financialData', {})
    
    rev_growth = f_data.get('revenueGrowth', {}).get('raw', None) if isinstance(f_data.get('revenueGrowth'), dict) else f_data.get('revenueGrowth')
    prof_margin = f_data.get('profitMargins', {}).get('raw', None) if isinstance(f_data.get('profitMargins'), dict) else f_data.get('profitMargins')
    
    if rev_growth is None or prof_margin is None:
        continue
        
    rule_of_30_val = rev_growth + prof_margin
    if rule_of_30_val <= 0.3:
        continue
        
    final_results.append(ticker)

print(f"Passed: {len(final_results)}")
print(final_results[:20])
