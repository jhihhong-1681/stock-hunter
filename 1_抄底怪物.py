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
    page_title="阿紘的股票儀表板",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 阿紘的股票儀表板 - 股市抄底神器")
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
use_fundamental = st.sidebar.checkbox(
    "啟用基本面篩選 (Rule of 30)",
    value=True,
    help="啟用：只顯示「營收YoY成長率 + 淨利率 > 30%」的股票。\n關閉：直接顯示所有技術面通過的股票，速度更快。"
)
if use_fundamental:
    st.sidebar.info("採用 Rule of 30：\n(營收 YoY 成長率 + 淨利率) > 30%")
else:
    st.sidebar.warning("⚡ 快速模式：僅技術面篩選，不做基本面過濾")

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

@st.cache_data(ttl=3600*24)
def get_sp500_tickers():
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
    url = 'https://en.wikipedia.org/wiki/Nasdaq-100'
    try:
        html = fetch_url(url)
        table = pd.read_html(io.StringIO(html))
        df = table[4]
        if 'Ticker' in df.columns:
            return df['Ticker'].str.replace('.', '-', regex=False).tolist()
        return df.iloc[:, 0].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        st.error(f"獲取 Nasdaq 100 名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_all_nasdaq_tickers():
    try:
        tickers = si.tickers_nasdaq()
        return [t.replace('.', '-') for t in tickers]
    except Exception as e:
        st.error(f"獲取 Nasdaq 名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_all_us_tickers():
    try:
        nasdaq = si.tickers_nasdaq()
        other = si.tickers_other()
        all_tickers = list(set(nasdaq + other))
        clean_tickers = [t.replace('.', '-') for t in all_tickers if '$' not in t]
        return clean_tickers
    except Exception as e:
        st.error(f"獲取全美市場名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_twse_tickers():
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        data = fetch_url(url, as_json=True)
        return [item['Code'] + '.TW' for item in data if len(item['Code']) == 4]
    except Exception as e:
        st.error(f"獲取台灣上市名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_tpex_tickers():
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        data = fetch_url(url, as_json=True)
        return [item['SecuritiesCompanyCode'] + '.TWO' for item in data if len(item['SecuritiesCompanyCode']) == 4]
    except Exception as e:
        st.error(f"獲取台灣上櫃名單失敗: {e}")
        return []

@st.cache_data(ttl=3600*24)
def get_tw_emerging_tickers():
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
    mapping = {}
    import re
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        data = fetch_url(url, as_json=True)
        for item in data:
            if len(item['Code']) == 4:
                mapping[item['Code'] + '.TW'] = item['Name']
    except Exception:
        pass
    try:
        url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        data = fetch_url(url, as_json=True)
        for item in data:
             if len(item['SecuritiesCompanyCode']) == 4:
                 mapping[item['SecuritiesCompanyCode'] + '.TWO'] = item['CompanyName']
    except Exception:
        pass
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

@st.cache_data(ttl=3600)
def fetch_stock_prices_new(tickers, days_needed):
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=max(60, days_needed * 2 + 30))

    import concurrent.futures

    all_close_data = {}

    def fetch_single(ticker):
        try:
            tkr = yf.Ticker(ticker)
            hist = tkr.history(start=start_date, end=end_date, auto_adjust=False)
            if not hist.empty and 'Close' in hist.columns:
                return ticker, hist['Close']
        except Exception:
            pass
        return ticker, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_single, t): t for t in tickers}
        for future in concurrent.futures.as_completed(futures):
            ticker, series = future.result()
            if series is not None:
                all_close_data[ticker] = series

    if not all_close_data:
        return None

    merged_close = pd.DataFrame(all_close_data)
    return merged_close

@st.cache_data(ttl=3600*12, show_spinner=False)
def fetch_fundamentals_cached(tickers_tuple):
    """批次抓取基本面資料（已修正：移除已棄用的 asynchronous=True）"""
    import time
    fin_data = {}
    yq_batch_size = 25
    for j in range(0, len(tickers_tuple), yq_batch_size):
        batch = list(tickers_tuple[j:j+yq_batch_size])
        for attempt in range(3):
            try:
                yq = Ticker(batch)  # ✅ 修正：移除 asynchronous=True（新版 yahooquery 已棄用）
                res = yq.financial_data
                if isinstance(res, dict):
                    failed = sum(1 for v in res.values() if isinstance(v, str))
                    if failed == len(batch) and attempt < 2:
                        time.sleep(3 + attempt * 2)
                        continue
                    fin_data.update(res)
                    break
            except Exception:
                if attempt < 2:
                    time.sleep(3 + attempt * 2)
        time.sleep(1.5)
    return fin_data

@st.cache_data(ttl=3600*12, show_spinner=False)
def fetch_heavy_data_cached(tickers_tuple):
    """批次抓取公司簡介與現金流量（已修正：移除已棄用的 asynchronous=True）"""
    import time
    profiles = {}
    cf = {}
    price = {}
    for k in range(0, len(tickers_tuple), 25):
        chunk = list(tickers_tuple[k:k+25])
        try:
            yq = Ticker(chunk)  # ✅ 修正：移除 asynchronous=True
            p = yq.asset_profile
            c = yq.cash_flow(frequency='q')
            pr = yq.price
            if isinstance(p, dict): profiles.update(p)
            if isinstance(pr, dict): price.update(pr)
            if not isinstance(c, str):
                if len(cf) == 0: cf = c
                elif isinstance(c, pd.DataFrame) and not c.empty:
                    cf = pd.concat([cf, c])
        except Exception:
            pass
        time.sleep(1.5)
    return profiles, cf, price

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
            if len(tickers) > 3000:
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

    # 第一階段：技術面篩選
    status_text = st.empty()
    progress_bar = st.progress(0)

    price_survivors = []
    total_tickers = len(tickers)

    status_text.text("正在進行第一階段：技術面篩選 (跌幅)...")

    for i, ticker in enumerate(tickers):
        if i % 10 == 0:
            progress_bar.progress(i / total_tickers)

        try:
            if ticker not in close_data.columns:
                continue

            series = close_data[ticker].dropna()
            recent_window = series.iloc[-(drop_days + 1):]
            if len(recent_window) < (drop_days + 1):
                continue

            period_high = recent_window.max()
            period_low = recent_window.min()
            last_close = recent_window.iloc[-1]

            drop_pct = (last_close - period_high) / period_high
            target_drop = -(drop_pct_threshold / 100.0)
            if drop_pct > target_drop:
                continue

            rebound_pct = (last_close - period_low) / period_low
            target_rebound = rebound_pct_threshold / 100.0
            if rebound_pct < target_rebound:
                continue

            price_survivors.append({
                'Ticker': ticker,
                'Drop_Pct': drop_pct,
                'Rebound_Pct': rebound_pct,
                'Last_Price': last_close
            })
        except Exception:
            continue

    progress_bar.progress(1.0)
    st.write(f"📊 **第一階段篩選通過：** 共 {len(price_survivors)} 檔股票符合技術面條件。")

    if not price_survivors:
        st.warning("沒有股票符合目前的價格條件，請嘗試放寬側邊欄的篩選標準。")
        st.stop()

    # 提前獲取台股中文名稱對應表
    if "台灣" in market_choice:
        tw_mapping = get_tw_name_mapping()
    else:
        tw_mapping = {}

    final_results = []
    surviving_tickers = [item['Ticker'] for item in price_survivors]
    price_info_map = {item['Ticker']: item for item in price_survivors}

    # ── 快速模式：跳過基本面篩選 ──────────────────────────────────────
    if not use_fundamental:
        status_text.text("⚡ 快速模式：直接整理技術面結果...")
        progress_bar.progress(0)

        # 批次取得公司名稱（用 yahooquery price 模組）
        name_map = {}
        try:
            for k in range(0, len(surviving_tickers), 50):
                chunk = surviving_tickers[k:k+50]
                yq = Ticker(chunk)
                pr = yq.price
                if isinstance(pr, dict):
                    for t, v in pr.items():
                        if isinstance(v, dict):
                            name_map[t] = v.get('shortName', t)
                progress_bar.progress(min((k+50)/len(surviving_tickers), 1.0))
        except Exception:
            pass

        for item in price_survivors:
            ticker = item['Ticker']
            short_name = tw_mapping.get(ticker, name_map.get(ticker, ticker))
            sc_label = f"{item['Drop_Pct']*100:.2f}%"
            final_results.append({
                '公司名稱': short_name,
                '股票代號': ticker,
                '最新收盤價': f"${item['Last_Price']:.2f}",
                f'過去 {drop_days} 天最大跌幅': f"{item['Drop_Pct']*100:.2f}%",
                '谷底反彈幅度': f"{item['Rebound_Pct']*100:.2f}%",
                'Rule of 30 (%)': '（未篩選）',
                '營收成長 YoY': '（未篩選）',
                '淨利率': '（未篩選）',
                '近三季資本支出': '（未篩選）',
                '公司簡介': '（未篩選）',
            })

        progress_bar.progress(1.0)
        status_text.empty()

    # ── 基本面模式：套用 Rule of 30 ───────────────────────────────────
    else:
        status_text.text("正在進行第二階段：基本面篩選 (yahooquery 批次獲取財報)...")
        progress_bar.progress(0)

        try:
            fin_modules_data = fetch_fundamentals_cached(tuple(surviving_tickers))
            progress_bar.progress(0.7)
        except Exception as e:
            st.error(f"取得基本面初篩資料時發生錯誤: {e}")
            st.stop()

        if not isinstance(fin_modules_data, dict):
            fin_modules_data = {}

        rule30_passed = []
        missing_data_count = 0
        for ticker in surviving_tickers:
            f_data = fin_modules_data.get(ticker, {})
            if not isinstance(f_data, dict):
                missing_data_count += 1
                continue

            rev_growth = f_data.get('revenueGrowth')
            prof_margin = f_data.get('profitMargins')

            if rev_growth is None or prof_margin is None:
                missing_data_count += 1
                continue
            rule_of_30_val = rev_growth + prof_margin

            if rule_of_30_val > 0.3:
                rule30_passed.append({
                    'ticker': ticker,
                    'rev_growth': rev_growth,
                    'prof_margin': prof_margin,
                    'rule_of_30_val': rule_of_30_val
                })

        if missing_data_count > 0:
            st.info(f"ℹ️ 有 {missing_data_count} 檔股票的基本面資料無法取得（API 限制），已略過。"
                    f"若結果為 0 檔，可嘗試關閉左側「啟用基本面篩選」改用快速模式。")

        status_text.text(f"正在進行第二階段：深層資料獲取 ({len(rule30_passed)} 檔合格股票)...")

        heavy_profiles = {}
        heavy_cf = {}
        heavy_price = {}

        if rule30_passed:
            passed_tickers = [item['ticker'] for item in rule30_passed]
            heavy_profiles, heavy_cf, heavy_price = fetch_heavy_data_cached(tuple(passed_tickers))

        progress_bar.progress(0.9)

        for idx, passed_item in enumerate(rule30_passed):
            ticker = passed_item['ticker']
            tech_item = price_info_map[ticker]

            p_data = heavy_profiles.get(ticker, {})
            if not isinstance(p_data, dict): p_data = {}

            capex_str = "無資料"
            if not isinstance(heavy_cf, str) and ticker in heavy_cf.index:
                try:
                    ticker_cf = heavy_cf.loc[ticker]
                    if isinstance(ticker_cf, pd.DataFrame) and 'CapitalExpenditure' in ticker_cf.columns and 'periodType' in ticker_cf.columns:
                        capex_3m = ticker_cf[ticker_cf['periodType'] == '3M']['CapitalExpenditure'].dropna()
                        last_3_capex = capex_3m.tail(3)
                        capex_vals = []
                        for val in last_3_capex:
                            abs_val = abs(val)
                            if abs_val >= 1e9: capex_vals.append(f"{abs_val/1e9:.1f}B")
                            else: capex_vals.append(f"{abs_val/1e6:.1f}M")
                        if capex_vals:
                            capex_str = " -> ".join(capex_vals)
                except Exception:
                    pass

            biz_summary = "無簡介"
            eng_summary = p_data.get('longBusinessSummary', "")
            if eng_summary:
                try:
                    translator = GoogleTranslator(source='auto', target='zh-TW')
                    biz_summary = translator.translate(eng_summary[:1500])
                    biz_summary = f"【業務與優勢】\n{biz_summary}"
                except Exception as e:
                    biz_summary = f"翻譯失敗: {eng_summary[:100]}..."

            short_name = ticker
            price_data = heavy_price.get(ticker, {})
            if isinstance(price_data, dict):
                short_name = price_data.get('shortName', ticker)

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

    st.session_state['scanned'] = True
    st.session_state['final_results'] = final_results
    st.session_state['scanned_market'] = market_choice

# --- 顯示篩選結果與圖表 ---
if st.session_state.get('scanned', False):
    final_results = st.session_state.get('final_results', [])

    st.subheader(f"🎉 最終篩選結果 ({len(final_results)} 檔)")

    if final_results:
        res_df = pd.DataFrame(final_results)
        res_df.index = res_df.index + 1
        st.dataframe(res_df, use_container_width=True)

        if run_button:
            st.balloons()

        st.markdown("---")
        st.subheader("📈 個股近期走勢")

        chart_options = [f"{item['股票代號']} - {item['公司名稱']}" for item in final_results]

        if chart_options:
            selected_option = st.selectbox("請選擇要查看的近期股票線圖：", chart_options)
            selected_ticker = selected_option.split(" - ")[0]

            is_tw = selected_ticker.endswith('.TW') or selected_ticker.endswith('.TWO')

            if is_tw:
                st.info("ℹ️ 台股因版權限制，以下為本地端資料繪製近期走勢：")
                local_data = get_historical_data(selected_ticker)
                if local_data is not None:
                    st.line_chart(local_data)
                else:
                    st.warning("暫時無法取得本地走勢圖資料。")

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
                </body>
                </html>
                """
                import streamlit.components.v1 as components
                components.html(html_code, height=600)
    else:
        if use_fundamental:
            st.warning("沒有股票同時符合您的「技術面」與「基本面」條件。\n\n💡 建議：試試關閉左側「啟用基本面篩選」改用快速模式，先確認技術面結果。")
        else:
            st.warning("沒有股票符合您的技術面條件，請嘗試放寬標準。")

else:
    st.info("👈 請在左邊設定好條件後，點擊「🚀 開始篩選」按鈕。")

    st.markdown("### 💡 篩選策略說明")
    st.markdown("""
    這個工具結合了**左側交易（抄底）**與**基本面過濾**的策略：
    1. **跌深反彈**：找出短期內被大量拋售（累積跌幅大）的股票。
    2. **基本面保護 (Rule of 30)**：結合營收成長(YoY)與淨利率，要求相加 > 30%，確保找到具備高成長或高獲利能力的好公司，避免買到真正出問題的股票（接刀子）。
    3. **⚡ 快速模式**：關閉基本面篩選，直接顯示所有技術面通過的股票，適合快速瀏覽或 API 資料不穩定時使用。
    """)
