import pandas as pd

def get_tw_emerging_tickers():
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=5"
        # pd.read_html requires lxml or html5lib or bs4, which are present because app.py uses it.
        # But some sites block default User-Agent for pd.read_html. Let's use urllib
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        html = urllib.request.urlopen(req).read()
        dfs = pd.read_html(html)
        df = dfs[0]
        df.to_csv("emg_df.csv", index=False, encoding="utf-8-sig")
        return []
    except Exception as e:
        print(f"Error: {e}")
        return []

tickers = get_tw_emerging_tickers()
print("Check emg_df.csv")
