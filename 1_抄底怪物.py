import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import ssl
import yahoo_fin.stock_info as si
from deep_translator import GoogleTranslator
import requests
import io
import urllib3
import concurrent.futures
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SSL fix for Streamlit Cloud
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

# ─── 頁面設定 ─────────────────────────────────────────────────────────────────
st.set_page_config(page_title="抄底怪物 - 阿紘的股票儀表板", page_icon="🎯", layout="wide")

from utils.styles import load_css
load_css()
st.title("🎯 抄底怪物 - 股市超跌篩選器")
st.markdown("這個工具可以幫助你從 **S&P 500、Nasdaq、全美市場** 中，找出近期超跌但基本面良好的股票。\n請在左側側邊欄設定條件後點擊「開始篩選」。")

# ─── 側邊欄 ───────────────────────────────────────────────────────────────────
st.sidebar.header("⚙️ 篩選條件設定")

market_choice = st.sidebar.selectbox(
    "0. 選擇掃描的市場",
    ("S&P 500 (大型股)", "Nasdaq 100 (大型科技股)", "納斯達克全部 (Nasdaq)",
     "全美市場 (包含羅素2000中小型股)",
     "台灣上市 (TWSE)", "台灣上櫃 (TPEx)", "台灣興櫃 (Emerging)", "台灣全部市場")
)
st.sidebar.markdown("---")

drop_days = st.sidebar.selectbox(
    "1. 計算跌幅的天數 (Days)",
    options=[5, 15, 30, 60, 90, 180], index=0,
    help="計算過去幾天的累積跌幅"
)
drop_pct_threshold = st.sidebar.slider(
    "2. 要求的最少累積跌幅 (%)", min_value=0, max_value=50, value=10, step=1,
    help="從期間高點到現在，至少跌了幾%"
)
rebound_pct_threshold = st.sidebar.slider(
    "3. 要求的最少谷底反彈幅度 (%)", min_value=0, max_value=50, value=0, step=1,
    help="設定 0 代表不限制"
)

st.sidebar.markdown("---")
st.sidebar.subheader("基本面條件")
use_fundamental = st.sidebar.checkbox(
    "啟用基本面篩選 (Rule of 30)", value=True,
    help="啟用：只顯示「營收YoY成長率 + 淨利率 > 30%」的股票\n關閉：快速模式，只看技術面"
)
if use_fundamental:
    st.sidebar.info("採用 Rule of 30：\n(營收 YoY 成長率 + 淨利率) > 30%")
else:
    st.sidebar.warning("⚡ 快速模式：僅技術面篩選")

run_button = st.sidebar.button("🚀 開始篩選", type="primary", use_container_width=True)


# ─── 資料抓取函式 ─────────────────────────────────────────────────────────────

def fetch_url(url, as_json=False):
    hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    r = requests.get(url, headers=hdrs, verify=False, timeout=20)
    r.raise_for_status()
    return r.json() if as_json else r.text

