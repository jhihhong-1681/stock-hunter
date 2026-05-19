import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import json
from pathlib import Path
from datetime import date, timedelta

st.set_page_config(page_title="個股對比 - 阿紘的股票儀表板", page_icon="📊", layout="wide")
from utils.styles import load_css
load_css()
st.title("📊 個股 vs 大盤績效對比")
st.markdown("輸入多檔股票（逗號分隔，最多 6 檔），台股加 `.TW`。圖例點一下可以**隱藏/顯示**該條線。")

STOCK_COLORS = ["#e05c00", "#9b59b6", "#2ecc71", "#e74c3c", "#f39c12", "#1abc9c"]

# --- 從自選股選取 ---
WATCHLIST_FILE = Path(__file__).parent.parent / "data" / "watchlist.json"
try:
    watchlist = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
except Exception:
    watchlist = []

if watchlist:
    with st.expander("⭐ 從自選股清單選取（最多 6 檔）"):
        picked = st.multiselect(
            "選擇股票加入比較",
            options=watchlist,
            max_selections=6,
            key="compare_from_watchlist"
        )
        if picked:
            st.session_state["compare_prefill"] = ", ".join(picked)

prefill = st.session_state.pop("compare_prefill", "NVDA, AAPL")

col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    tickers_input = st.text_input("股票代號（逗號分隔）",
                                   value=prefill,
                                   placeholder="2330.TW, NVDA, AAPL")
with col2:
    start_date = st.date_input("開始日期", value=date.today() - timedelta(days=365))
with col3:
    end_date = st.date_input("結束日期", value=date.today())

tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()][:6]
if not tickers:
    st.info("請輸入至少一個股票代號")
    st.stop()

INDICES = {"^GSPC": "S&P 500", "^IXIC": "NASDAQ"}

@st.cache_data(ttl=1800)
def fetch_data(tickers: tuple, start: date, end: date):
    all_tickers = list(tickers) + list(INDICES.keys())
    return yf.download(all_tickers, start=start, end=end, progress=False, auto_adjust=True)

with st.spinner("下載資料中..."):
    data = fetch_data(tuple(tickers), start_date, end_date)

if data.empty or "Close" not in data:
    st.error("無法取得資料，請確認代號與日期範圍是否正確。")
    st.stop()

close = data["Close"]
if isinstance(close, pd.Series):
    close = close.to_frame()

valid_tickers = [t for t in tickers if t in close.columns and not close[t].dropna().empty]
missing = [t for t in tickers if t not in valid_tickers]
if missing:
    st.warning(f"以下代號無法取得資料，已略過：{', '.join(missing)}")
if not valid_tickers:
    st.error("所有代號都無法取得資料。")
    st.stop()

valid_indices = [k for k in INDICES if k in close.columns and not close[k].dropna().empty]
all_cols = valid_tickers + valid_indices
close = close[all_cols].dropna()

if len(close) < 2:
    st.error("資料筆數不足，請擴大日期範圍。")
    st.stop()

# --- 指標計算 ---
def total_ret(s): return (s.iloc[-1] / s.iloc[0] - 1) * 100
def max_drawdown(s):
    return float(((s - s.cummax()) / s.cummax()).min() * 100)

norm = (close / close.iloc[0]) * 100
sp500 = close.get("^GSPC")

# 大盤基準列
idx_cols = st.columns(len(valid_indices) + 1)
idx_cols[0].markdown("**大盤基準**")
for i, k in enumerate(valid_indices):
    ret = total_ret(close[k])
    mdd = max_drawdown(close[k])
    idx_cols[i + 1].metric(INDICES[k], f"{ret:+.2f}%", f"最大回撤 {mdd:.2f}%", delta_color="inverse")

st.markdown("---")

# 個股指標卡
for i, t in enumerate(valid_tickers):
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

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric(f"{t} 總報酬", f"{ret:+.2f}%")
    c2.metric("vs S&P500 Alpha", f"{alpha:+.2f}%")
    c3.metric("Beta", f"{beta:.2f}")
    c4.metric("相關係數", f"{corr:.2f}")
    c5.metric("最大回撤", f"{mdd:.2f}%", delta_color="inverse")

st.markdown("---")

# --- 績效走勢圖（點圖例可隱藏/顯示） ---
fig = go.Figure()

for i, t in enumerate(valid_tickers):
    fig.add_trace(go.Scatter(
        x=norm.index, y=norm[t],
        name=t,
        line=dict(color=STOCK_COLORS[i % len(STOCK_COLORS)], width=2.5)
    ))

index_styles = [
    dict(color="#4a90e2", width=2, dash="dash"),
    dict(color="#aaaaaa", width=2, dash="dot"),
]
for i, k in enumerate(valid_indices):
    fig.add_trace(go.Scatter(
        x=norm.index, y=norm[k],
        name=INDICES[k],
        line=index_styles[i % len(index_styles)]
    ))

fig.update_layout(
    title=f"績效走勢（基準 = 100，{start_date} ~ {end_date}）",
    yaxis_title="相對績效",
    height=540,
    hovermode="x unified",
    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
)
st.plotly_chart(fig, use_container_width=True)
st.caption("💡 點擊圖例中的名稱可隱藏/顯示該線條；雙擊可單獨顯示。")

with st.expander("📖 指標說明"):
    st.markdown("""
- **Alpha（超額報酬）**：個股總報酬 − S&P 500 同期報酬，正值代表跑贏大盤。
- **Beta**：相對大盤的波動倍率。Beta > 1 代表波動比大盤大；< 1 較穩定。
- **相關係數**：與大盤走勢的同步程度（−1 至 1）。
- **最大回撤**：期間內最嚴重的高點到低點跌幅。
""")
