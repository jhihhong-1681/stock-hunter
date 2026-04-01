import yfinance as yf
import pandas as pd
import datetime

def get_sp500_tickers():
    """從維基百科獲取 S&P 500 股票代號"""
    import urllib.request
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    
    # 加入 User-Agent 標頭，防止維基百科阻擋請求 (403 Forbidden Error)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req).read()
    
    # 使用 pandas 的 read_html 來抓取表格
    table = pd.read_html(html)
    df = table[0]
    # 將代號中的點替換為破折號（例如 BRK.B -> BRK-B，以符合 yfinance 格式）
    tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
    return tickers

def main():
    print("正在獲取 S&P 500 股票代號...")
    try:
        tickers = get_sp500_tickers()
    except Exception as e:
        print(f"獲取股票代號失敗: {e}")
        return

    print(f"共找到 {len(tickers)} 檔股票，開始下載近期價格資料...")
    
    end_date = datetime.date.today()
    # 往前推 60 天，確保有足夠的資料計算 14 天的 RSI 及 5 天的跌幅
    start_date = end_date - datetime.timedelta(days=60)
    
    # 批次下載所有股票資料，速度較快
    data = yf.download(tickers, start=start_date, end=end_date, progress=False)
    
    if 'Close' not in data:
        print("無法取得收盤價資料。")
        return
        
    close_data = data['Close']
    
    # 第一階段篩選：價格條件 (5天跌幅 > 10% 且 RSI < 30)
    print("正在篩選符合價格條件（過去 5 天跌幅 > 10% 且 RSI < 30）的股票...")
    price_survivors = []
    
    for ticker in tickers:
        try:
            if ticker not in close_data.columns:
                continue
            # 移除空值
            series = close_data[ticker].dropna()
            if len(series) < 20: # 確保有足夠天數的資料
                continue
            
            # 計算過去 5 天的跌幅
            last_close = series.iloc[-1]
            close_5d_ago = series.iloc[-6]
            drop_pct = (last_close - close_5d_ago) / close_5d_ago
            
            # 跌幅要大於 10% (即變動率 < -0.10)
            if drop_pct > -0.10:
                continue
                
            # 計算 14 天 RSI
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]
            
            # RSI 必須小於 30
            if pd.isna(current_rsi) or current_rsi >= 30:
                continue
                
            price_survivors.append({
                'Ticker': ticker,
                'Drop_5D': drop_pct,
                'RSI': current_rsi
            })
        except Exception:
            continue
            
    print(f"第一階段篩選完成，共有 {len(price_survivors)} 檔股票符合價格條件。")
    if not price_survivors:
        print("沒有符合條件的股票。")
        return
        
    # 第二階段篩選：營收成長為正
    print("正在檢查這些股票的營收成長率（需為正成長）...")
    final_results = []
    
    for item in price_survivors:
        ticker = item['Ticker']
        try:
            info = yf.Ticker(ticker).info
            rev_growth = info.get('revenueGrowth', None)
            
            # 營收成長必須存在且 > 0
            if rev_growth is not None and rev_growth > 0:
                final_results.append({
                    '股票代號': ticker,
                    '過去5天跌幅': f"{item['Drop_5D']*100:.2f}%",
                    'RSI (14天)': round(item['RSI'], 2),
                    '營收成長率': f"{rev_growth*100:.2f}%"
                })
                print(f"[ MATCH ] 符合所有條件: {ticker}")
        except Exception:
            continue

    print("\n" + "="*40)
    print(">>> 最終篩選結果 <<<")
    print("="*40)
    
    if final_results:
        res_df = pd.DataFrame(final_results)
        print(res_df.to_string(index=False))
    else:
        print("沒有股票同時符合「跌破10%、RSI<30」以及「營收正成長」的條件。")

if __name__ == "__main__":
    main()
