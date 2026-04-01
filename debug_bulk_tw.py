import json
from yahooquery import Ticker
import pandas as pd
import requests

url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
import urllib3
urllib3.disable_warnings()
data = requests.get(url, verify=False).json()
tickers = [item['Code'] + '.TW' for item in data if len(item['Code']) == 4][:100]

yq_tickers = Ticker(tickers, asynchronous=True)
modules_data = yq_tickers.get_modules('price financialData assetProfile cashflowStatementHistoryQuarterly')

passed = 0
for ticker in tickers:
    data = modules_data.get(ticker, {})
    if not isinstance(data, dict):
        continue
    f_data = data.get('financialData', {})
    
    # how is it structured?
    rg = f_data.get('revenueGrowth')
    if isinstance(rg, dict):
        rev_growth = rg.get('raw')
    else:
        rev_growth = rg
        
    pm = f_data.get('profitMargins')
    if isinstance(pm, dict):
        prof_margin = pm.get('raw')
    else:
        prof_margin = pm
        
    if rev_growth is not None and prof_margin is not None:
        if rev_growth + prof_margin > 0.3:
            passed += 1
            print(f"Passed: {ticker}: RG={rev_growth}, PM={prof_margin}")
    elif rev_growth is None and prof_margin is None and isinstance(f_data, dict) and len(f_data) > 0:
        pass # printed too much

print(f"Total passed: {passed} out of 100")
