import yfinance as yf
import pandas as pd

tickers = ['NVDA', 'AAPL', 'MSFT', 'AMD']
for t in tickers:
    tk = yf.Ticker(t)
    info = tk.info
    rev = info.get('revenueGrowth', 0)
    pm = info.get('profitMargins', 0)
    cr = info.get('currentRatio', 0)
    cf = info.get('operatingCashflow', 0)
    
    financials = tk.income_stmt
    inc = financials.loc['Research And Development'] / financials.loc['Total Revenue'] if not financials.empty and 'Research And Development' in financials.index else pd.Series()
    
    print(f'[{t}]')
    print(f'  Rev (>=30%?): {rev * 100:.2f}% {"(PASS)" if rev>=0.3 else "(FAIL)"}')
    print(f'  PM  (>=0%?): {pm * 100:.2f}% {"(PASS)" if pm>=0 else "(FAIL)"}')
    print(f'  CR  (>1.2?): {cr} {"(PASS)" if cr>1.2 else "(FAIL)"}')
    print(f'  CF  (>0?): {cf} {"(PASS)" if cf>0 else "(FAIL)"}')
    
    ratios = inc.dropna()
    is_increasing = True
    if len(ratios) >= 2:
        for i in range(len(ratios)-1):
            if ratios.iloc[i] < (ratios.iloc[i+1] * 0.95):
                is_increasing = False
                break
    else:
        is_increasing = False
        
    print(f'  R&D Growth: {[round(x, 4) for x in ratios.tolist()]} {"(PASS)" if is_increasing else "(FAIL)"}')
    print('-' * 40)
