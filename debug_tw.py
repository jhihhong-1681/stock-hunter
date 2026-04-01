from yahooquery import Ticker

tickers = ['2330.TW', '1256.TW', '2317.TW', '2454.TW']
yq_tickers = Ticker(tickers, asynchronous=True)
modules_data = yq_tickers.get_modules('price financialData assetProfile cashflowStatementHistoryQuarterly')

for ticker in tickers:
    data = modules_data.get(ticker, {})
    if not isinstance(data, dict):
        print(f"{ticker}: data is not dict, it's {type(data)}")
        continue
    
    f_data = data.get('financialData', {})
    
    print(f"[{ticker}] f_data keys: {list(f_data.keys())[:10] if isinstance(f_data, dict) else type(f_data)}")
    if isinstance(f_data, str):
        print(f"  f_data string content: {f_data}")
        continue
        
    rev_growth = f_data.get('revenueGrowth', {})
    prof_margin = f_data.get('profitMargins', {})
    
    rev_val = rev_growth.get('raw', None) if isinstance(rev_growth, dict) else rev_growth
    pm_val = prof_margin.get('raw', None) if isinstance(prof_margin, dict) else prof_margin
    print(f"  rev: {rev_val}, pm: {pm_val}")
