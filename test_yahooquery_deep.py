from yahooquery import Ticker
import time

tickers = ["AAPL", "GOOG", "TSLA"]

start_time = time.time()
print(f"Testing deep fundamentals yahooquery for {len(tickers)} stocks...")

tkrs = Ticker(tickers, asynchronous=True)

# 1. Cash flow (operatingCashflow) AND currentRatio
financial_data = tkrs.financial_data
# 2. Income Statement (Research And Development, Total Revenue)
income = tkrs.income_statement(frequency='a')

for ticker in tickers:
    print(f"\n--- {ticker} ---")
    
    # Check financial_data
    f_data = financial_data.get(ticker, {})
    if isinstance(f_data, dict):
        op_cashflow = f_data.get('operatingCashflow')
        current_ratio = f_data.get('currentRatio')
        print(f"Operating Cashflow: {op_cashflow}, Current Ratio: {current_ratio}")
    else:
        print(f"Financial Data Error: {f_data}")

    # Check income statement
    if isinstance(income, str): # Error message
        print(f"Income Statement Error: {income}")
        continue
        
    try:
        # income is a pandas dataframe multi-indexed by symbol and asOfDate
        ticker_income = income.loc[ticker]
        if 'ResearchAndDevelopment' in ticker_income.columns and 'TotalRevenue' in ticker_income.columns:
            rnd = ticker_income['ResearchAndDevelopment'].tail(4).tolist()
            rev = ticker_income['TotalRevenue'].tail(4).tolist()
            print(f"Recent R&D (last 4 yrs): {rnd}")
            print(f"Recent Total Revenue (last 4 yrs): {rev}")
        else:
            print("Missing R&D or Total Revenue columns in Income Statement")
            # print("Columns available:", ticker_income.columns.tolist())
    except KeyError:
         print("No income statement data found for ticker in dataframe")
    except Exception as e:
         print(f"Error parsing income statement: {e}")

print(f"\nFinished in {time.time() - start_time:.2f} seconds.")