@st.cache_data(ttl=3600*24)
def get_sp500_tickers():
    try:
        html = fetch_url('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
        df = pd.read_html(io.StringIO(html))[0]
        return df['Symbol'].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        st.error(f"S&P 500 名單失敗: {e}"); return []

@st.cache_data(ttl=3600*24)
def get_nasdaq100_tickers():
    try:
        html = fetch_url('https://en.wikipedia.org/wiki/Nasdaq-100')
        tables = pd.read_html(io.StringIO(html))
        df = tables[4]
        col = 'Ticker' if 'Ticker' in df.columns else df.columns[0]
        return df[col].str.replace('.', '-', regex=False).tolist()
    except Exception as e:
        st.error(f"Nasdaq 100 名單失敗: {e}"); return []

@st.cache_data(ttl=3600*24)
def get_all_nasdaq_tickers():
    try:
        return [t.replace('.', '-') for t in si.tickers_nasdaq()]
    except Exception as e:
        st.error(f"Nasdaq 名單失敗: {e}"); return []

@st.cache_data(ttl=3600*24)
def get_all_us_tickers():
    try:
        all_t = list(set(si.tickers_nasdaq() + si.tickers_other()))
        return [t.replace('.', '-') for t in all_t if '$' not in t]
    except Exception as e:
        st.error(f"全美市場名單失敗: {e}"); return []

@st.cache_data(ttl=3600*24, show_spinner=False)
def _isin_fetch(mode: int, suffix: str):
    """
    從 isin.twse.com.tw 取得台灣股票代號 + 中文名稱。
    mode: 2=上市(TWSE)  4=上櫃(TPEx)  5=興櫃(Emerging)
    回傳 (tickers_list, {ticker: name})
    isin.twse.com.tw 為 ISIN 國際標準網域，全球 IP 均可存取。
    """
    import re
    try:
        hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(
            f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={mode}",
            headers=hdrs, verify=False, timeout=25
        )
        r.encoding = 'big5'   # ISIN 頁面使用 Big5 編碼
        df = pd.read_html(io.StringIO(r.text))[0]
        tickers, names = [], {}
        for val in df.iloc[:, 0].astype(str):
            # 格式：「1234　公司名稱」（全型空白或半型空白分隔）
            parts = re.split(r'[\s\u3000]+', val.strip(), maxsplit=1)
            if parts and re.fullmatch(r'\d{4}', parts[0]):
                ticker = parts[0] + suffix
                tickers.append(ticker)
                names[ticker] = parts[1].strip() if len(parts) > 1 else parts[0]
        return tickers, names
    except Exception as e:
        return [], {}

@st.cache_data(ttl=3600*24)
def get_twse_tickers():
    tickers, _ = _isin_fetch(2, '.TW')
    if not tickers: st.error("台灣上市名單失敗（ISIN 頁面無法取得）")
    return tickers

@st.cache_data(ttl=3600*24)
def get_tpex_tickers():
    tickers, _ = _isin_fetch(4, '.TWO')
    if not tickers: st.error("台灣上櫃名單失敗（ISIN 頁面無法取得）")
    return tickers

@st.cache_data(ttl=3600*24)
def get_tw_emerging_tickers():
    tickers, _ = _isin_fetch(5, '.TWO')
    if not tickers: st.error("台灣興櫃名單失敗（ISIN 頁面無法取得）")
    return tickers

@st.cache_data(ttl=3600*24)
def get_tw_name_mapping():
    _, n2 = _isin_fetch(2, '.TW')
    _, n4 = _isin_fetch(4, '.TWO')
    _, n5 = _isin_fetch(5, '.TWO')
    return {**n2, **n4, **n5}

@st.cache_data(ttl=3600)
def fetch_stock_prices(tickers, days_needed):
    """給美股用（S&P 500 / Nasdaq 等），透過 yfinance 抓取。"""
    end_date = datetime.date.today()
    start_date = end_date - datetime.timedelta(days=max(60, days_needed * 2 + 30))
    all_data = {}

    def _fetch_one(ticker):
        try:
            hist = yf.Ticker(ticker).history(start=start_date, end=end_date, auto_adjust=False)
            if not hist.empty and 'Close' in hist.columns:
                return ticker, hist['Close']
        except: pass
        return ticker, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for ticker, series in ex.map(lambda t: _fetch_one(t), tickers):
            if series is not None:
                all_data[ticker] = series

    return pd.DataFrame(all_data) if all_data else None


# ─── 台股：直接從證交所 / 櫃買中心抓收盤價 ────────────────────────────────────

@st.cache_data(ttl=3600*20, show_spinner=False)
def _fetch_twse_day(date_str: str) -> dict:
    """
    抓單日 TWSE 全市場收盤價（直接從證交所）。
    date_str = 'YYYYMMDD'；非交易日回傳 {}。
    回傳 { '4碼代號': float }
    """
    import re
    try:
        hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(
            f"https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY_ALL"
            f"?response=json&date={date_str}",
            headers=hdrs, verify=False, timeout=15
        )
        d = r.json()
        # 若請求非交易日，TWSE 會回傳最近的交易日；比對日期確認是否符合
        if d.get('stat') != 'OK' or not d.get('data'):
            return {}
        if d.get('date', '') != date_str:
            return {}  # 非交易日
        result = {}
        for row in d['data']:
            code = str(row[0]).strip()
            if not re.fullmatch(r'\d{4}', code):
                continue
            try:
                p = str(row[7]).replace(',', '').strip()
                if p and p != '--':
                    result[code] = float(p)
            except:
                pass
        return result
    except:
        return {}


@st.cache_data(ttl=3600*20, show_spinner=False)
def _fetch_tpex_day(date_roc: str) -> dict:
    """
    抓單日 TPEx 全市場收盤價（直接從櫃買中心）。
    date_roc = 'YYY/MM/DD'（民國年）；非交易日回傳 {}。
    回傳 { '4碼代號': float }
    """
    import re
    try:
        hdrs = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(
            f"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes"
            f"?response=json&date={date_roc}",
            headers=hdrs, verify=False, timeout=15
        )
        d = r.json()
        tables = d.get('tables', [])
        if not tables or not tables[0].get('data'):
            return {}
        result = {}
        for row in tables[0]['data']:
            code = str(row[0]).strip()
            if not re.fullmatch(r'\d{4}', code):
                continue
            try:
                p = str(row[2]).replace(',', '').strip()
                if p and p != '--':
                    result[code] = float(p)
            except:
                pass
        return result
    except:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_tw_prices_from_exchange(days_needed: int,
                                   include_twse: bool,
                                   include_tpex: bool):
    """
    直接從證交所 / 櫃買中心抓歷史收盤價，不走 Yahoo Finance。
    回傳 DataFrame：index=date，columns=ticker（2330.TW / 3008.TWO）。
    """
    # 多準備 1.8 倍天數以因應假日
    candidate_count = int(days_needed * 1.8) + 20
    candidates: list[datetime.date] = []
    d = datetime.date.today()
    while len(candidates) < candidate_count:
        if d.weekday() < 5:          # 週一～五
            candidates.append(d)
        d -= datetime.timedelta(days=1)

    def fetch_day(date: datetime.date):
        day: dict = {}
        if include_twse:
            for code, price in _fetch_twse_day(date.strftime('%Y%m%d')).items():
                day[code + '.TW'] = price
        if include_tpex:
            roc_str = f"{date.year - 1911}/{date.strftime('%m/%d')}"
            for code, price in _fetch_tpex_day(roc_str).items():
                day[code + '.TWO'] = price
        return date, day

    price_by_date: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for date, day in ex.map(fetch_day, candidates):
            if day:                  # 有資料 → 是交易日
                price_by_date[date] = day

    if not price_by_date:
        return None

    df = pd.DataFrame(price_by_date).T
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    return df

@st.cache_data(ttl=3600*6, show_spinner=False)
def fetch_fundamentals_yf(tickers_tuple):
    """
    用 yfinance .info 抓取基本面資料（自帶 Yahoo Finance 認證，比 yahooquery 穩定）
    回傳 dict: { ticker: { revenueGrowth, profitMargins, shortName, longBusinessSummary } }
    """
    result = {}

    def _fetch_one(ticker):
        for attempt in range(2):
            try:
                info = yf.Ticker(ticker).info
                return ticker, {
                    'revenueGrowth':        info.get('revenueGrowth'),
                    'profitMargins':        info.get('profitMargins'),
                    'shortName':            info.get('shortName', ticker),
                    'longBusinessSummary':  info.get('longBusinessSummary', ''),
                }
            except Exception:
                if attempt == 0: time.sleep(1)
        return ticker, {}

    # 最多 10 個 thread 並發，避免被 rate limit
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(_fetch_one, t): t for t in tickers_tuple}
        for future in concurrent.futures.as_completed(futures):
            ticker, data = future.result()
            result[ticker] = data

    return result

