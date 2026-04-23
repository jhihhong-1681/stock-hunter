import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="法人籌碼 - 阿紘的股票儀表板", page_icon="🏦", layout="wide")
st.title("🏦 三大法人買賣超（台股）")
st.markdown("資料來源：FinMind API（不限 IP，每日收盤後更新）。")

# 預設往前最近工作日
default_date = date.today() - timedelta(days=1)
while default_date.weekday() >= 5:
    default_date -= timedelta(days=1)

selected_date = st.date_input("選擇查詢日期（限交易日）", value=default_date)

INVESTOR_MAP = {
    "外陸資(不含外資自營商)": "外資",
    "外資自營商": "外資自營商",
    "投信": "投信",
    "自營商(自行買賣)": "自營商(自行)",
    "自營商(避險)": "自營商(避險)",
    "三大法人": "三大法人合計",
}

@st.cache_data(ttl=3600)
def fetch_finmind(query_date: date):
    """FinMind API - 不限 IP，免費使用（無需 token）"""
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInstitutionalInvestors",
        "start_date": query_date.strftime("%Y-%m-%d"),
        "end_date": query_date.strftime("%Y-%m-%d"),
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
        if data.get("status") != 200 or not data.get("data"):
            return None, data.get("msg", "查無資料，可能非交易日或資料尚未更新")
        return pd.DataFrame(data["data"]), None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=3600*24)
def fetch_stock_names():
    """從 TWSE OpenAPI 取得股票名稱對照"""
    try:
        r = requests.get(
            "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            headers={"User-Agent": "Mozilla/5.0", "accept": "*/*"},
            timeout=15, verify=False
        )
        items = r.json()
        return {item["公司代號"]: item["公司名稱"] for item in items if "公司代號" in item}
    except Exception:
        return {}

with st.spinner("下載法人資料中..."):
    raw_df, err = fetch_finmind(selected_date)
    name_map = fetch_stock_names()

if raw_df is None:
    st.error(f"無法取得資料：{err}")
    st.info("FinMind 免費額度：每天 30 次請求。若遇到額度限制，請稍後再試。")
    st.stop()

# --- 整理資料：計算淨買賣（買 - 賣）並 pivot ---
raw_df["net"] = raw_df["buy"] - raw_df["sell"]
raw_df["investor"] = raw_df["name"].map(INVESTOR_MAP).fillna(raw_df["name"])
raw_df["名稱"] = raw_df["stock_id"].map(name_map).fillna("")
raw_df["代號"] = raw_df["stock_id"]

pivot = raw_df.pivot_table(
    index=["代號", "名稱"], columns="investor", values="net", aggfunc="sum"
).reset_index()
pivot.columns.name = None

# 確保關鍵欄位存在
for col in ["外資", "投信", "自營商(自行)", "三大法人合計"]:
    if col not in pivot.columns:
        pivot[col] = 0

# --- 前 N 大篩選 ---
top_n = st.slider("顯示前 N 大", min_value=10, max_value=50, value=20, step=5)

def show_investor_tab(df, col):
    if col not in df.columns:
        st.warning(f"找不到欄位：{col}")
        return
    valid = df[["代號", "名稱", col]].dropna(subset=[col])
    top_buy = valid.nlargest(top_n, col)
    top_sell = valid.nsmallest(top_n, col)
    top_buy["label"] = top_buy["代號"] + " " + top_buy["名稱"]
    top_sell["label"] = top_sell["代號"] + " " + top_sell["名稱"]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**買超前 {top_n}**")
        fig = px.bar(top_buy, x=col, y="label", orientation="h",
                     color_discrete_sequence=["#d90000"], labels={col: "股數（張）", "label": ""})
        fig.update_layout(height=520, margin=dict(l=0, r=10, t=10, b=10),
                          yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown(f"**賣超前 {top_n}**")
        fig2 = px.bar(top_sell, x=col, y="label", orientation="h",
                      color_discrete_sequence=["#007a00"], labels={col: "股數（張）", "label": ""})
        fig2.update_layout(height=520, margin=dict(l=0, r=10, t=10, b=10),
                           yaxis={"categoryorder": "total descending"})
        st.plotly_chart(fig2, use_container_width=True)

tab1, tab2, tab3 = st.tabs(["🌍 外資", "📦 投信", "🏢 自營商"])
with tab1:
    show_investor_tab(pivot, "外資")
with tab2:
    show_investor_tab(pivot, "投信")
with tab3:
    show_investor_tab(pivot, "自營商(自行)")

st.markdown("---")
st.subheader("📋 完整資料表（依三大法人合計排序）")
display_cols = [c for c in ["代號", "名稱", "外資", "投信", "自營商(自行)", "自營商(避險)", "三大法人合計"]
                if c in pivot.columns]
sort_col = "三大法人合計" if "三大法人合計" in pivot.columns else display_cols[-1]
st.dataframe(
    pivot[display_cols].sort_values(sort_col, ascending=False).reset_index(drop=True),
    use_container_width=True
)
