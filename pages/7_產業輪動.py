import time
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="產業輪動 - 阿紘的股票儀表板", page_icon="🔄", layout="wide")
from utils.styles import load_css
load_css()
st.title("🔄 產業輪動雷達圖（美股）")
st.markdown("透過各產業 ETF 的相對強弱，判斷目前資金流向哪個板塊。")

SECTOR_ETFS = {
    "科技": "XLK",
    "半導體": "SOXX",
    "軟體服務": "IGV",
    "金融": "XLF",
    "銀行": "KBE",
    "金融科技": "FINX",
    "能源": "XLE",
    "油氣開採": "XOP",
    "公用事業": "XLU",
    "核能鈾礦": "NLR",
    "醫療保健": "XLV",
    "生技": "XBI",
    "製藥": "XPH",
    "工業": "XLI",
    "國防太空": "ITA",
    "運輸": "XTN",
    "非必需消費": "XLY",
    "零售": "XRT",
    "房屋建築": "XHB",
    "必需消費": "XLP",
    "原材料": "XLB",
    "稀土關鍵金屬": "SETM",
    "礦業": "XME",
    "房地產": "XLRE",
    "通訊服務": "XLC",
    "資安": "CIBR",
}

PERIODS = {
    "1 週": 5,
    "1 個月": 21,
    "3 個月": 63,
    "6 個月": 126,
    "1 年": 252,
}

COLORS = ["#e05c00", "#4a90e2", "#2ecc71", "#e74c3c"]

@st.cache_data(ttl=3600)
def fetch_sector_data():
    tickers = list(SECTOR_ETFS.values())
    data = yf.download(tickers, period="1y", progress=False, auto_adjust=True)
    close = data["Close"] if "Close" in data else pd.DataFrame()
    if isinstance(close, pd.Series):
        close = close.to_frame()

    # 一次抓 26 檔時，Yahoo 偶爾會讓少數幾檔（尤其冷門主題型 ETF）在批次下載中
    # 回傳空值，導致該產業全部區間都顯示 0%。對缺資料的逐一單獨補抓一次。
    missing = [t for t in tickers if t not in close.columns or close[t].dropna().shape[0] < 2]
    for t in missing:
        try:
            single = yf.download(t, period="1y", progress=False, auto_adjust=True, threads=False)
            if not single.empty and "Close" in single:
                close[t] = single["Close"]
        except Exception:
            continue

    return close

@st.cache_data(ttl=86400)
def fetch_holdings(etf_ticker: str) -> pd.DataFrame:
    # Yahoo 的 fund holdings 端點在 Cloud IP 上偶爾會回傳空值或被限流，
    # 單次失敗就直接快取空結果會讓查詢卡住 24 小時，改成重試幾次再放棄。
    for attempt in range(3):
        try:
            fd = yf.Ticker(etf_ticker).funds_data
            holdings = fd.top_holdings
            if holdings is not None and not holdings.empty:
                df = holdings.reset_index().rename(columns={
                    "Symbol": "代號", "Name": "名稱", "Holding Percent": "權重"
                })
                df["權重"] = df["權重"] * 100
                return df
        except Exception:
            pass
        if attempt < 2:
            time.sleep(2)
    return pd.DataFrame()

PORTFOLIO_SHEET_ID = "1eaUErkLJUOH7aaIKhDWM5vQwAbE2Zrl0w9jI3KK-9yU"
PORTFOLIO_CSV_URL = f"https://docs.google.com/spreadsheets/d/{PORTFOLIO_SHEET_ID}/export?format=csv"

@st.cache_data(ttl=1800)
def fetch_current_holdings() -> set:
    """直接讀『輸輸贏贏』試算表目前還有部位的持股代號，不透過自選股清單，
    避免要手動按同步才是最新。
    注意：不能用「股數」欄位判斷是否還有持有——出清後股數欄位仍會保留原本數字，
    只有「總投入」和「現值」欄位會被清空，所以要用這兩欄是否同時有值來判斷。"""
    try:
        raw = pd.read_csv(PORTFOLIO_CSV_URL, header=None)
    except Exception:
        return set()

    header_row = None
    for i, row in raw.iterrows():
        if row.astype(str).str.contains("股票代號").any():
            header_row = i
            break
    if header_row is None:
        return set()

    df = raw.iloc[header_row + 1:].copy()
    df.columns = raw.iloc[header_row]

    tickers = set()
    for _, r in df.iterrows():
        market = str(r.get("市場", "")).strip()
        code = str(r.get("股票代號", "")).strip()
        invested = str(r.get("總投入", "")).strip()
        value = str(r.get("現值", "")).strip()
        if not code or code.lower() == "nan" or market not in ("美股", "台股"):
            continue
        if not invested or invested.lower() == "nan" or not value or value.lower() == "nan":
            continue
        tickers.add(f"{code}.TW" if market == "台股" else code.upper())

    return tickers

my_holdings = fetch_current_holdings()

with st.spinner("載入產業 ETF 資料..."):
    close = fetch_sector_data()

if close is None or close.empty:
    st.error("無法取得資料，請稍後再試。")
    st.stop()

