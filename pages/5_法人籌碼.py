import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import io
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(page_title="法人籌碼 - 阿紘的股票儀表板", page_icon="🏦", layout="wide")
st.title("🏦 三大法人買賣超（台股）")
st.markdown("資料來源：台灣證券交易所，每日收盤後約 1-2 小時更新。")

# 預設往前最近工作日
default_date = date.today() - timedelta(days=1)
while default_date.weekday() >= 5:
    default_date -= timedelta(days=1)

selected_date = st.date_input("選擇查詢日期（限交易日）", value=default_date)

INVESTOR_MAP = {
    "外陸資買賣超股數(不含外資自營商)": "外資",
    "投信買賣超股數": "投信",
    "自營商買賣超股數(自行買賣)": "自營商(自行)",
    "自營商買賣超股數(避險)": "自營商(避險)",
    "三大法人買賣超股數": "三大法人合計",
}

def _make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    # 先訪問頁面取得 session cookies
    try:
        s.get("https://www.twse.com.tw/zh/trading/fund/T86.html", verify=False, timeout=8)
    except Exception:
        pass
    return s

@st.cache_data(ttl=3600)
def fetch_twse_json(query_date: date):
    """方法一：TWSE JSON API（新版 rwd 路徑）"""
    date_str = query_date.strftime("%Y%m%d")
    s = _make_session()
    s.headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
    s.headers["X-Requested-With"] = "XMLHttpRequest"
    s.headers["Referer"] = "https://www.twse.com.tw/zh/trading/fund/T86.html"

    urls = [
        f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json",
        f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999",
    ]
    for url in urls:
        try:
            r = s.get(url, verify=False, timeout=15)
            if r.status_code == 200 and r.text.strip():
                data = r.json()
                if data.get("stat") == "OK" and data.get("data"):
                    df = pd.DataFrame(data["data"], columns=data["fields"])
                    return df, None
        except Exception:
            continue
    return None, "json_failed"

@st.cache_data(ttl=3600)
def fetch_twse_csv(query_date: date):
    """方法二：TWSE CSV 下載（Big5 編碼）"""
    date_str = query_date.strftime("%Y%m%d")
    s = _make_session()
    url = f"https://www.twse.com.tw/fund/T86?response=csv&date={date_str}&selectType=ALLBUT0999"
    try:
        r = s.get(url, verify=False, timeout=20)
        if r.status_code != 200 or not r.content:
            return None, "csv_empty"
        content = r.content.decode("big5", errors="ignore")
        lines = [l for l in content.splitlines() if l.strip()]
        # 找到標頭列（包含「證券代號」）
        header_idx = next((i for i, l in enumerate(lines) if "證券代號" in l), None)
        if header_idx is None:
            return None, "csv_no_header"
        csv_text = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_text), thousands=",")
        df = df.dropna(subset=[df.columns[0]])
        df = df[df.iloc[:, 0].astype(str).str.match(r"^\d{4}")]
        return df, None
    except Exception as e:
        return None, str(e)

@st.cache_data(ttl=3600)
def fetch_twse_openapi():
    """方法三：TWSE OpenAPI（只有最新交易日，不支援日期參數）"""
    url = "https://openapi.twse.com.tw/v1/fund/T86"
    try:
        r = requests.get(url, headers={"accept": "*/*", "User-Agent": "Mozilla/5.0"},
                         verify=False, timeout=15)
        if r.status_code == 200 and r.text.strip() and r.text.strip() != "[]":
            data = r.json()
            if data:
                return pd.DataFrame(data), None
        return None, "openapi_empty"
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

def clean_json_df(df):
    rename = {"證券代號": "代號", "證券名稱": "名稱"}
    rename.update(INVESTOR_MAP)
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in INVESTOR_MAP.values():
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", "").apply(pd.to_numeric, errors="coerce")
    return df

def clean_csv_df(df, name_map):
    # CSV 欄位名稱可能略有不同，做模糊比對
    col_map = {}
    for orig, new in INVESTOR_MAP.items():
        key = orig.replace("股數", "").replace("買賣超", "")
        for c in df.columns:
            if key in c:
                col_map[c] = new
                break
    df = df.rename(columns=col_map)
    if "證券代號" in df.columns:
        df = df.rename(columns={"證券代號": "代號", "證券名稱": "名稱"})
    elif df.columns[0] != "代號":
        df = df.rename(columns={df.columns[0]: "代號", df.columns[1]: "名稱"})
    for col in INVESTOR_MAP.values():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
    if "名稱" not in df.columns:
        df.insert(1, "名稱", df["代號"].map(name_map).fillna(""))
    return df

with st.spinner("嘗試抓取 TWSE 資料..."):
    name_map = fetch_stock_names()
    df, source = None, ""

    raw, err = fetch_twse_json(selected_date)
    if raw is not None:
        df = clean_json_df(raw)
        source = "TWSE JSON API"
    else:
        raw_csv, err2 = fetch_twse_csv(selected_date)
        if raw_csv is not None:
            df = clean_csv_df(raw_csv, name_map)
            source = "TWSE CSV"
        else:
            raw_api, err3 = fetch_twse_openapi()
            if raw_api is not None:
                df = clean_json_df(raw_api)
                source = "TWSE OpenAPI（最新交易日）"

if df is None:
    st.error("三種方式均無法取得資料，可能原因：")
    st.markdown("""
    1. **選擇的日期非交易日**（例假日）
    2. **資料尚未更新**（通常收盤後 1-2 小時，約台灣時間下午 5-6 點）
    3. **Streamlit Cloud 海外 IP 被 TWSE 封鎖**（此情況無法避免）

    若確認是 IP 問題，可考慮改用 FinMind Token（免費註冊）—— 在右上角選單切換頁面後回來，或直接在此頁加入 token 輸入。
    """)
    st.stop()

st.caption(f"資料來源：{source}")

# 確保必要欄位
for col in ["外資", "投信", "自營商(自行)", "三大法人合計"]:
    if col not in df.columns:
        df[col] = 0

if "名稱" not in df.columns:
    df.insert(1, "名稱", df.get("代號", pd.Series()).map(name_map).fillna(""))

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
