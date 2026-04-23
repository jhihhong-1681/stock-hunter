import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="產業輪動 - 阿紘的股票儀表板", page_icon="🔄", layout="wide")
st.title("🔄 產業輪動雷達圖（美股）")
st.markdown("透過各產業 ETF 的相對強弱，判斷目前資金流向哪個板塊。")

SECTOR_ETFS = {
    "科技": "XLK",
    "金融": "XLF",
    "能源": "XLE",
    "醫療": "XLV",
    "工業": "XLI",
    "非必需消費": "XLY",
    "必需消費": "XLP",
    "公用事業": "XLU",
    "原材料": "XLB",
    "房地產": "XLRE",
    "通訊服務": "XLC",
}

PERIODS = {
    "1 週": 5,
    "1 個月": 21,
    "3 個月": 63,
    "6 個月": 126,
}

COLORS = ["#e05c00", "#4a90e2", "#2ecc71", "#e74c3c"]

@st.cache_data(ttl=3600)
def fetch_sector_data():
    tickers = list(SECTOR_ETFS.values())
    data = yf.download(tickers, period="6mo", progress=False, auto_adjust=True)
    return data["Close"] if "Close" in data else pd.DataFrame()

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

sectors = list(SECTOR_ETFS.keys())

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

# --- 明細表 ---
st.markdown("---")
st.subheader("📋 完整報酬率明細")
table = pd.DataFrame(
    {period: {s: f"{results[period].get(s, 0):+.2f}%" for s in sectors}
     for period in PERIODS.keys()}
)
st.dataframe(table, use_container_width=True)
