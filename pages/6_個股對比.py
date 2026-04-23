import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import date, timedelta

st.set_page_config(page_title="個股對比 - 阿紘的股票儀表板", page_icon="📊", layout="wide")
st.title("📊 個股 vs S&P 500 績效對比")
st.markdown("輸入任一股票（台股加 `.TW`），與 S&P 500 同期績效一鍵比較。")

col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    ticker = st.text_input("股票代號", value="NVDA", placeholder="2330.TW 或 NVDA")
with col2:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=365))
with col3:
    end_date = st.date_input("結束日期", value=date.today())

if not ticker.strip():
    st.info("請輸入股票代號")
    st.stop()

ticker = ticker.strip().upper()

@st.cache_data(ttl=1800)
def fetch_data(ticker: str, start: date, end: date):
    return yf.download([ticker, "^GSPC"], start=start, end=end, progress=False, auto_adjust=True)

with st.spinner("下載資料中..."):
    data = fetch_data(ticker, start_date, end_date)

if data.empty or "Close" not in data:
    st.error("無法取得資料，請確認代號與日期範圍是否正確。")
    st.stop()

close = data["Close"]
if isinstance(close, pd.Series):
    close = close.to_frame()

missing = [t for t in [ticker, "^GSPC"] if t not in close.columns]
if missing:
    st.error(f"找不到以下股票的資料：{', '.join(missing)}")
    st.stop()

close = close[[ticker, "^GSPC"]].dropna()
if len(close) < 2:
    st.error("資料筆數不足，請擴大日期範圍。")
    st.stop()

# --- 指標計算 ---
norm = (close / close.iloc[0]) * 100

stock_ret = (close[ticker].iloc[-1] / close[ticker].iloc[0] - 1) * 100
sp500_ret = (close["^GSPC"].iloc[-1] / close["^GSPC"].iloc[0] - 1) * 100
alpha = stock_ret - sp500_ret

daily = close.pct_change().dropna()
cov_matrix = np.cov(daily[ticker], daily["^GSPC"])
beta = cov_matrix[0, 1] / cov_matrix[1, 1] if cov_matrix[1, 1] != 0 else 0
corr = float(np.corrcoef(daily[ticker], daily["^GSPC"])[0, 1])

def max_drawdown(series: pd.Series) -> float:
    peak = series.cummax()
    return float(((series - peak) / peak).min() * 100)

stock_mdd = max_drawdown(close[ticker])
sp500_mdd = max_drawdown(close["^GSPC"])

# --- 指標顯示 ---
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(f"{ticker} 總報酬", f"{stock_ret:+.2f}%")
m2.metric("S&P 500 總報酬", f"{sp500_ret:+.2f}%")
m3.metric("超額報酬 (Alpha)", f"{alpha:+.2f}%", delta_color="normal")
m4.metric("Beta", f"{beta:.2f}")
m5.metric("相關係數", f"{corr:.2f}")

st.markdown("---")

# --- 績效走勢圖 ---
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=norm.index, y=norm[ticker],
    name=ticker, line=dict(color="#e05c00", width=2.5)
))
fig.add_trace(go.Scatter(
    x=norm.index, y=norm["^GSPC"],
    name="S&P 500", line=dict(color="#4a90e2", width=2, dash="dash")
))
fig.update_layout(
    title=f"{ticker} vs S&P 500（基準 = 100，{start_date} ~ {end_date}）",
    yaxis_title="相對績效",
    height=500,
    hovermode="x unified",
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
)
st.plotly_chart(fig, use_container_width=True)

# --- 最大回撤 ---
st.markdown("---")
c1, c2 = st.columns(2)
c1.metric(f"{ticker} 最大回撤", f"{stock_mdd:.2f}%", delta_color="inverse")
c2.metric("S&P 500 最大回撤", f"{sp500_mdd:.2f}%", delta_color="inverse")

# --- 說明 ---
with st.expander("📖 指標說明"):
    st.markdown("""
- **Alpha（超額報酬）**：個股總報酬 − S&P 500 同期報酬，正值代表跑贏大盤。
- **Beta**：相對大盤的波動倍率。Beta > 1 代表波動比大盤大；< 1 代表較穩定。
- **相關係數**：與大盤走勢的同步程度（−1 至 1）。
- **最大回撤**：期間內最嚴重的高點到低點跌幅。
""")
