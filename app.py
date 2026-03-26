import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import urllib.request
import ssl
import yahoo_fin.stock_info as si
from yahooquery import Ticker
from deep_translator import GoogleTranslator

# 關閉全域 SSL 憑證驗證 (解決 Streamlit Cloud 抓取台股或是維基百科時的憑證錯誤)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
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
    ("S&P 500 (大型股)", "Nasdaq 100 (大型科技股)", "納斯達克全部 (Nasdaq)", "全美市場 (包含羅素2000中小型股)", 
     "台灣上市 (TWSE)", "台灣上櫃 (TPEx)", "台灣興櫃 (Emerging)", "台灣全部市場")
)
st.sidebar.markdown("---")

# 1. 下跌天數
drop_days = st.sidebar.selectbox(
    "1. 計算跌幅的天數 (Days)", 
    options=[5, 15, 30, 60, 90, 180],
    index=0,
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
st.sidebar.info("採用 Rule of 30：\n(營收 YoY 成長率 + 淨利率) > 30%")

run_button = st.sidebar.button("🚀 開始篩選", type="primary", use_container_width=True)


# --- 核心邏輯與快取 (Caching) ---
import requests
import io
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_url(url, as_json=False):
    """使用 requests 並且關閉 SSL 憑證驗證，解決在 Linux 伺服器上的憑證報錯問題"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(url, headers=headers, verify=False, timeout=20)
    response.raise_for_status()
    if as_json:
        return response.json()
    return response.text

# 使用 st.cache_data 避免每次調整參數都重新下載資料
@st.cache_data(ttl=3600*24) # 快取 24 小時
def get_sp500_tickers():
    """從維基百科獲取 S&P 500 股票代號"""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    try:
        html = fetch_url(url)
        table = pd.read_html(io.StringIO(html))
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
    try:
        html = fetch_url(url)
        table = pd.read_html(io.StringIO(html))
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

@st.cache_data(ttl=3600*24)
def get_twse_tickers():
    """獲取台灣上市股票"""
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        data = fetch_url(url, as_json=True)
        return [item['Code'] + '.TW' for item in data if len(item['Code']) == 4]
    except Exception as e:
        st.error(f"獲取台灣上市名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_tpex_tickers():
    """獲取台灣上櫃股票"""
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        data = fetch_url(url, as_json=True)
        return [item['SecuritiesCompanyCode'] + '.TWO' for item in data if len(item['SecuritiesCompanyCode']) == 4]
    except Exception as e:
        st.error(f"獲取台灣上櫃名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_tw_emerging_tickers():
    """獲取台灣興櫃股票"""
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=5"
        html = fetch_url(url)
        dfs = pd.read_html(io.StringIO(html))
        df = dfs[0]
        import re
        series = df.iloc[:, 0].astype(str)
        tickers = []
        for val in series:
            match = re.match(r'^(\d{4})[^\d]', val)
            if match:
                tickers.append(match.group(1) + '.TWO')
        return tickers
    except Exception as e:
        st.error(f"獲取台灣興櫃名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_tw_name_mapping():
    """獲取台灣股票代號到中文名稱的映射"""
    mapping = {}
    import re
    # TWSE
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        data = fetch_url(url, as_json=True)
        for item in data:
            if len(item['Code']) == 4:
                mapping[item['Code'] + '.TW'] = item['Name']
    except Exception:
        pass
    # TPEx
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        data = fetch_url(url, as_json=True)
        for item in data:
             if len(item['SecuritiesCompanyCode']) == 4:
                 mapping[item['SecuritiesCompanyCode'] + '.TWO'] = item['CompanyName']
    except Exception:
        pass
    # Emerging
    try:
        url = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=5"
        html = fetch_url(url)
        dfs = pd.read_html(io.StringIO(html))
        df = dfs[0]
        series = df.iloc[:, 0].astype(str)
        for val in series:
            match = re.match(r'^(\d{4})[^\d]+(.*)$', val)
            if match:
                mapping[match.group(1) + '.TWO'] = match.group(2).strip()
    except Exception:
        pass
    return mapping

@st.cache_data(ttl=3600) # 快取 1 小時 (股價資料)
def fetch_stock_prices_new(tickers, days_needed):
    """批次下載股票歷史價格"""
    end_date = datetime.date.today()
    # 往前推足夠的天數以計算 RSI (14天) + 使用者指定的下跌天數 + 週末假日緩衝
    start_date = end_date - datetime.timedelta(days=max(60, days_needed * 2 + 30))
    
    # 將大量的 tickers 平均分批下載，避免 yfinance 發生內部執行緒錯誤 (dictionary changed size during iteration)
    batch_size = 500
    all_close_data = []
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        data = yf.download(batch, start=start_date, end=end_date, progress=False, threads=True)
        
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

# --- 輔助函數：取得本地歷史資料供台股繪圖 ---
@st.cache_data(ttl=3600)
def get_historical_data(ticker):
    try:
        hist = yf.download(ticker, period="6mo", progress=False)
        if not hist.empty and 'Close' in hist:
            return hist['Close']
    except:
        pass
    return None

# --- 執行篩選 ---
if run_button:
    with st.spinner(f"正在抓取 {market_choice} 名單..."):
        if "S&P 500" in market_choice:
            tickers = get_sp500_tickers()
        elif "Nasdaq 100" in market_choice:
            tickers = get_nasdaq100_tickers()
        elif "納斯達克全部" in market_choice:
            tickers = get_all_nasdaq_tickers()
        elif "全美市場" in market_choice:
            tickers = get_all_us_tickers()
            if len(tickers) > 3000: # 避免一次抓太多導致 yfinance 卡死或是 API Rate Limit
                st.warning("全美市場股票數量眾多 (>4000檔)，下載時間會比較久，請耐心等候。")
        elif "台灣上市" in market_choice:
            tickers = get_twse_tickers()
        elif "台灣上櫃" in market_choice:
            tickers = get_tpex_tickers()
        elif "台灣興櫃" in market_choice:
            tickers = get_tw_emerging_tickers()
        elif "台灣全部市場" in market_choice:
            tickers = get_twse_tickers() + get_tpex_tickers() + get_tw_emerging_tickers()
            if len(tickers) > 1000:
                st.warning("台灣全部市場股票數量較多，下載時間會比較久，請耐心等候。")
        
    if not tickers:
        st.stop()
        
    st.info(f"✅ 成功獲取 {len(tickers)} 檔 {market_choice} 股票名單。")
    
    with st.spinner(f"正在下載 {len(tickers)} 檔股票近期的價格資料，這可能需要一點時間..."):
        close_data = fetch_stock_prices_new(tickers, drop_days)
        
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
    
    # 提前獲取台股中文名稱對應表
    if "台灣" in market_choice:
        tw_mapping = get_tw_name_mapping()
    else:
        tw_mapping = {}
    
    if not price_survivors:
        st.warning("沒有股票符合技術面條件")
        st.stop()
        
    # 抽取出所有倖存者的代號進行批次查詢
    surviving_tickers = [item['Ticker'] for item in price_survivors]
    total_survivors = len(surviving_tickers)
    
    # 建立一個快速查詢 Ticker -> (Drop_Pct, Last_Price) 的字典
    price_info_map = {item['Ticker']: item for item in price_survivors}
    
    # 階段 2-1: 恢復您原本穩定且絕對不會被 Cloud 阻擋的原生寫法 (financial_data)，但結合最快的「分段懶加載」技術
    status_text.text("正在進行第二階段：基本面初篩 (快速抓取營收與淨利率)...")
    try:
        yq_tickers = Ticker(surviving_tickers, asynchronous=True)
        fin_modules_data = yq_tickers.financial_data
    except Exception as e:
        st.error(f"取得基本面初篩資料時發生錯誤: {e}")
        st.stop()
        
    if not isinstance(fin_modules_data, dict):
        fin_modules_data = {}
        
    rule30_passed = []
    for ticker in surviving_tickers:
        f_data = fin_modules_data.get(ticker, {})
        if not isinstance(f_data, dict): continue
        
        rev_growth = f_data.get('revenueGrowth')
        prof_margin = f_data.get('profitMargins')
        
        if rev_growth is None or prof_margin is None: continue
        rule_of_30_val = rev_growth + prof_margin
        
        if rule_of_30_val > 0.3:
            rule30_passed.append({
                'ticker': ticker,
                'rev_growth': rev_growth,
                'prof_margin': prof_margin,
                'rule_of_30_val': rule_of_30_val
            })
            
    # 階段 2-2: 只針對「通過」 Rule of 30 的少數菁英股票，去抓取極度耗時的「公司簡介」與「現金流量表」
    status_text.text(f"正在進行第二階段：基本面深層資料獲取 (抓取 {len(rule30_passed)} 檔合格股票的財報與簡介)...")
    heavy_profiles = {}
    heavy_cf = {}
    heavy_price = {}
    
    if rule30_passed:
        passed_tickers = [item['ticker'] for item in rule30_passed]
        try:
            yq_heavy = Ticker(passed_tickers, asynchronous=True)
            heavy_profiles = yq_heavy.asset_profile
            heavy_cf = yq_heavy.cash_flow(frequency='q')
            heavy_price = yq_heavy.price
            
            if not isinstance(heavy_profiles, dict): heavy_profiles = {}
            if not isinstance(heavy_price, dict): heavy_price = {}
        except Exception:
            pass
            
    progress_bar.progress(0.9)
            
    # 整合最終資料
    for idx, passed_item in enumerate(rule30_passed):
        ticker = passed_item['ticker']
        tech_item = price_info_map[ticker]
        
        p_data = heavy_profiles.get(ticker, {})
        if not isinstance(p_data, dict): p_data = {}
        
        # 3. 取得近三季資本支出 (不作為篩選條件，僅顯示)
        capex_str = "無資料"
        if not isinstance(heavy_cf, str) and ticker in heavy_cf.index:
            try:
                ticker_cf = heavy_cf.loc[ticker]
                if isinstance(ticker_cf, pd.DataFrame) and 'CapitalExpenditure' in ticker_cf.columns and 'periodType' in ticker_cf.columns:
                    capex_3m = ticker_cf[ticker_cf['periodType'] == '3M']['CapitalExpenditure'].dropna()
                    last_3_capex = capex_3m.tail(3)
                    capex_vals = []
                    for val in last_3_capex:
                        abs_val = abs(val) # 資本支出通常是現金流出(負數)
                        if abs_val >= 1e9: capex_vals.append(f"{abs_val/1e9:.1f}B")
                        else: capex_vals.append(f"{abs_val/1e6:.1f}M")
                    if capex_vals:
                        capex_str = " -> ".join(capex_vals)
            except Exception:
                pass
            
        # 取得公司簡介並翻譯
        biz_summary = "無簡介"
        eng_summary = p_data.get('longBusinessSummary', "")
        if eng_summary:
            try:
                # 翻譯成繁體中文 (為了避免過長，最多取前1500字元翻譯)
                translator = GoogleTranslator(source='auto', target='zh-TW')
                biz_summary = translator.translate(eng_summary[:1500])
                biz_summary = f"【業務與優勢】\n{biz_summary}"
            except Exception as e:
                biz_summary = f"翻譯失敗: {eng_summary[:100]}..."
            
        short_name = heavy_price.get(ticker, {}).get('shortName', ticker)
        if ticker in tw_mapping:
            short_name = tw_mapping[ticker]
            
        final_results.append({
            '公司名稱': short_name,
            '股票代號': ticker,
            '最新收盤價': f"${tech_item['Last_Price']:.2f}",
            f'過去 {drop_days} 天最大跌幅': f"{tech_item['Drop_Pct']*100:.2f}%",
            '谷底反彈幅度': f"{tech_item['Rebound_Pct']*100:.2f}%",
            'Rule of 30 (%)': f"{passed_item['rule_of_30_val']*100:.1f}%",
            '營收成長 YoY': f"{passed_item['rev_growth']*100:.1f}%",
            '淨利率': f"{passed_item['prof_margin']*100:.1f}%",
            '近三季資本支出': capex_str,
            '公司簡介': biz_summary
        })
                
    progress_bar.progress(1.0)
    status_text.empty()
    
    # 將結果儲存到 session state，即使重整也不會遺失
    st.session_state['scanned'] = True
    st.session_state['final_results'] = final_results
    st.session_state['scanned_market'] = market_choice

# --- 顯示篩選結果與圖表 (獨立於 run_button) ---
if st.session_state.get('scanned', False):
    final_results = st.session_state.get('final_results', [])
    
    # 顯示最終結果
    st.subheader(f"🎉 最終篩選結果 ({len(final_results)} 檔)")
    
    if final_results:
        res_df = pd.DataFrame(final_results)
        # 設定 DataFrame 顯示索引為 1 開始
        res_df.index = res_df.index + 1
        st.dataframe(res_df, use_container_width=True)
        
        if run_button: # 只在按鈕剛按下的那次放氣球
            st.balloons()
            
        # 新增 TradingView 圖表或本地圖表區塊
        st.markdown("---")
        st.subheader("📈 個股近期走勢")
        
        # 建立選項清單 (例如: "2330.TW - 台積電")
        chart_options = [f"{item['股票代號']} - {item['公司名稱']}" for item in final_results]
        
        if chart_options:
            selected_option = st.selectbox("請選擇要查看的近期股票線圖：", chart_options)
            selected_ticker = selected_option.split(" - ")[0]
            
            is_tw = selected_ticker.endswith('.TW') or selected_ticker.endswith('.TWO')
            
            if is_tw:
                st.info("ℹ️ 由於【台灣證交所】的嚴格版權限制，TradingView 官方禁止任何包含此工具在內的第三方網站『直接嵌入』台股的線圖，這就是為什麼強制顯示出來會被 TradingView 封鎖的緣故！因此，以下為您拉取本地端資料繪製近期走勢：")
                
                # 本地繪圖
                local_data = get_historical_data(selected_ticker)
                if local_data is not None:
                    st.line_chart(local_data)
                else:
                    st.warning("暫時無法取得本地走勢圖資料。")
                
                # 將 YF Ticker 轉換為 TradingView 格式以產生連結
                tv_symbol = selected_ticker
                if selected_ticker.endswith(".TW"):
                    tv_symbol = f"TWSE:{selected_ticker.replace('.TW', '')}"
                elif selected_ticker.endswith(".TWO"):
                    tv_symbol = f"TPEX:{selected_ticker.replace('.TWO', '')}"
                    
                tv_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"
                st.markdown(f"👉 **[請點擊這裡，直接在 TradingView 官網開啟 {selected_option} 完整線圖]({tv_url})**")
            else:
                tv_symbol = selected_ticker
                
                html_code = f"""
                <!DOCTYPE html>
                <html>
                <head>
                <style>
                  body {{ margin: 0; padding: 0; overflow: hidden; }}
                </style>
                </head>
                <body>
                <!-- TradingView Widget BEGIN -->
                <div class="tradingview-widget-container">
                  <div id="tradingview_12345" style="height: 600px; width: 100%;"></div>
                  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
                  <script type="text/javascript">
                  new TradingView.widget(
                  {{
                  "autosize": true,
                  "symbol": "{tv_symbol}",
                  "interval": "D",
                  "timezone": "Asia/Taipei",
                  "theme": "light",
                  "style": "1",
                  "locale": "zh_TW",
                  "enable_publishing": false,
                  "hide_top_toolbar": false,
                  "hide_legend": false,
                  "save_image": false,
                  "container_id": "tradingview_12345"
                }}
                  );
                  </script>
                </div>
                <!-- TradingView Widget END -->
                </body>
                </html>
                """
                import streamlit.components.v1 as components
                components.html(html_code, height=600)
    else:
        st.warning("沒有股票同時符合您的「技術面」與「基本面」條件，請嘗試放寬標準。")
    
else:
    # 預設首頁內容
    st.info("👈 請在左邊設定好條件後，點擊「🚀 開始篩選」按鈕。")

    st.markdown("### 💡 篩選策略說明")
    st.markdown("""
    這個工具結合了**左側交易（抄底）**與**基本面過濾**的策略：
    1. **跌深反彈**：找出短期內被大量拋售（累積跌幅大）的股票。
    2. **基本面保護 (Rule of 30)**：結合營收成長(YoY)與淨利率，要求相加 > 30%，確保找到具備高成長或高獲利能力的好公司，避免買到真正出問題的股票（接刀子）。
    """)
