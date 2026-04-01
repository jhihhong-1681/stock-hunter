import pandas as pd
from yahooquery import Ticker

surviving_tickers = ['AAPL', 'GOOG', 'TSLA', 'AMZN', 'MSFT']

try:
    yq_tickers = Ticker(surviving_tickers, asynchronous=True)
    fin_data_dict = yq_tickers.financial_data
    income_df = yq_tickers.income_statement(frequency='a')
except Exception as e:
    print(f"Error fetching: {e}")
    exit()

print("Testing Filtering Logic:\n")

for ticker in surviving_tickers:
    print(f"--- {ticker} ---")
    f_data = fin_data_dict.get(ticker, {})
    if not isinstance(f_data, dict):
        print(f"FAILED because: f_data is not a dictionary: {f_data}")
        continue
    
    rev_growth = f_data.get('revenueGrowth')
    prof_margin = f_data.get('profitMargins')
    op_cashflow = f_data.get('operatingCashflow')
    curr_ratio = f_data.get('currentRatio')
    
    target_rev_growth = 10 / 100.0
    target_prof_margin = -50 / 100.0
    
    fail_reason = []
    
    if rev_growth is None or rev_growth < target_rev_growth:
         fail_reason.append(f"Rev Growth failed: {rev_growth} < {target_rev_growth}")
    if prof_margin is None or prof_margin < target_prof_margin:
         fail_reason.append(f"Margin failed: {prof_margin} < {target_prof_margin}")
         
    if op_cashflow is None or op_cashflow <= 0:
         fail_reason.append(f"Op Cashflow failed: {op_cashflow} <= 0")
    if curr_ratio is None or curr_ratio <= 1.2:
         fail_reason.append(f"Current ratio failed: {curr_ratio} <= 1.2")
         
    if isinstance(income_df, str) or ticker not in income_df.index:
         fail_reason.append(f"Income statement missing: Is string? {isinstance(income_df, str)}. In Index? {ticker in income_df.index if not isinstance(income_df, str) else False}")
    else:
         try:
             ticker_income = income_df.loc[ticker]
             if 'ResearchAndDevelopment' not in ticker_income.columns or 'TotalRevenue' not in ticker_income.columns:
                  fail_reason.append(f"Missing R&D or Revenue columns. Columns: {ticker_income.columns.tolist() if not isinstance(ticker_income, pd.Series) else ticker_income.index.tolist()}")
             else:
                  rnd = ticker_income['ResearchAndDevelopment']
                  rev = ticker_income['TotalRevenue']
                  ratios = (rnd / rev).replace([float('inf'), -float('inf')], float('nan')).dropna()
                  
                  if len(ratios) < 2:
                      fail_reason.append(f"Not enough ratio history length: {len(ratios)}")
                  else:
                      is_increasing = True
                      for j in range(len(ratios)-1):
                          if ratios.iloc[j] < (ratios.iloc[j+1] * 0.95):
                              is_increasing = False
                              break
                      if not is_increasing:
                          fail_reason.append(f"R&D Ratio not increasing: {ratios.tolist()}")
                          
         except Exception as e:
              fail_reason.append(f"Exception parsing income df: {e}")
              
    if not fail_reason:
         print("PASSED!")
    else:
         print("FAILED because:")
         for r in fail_reason:
              print(f"  - {r}")
