import streamlit as st

_CSS = """
<style>
/* ── 標題下方強調線 ──────────────────────────────────── */
h1 {
    padding-bottom: 0.55rem !important;
    border-bottom: 2px solid rgba(255,75,75,0.30) !important;
    margin-bottom: 1.4rem !important;
}

/* ── Metric 卡片 ─────────────────────────────────────── */
[data-testid="stMetric"] {
    background : rgba(255,255,255,0.04);
    border     : 1px solid rgba(255,255,255,0.09);
    border-radius: 10px;
    padding    : 1rem 1.25rem !important;
    transition : border-color 0.2s;
}
[data-testid="stMetric"]:hover {
    border-color: rgba(255,75,75,0.35);
}
[data-testid="stMetricLabel"] p {
    font-size     : 0.76rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color         : rgba(250,250,250,0.50);
}
[data-testid="stMetricValue"] {
    font-size  : 1.55rem;
    font-weight: 700;
}

/* ── Tabs ────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap           : 2px;
    background    : rgba(255,255,255,0.03);
    border-radius : 8px;
    padding       : 3px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    padding      : 6px 20px;
    font-weight  : 500;
}
.stTabs [aria-selected="true"] {
    background: rgba(255,75,75,0.18) !important;
}

/* ── Primary 按鈕 ────────────────────────────────────── */
.stButton > button[kind="primary"] {
    border-radius: 8px;
    font-weight  : 600;
    letter-spacing: 0.04em;
    transition   : transform 0.15s, box-shadow 0.15s;
}
.stButton > button[kind="primary"]:hover {
    transform : translateY(-2px);
    box-shadow: 0 6px 20px rgba(255,75,75,0.35);
}

/* ── 分隔線 ──────────────────────────────────────────── */
hr {
    border-color: rgba(255,255,255,0.08) !important;
    margin: 1.4rem 0 !important;
}

/* ── Alert / Info box ────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 8px;
}

/* ── Caption ─────────────────────────────────────────── */
.stCaption p {
    font-size: 0.77rem;
    color    : rgba(250,250,250,0.42);
}

/* ── Sidebar ─────────────────────────────────────────── */
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0.8rem;
}
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.08) !important;
    margin: 0.3rem 0 !important;
}

/* ── DataFrame 圓角 ──────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 8px;
    overflow     : hidden;
}

/* ── Selectbox / Slider 統一圓角 ─────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stNumberInput"] > div > div > input {
    border-radius: 6px !important;
}
</style>
"""

def load_css():
    """每個頁面的 set_page_config 之後呼叫此函式，套用全站統一樣式。"""
    st.markdown(_CSS, unsafe_allow_html=True)