import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.express as px
import time
import io

# --- 頁面設定 ---
st.set_page_config(
    page_title="每日行情 - 阿紘的股票儀表板",
    page_icon="📈",
    layout="wide"
)

st.title("📈 市場產業熱力圖 (Treemap)")
st.markdown("以方塊圖一目了然觀察台股與美股的產業資金流向。板塊大小代表成交金額或市值，**顏色為紅漲綠跌。**")

# --- 1. 大盤指數概況 ---
st.header("📊 全球重點大盤近五日走勢")

INDICES = {
    "^TWII": "台灣加權指數 (TAIEX)",
    "^GSPC": "標普 500 (S&P 500)",
    "^IXIC": "納斯達克 (Nasdaq)",
    "DIA": "道瓊工業ETF (Dow Jones)",
    "^SOX": "費城半導體 (PHLX)"
}

@st.cache_data(ttl=1800)
def fetch_indices_data():
    tickers = list(INDICES.keys())
    try:
        data = yf.download(tickers, period="5d", progress=False)
        results = {}
        for ticker in tickers:
            if ticker in data['Close']:
                close_series = data['Close'][ticker].dropna()
                if len(close_series) >= 2:
                    last_close = float(close_series.iloc[-1])
                    prev_close = float(close_series.iloc[-2])
                    change = last_close - prev_close
                    change_pct = (change / prev_close) * 100
                    results[ticker] = {
                        "price": last_close,
                        "change": change,
                        "change_pct": change_pct
                    }
        return results
    except Exception as e:
        return None

indices_data = fetch_indices_data()

if indices_data:
    cols = st.columns(len(INDICES))
    for idx, (ticker, name) in enumerate(INDICES.items()):
        if ticker in indices_data:
            info = indices_data[ticker]
            with cols[idx]:
                st.metric(
                    label=name,
                    value=f"{info['price']:,.2f}",
                    delta=f"{info['change']:,.2f} ({info['change_pct']:.2f}%)"
                )
else:
    st.warning("暫時無法取得大盤指數資料。")

st.markdown("---")

# --- 2. 產業熱力圖 ---
st.header("🔍 產業板塊漲跌幅 (熱力圖)")

col1, col2 = st.columns([1, 1])
with col1:
    selected_market = st.radio("請選擇市場：", ["台灣股市 (上市櫃全市場)", "美國股市 (S&P 500)"], horizontal=True)
with col2:
    timeframe_map = {
        "一日 (Daily)": "5d", # 抓5天取最新和前一天
        "一週 (1 Week)": "1mo", # 抓1個月取最新和往前約5天
        "一個月 (1 Month)": "3mo", 
        "三個月 (3 Months)": "6mo"
    }
    selected_tf = st.radio("請選擇漲跌幅區間：", list(timeframe_map.keys()), horizontal=True)

st.markdown("---")
top_n = st.slider("顯示前 N 大活躍/權值股 (縮小範圍可獲得更快的載入速度，並過濾冷門股)", min_value=50, max_value=500, value=150, step=50)
st.info("💡 **互動提示**：您可以直接點擊下方圖表中的板塊（例如『半導體業』），圖表會自動放大該產業的內部個股！點擊上方標題列即可返回全局。")

# 靜態字典配置區
TWSE_INDUSTRY_MAP = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械",
    "06": "電器電纜", "07": "化學工業", "08": "生技醫療業", "09": "玻璃陶瓷", "10": "造紙工業",
    "11": "鋼鐵工業", "12": "橡膠工業", "13": "汽車工業", "14": "建材營造", "15": "航運業",
    "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨", "19": "綜合", "20": "其他",
    "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業", "25": "電腦及週邊設備業",
    "26": "光電業", "27": "通信網路業", "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
    "31": "其他電子業", "32": "文化創意業", "33": "農業科技業", "34": "電子商務業"
}

