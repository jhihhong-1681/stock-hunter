import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    url_info = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    print("Fetching", url_info)
    r1 = requests.get(url_info, headers=headers, verify=False, timeout=10)
    print("r1 status:", r1.status_code)
    info_json = r1.json()
    print("r1 length:", len(info_json))
    
    url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    print("Fetching", url_price)
    r2 = requests.get(url_price, headers=headers, verify=False, timeout=10)
    print("r2 status:", r2.status_code)
    price_json = r2.json()
    print("r2 length:", len(price_json))
    
except Exception as e:
    print(f"Exception: {e}")
