import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import urllib.request
import yahoo_fin.stock_info as si
from yahooquery import Ticker
# --- 頁面設定 ---
st.set_page_config(
    page_title="Stock Hunter 股票獵人",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Stock Hunter 股票獵人 - 股市抄底神器")
st.markdown("""
這個工具可以幫助你從 **S&P 500、Nasdaq、全美市場** 中，找出近期超跌但基本面良好的股票。
請在左側側邊欄選擇你要掃描的市場並調整篩選條件，然後點擊「開始篩選」。
""")

# --- 側邊欄：篩選條件設定 ---
st.sidebar.header("⚙️ 篩選條件設定")

# 0. 選擇市場
market_choice = st.sidebar.selectbox(
    "0. 選擇掃描的市場",
    ("S&P 500 (大型股)", "Nasdaq 100 (大型科技股)", "納斯達克全部 (Nasdaq)", "全美市場 (包含羅素2000中小型股)")
)
st.sidebar.markdown("---")

# 1. 下跌天數
drop_days = st.sidebar.number_input(
    "1. 計算跌幅的天數 (Days)", 
    min_value=1, max_value=30, value=5, step=1,
    help="計算過去幾天的累積跌幅。例如：5 代表比較今天與 5 天前的收盤價。"
)

# 2. 下跌幅度
drop_pct_threshold = st.sidebar.slider(
    "2. 要求的最少累積跌幅 (%)",
    min_value=0, max_value=50, value=10, step=1,
    help="例如：設定 10%，代表這段期間內從最高點到目前至少要跌 10%。"
)

# 3. 谷底反彈幅度
rebound_pct_threshold = st.sidebar.slider(
    "3. 要求的最少谷底反彈幅度 (%)",
    min_value=0, max_value=50, value=0, step=1,
    help="例如：設定 5%，代表股價從這段期間的最低點到目前，必須已經回升至少 5%。設定 0 代表不限制。"
)

st.sidebar.markdown("---")
st.sidebar.subheader("基本面條件")

# 4. 營收成長率
rev_growth_min = st.sidebar.number_input(
    "4. 最低營收成長率 (%)",
    min_value=-50, max_value=200, value=0, step=1,
    help="例如：設定 0 代表要求營收必須正成長 (>0%)。"
)

# 5. 淨利率
profit_margin_min = st.sidebar.number_input(
    "5. 最低淨利率 (%)",
    min_value=-50, max_value=100, value=0, step=1,
    help="例如：設定 0 代表要求公司必須是賺錢的 (淨利率 > 0%)。"
)

run_button = st.sidebar.button("🚀 開始篩選", type="primary", use_container_width=True)


# --- 核心邏輯與快取 (Caching) ---
# 使用 st.cache_data 避免每次調整參數都重新下載資料
@st.cache_data(ttl=3600*24) # 快取 24 小時
def get_sp500_tickers():
    """從維基百科獲取 S&P 500 股票代號"""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read()
        table = pd.read_html(html)
        df = table[0]
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        return tickers
    except Exception as e:
        st.error(f"獲取 S&P 500 名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_nasdaq100_tickers():
    """從維基百科獲取 Nasdaq 100 代號"""
    url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        html = urllib.request.urlopen(req).read()
        table = pd.read_html(html)
        df = table[4] # 通常 Nasdaq-100 表格在第5個位置
        if 'Ticker' in df.columns:
            return df['Ticker'].str.replace('.', '-', regex=False).tolist()
        return df.iloc[:, 0].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        st.error(f"獲取 Nasdaq 100 名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_all_nasdaq_tickers():
    """使用 yahoo_fin 獲取所有 Nasdaq 股票"""
    try:
        tickers = si.tickers_nasdaq()
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        st.error(f"獲取 Nasdaq 名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_all_us_tickers():
    """使用 yahoo_fin 獲取全美市場 (Nasdaq + NYSE + AMEX)，包含羅素2000中小型股"""
    try:
        nasdaq = si.tickers_nasdaq()
        other = si.tickers_other() # 包含 NYSE 與 AMEX
        # 移除含有 '$' 的非普通股代號
        all_tickers = list(set(nasdaq + other))
        clean_tickers = [t.replace('.', '-') for t in all_tickers if '$' not in t]
        return clean_tickers
    except Exception as e:
        st.error(f"獲取全美市場名單失敗: {e}")
        return []

@st.cache_data(ttl=3600) # 快取 1 小時 (股價資料)
def download_stock_data(tickers, days_needed):
    """批次下載股票歷史價格"""
    end_date = datetime.date.today()
    # 往前推足夠的天數以計算 RSI (14天) + 使用者指定的下跌天數 + 週末假日緩衝
    start_date = end_date - datetime.timedelta(days=max(60, days_needed * 2 + 30))
    
    # 將大量的 tickers 平均分批下載，避免 yfinance 發生內部執行緒錯誤 (dictionary changed size during iteration)
    batch_size = 500
    all_close_data = []
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        data = yf.download(batch, start=start_date, end=end_date, progress=False)
        
        if 'Close' in data:
            df_close = data['Close']
            # 當只下載一檔股票時，yfinance 回傳的是 Series，需轉為 DataFrame 才能跟其他批次合併
            if isinstance(df_close, pd.Series):
                df_close = df_close.to_frame(name=batch[0])
            all_close_data.append(df_close)
            
    if not all_close_data:
        return None
        
    # 合併所有的收盤價資料表
    merged_close = pd.concat(all_close_data, axis=1)
    
    # 移除重複的欄位名稱 (若有)
    merged_close = merged_close.loc[:, ~merged_close.columns.duplicated()]
    return merged_close

# --- 不再使用 get_all_fundamentals，改在迴圈內使用 yahooquery 直接批次抓取 ---

# --- 執行篩選 ---
if run_button:
    with st.spinner(f"正在抓取 {market_choice} 名單..."):
        if "S&P 500" in market_choice:
            tickers = get_sp500_tickers()
        elif "Nasdaq 100" in market_choice:
            tickers = get_nasdaq100_tickers()
        elif "納斯達克全部" in market_choice:
            tickers = get_all_nasdaq_tickers()
        else:
            tickers = get_all_us_tickers()
            if len(tickers) > 3000: # 避免一次抓太多導致 yfinance 卡死或是 API Rate Limit
                st.warning("全美市場股票數量眾多 (>4000檔)，下載時間會比較久，請耐心等候。")
        
    if not tickers:
        st.stop()
        
    st.info(f"✅ 成功獲取 {len(tickers)} 檔 {market_choice} 股票名單。")
    
    with st.spinner(f"正在下載 {len(tickers)} 檔股票近期的價格資料，這可能需要一點時間..."):
        close_data = download_stock_data(tickers, drop_days)
        
    if close_data is None or close_data.empty:
        st.error("無法取得收盤價資料。")
        st.stop()
        
    # 第一階段：價格與技術面篩選
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    price_survivors = []
    total_tickers = len(tickers)
    
    status_text.text("正在進行第一階段：技術面篩選 (跌幅)...")
    
    for i, ticker in enumerate(tickers):
        # 更新進度條
        if i % 10 == 0:
            progress_bar.progress(i / total_tickers)
            
        try:
            if ticker not in close_data.columns:
                continue
            
            series = close_data[ticker].dropna()
            
            # 取得近 X 天的資料 (包含今天，往前推 drop_days + 1)
            recent_window = series.iloc[-(drop_days + 1):]
            if len(recent_window) < (drop_days + 1):
                continue
                
            # 計算區間內的最高價、最低價與最新收盤價
            period_high = recent_window.max()
            period_low = recent_window.min()
            last_close = recent_window.iloc[-1]
            
            # 計算從最高點跌下來的幅度 (負數表示跌)
            drop_pct = (last_close - period_high) / period_high
            
            # 判斷跌幅條件 (注意 drop_pct 是負數)
            target_drop = -(drop_pct_threshold / 100.0)
            if drop_pct > target_drop: 
                continue # 跌幅不夠大
                
            # 計算谷底反彈幅度 (正數表示漲)
            rebound_pct = (last_close - period_low) / period_low
            target_rebound = rebound_pct_threshold / 100.0
            if rebound_pct < target_rebound:
                continue # 反彈不夠大
                
            price_survivors.append({
                'Ticker': ticker,
                'Drop_Pct': drop_pct,
                'Rebound_Pct': rebound_pct,
                'Last_Price': last_close
            })
        except Exception:
            continue
            
    progress_bar.progress(1.0)
    
    # 顯示第一階段結果
    st.write(f"📊 **第一階段篩選通過：** 共 {len(price_survivors)} 檔股票符合技術面條件。")
    
    if not price_survivors:
        st.warning("沒有股票符合目前的價格條件，請嘗試放寬側邊欄的篩選標準。")
        st.stop()
        
    # 第二階段：基本面篩選
    status_text.text("正在進行第二階段：基本面篩選 (yahooquery 批次獲取財報)...")
    progress_bar.progress(0)
    
    final_results = []
    
    if not price_survivors:
        st.warning("沒有股票符合技術面條件")
        st.stop()
        
    # 抽取出所有倖存者的代號進行批次查詢
    surviving_tickers = [item['Ticker'] for item in price_survivors]
    total_survivors = len(surviving_tickers)
    
    # 使用 yahooquery 進行非同步批量查詢
    try:
        yq_tickers = Ticker(surviving_tickers, asynchronous=True)
        # 一次抓取所有基本財報數據
        fin_data_dict = yq_tickers.financial_data
        # 一次抓取所有 income statement (避免每檔股票單獨請求)
        income_df = yq_tickers.income_statement(frequency='a')
    except Exception as e:
        st.error(f"取得基本面資料時發生錯誤: {e}")
        st.stop()
    
    # 建立一個快速查詢 Ticker -> (Drop_Pct, Last_Price) 的字典
    price_info_map = {item['Ticker']: item for item in price_survivors}
    
    for i, ticker in enumerate(surviving_tickers):
        progress_bar.progress(i / total_survivors)
        item = price_info_map[ticker]
        
        # 確認該 Ticker 有回傳資料 (若為 dict 代表成功)
        f_data = fin_data_dict.get(ticker, {})
        if not isinstance(f_data, dict):
            continue
            
        rev_growth = f_data.get('revenueGrowth')
        prof_margin = f_data.get('profitMargins')
        op_cashflow = f_data.get('operatingCashflow')
        curr_ratio = f_data.get('currentRatio')
        
        # 準備進行條件判斷
        target_rev_growth = rev_growth_min / 100.0
        target_prof_margin = profit_margin_min / 100.0
        
        # 1. 基本條件: 營收成長與淨利率
        if rev_growth is None or rev_growth < target_rev_growth:
            continue
        if prof_margin is None or prof_margin < target_prof_margin:
            continue
            
        # 2. 現金流與流動比率 (防禦力測試)
        if op_cashflow is None or op_cashflow <= 0:
            continue
        if curr_ratio is None or curr_ratio <= 1.2:
            continue
            
        # 3. 研發佔比持續上升測試
        # 確認 income_df 不是字串(錯誤訊息) 並且有包含這檔股票的資料
        if isinstance(income_df, str) or ticker not in income_df.index:
            continue
            
        try:
            ticker_income = income_df.loc[ticker]
            # 確認欄位存在
            if 'ResearchAndDevelopment' not in ticker_income.columns or 'TotalRevenue' not in ticker_income.columns:
                continue
                
            rnd = ticker_income['ResearchAndDevelopment']
            rev = ticker_income['TotalRevenue']
            
            # 計算每年佔比並剔除空值 (除以 0 處理)
            ratios = (rnd / rev).replace([float('inf'), -float('inf')], float('nan')).dropna()
            
            if len(ratios) < 2:
                continue
                
            is_increasing = True
            for j in range(len(ratios)-1):
                # 容許 5% 的微幅落差：如果「新的一年 (j+1)」比「舊的一年 (j)」少了超過 5%，代表衰退
                if ratios.iloc[j+1] < (ratios.iloc[j] * 0.95):
                    is_increasing = False
                    break
                    
            if not is_increasing:
                continue
                
        except Exception:
            # 解析 dataframe 發生未預期的錯誤則略過
            continue
            
        # 通過所有深層測試
        short_name = f_data.get('shortName', ticker)
        final_results.append({
            '公司名稱': short_name,
            '股票代號': ticker,
            '最新收盤價': f"${item['Last_Price']:.2f}",
            f'過去 {drop_days} 天最大跌幅': f"{item['Drop_Pct']*100:.2f}%",
            '谷底反彈幅度': f"{item['Rebound_Pct']*100:.2f}%",
            '營收成長率': f"{rev_growth*100:.2f}%",
            '淨利率': f"{prof_margin*100:.2f}%",
            '財務體質': "合格 (現金流>0, 流動比>1.2, R&D穩定提升)"
        })
                
    progress_bar.progress(1.0)
    status_text.empty()
    
    # 顯示最終結果
    st.subheader(f"🎉 最終篩選結果 ({len(final_results)} 檔)")
    
    if final_results:
        res_df = pd.DataFrame(final_results)
        # 設定 DataFrame 顯示索引為 1 開始
        res_df.index = res_df.index + 1
        st.dataframe(res_df, use_container_width=True)
        st.balloons()
    else:
        st.warning("沒有股票同時符合您的「技術面」與「基本面」條件，請嘗試放寬標準。")
    
else:
    # 預設首頁內容
    st.info("👈 請在左邊設定好條件後，點擊「🚀 開始篩選」按鈕。")

    st.markdown("### 💡 篩選策略說明")
    st.markdown("""
    這個工具結合了**左側交易（抄底）**與**基本面過濾**的策略：
    1. **跌深反彈**：找出短期內被大量拋售（累積跌幅大）的股票。
    2. **基本面保護**：為了避免買到真正出問題的公司（即所謂的「接刀子」），我們加入營收成長及淨利率的門檻，確保這家公司仍在賺錢且持續成長。
    """)
