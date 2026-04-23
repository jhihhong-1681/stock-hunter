import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

st.set_page_config(page_title="法人籌碼 - 阿紘的股票儀表板", page_icon="🏦", layout="wide")
st.title("🏦 三大法人買賣超（台股）")
st.markdown("資料來源：台灣證券交易所，每日收盤後更新。")

# 預設往前一個工作日
default_date = date.today() - timedelta(days=1)
if default_date.weekday() >= 5:
    default_date -= timedelta(days=default_date.weekday() - 4)

selected_date = st.date_input("選擇查詢日期（限交易日）", value=default_date)

@st.cache_data(ttl=3600)
def fetch_institutional(query_date: date):
    date_str = query_date.strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15, verify=False)
        data = r.json()
        if data.get("stat") != "OK":
            return None, data.get("stat", "查無資料，請確認是否為交易日")
        df = pd.DataFrame(data["data"], columns=data["fields"])
        return df, None
    except Exception as e:
        return None, str(e)

with st.spinner("下載法人資料中..."):
    df, err = fetch_institutional(selected_date)

if err:
    st.error(f"無法取得資料：{err}")
    st.stop()

# --- 數值欄位整理 ---
NUM_COLS = {
    "外陸資買賣超股數(不含外資自營商)": "外資",
    "投信買賣超股數": "投信",
    "自營商買賣超股數(自行買賣)": "自營商(自行)",
    "自營商買賣超股數(避險)": "自營商(避險)",
    "三大法人買賣超股數": "三大法人合計",
}
RENAME = {"證券代號": "代號", "證券名稱": "名稱"}
RENAME.update(NUM_COLS)
df = df.rename(columns={k: v for k, v in RENAME.items() if k in df.columns})

for col in NUM_COLS.values():
    if col in df.columns:
        df[col] = df[col].astype(str).str.replace(",", "").apply(pd.to_numeric, errors="coerce")

# --- 前 N 大篩選 ---
top_n = st.slider("顯示前 N 大", min_value=10, max_value=50, value=20, step=5)

def show_investor_tab(df, col):
    if col not in df.columns:
        st.warning(f"找不到欄位：{col}")
        return
    valid = df[["代號", "名稱", col]].dropna(subset=[col])
    top_buy = valid.nlargest(top_n, col)
    top_sell = valid.nsmallest(top_n, col)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**買超前 {top_n}**")
        fig = px.bar(top_buy, x=col, y="名稱", orientation="h",
                     color_discrete_sequence=["#d90000"], labels={col: "股數"})
        fig.update_layout(height=520, margin=dict(l=0, r=10, t=10, b=10),
                          yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.markdown(f"**賣超前 {top_n}**")
        fig2 = px.bar(top_sell, x=col, y="名稱", orientation="h",
                      color_discrete_sequence=["#007a00"], labels={col: "股數"})
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
st.dataframe(df[display_cols].sort_values(sort_col, ascending=False).reset_index(drop=True),
             use_container_width=True)
