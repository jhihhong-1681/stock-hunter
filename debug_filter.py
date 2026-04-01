import yfinance as yf
from yahooquery import Ticker
import pandas as pd
import datetime
import urllib.request

# Get Nasdaq 100 tickers
def get_nasdaq100_tickers():
    url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    table = pd.read_html(html)
    df = table[4]
    if 'Ticker' in df.columns:
        return df['Ticker'].str.replace('.', '-', regex=False).tolist()
    return df.iloc[:, 0].str.replace('.', '-', regex=False).tolist()

tickers = get_nasdaq100_tickers()
print(f"Got {len(tickers)} tickers.")

end_date = datetime.date.today()
start_date = end_date - datetime.timedelta(days=90)
data = yf.download(tickers, start=start_date, end=end_date, progress=False)
close_data = data['Close']

drop_days = 30
target_drop = -0.10

price_survivors = []
for ticker in tickers:
    if ticker not in close_data.columns: continue
    series = close_data[ticker].dropna()
    recent_window = series.iloc[-(drop_days + 1):]
    if len(recent_window) < (drop_days + 1): continue
    
    period_high = recent_window.max()
    period_low = recent_window.min()
    last_close = recent_window.iloc[-1]
    
    drop_pct = (last_close - period_high) / period_high
    max_drop = (period_low - period_high) / period_high
    
    if drop_pct <= target_drop:
        price_survivors.append(ticker)
        print(f"[Price OK] {ticker}: Drop to Last Close = {drop_pct*100:.1f}%, Max Drop = {max_drop*100:.1f}%")

print(f"\nPrice survivors: {len(price_survivors)}")

# Check fundamentals
if price_survivors:
    yq_tickers = Ticker(price_survivors, asynchronous=True)
    f_data_dict = yq_tickers.financial_data
    
    for ticker in price_survivors:
        f_data = f_data_dict.get(ticker, {})
        if not isinstance(f_data, dict):
            print(f"[Fundamental] {ticker} missing data")
            continue
            
        rev_growth = f_data.get('revenueGrowth', 0) or 0
        prof_margin = f_data.get('profitMargins', 0) or 0
        op_cashflow = f_data.get('operatingCashflow', 0) or 0
        curr_ratio = f_data.get('currentRatio', 0) or 0
        
        rule30 = rev_growth + prof_margin
        r30_pass = rule30 > 0.3
        cash_pass = op_cashflow > 0
        cr_pass = curr_ratio > 1.2
        
        print(f"{ticker}: Rule30={rule30:.2f}({r30_pass}), OpCF={op_cashflow}({cash_pass}), CR={curr_ratio:.2f}({cr_pass})")