@st.cache_data(ttl=3600*12)
def get_tw_industry_data():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        url_info = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        info_json = requests.get(url_info, headers=headers, verify=False, timeout=10).json()
        industry_map = {item['公司代號']: item['產業別'] for item in info_json if '公司代號' in item}
        
        url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        price_json = requests.get(url_price, headers=headers, verify=False, timeout=10).json()
        return industry_map, price_json
    except Exception as e:
        return {}, []

@st.cache_data(ttl=3600*24)
def get_sp500_components():
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, verify=False)
        table = pd.read_html(io.StringIO(r.text))[0]
        tickers = table['Symbol'].str.replace('.', '-', regex=False).tolist()
        sectors = table['GICS Sector'].tolist()
        names = table['Security'].tolist()
        return tickers, sectors, names
    except Exception:
        return [], [], []

@st.cache_data(ttl=3600)
def fetch_historical_prices(tickers, period):
    # 分批避免 Timeout
    df = yf.download(tickers, period=period, progress=False, threads=True)
    return df

def calculate_period_change(df, tf_label):
    if df.empty or 'Close' not in df:
        return {}
    
    close_df = df['Close']
    changes = {}
    
    # 計算時間跨度的 index offset
    offset = 1 # 預設一日
    if "一週" in tf_label: offset = 5
    elif "一個月" in tf_label: offset = 21
    elif "三個月" in tf_label: offset = 63
        
    for ticker in close_df.columns:
        series = close_df[ticker].dropna()
        if len(series) > offset:
            last_price = float(series.iloc[-1])
            past_price = float(series.iloc[-(offset+1)])
            if past_price > 0:
                pct = ((last_price - past_price) / past_price) * 100
                changes[ticker] = pct
        elif len(series) >= 2: # 最少退回到只有2天
            last_price = float(series.iloc[-1])
            past_price = float(series.iloc[0])
            if past_price > 0:
                changes[ticker] = ((last_price - past_price) / past_price) * 100
                
    return changes

