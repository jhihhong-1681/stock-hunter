import pandas as pd
import urllib.request
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

def fetch_tw_stocks(mode):
    url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read()
        dfs = pd.read_html(html)
        df = dfs[0]
        print(f"Mode {mode} total records: len(df)")
        print(df.head(5))
    except Exception as e:
        print(f"Error {mode}: {e}")

fetch_tw_stocks(2) # 上市
fetch_tw_stocks(4) # 上櫃
fetch_tw_stocks(5) # 興櫃