if isinstance(close, pd.Series):
    close = close.to_frame()

# --- 計算各週期報酬 ---
def period_return(series: pd.Series, offset: int) -> float:
    s = series.dropna()
    if len(s) > offset:
        return (s.iloc[-1] / s.iloc[-(offset + 1)] - 1) * 100
    if len(s) >= 2:
        return (s.iloc[-1] / s.iloc[0] - 1) * 100
    return 0.0

results: dict[str, dict[str, float]] = {}
for period_name, offset in PERIODS.items():
    results[period_name] = {
        sector: period_return(close[etf], offset)
        for sector, etf in SECTOR_ETFS.items()
        if etf in close.columns
    }

all_sectors = list(SECTOR_ETFS.keys())
sectors = st.multiselect(
    "選擇要顯示的產業（預設全部，可取消勾選以簡化圖表）",
    all_sectors,
    default=all_sectors
)
if not sectors:
    st.info("請至少選擇一個產業。")
    st.stop()

# --- 週期選擇 ---
selected = st.multiselect(
    "選擇比較的時間區間",
    list(PERIODS.keys()),
    default=["1 週", "1 個月", "3 個月"]
)

if not selected:
    st.info("請至少選擇一個時間區間。")
    st.stop()

# --- 雷達圖 ---
fig = go.Figure()
for i, period in enumerate(selected):
    values = [results[period].get(s, 0) for s in sectors]
    values_closed = values + [values[0]]
    sectors_closed = sectors + [sectors[0]]
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=sectors_closed,
        fill="toself",
        name=period,
        line_color=COLORS[i % len(COLORS)],
        opacity=0.55,
    ))

fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, ticksuffix="%")),
    height=620,
    title="各產業板塊相對強弱（%報酬）",
    legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5)
)
st.plotly_chart(fig, use_container_width=True)

# --- 長條圖比較 ---
st.markdown("---")
st.subheader("📊 各產業報酬率長條圖")

bar_period = st.radio("選擇區間", list(PERIODS.keys()), horizontal=True)
bar_df = pd.DataFrame({
    "產業": sectors,
    "報酬率(%)": [results[bar_period].get(s, 0) for s in sectors]
}).sort_values("報酬率(%)", ascending=False)

bar_df["顏色"] = bar_df["報酬率(%)"].apply(lambda x: "#d90000" if x > 0 else "#007a00")

fig2 = px.bar(
    bar_df, x="產業", y="報酬率(%)",
    color="顏色", color_discrete_map="identity",
    text=bar_df["報酬率(%)"].apply(lambda x: f"{x:+.2f}%")
)
fig2.update_traces(textposition="outside")
fig2.update_layout(
    height=420,
    showlegend=False,
    yaxis_ticksuffix="%",
    margin=dict(t=20, b=20)
)
st.plotly_chart(fig2, use_container_width=True)

# --- 明細表（數值，帶紅綠色） ---
st.markdown("---")
st.subheader("📋 完整報酬率明細")
st.caption("👆 點一下表格中的產業列，可在下方看到該產業 ETF 追蹤的成分股與權重。")

table_num = pd.DataFrame(
    {period: {s: results[period].get(s, 0) for s in sectors}
     for period in PERIODS.keys()}
)
table_display = table_num.reset_index().rename(columns={"index": "產業"})
period_cols = list(PERIODS.keys())

def color_cell(val):
    if val > 0:
        return "color: #ff4d4d; font-weight: bold"
    if val < 0:
        return "color: #00cc66; font-weight: bold"
    return ""

try:
    styled_table = table_display.style \
        .map(color_cell, subset=period_cols) \
        .format({p: "{:+.2f}%" for p in period_cols})
except AttributeError:
    styled_table = table_display.style \
        .applymap(color_cell, subset=period_cols) \
        .format({p: "{:+.2f}%" for p in period_cols})

event = st.dataframe(
    styled_table,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    key="sector_detail_table",
)

selected_rows = event.selection.rows if event and event.selection else []
if selected_rows:
    picked_sector = table_display.iloc[selected_rows[0]]["產業"]
    etf = SECTOR_ETFS.get(picked_sector)
    st.markdown(f"#### 🔎 {picked_sector}（{etf}）追蹤成分股與權重")
    with st.spinner(f"載入 {etf} 成分股..."):
        holdings_df = fetch_holdings(etf)
    if holdings_df.empty:
        st.info("查無這檔 ETF 的成分股資料。")
    else:
        holdings_df = holdings_df.copy()
        holdings_df["名稱"] = holdings_df.apply(
            lambda r: f"⭐ {r['名稱']}" if r["代號"] in my_holdings else r["名稱"], axis=1
        )
        if my_holdings:
            st.caption("⭐ = 你目前還持有的標的（直接讀輸輸贏贏試算表的目前部位）")
        st.dataframe(
            holdings_df.style.format({"權重": "{:.2f}%"}),
            use_container_width=True,
            hide_index=True,
        )
else:
    st.info("👆 點一下上表任一列，查看該產業的成分股與權重")
