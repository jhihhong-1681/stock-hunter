import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import json
import base64
import requests
from pathlib import Path

st.set_page_config(page_title="自選股清單 - 阿紘的股票儀表板", page_icon="⭐", layout="wide")
from utils.styles import load_css
load_css()
st.title("⭐ 自選股清單")
st.markdown("追蹤你關注的股票，台股加 `.TW`（例：`2330.TW`），美股直接輸入（例：`NVDA`）。")

# --- GitHub 讀寫設定 ---
REPO      = "jhihhong-1681/stock-hunter"
GH_PATH   = "data/watchlist.json"
GH_TOKEN  = st.secrets.get("GH_PAT", "")
GH_HEADERS = {
    "Authorization": f"token {GH_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}
GH_URL = f"https://api.github.com/repos/{REPO}/contents/{GH_PATH}"

# 備用：本地檔案路徑
LOCAL_FILE = Path(__file__).parent.parent / "data" / "watchlist.json"

def load_watchlist() -> list:
    if GH_TOKEN:
        try:
            r = requests.get(GH_URL, headers=GH_HEADERS, timeout=10)
            if r.status_code == 200:
                content = base64.b64decode(r.json()["content"]).decode("utf-8")
                return json.loads(content)
        except Exception:
            pass
    # fallback：讀本地檔
    try:
        return json.loads(LOCAL_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def save_watchlist(tickers: list) -> str:
    """回傳錯誤訊息字串，成功回傳空字串"""
    content_b64 = base64.b64encode(
        json.dumps(tickers, ensure_ascii=False).encode("utf-8")
    ).decode("utf-8")
    if GH_TOKEN:
        try:
            r_get = requests.get(GH_URL, headers=GH_HEADERS, timeout=10)
            sha = r_get.json().get("sha", "") if r_get.status_code == 200 else ""
            payload = {
                "message": f"chore: update watchlist ({len(tickers)} stocks)",
                "content": content_b64,
                "sha": sha
            }
            r_put = requests.put(GH_URL, headers=GH_HEADERS, json=payload, timeout=10)
            if r_put.status_code not in (200, 201):
                return f"GitHub 寫入失敗 ({r_put.status_code})：{r_put.json().get('message','')}"
        except Exception as e:
            return f"GitHub 連線錯誤：{e}"
    else:
        return "⚠️ 未偵測到 GH_PAT，清單只存在本機"
    LOCAL_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_FILE.write_text(json.dumps(tickers, ensure_ascii=False), encoding="utf-8")
    return ""

if 'watchlist' not in st.session_state:
    st.session_state.watchlist = load_watchlist()
if 'sync_error' not in st.session_state:
    st.session_state.sync_error = ""

# 顯示上次同步錯誤（持久顯示直到下次成功）
if st.session_state.sync_error:
    st.error(f"🔴 GitHub 同步失敗：{st.session_state.sync_error}")

# --- 加入單檔 ---
col1, col2 = st.columns([4, 1])
with col1:
    new_ticker = st.text_input("輸入股票代號", placeholder="2330.TW 或 NVDA", label_visibility="collapsed")
with col2:
    if st.button("➕ 加入", use_container_width=True):
        t = new_ticker.strip().upper()
        if t and t not in st.session_state.watchlist:
            st.session_state.watchlist.append(t)
            st.session_state.sync_error = save_watchlist(st.session_state.watchlist)
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
        st.session_state.sync_error = save_watchlist(st.session_state.watchlist)
        if not st.session_state.sync_error:
            st.success(f"已加入 {added} 檔，清單已同步到 GitHub ✅")
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
            st.session_state.sync_error = save_watchlist(st.session_state.watchlist)
            st.rerun()

st.markdown("---")

# --- 抓取報價（5日快取）---
PERIOD_MAP = {"1 週": "5d", "1 個月": "1mo", "3 個月": "3mo", "6 個月": "6mo", "1 年": "1y"}

@st.cache_data(ttl=300)
def fetch_quote(tickers: tuple):
    rows = []
    for ticker in tickers:
        try:
            hist = yf.download(ticker, period="6mo", progress=False, auto_adjust=True)
            if hist.empty:
                raise ValueError("empty")
            close = hist['Close'].dropna()
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            price  = float(close.iloc[-1])
            prev   = float(close.iloc[-2])  if len(close) >= 2  else price
            w_prev = float(close.iloc[-6])  if len(close) >= 6  else float(close.iloc[0])
            m_prev = float(close.iloc[-22]) if len(close) >= 22 else float(close.iloc[0])
            h_prev = float(close.iloc[0])
            rows.append({
                "代號":       ticker,
                "現價":       price,
                "日漲跌(%)":   ((price - prev)   / prev)   * 100 if prev   else 0,
                "週漲跌(%)":   ((price - w_prev)  / w_prev) * 100 if w_prev else 0,
                "月漲跌(%)":   ((price - m_prev)  / m_prev) * 100 if m_prev else 0,
                "半年漲跌(%)": ((price - h_prev)  / h_prev) * 100 if h_prev else 0,
            })
        except Exception:
            rows.append({"代號": ticker, "現價": None,
                         "日漲跌(%)": None, "週漲跌(%)": None,
                         "月漲跌(%)": None, "半年漲跌(%)": None})
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

pct_cols = ["日漲跌(%)", "週漲跌(%)", "月漲跌(%)", "半年漲跌(%)"]
fmt_dict = {"現價": "{:.2f}", **{c: "{:+.2f}%" for c in pct_cols}}
try:
    styled = df.style.map(color_pct, subset=pct_cols).format(fmt_dict, na_rep="N/A")
except AttributeError:
    styled = df.style.applymap(color_pct, subset=pct_cols).format(fmt_dict, na_rep="N/A")
st.dataframe(styled, use_container_width=True, hide_index=True)

# --- 走勢圖 ---
st.markdown("---")
st.subheader("📈 股價走勢")

chart_col1, chart_col2 = st.columns([3, 1])
with chart_col1:
    selected_chart = st.multiselect(
        "選擇要顯示的股票（最多 20 檔）",
        options=st.session_state.watchlist,
        default=st.session_state.watchlist[:10],
        max_selections=20,
    )
with chart_col2:
    period_label = st.radio("區間", list(PERIOD_MAP.keys()), horizontal=False, index=1)
yf_period = PERIOD_MAP[period_label]

if not selected_chart:
    st.info("請從上方選擇要比較的股票。")
    st.stop()

COLORS = ["#e05c00", "#4a90e2", "#2ecc71", "#9b59b6", "#e74c3c", "#f39c12",
          "#1abc9c", "#e67e22", "#aaaaaa", "#c0392b", "#ff6b9d", "#00d2ff",
          "#f8c537", "#a8ff78", "#ff9a3c", "#c471ed", "#12c2e9", "#f64f59",
          "#43e97b", "#fa709a"]

with st.spinner("載入歷史資料..."):
    hist_close = fetch_history(tuple(selected_chart), yf_period)

if hist_close.empty:
    st.warning("無法取得歷史資料。")
    st.stop()

tab_norm, tab_price = st.tabs(["📊 相對績效（基準=100）", "💰 原始股價"])

valid = [t for t in selected_chart if t in hist_close.columns and not hist_close[t].dropna().empty]

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
            height=480, hovermode="x unified", yaxis_title="相對績效",
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01)
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
            height=480, hovermode="x unified", yaxis_title="股價",
            legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.01)
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("💡 點擊圖例可隱藏/顯示個別股票。")
