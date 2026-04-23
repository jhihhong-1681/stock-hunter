import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from datetime import date, timedelta

st.set_page_config(page_title="個股對比 - 阿紘的股票儀表板", page_icon="📊", layout="wide")
st.title("📊 個股 vs S&P 500 績效對比")
st.markdown("輸入多檔股票（逗號分隔），台股加 `.TW`（例：`2330.TW`），美股直接輸入（例：`NVDA`）。")

COLORS = ["#e05c00", "#9b59b6", "#2ecc71", "#e74c3c", "#f39c12", "#1abc9c"]

col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    tickers_input = st.text_input("股票代號（逗號分隔，最多 6 檔）",
                                   value="NVDA, AAPL",
                                   placeholder="2330.TW, NVDA, AAPL")
with col2:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=365))
with col3:
    end_date = st.date_input("結束日期", value=date.today())

tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()][:6]
if not tickers:
    st.info("請輸入至少一個股票代號")
    st.stop()

@st.cache_data(ttl=1800)
def fetch_data(tickers: tuple, start: date, end: date):
    all_tickers = list(tickers) + ["^GSPC"]
    return yf.download(all_tickers, start=start, end=end, progress=False, auto_adjust=True)

with st.spinner("下載資料中..."):
    data = fetch_data(tuple(tickers), start_date, end_date)

if data.empty or "Close" not in data:
    st.error("無法取得資料，請確認代號與日期範圍是否正確。")
    st.stop()

close = data["Close"]
if isinstance(close, pd.Series):
    close = close.to_frame()

# 只保留有資料的 ticker
valid_tickers = [t for t in tickers if t in close.columns and not close[t].dropna().empty]
missing = [t for t in tickers if t not in valid_tickers]
if missing:
    st.warning(f"以下代號無法取得資料，已略過：{', '.join(missing)}")
if not valid_tickers:
    st.error("所有代號都無法取得資料。")
    st.stop()

all_cols = valid_tickers + (["^GSPC"] if "^GSPC" in close.columns else [])
close = close[all_cols].dropna()

if len(close) < 2:
    st.error("資料筆數不足，請擴大日期範圍。")
    st.stop()

# --- 指標計算 ---
def total_ret(series): return (series.iloc[-1] / series.iloc[0] - 1) * 100
def max_drawdown(series):
    peak = series.cummax()
    return float(((series - peak) / peak).min() * 100)

norm = (close / close.iloc[0]) * 100
sp500 = close["^GSPC"] if "^GSPC" in close.columns else None

metrics = []
for t in valid_tickers:
    ret = total_ret(close[t])
    sp_ret = total_ret(sp500) if sp500 is not None else 0
    alpha = ret - sp_ret
    daily = close[t].pct_change().dropna()
    mdd = max_drawdown(close[t])
    beta, corr = 0.0, 0.0
    if sp500 is not None:
        sp_daily = sp500.pct_change().dropna()
        idx = daily.index.intersection(sp_daily.index)
        if len(idx) > 1:
            cov = np.cov(daily[idx], sp_daily[idx])
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0
            corr = float(np.corrcoef(daily[idx], sp_daily[idx])[0, 1])
    metrics.append({"代號": t, "總報酬(%)": ret, "Alpha(%)": alpha,
                    "Beta": beta, "相關係數": corr, "最大回撤(%)": mdd})

# --- 指標卡 ---
if sp500 is not None:
    sp_ret = total_ret(sp500)
    sp_mdd = max_drawdown(sp500)
    st.markdown(f"**S&P 500 同期基準：總報酬 {sp_ret:+.2f}%｜最大回撤 {sp_mdd:.2f}%**")
    st.markdown("---")

for i, m in enumerate(metrics):
    c1, c2, c3, c4, c5 = st.columns(5)
    label = m["代號"]
    c1.metric(f"{label} 總報酬", f"{m['總報酬(%)']:+.2f}%")
    c2.metric("Alpha", f"{m['Alpha(%)']:+.2f}%")
    c3.metric("Beta", f"{m['Beta']:.2f}")
    c4.metric("相關係數", f"{m['相關係數']:.2f}")
    c5.metric("最大回撤", f"{m['最大回撤(%)']:.2f}%", delta_color="inverse")

st.markdown("---")

# --- 績效走勢圖 ---
fig = go.Figure()
for i, t in enumerate(valid_tickers):
    fig.add_trace(go.Scatter(
        x=norm.index, y=norm[t],
        name=t, line=dict(color=COLORS[i % len(COLORS)], width=2.5)
    ))
if sp500 is not None:
    fig.add_trace(go.Scatter(
        x=norm.index, y=norm["^GSPC"],
        name="S&P 500", line=dict(color="#4a90e2", width=2, dash="dash")
    ))

fig.update_layout(
    title=f"績效走勢（基準 = 100，{start_date} ~ {end_date}）",
    yaxis_title="相對績效",
    height=520,
    hovermode="x unified",
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
)
st.plotly_chart(fig, use_container_width=True)

with st.expander("📖 指標說明"):
    st.markdown("""
- **Alpha（超額報酬）**：個股總報酬 − S&P 500 同期報酬，正值代表跑贏大盤。
- **Beta**：相對大盤的波動倍率。Beta > 1 代表波動比大盤大；< 1 較穩定。
- **相關係數**：與大盤走勢的同步程度（−1 至 1）。
- **最大回撤**：期間內最嚴重的高點到低點跌幅。
""")
