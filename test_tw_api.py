import urllib.request
import json
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

def fetch_twse():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    data = json.loads(html)
    tickers = [item['Code'] + '.TW' for item in data if len(item['Code']) == 4]
    print(f"TWSE total 4-digit tickers: {len(tickers)}")
    print(tickers[:5])

def fetch_tpex():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    data = json.loads(html)
    tickers = [item['SecuritiesCompanyCode'] + '.TWO' for item in data if len(item['SecuritiesCompanyCode']) == 4]
    print(f"TPEx total 4-digit tickers: {len(tickers)}")
    print(tickers[:5])

try:
    fetch_twse()
except Exception as e:
    print("TWSE error:", e)

try:
    fetch_tpex()
except Exception as e:
    print("TPEx error:", e)