@st.cache_data(ttl=3600)
def get_historical_data(ticker):
    try:
        hist = yf.download(ticker, period="6mo", progress=False)
        if not hist.empty and 'Close' in hist:
            return hist['Close']
    except: pass
    return None


# ─── 主邏輯：執行篩選 ────────────────────────────────────────────────────────
if run_button:
    # 1. 取得股票名單
    with st.spinner(f"正在抓取 {market_choice} 名單..."):
        if "S&P 500" in market_choice:          tickers = get_sp500_tickers()
        elif "Nasdaq 100" in market_choice:      tickers = get_nasdaq100_tickers()
        elif "納斯達克全部" in market_choice:    tickers = get_all_nasdaq_tickers()
        elif "全美市場" in market_choice:
            tickers = get_all_us_tickers()
            if len(tickers) > 3000: st.warning("全美市場數量龐大，載入時間較長，請耐心等候。")
        elif "台灣上市" in market_choice:        tickers = get_twse_tickers()
        elif "台灣上櫃" in market_choice:        tickers = get_tpex_tickers()
        elif "台灣興櫃" in market_choice:        tickers = get_tw_emerging_tickers()
        elif "台灣全部市場" in market_choice:
            tickers = get_twse_tickers() + get_tpex_tickers() + get_tw_emerging_tickers()

    if not tickers:
        st.stop()
    st.info(f"✅ 成功獲取 {len(tickers)} 檔 {market_choice} 股票名單。")

    # 2. 下載收盤價（yfinance 支援 .TW / .TWO，台股與美股共用同一路徑）
    with st.spinner(f"正在下載 {len(tickers)} 檔股票價格資料..."):
        close_data = fetch_stock_prices(tickers, drop_days)
    if close_data is None or close_data.empty:
        st.error("無法取得收盤價資料。"); st.stop()

    # 3. 第一階段：技術面篩選
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.text("第一階段：技術面篩選（跌幅）...")

    price_survivors = []
    for i, ticker in enumerate(tickers):
        if i % 10 == 0:
            progress_bar.progress(i / len(tickers))
        try:
            if ticker not in close_data.columns: continue
            series = close_data[ticker].dropna()
            window = series.iloc[-(drop_days + 1):]
            if len(window) < drop_days + 1: continue

            high  = window.max()
            low   = window.min()
            last  = window.iloc[-1]

            drop_pct    = (last - high) / high
            rebound_pct = (last - low)  / low

            if drop_pct    > -(drop_pct_threshold / 100): continue
            if rebound_pct < rebound_pct_threshold / 100: continue

            price_survivors.append({
                'Ticker': ticker, 'Drop_Pct': drop_pct,
                'Rebound_Pct': rebound_pct, 'Last_Price': last
            })
        except: continue

    progress_bar.progress(1.0)
    st.write(f"📊 **第一階段篩選通過：** 共 {len(price_survivors)} 檔股票符合技術面條件。")

    if not price_survivors:
        st.warning("沒有股票符合技術面條件，請放寬標準。"); st.stop()

    tw_mapping = get_tw_name_mapping() if "台灣" in market_choice else {}
    price_info_map = {item['Ticker']: item for item in price_survivors}
    surviving_tickers = [item['Ticker'] for item in price_survivors]
    final_results = []

    # ── 快速模式：跳過基本面 ──────────────────────────────────────────────────
    if not use_fundamental:
        status_text.text("⚡ 快速模式：整理結果中...")
        progress_bar.progress(0)
        # 批次取公司名稱
        name_map = {}
        chunks = [surviving_tickers[i:i+50] for i in range(0, len(surviving_tickers), 50)]
        for ci, chunk in enumerate(chunks):
            try:
                chunk_data = yf.download(chunk, period="1d", progress=False)
                # 用 info 取名稱（小批量）
                for t in chunk[:10]:  # 只取前10個名稱避免太慢
                    try: name_map[t] = yf.Ticker(t).info.get('shortName', t)
                    except: name_map[t] = t
            except: pass
            progress_bar.progress((ci+1)/len(chunks))

        for item in price_survivors:
            t = item['Ticker']
            final_results.append({
                '公司名稱':              tw_mapping.get(t, name_map.get(t, t)),
                '股票代號':              t,
                '最新收盤價':            item['Last_Price'],
                f'過去{drop_days}天跌幅(%)': abs(item['Drop_Pct']) * 100,
                '谷底反彈(%)':           item['Rebound_Pct'] * 100,
            })
        progress_bar.progress(1.0)
        status_text.empty()

    # ── 基本面模式：Rule of 30 ─────────────────────────────────────────────────
    else:
        status_text.text(f"第二階段：基本面篩選（用 yfinance 抓取 {len(surviving_tickers)} 檔財報）...")
        progress_bar.progress(0)

        fin_data = fetch_fundamentals_yf(tuple(surviving_tickers))
        progress_bar.progress(0.8)

        missing = sum(1 for t in surviving_tickers
                      if not fin_data.get(t) or
                         fin_data[t].get('revenueGrowth') is None or
                         fin_data[t].get('profitMargins') is None)

        if missing > 0:
            st.info(f"ℹ️ {missing} 檔股票基本面資料不完整（已略過）。"
                    f"若最終結果為 0，可嘗試關閉左側「啟用基本面篩選」先看技術面結果。")

        rule30_passed = []
        for ticker in surviving_tickers:
            d = fin_data.get(ticker, {})
            rev    = d.get('revenueGrowth')
            margin = d.get('profitMargins')
            if rev is None or margin is None: continue
            rule30 = rev + margin
            if rule30 > 0.30:
                rule30_passed.append({
                    'ticker': ticker, 'rev': rev,
                    'margin': margin, 'rule30': rule30
                })

        st.write(f"🔍 通過 Rule of 30 篩選：{len(rule30_passed)} 檔")
        progress_bar.progress(0.9)

        for item in rule30_passed:
            t     = item['ticker']
            tech  = price_info_map[t]
            d     = fin_data.get(t, {})
            name  = tw_mapping.get(t, d.get('shortName', t))

            # 公司簡介（翻譯）
            summary = d.get('longBusinessSummary', '')
            biz = '無簡介'
            if summary:
                try:
                    translator = GoogleTranslator(source='auto', target='zh-TW')
                    biz = translator.translate(summary[:1500])
                    biz = f"【業務與優勢】\n{biz}"
                except:
                    biz = summary[:200] + '...'

            final_results.append({
                '公司名稱':              name,
                '股票代號':              t,
                '最新收盤價':            tech['Last_Price'],
                f'過去{drop_days}天跌幅(%)': abs(tech['Drop_Pct']) * 100,
                '谷底反彈(%)':           tech['Rebound_Pct'] * 100,
                'Rule of 30 (%)':        item['rule30'] * 100,
                '營收成長 YoY (%)':      item['rev'] * 100,
                '淨利率 (%)':            item['margin'] * 100,
                '公司簡介':              biz,
            })

        progress_bar.progress(1.0)
        status_text.empty()

    st.session_state['scanned']        = True
    st.session_state['final_results']  = final_results
    st.session_state['scanned_market'] = market_choice