if st.button(f"🚀 產生 {selected_market} 熱力圖", type="primary"):
    color_scale = ['#007a00', '#222222', '#d90000']
    
    if selected_market == "台灣股市 (上市櫃全市場)":
        with st.spinner("正在獲取台股產業分類與價格..."):
            tw_ind_map, tw_price = get_tw_industry_data()
            
            if not tw_ind_map:
                st.error("無法取得台股資料 (這通常發生在公開發佈到國外雲端主機時被台灣證交所阻擋)。請嘗試在本機端執行！")
                st.stop()
                
            yq_period = timeframe_map[selected_tf]
            
            # 過濾只取有產業別的有價證券
            valid_tickers = []
            size_map = {}
            name_map = {}
            
            for item in tw_price:
                code = item.get('Code', '')
                try:
                    t_val = float(item.get('TradeValue', 0))
                except:
                    t_val = 0
                    
                # 過濾掉交易額過低(防雷) 或沒有產業代碼的
                if code in tw_ind_map and t_val > 1000000:
                    valid_tickers.append(f"{code}.TW")
                    size_map[f"{code}.TW"] = t_val
                    name_map[f"{code}.TW"] = f"{code} {item.get('Name', '')}"

            # 為了效能與畫面簡潔，只取成交金額前 N 大的股票
            sorted_valid = sorted(valid_tickers, key=lambda x: size_map[x], reverse=True)[:top_n]

            st.info(f"成功抓取全市場最活躍之 {len(sorted_valid)} 檔股票。正在下載 {selected_tf} 的歷史數據進行運算...")

            df_hist = fetch_historical_prices(sorted_valid, yq_period)
            change_map = calculate_period_change(df_hist, selected_tf)
            
            plot_data = []
            for tkr in sorted_valid:
                if tkr in change_map and tkr in size_map:
                    raw_code = tkr.replace('.TW', '')
                    ind_code = tw_ind_map.get(raw_code, '')
                    ind_name = TWSE_INDUSTRY_MAP.get(ind_code, '其他')
                    
                    plot_data.append({
                        "Market": "台灣股市",
                        "Industry": ind_name,
                        "Stock": name_map.get(tkr, tkr),
                        "Size": size_map[tkr],
                        "Change": change_map[tkr],
                        "Label": f"{name_map.get(tkr, tkr)}<br>{change_map[tkr]:+.2f}%"
                    })
                    
            if plot_data:
                plot_df = pd.DataFrame(plot_data)
                
                fig = px.treemap(
                    plot_df,
                    path=[px.Constant("台股市場"), 'Industry', 'Stock'],
                    values='Size',
                    color='Change',
                    color_continuous_scale=color_scale,
                    color_continuous_midpoint=0,
                    custom_data=['Label']
                )
                
                fig.update_traces(
                    texttemplate="%{customdata[0]}",
                    textposition="middle center",
                    textfont_color="white",
                    hovertemplate="<b>%{label}</b><br>漲跌幅: %{color:+.2f}%<br>成交規模: %{value:,.0f}<extra></extra>"
                )
                
                fig.update_layout(height=800, margin=dict(t=30, l=10, r=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("無法分析足夠的資料以繪製熱力圖。")

    elif selected_market == "美國股市 (S&P 500)":
        with st.spinner("正在獲取 S&P 500 成分股清單..."):
            us_tickers, us_sectors, us_names = get_sp500_components()
            
            if not us_tickers:
                st.error("無法取得美股成分股清單。")
                st.stop()
                
            yq_period = timeframe_map[selected_tf]
            st.info(f"成功抓取 {len(us_tickers)} 檔 S&P 500 成分股。正在下載 {selected_tf} 的歷史數據...")
            
            df_hist = fetch_historical_prices(us_tickers, yq_period)
            change_map = calculate_period_change(df_hist, selected_tf)
            
            # 計算粗估市值 (Volume * Close) 作為板塊大小
            size_map = {}
            if 'Volume' in df_hist and 'Close' in df_hist:
                for t in us_tickers:
                    if t in df_hist['Volume'] and t in df_hist['Close']:
                        v = df_hist['Volume'][t].dropna()
                        c = df_hist['Close'][t].dropna()
                        if not v.empty and not c.empty:
                            size_map[t] = float(v.iloc[-1]) * float(c.iloc[-1])
            
            # 依照估計市值排序，過濾出前 N 大
            sorted_us_tickers = sorted(
                [t for t in us_tickers if t in size_map and size_map[t] > 0], 
                key=lambda x: size_map[x], 
                reverse=True
            )[:top_n]
            
            plot_data = []
            for tkr in sorted_us_tickers:
                # 找回原本在 S&P500 陣列中的 index 來取得 Sector
                orig_idx = us_tickers.index(tkr)
                sector = us_sectors[orig_idx] if orig_idx < len(us_sectors) else "Other"
                name_sym = f"{tkr}"
                
                plot_data.append({
                    "Market": "S&P 500",
                    "Sector": sector,
                    "Stock": name_sym,
                    "Size": size_map[tkr],
                    "Change": change_map[tkr],
                    "Label": f"{name_sym}<br>{change_map[tkr]:+.2f}%"
                })
                    
            if plot_data:
                plot_df = pd.DataFrame(plot_data)
                
                fig = px.treemap(
                    plot_df,
                    path=[px.Constant("美股市場 (S&P 500)"), 'Sector', 'Stock'],
                    values='Size',
                    color='Change',
                    color_continuous_scale=color_scale,
                    color_continuous_midpoint=0,
                    custom_data=['Label']
                )
                
                fig.update_traces(
                    texttemplate="%{customdata[0]}",
                    textposition="middle center",
                    textfont_color="white",
                    hovertemplate="<b>%{label}</b><br>漲跌幅: %{color:+.2f}%<br>市場規模估算: %{value:,.0f}<extra></extra>"
                )
                
                fig.update_layout(height=800, margin=dict(t=30, l=10, r=10, b=10))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("無法分析足夠的資料以繪製熱力圖。")
