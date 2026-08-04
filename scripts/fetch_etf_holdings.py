"""
每日由 GitHub Actions 執行，預先抓好「產業輪動」頁面用到的各檔 ETF 成分股與權重，
存成 JSON 給網頁直接讀取。ETF 成分股組成本來就不常變動（基金公司通常一季才調整一次），
不需要使用者點擊當下才即時去問 Yahoo（那樣會遇到雲端 IP 被限流的問題）。
"""
import json
import time
from pathlib import Path

import yfinance as yf

OUTPUT = Path(__file__).parent.parent / "data" / "etf_holdings.json"

# 對應 pages/7_產業輪動.py 的 SECTOR_ETFS 值，兩邊改動時要一起更新。
ETF_TICKERS = [
    "XLK", "SOXX", "IGV", "XLF", "KBE", "FINX", "XLE", "XOP", "XLU", "NLR",
    "XLV", "XBI", "XPH", "XLI", "ITA", "XTN", "XLY", "XRT", "XHB", "XLP",
    "XLB", "SETM", "XME", "XLRE", "XLC", "CIBR",
]


def fetch_one(ticker: str):
    for attempt in range(3):
        try:
            holdings = yf.Ticker(ticker).funds_data.top_holdings
            if holdings is not None and not holdings.empty:
                df = holdings.reset_index().rename(columns={
                    "Symbol": "代號", "Name": "名稱", "Holding Percent": "權重"
                })
                df["權重"] = (df["權重"] * 100).round(2)
                return df.to_dict(orient="records")
        except Exception as e:
            print(f"  {ticker} attempt {attempt + 1} failed: {e}")
        if attempt < 2:
            time.sleep(2)
    return None


def main():
    existing = {}
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8")).get("holdings", {})
        except Exception:
            existing = {}

    result = dict(existing)
    for ticker in ETF_TICKERS:
        print(f"Fetching {ticker}...")
        holdings = fetch_one(ticker)
        if holdings:
            result[ticker] = holdings
            print(f"  got {len(holdings)} holdings")
        else:
            print(f"  failed, keeping previous data if any")

    from datetime import date
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"date": date.today().isoformat(), "holdings": result}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(result)} ETFs to {OUTPUT}")


if __name__ == "__main__":
    main()
