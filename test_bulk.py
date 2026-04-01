import yfinance as yf
import time

# List of 20 random NASDAQ stocks to test bulk capability
tickers = ["AAPL", "MSFT", "GOOG", "AMZN", "META", "TSLA", "NVDA", "ADBE", "NFLX", "INTC",
           "CSCO", "PEP", "AVGO", "TXN", "QCOM", "AMGN", "HON", "SBUX", "GILD", "MDLZ"]

start_time = time.time()
print(f"Testing yfinance Tickers object for {len(tickers)} stocks...")

# Method 1: yf.Tickers
tkrs = yf.Tickers(' '.join(tickers))
for ticker in tickers:
    info = tkrs.tickers[ticker].info
    print(f"{ticker}: Rev Growth: {info.get('revenueGrowth')} Margin: {info.get('profitMargins')}")

print(f"Finished in {time.time() - start_time:.2f} seconds.")
