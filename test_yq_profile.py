from yahooquery import Ticker

tickers = ['AAPL', 'NVDA']
yq = Ticker(tickers, asynchronous=True)

# 1. Test asset profile for business summary
profiles = yq.asset_profile
print("Asset Profile AAPL:")
if isinstance(profiles, dict) and 'AAPL' in profiles:
    print(profiles['AAPL'].keys())
    print("Summary:", profiles['AAPL'].get('longBusinessSummary', 'No Summary')[:100], "...")

# 2. Test quarterly cash flow for last 3 quarters capex
cf_q = yq.cash_flow(frequency='q')
print("\nQuarterly Cash Flow index:")
print(cf_q.columns)
if not isinstance(cf_q, str) and 'AAPL' in cf_q.index:
    aapl_cf = cf_q.loc['AAPL']
    print("\nAAPL Capex (Q) cols:")
    print(aapl_cf[['asOfDate', 'periodType', 'CapitalExpenditure']].tail(6))
