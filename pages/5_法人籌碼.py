import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="法人籌碼 - 阿紘的股票儀表板", page_icon="🏦", layout="wide")
st.title("🏦 三大法人買賣超（台股）")

# --- FinMind Token 說明 ---
with st.expander("🔑 設定 FinMind API Token（首次使用請展開）", expanded="finmind_token" not in st.session_state):
    st.markdown("""
    資料來源為 [FinMind](https://finmindtrade.com/)，**免費註冊**即可取得 token，不需信用卡。

    1. 前往 [https://finmindtrade.com/](https://finmindtrade.com/) → 右上角「登入/註冊」
    2. 完成免費註冊後，進入「個人頁面」複製你的 **API Token**
    3. 貼到下方欄位，即可使用（免費版每天 600 次請求）
    """)
    token_input = st.text_input("貼上你的 FinMind Token", type="password",
                                 value=st.session_state.get("finmind_token", ""))
    if st.button("儲存 Token"):
        st.session_state["finmind_token"] = token_input.strip()
        st.success("Token 已儲存，本次 session 有效。")
        st.rerun()

token = st.session_state.get("finmind_token", "")
if not token:
    st.warning("尚未設定 FinMind Token，請展開上方說明完成設定。")
    st.stop()

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
def fetch_finmind(query_date: date, token: str):
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInstitutionalInvestors",
        "start_date": query_date.strftime("%Y-%m-%d"),
        "end_date": query_date.strftime("%Y-%m-%d"),
        "token": token,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
        if data.get("status") != 200:
            return None, f"FinMind 回傳：{data.get('msg', '未知錯誤')}（status {data.get('status')}）"
        if not data.get("data"):
            return None, "查無資料，可能非交易日或該日資料尚未更新（通常收盤後 ~1 小時）"
        return pd.DataFrame(data["data"]), None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=3600 * 24)
def fetch_stock_names():
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
    raw_df, err = fetch_finmind(selected_date, token)
    name_map = fetch_stock_names()

if raw_df is None:
    st.error(f"無法取得資料：{err}")
    st.stop()

# --- 整理：計算淨買賣並 pivot ---
raw_df["net"] = raw_df["buy"] - raw_df["sell"]
raw_df["investor"] = raw_df["name"].map(INVESTOR_MAP).fillna(raw_df["name"])
raw_df["名稱"] = raw_df["stock_id"].map(name_map).fillna("")
raw_df["代號"] = raw_df["stock_id"]

pivot = raw_df.pivot_table(
    index=["代號", "名稱"], columns="investor", values="net", aggfunc="sum"
).reset_index()
pivot.columns.name = None

for col in ["外資", "投信", "自營商(自行)", "三大法人合計"]:
    if col not in pivot.columns:
        pivot[col] = 0

top_n = st.slider("顯示前 N 大", min_value=10, max_value=50, value=20, step=5)

def show_investor_tab(df, col):
    if col not in df.columns:
        st.warning(f"找不到欄位：{col}")
        return
    valid = df[["代號", "名稱", col]].dropna(subset=[col])
    top_buy = valid.nlargest(top_n, col).copy()
    top_sell = valid.nsmallest(top_n, col).copy()
    top_buy["label"] = top_buy["代號"] + " " + top_buy["名稱"]
    top_sell["label"] = top_sell["代號"] + " " + top_sell["名稱"]

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
