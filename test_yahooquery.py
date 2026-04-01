from yahooquery import Ticker
import time

# List of 20 random NASDAQ stocks to test bulk capability
tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "ADBE", "NFLX", "INTC",
           "CSCO", "PEP", "AVGO", "TXN", "QCOM", "AMGN", "HON", "SBUX", "GILD", "MDLZ"]

start_time = time.time()
print(f"Testing yahooquery for {len(tickers)} stocks...")

tkrs = Ticker(tickers, asynchronous=True)
# financial_data gets revenueGrowth and profitMargins
data = tkrs.financial_data

for ticker, info in data.items():
    if isinstance(info, dict):
        print(f"{ticker}: Rev Growth: {info.get('revenueGrowth')} Margin: {info.get('profitMargins')}")
    else:
        print(f"{ticker}: Error/String -> {info}")

print(f"Finished in {time.time() - start_time:.2f} seconds.")
