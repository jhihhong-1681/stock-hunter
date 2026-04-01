import pandas as pd
from yahooquery import Ticker

# Pick 30 large well-known tech stocks to analyze their R&D behavior
surviving_tickers = ['AAPL', 'GOOG', 'TSLA', 'AMZN', 'MSFT', 'META', 'NVDA', 'ADBE', 
                     'NFLX', 'INTC', 'CSCO', 'PEP', 'AVGO', 'TXN', 'QCOM', 'AMGN', 'HON', 
                     'SBUX', 'GILD', 'MDLZ', 'AMD', 'CRM', 'ORCL', 'IBM', 'NOW', 'INTU']

yq_tickers = Ticker(surviving_tickers, asynchronous=True)
income_df = yq_tickers.income_statement(frequency='a')

passed_count = 0
failed_count = 0
no_data_count = 0

print("Analyzing R&D Ratio Trend Strict vs Relaxed")

for ticker in surviving_tickers:
    if isinstance(income_df, str) or ticker not in income_df.index:
        no_data_count += 1
        continue
        
    try:
        ticker_income = income_df.loc[ticker]
        if 'ResearchAndDevelopment' not in ticker_income.columns or 'TotalRevenue' not in ticker_income.columns:
            no_data_count += 1
            continue
            
        rnd = ticker_income['ResearchAndDevelopment']
        rev = ticker_income['TotalRevenue']
        ratios = (rnd / rev).replace([float('inf'), -float('inf')], float('nan')).dropna()
        
        if len(ratios) < 2:
            no_data_count += 1
            continue
            
        print(f"\n{ticker} R&D Ratios over years (Oldest to Newest):")
        # Ensure chronological order. Usually index is asOfDate
        # In yahooquery, the returned data might have index as dates
        pass_strict = True
        for j in range(len(ratios)-1):
            if ratios.iloc[j] < (ratios.iloc[j+1] * 0.95):
                pass_strict = False
                break
                
        # Let's test a relaxed trend: The last year's ratio must simply be >= the average of the previous years.
        # Or simply, R&D ratio is generally maintained (latest >= 90% of max of previous 3 years)
        latest_ratio = ratios.iloc[-1]
        hist_ratios = ratios.iloc[:-1]
        
        pass_relaxed = True
        if latest_ratio < (hist_ratios.mean() * 0.85):
            pass_relaxed = False
            
        print(f"  Ratios: {[round(r, 3) for r in ratios.tolist()]}")
        print(f"  Strict Pass: {pass_strict}")
        print(f"  Relaxed Pass: {pass_relaxed}")
        
    except Exception as e:
        pass