# ─── 顯示結果 ────────────────────────────────────────────────────────────────
if st.session_state.get('scanned', False):
    final_results = st.session_state.get('final_results', [])
    st.subheader(f"🎉 最終篩選結果 ({len(final_results)} 檔)")

    if final_results:
        df = pd.DataFrame(final_results)
        df.index = df.index + 1
        drop_col = next((c for c in df.columns if '天跌幅' in c), None)
        fmt = {'最新收盤價': '${:.2f}', '谷底反彈(%)': '{:.1f}%'}
        if drop_col:
            fmt[drop_col] = '{:.1f}%'
        if 'Rule of 30 (%)' in df.columns:
            fmt.update({'Rule of 30 (%)': '{:.1f}%', '營收成長 YoY (%)': '{:.1f}%', '淨利率 (%)': '{:.1f}%'})
        styled = df.style.format(fmt)
        if drop_col:
            styled = styled.bar(subset=[drop_col], color='#ff4b4b', vmin=0, vmax=50)
        if '谷底反彈(%)' in df.columns:
            styled = styled.bar(subset=['谷底反彈(%)'], color='#21c354', vmin=0, vmax=30)
        if 'Rule of 30 (%)' in df.columns:
            styled = styled.bar(subset=['Rule of 30 (%)'], color='#1f77b4', vmin=0, vmax=100)
        st.dataframe(styled, use_container_width=True)
        if run_button: st.balloons()

        st.markdown("---")
        st.subheader("📈 個股近期走勢")
        options = [f"{r['股票代號']} - {r['公司名稱']}" for r in final_results]
        selected = st.selectbox("請選擇要查看的股票線圖：", options)
        sel_ticker = selected.split(" - ")[0]
        is_tw = sel_ticker.endswith('.TW') or sel_ticker.endswith('.TWO')

        if is_tw:
            st.info("ℹ️ 台股因版權限制以本地折線圖顯示：")
            data = get_historical_data(sel_ticker)
            if data is not None: st.line_chart(data)
            else: st.warning("暫時無法取得走勢圖。")
            sym = f"TWSE:{sel_ticker.replace('.TW','')}" if sel_ticker.endswith('.TW') \
                  else f"TPEX:{sel_ticker.replace('.TWO','')}"
            st.markdown(f"👉 **[在 TradingView 開啟完整線圖](https://www.tradingview.com/chart/?symbol={sym})**")
        else:
            html_code = f"""<html><head><style>body{{margin:0;padding:0;overflow:hidden}}</style></head><body>
            <div class="tradingview-widget-container">
              <div id="tv_chart" style="height:600px;width:100%"></div>
              <script src="https://s3.tradingview.com/tv.js"></script>
              <script>new TradingView.widget({{
                "autosize":true,"symbol":"{sel_ticker}","interval":"D",
                "timezone":"Asia/Taipei","theme":"light","style":"1","locale":"zh_TW",
                "enable_publishing":false,"container_id":"tv_chart"
              }});</script>
            </div></body></html>"""
            import streamlit.components.v1 as components
            components.html(html_code, height=600)
    else:
        if use_fundamental:
            st.warning("沒有股票同時符合「技術面」與「基本面 Rule of 30」條件。\n\n"
                       "💡 建議：試試關閉左側「啟用基本面篩選」確認技術面有結果，或放寬跌幅門檻。")
        else:
            st.warning("沒有股票符合技術面條件，請放寬標準。")

else:
    st.info("👈 請在左邊設定好條件後，點擊「🚀 開始篩選」按鈕。")
    st.markdown("""### 💡 篩選策略說明
這個工具結合了**左側交易（抄底）**與**基本面過濾**的策略：
1. **跌深反彈**：找出短期內被大量拋售（累積跌幅大）的股票。
2. **基本面保護 (Rule of 30)**：營收成長(YoY) + 淨利率 > 30%，確保不接刀。
3. **⚡ 快速模式**：關閉基本面篩選，直接看技術面通過的股票。""")
