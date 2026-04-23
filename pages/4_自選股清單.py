import streamlit as st
import yfinance as yf
import pandas as pd

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

# --- 抓取報價 ---
@st.cache_data(ttl=300)
def fetch_watchlist_data(tickers: tuple):
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

with st.spinner("更新報價中..."):
    df = fetch_watchlist_data(tuple(st.session_state.watchlist))

if df.empty:
    st.warning("無法取得任何報價。")
    st.stop()

def color_pct(val):
    if pd.isna(val):
        return ''
    return 'color: #d90000' if val > 0 else ('color: #007a00' if val < 0 else '')

try:
    styled = df.style.map(color_pct, subset=["日漲跌(%)", "週漲跌(%)"]) \
                     .format({"現價": "{:.2f}", "日漲跌(%)": "{:+.2f}%", "週漲跌(%)": "{:+.2f}%"}, na_rep="N/A")
except AttributeError:
    styled = df.style.applymap(color_pct, subset=["日漲跌(%)", "週漲跌(%)"]) \
                     .format({"現價": "{:.2f}", "日漲跌(%)": "{:+.2f}%", "週漲跌(%)": "{:+.2f}%"}, na_rep="N/A")
st.dataframe(styled, use_container_width=True, hide_index=True)
