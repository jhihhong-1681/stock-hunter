import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="自選股清單 - 阿紘的股票儀表板", page_icon="⭐", layout="wide")
st.title("⭐ 自選股清單")
st.markdown("追蹤你關注的股票，台股加 `.TW`（例：`2330.TW`），美股直接輸入（例：`NVDA`）。")

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 加入單檔 ---
col1, col2 = st.columns([4, 1])
with col1:
    new_ticker = st.text_input("輸入股票代號", placeholder="2330.TW 或 NVDA", label_visibility="collapsed")
with col2:
    if st.button("➕ 加入", use_container_width=True):
        t = new_ticker.strip().upper()
        if t and t not in st.session_state.watchlist:
            st.session_state.watchlist.append(t)
            st.rerun()

# --- 批次匯入 ---
with st.expander("📋 批次匯入 / 匯出"):
    bulk = st.text_area("貼上逗號分隔的代號，例：2330.TW, 2317.TW, NVDA", height=68)
    if st.button("匯入"):
        added = 0
        for t in [x.strip().upper() for x in bulk.split(',') if x.strip()]:
            if t not in st.session_state.watchlist:
                st.session_state.watchlist.append(t)
                added += 1
        st.success(f"已加入 {added} 檔")
        st.rerun()
    if st.session_state.watchlist:
        st.text_input("匯出（複製下方文字，下次可貼回批次匯入）",
                      value=", ".join(st.session_state.watchlist), disabled=True)

if not st.session_state.watchlist:
    st.info("清單目前為空，請加入股票代號。")
    st.stop()

# --- 清單管理 ---
st.markdown("---")
st.subheader(f"追蹤中（{len(st.session_state.watchlist)} 檔）")

remove_cols = st.columns(min(len(st.session_state.watchlist), 8))
for i, ticker in enumerate(list(st.session_state.watchlist)):
    with remove_cols[i % 8]:
        if st.button(f"✕ {ticker}", key=f"rm_{ticker}"):
            st.session_state.watchlist.remove(ticker)
            st.rerun()

st.markdown("---")

# --- 抓取報價（5日快取）---
PERIOD_MAP = {"1 週": "5d", "1 個月": "1mo", "3 個月": "3mo", "6 個月": "6mo", "1 年": "1y"}

@st.cache_data(ttl=300)
def fetch_quote(tickers: tuple):
    rows = []
    for ticker in tickers:
        try:
            hist = yf.download(ticker, period="5d", progress=False, auto_adjust=True)
            if hist.empty:
                raise ValueError("empty")
            close = hist['Close'].dropna()
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            price = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) >= 2 else price
            w_prev = float(close.iloc[0])
            rows.append({
                "代號": ticker,
                "現價": price,
                "日漲跌(%)": ((price - prev) / prev) * 100 if prev else 0,
                "週漲跌(%)": ((price - w_prev) / w_prev) * 100 if w_prev else 0,
            })
        except Exception:
            rows.append({"代號": ticker, "現價": None, "日漲跌(%)": None, "週漲跌(%)": None})
    return pd.DataFrame(rows)

@st.cache_data(ttl=1800)
def fetch_history(tickers: tuple, yf_period: str):
    data = yf.download(list(tickers), period=yf_period, progress=False, auto_adjust=True)
    if "Close" not in data:
        return pd.DataFrame()
    close = data["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame()
    return close

# --- 報價表 ---
with st.spinner("更新報價中..."):
    df = fetch_quote(tuple(st.session_state.watchlist))

if df.empty:
    st.warning("無法取得任何報價。")
    st.stop()

def color_pct(val):
    if pd.isna(val):
        return ''
    return 'color: #ff4d4d; font-weight:bold' if val > 0 else ('color: #00cc66; font-weight:bold' if val < 0 else '')

try:
    styled = df.style.map(color_pct, subset=["日漲跌(%)", "週漲跌(%)"]) \
                     .format({"現價": "{:.2f}", "日漲跌(%)": "{:+.2f}%", "週漲跌(%)": "{:+.2f}%"}, na_rep="N/A")
except AttributeError:
    styled = df.style.applymap(color_pct, subset=["日漲跌(%)", "週漲跌(%)"]) \
                     .format({"現價": "{:.2f}", "日漲跌(%)": "{:+.2f}%", "週漲跌(%)": "{:+.2f}%"}, na_rep="N/A")
st.dataframe(styled, use_container_width=True, hide_index=True)

# --- 走勢圖 ---
st.markdown("---")
st.subheader("📈 股價走勢")

period_label = st.radio("區間", list(PERIOD_MAP.keys()), horizontal=True, index=1)
yf_period = PERIOD_MAP[period_label]

COLORS = ["#e05c00", "#4a90e2", "#2ecc71", "#9b59b6", "#e74c3c", "#f39c12",
          "#1abc9c", "#e67e22", "#aaaaaa", "#c0392b"]

with st.spinner("載入歷史資料..."):
    hist_close = fetch_history(tuple(st.session_state.watchlist), yf_period)

if hist_close.empty:
    st.warning("無法取得歷史資料。")
    st.stop()

tab_norm, tab_price = st.tabs(["📊 相對績效（基準=100）", "💰 原始股價"])

valid = [t for t in st.session_state.watchlist if t in hist_close.columns and not hist_close[t].dropna().empty]

with tab_norm:
    if not valid:
        st.warning("無有效資料")
    else:
        norm = hist_close[valid].dropna()
        norm = (norm / norm.iloc[0]) * 100
        fig = go.Figure()
        for i, t in enumerate(valid):
            fig.add_trace(go.Scatter(
                x=norm.index, y=norm[t], name=t,
                line=dict(color=COLORS[i % len(COLORS)], width=2)
            ))
        fig.update_layout(
            height=420, hovermode="x unified", yaxis_title="相對績效",
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption("💡 點擊圖例可隱藏/顯示個別股票。")

with tab_price:
    if not valid:
        st.warning("無有效資料")
    else:
        fig2 = go.Figure()
        for i, t in enumerate(valid):
            series = hist_close[t].dropna()
            fig2.add_trace(go.Scatter(
                x=series.index, y=series, name=t,
                line=dict(color=COLORS[i % len(COLORS)], width=2)
            ))
        fig2.update_layout(
            height=420, hovermode="x unified", yaxis_title="股價",
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("💡 點擊圖例可隱藏/顯示個別股票。")
