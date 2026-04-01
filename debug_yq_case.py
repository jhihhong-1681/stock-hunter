from yahooquery import Ticker

tickers = ['2330.TW']
t = Ticker(tickers)
print(f"financial_data keys: {list(t.financial_data.keys())}")
print(f"get_modules keys: {list(t.get_modules('financialData').keys())}")
