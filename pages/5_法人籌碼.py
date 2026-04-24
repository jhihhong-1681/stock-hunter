import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import urllib3
from datetime import date, timedelta, datetime
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="法人籌碼 - 阿紘的股票儀表板", page_icon="🏦", layout="wide")
st.title("🏦 三大法人買賣超（台股）")

DATA_FILE = Path(__file__).parent.parent / "data" / "institutional_latest.json"
FUTURES_FILE = Path(__file__).parent.parent / "data" / "futures_latest.json"

INVESTOR_MAP = {
    "外陸資買賣超股數(不含外資自營商)": "外資",
    "投信買賣超股數": "投信",
    "自營商買賣超股數(自行買賣)": "自營商(自行)",
    "自營商買賣超股數(避險)": "自營商(避險)",
    "三大法人買賣超股數": "三大法人合計",
}

def load_from_file():
    """讀取 GitHub Actions 每日自動更新的本地 JSON"""
    if not DATA_FILE.exists():
        return None, "尚無快取資料"
    try:
        payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        df = pd.DataFrame(payload["records"])
        return df, payload.get("date", "未知")
    except Exception as e:
        return None, str(e)

def _make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Accept": "application/json, */*",
        "Referer": "https://www.twse.com.tw/zh/trading/fund/T86.html",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        s.get("https://www.twse.com.tw/zh/trading/fund/T86.html", verify=False, timeout=8)
    except Exception:
        pass
    return s

def fetch_twse_live(query_date: date):
    """直接向 TWSE 抓（本機或未被封鎖時使用）"""
    date_str = query_date.strftime("%Y%m%d")
    s = _make_session()
    urls = [
        f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json",
        f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999",
    ]
    for url in urls:
        try:
            r = s.get(url, verify=False, timeout=15)
            if r.status_code != 200 or not r.content:
                continue
            data = r.json()
            if data.get("stat") != "OK" or not data.get("data"):
                continue
            fields = data["fields"]
            rows = data["data"]
            rename = {"證券代號": "代號", "證券名稱": "名稱"}
            rename.update(INVESTOR_MAP)
            idx = {f: i for i, f in enumerate(fields)}
            n_fields = len(fields)
            records = []
            for row in rows:
                if len(row) != n_fields:
                    continue
                code = row[idx.get("證券代號", 0)]
                if not str(code).strip().isdigit():
                    continue
                rec = {}
                for orig, new in rename.items():
                    if orig not in idx:
                        continue
                    val = row[idx[orig]]
                    if new in INVESTOR_MAP.values():
                        try:
                            val = int(str(val).replace(",", ""))
                        except Exception:
                            val = 0
                    rec[new] = val
                records.append(rec)
            return pd.DataFrame(records), query_date.isoformat()
        except Exception:
            continue
    return None, None

# --- 載入資料 ---
with st.spinner("載入法人資料..."):
    df, data_date = load_from_file()

    if df is None:
        # 備援：直接向 TWSE 抓
        default_date = date.today() - timedelta(days=1)
        while default_date.weekday() >= 5:
            default_date -= timedelta(days=1)
        df, data_date = fetch_twse_live(default_date)

if df is None:
    st.error("無法取得資料。GitHub Actions 尚未執行（請等待每日 17:30 自動更新）。")
    st.stop()

# 顯示資料日期
st.caption(f"資料日期：{data_date}　｜　共 {len(df):,} 筆　｜　每日 17:30 自動更新")

# 確保必要欄位
for col in ["外資", "投信", "自營商(自行)", "三大法人合計"]:
    if col not in df.columns:
        df[col] = 0

# --- 外資台指期未平倉 ---
if FUTURES_FILE.exists():
    try:
        fut = json.loads(FUTURES_FILE.read_text(encoding="utf-8"))
        net_pos = fut.get("外資淨多空未平倉口數", 0)
        net_trade = fut.get("外資淨多空交易口數", 0)
        long_oi = fut.get("多方未平倉口數", 0)
        short_oi = fut.get("空方未平倉口數", 0)
        fut_date = fut.get("date", "")

        st.markdown("---")
        st.subheader("📉 外資台指期（TX）未平倉")
        st.caption(f"資料日期：{fut_date}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("淨多空未平倉（口）", f"{net_pos:+,}", help="正值=淨多單；負值=淨空單")
        c2.metric("今日淨交易（口）", f"{net_trade:+,}")
        c3.metric("多方未平倉", f"{long_oi:,}")
        c4.metric("空方未平倉", f"{short_oi:,}")

        # 視覺化
        fig_fut = go.Figure(go.Bar(
            x=["多方未平倉", "空方未平倉"],
            y=[long_oi, short_oi],
            marker_color=["#d90000", "#007a00"],
            text=[f"{long_oi:,}", f"{short_oi:,}"],
            textposition="outside",
        ))
        fig_fut.update_layout(
            height=280, margin=dict(l=0, r=0, t=10, b=10),
            yaxis_title="口數",
            showlegend=False,
        )
        st.plotly_chart(fig_fut, use_container_width=True)
        pos_label = "淨多單 (偏多)" if net_pos > 0 else "淨空單 (偏空)"
        st.caption(f"外資目前持有 **{abs(net_pos):,}** 口 **{pos_label}**")
    except Exception as e:
        st.warning(f"無法讀取台指期資料：{e}")

st.markdown("---")
top_n = st.slider("顯示前 N 大", min_value=10, max_value=50, value=20, step=5)

def show_investor_tab(df, col):
    if col not in df.columns:
        st.warning(f"找不到欄位：{col}")
        return
    valid = df[["代號", "名稱", col]].dropna(subset=[col])
    top_buy = valid.nlargest(top_n, col).copy()
    top_sell = valid.nsmallest(top_n, col).copy()
    top_buy["label"] = top_buy["代號"].astype(str) + " " + top_buy["名稱"].astype(str)
    top_sell["label"] = top_sell["代號"].astype(str) + " " + top_sell["名稱"].astype(str)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**買超前 {top_n}**")
        fig = px.bar(top_buy, x=col, y="label", orientation="h",
                     color_discrete_sequence=["#d90000"], labels={col: "張數", "label": ""})
        fig.update_layout(height=520, margin=dict(l=0, r=10, t=10, b=10),
                          yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown(f"**賣超前 {top_n}**")
        fig2 = px.bar(top_sell, x=col, y="label", orientation="h",
                      color_discrete_sequence=["#007a00"], labels={col: "張數", "label": ""})
        fig2.update_layout(height=520, margin=dict(l=0, r=10, t=10, b=10),
                           yaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig2, use_container_width=True)

tab1, tab2, tab3 = st.tabs(["🌍 外資", "📦 投信", "🏢 自營商"])
with tab1:
    show_investor_tab(df, "外資")
with tab2:
    show_investor_tab(df, "投信")
with tab3:
    show_investor_tab(df, "自營商(自行)")

st.markdown("---")
st.subheader("📋 完整資料表（依三大法人合計排序）")
display_cols = [c for c in ["代號", "名稱", "外資", "投信", "自營商(自行)", "自營商(避險)", "三大法人合計"]
                if c in df.columns]
sort_col = "三大法人合計" if "三大法人合計" in df.columns else display_cols[-1]
st.dataframe(
    df[display_cols].sort_values(sort_col, ascending=False).reset_index(drop=True),
    use_container_width=True
)
