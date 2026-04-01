from yahooquery import Ticker
import time

tickers = ['AAPL', 'MSFT', '2330.TW', '1256.TW']

t0 = time.time()
yq_tickers = Ticker(tickers, asynchronous=True)
m = yq_tickers.get_modules('financialData assetProfile cashflowStatementHistoryQuarterly')
t1 = time.time()
print(f"Time for get_modules: {t1-t0:.2f}s")
for t in tickers:
    data = m.get(t, {})
    if isinstance(data, dict):
        fin = data.get('financialData', {})
        prof = data.get('assetProfile', {})
        cf = data.get('cashflowStatementHistoryQuarterly', {}).get('cashflowStatements', [])
        
        rev = fin.get('revenueGrowth', {})
        rev_val = rev.get('raw', None) if isinstance(rev, dict) else rev
        
        prof_margin = fin.get('profitMargins', {})
        pm_val = prof_margin.get('raw', None) if isinstance(prof_margin, dict) else prof_margin
        
        name = prof.get('longBusinessSummary')
        print(f"{t}: Rev {rev_val}, PM {pm_val}, CF quarters: {len(cf)}")
        
t2 = time.time()
yq2 = Ticker(tickers, asynchronous=True)
f = yq2.financial_data
p = yq2.asset_profile
c = yq2.cash_flow(frequency='q')
t3 = time.time()
print(f"Time for individual props: {t3-t2:.2f}s")
