import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="持股更新 - 阿紘的股票儀表板", page_icon="📊", layout="wide")
from utils.styles import load_css
load_css()
st.title("📊 持股更新")
st.markdown("取代 Google Sheet 的持股編輯介面：登入後可以直接修改股數、成本、現價、現金、總資產等欄位，即時同步到雲端。")

EDITOR_URL = "https://jhihhong-1681.github.io/portfolio-calendar/holdings-editor.html"

st.link_button("↗ 在新分頁開啟完整版", EDITOR_URL)

components.iframe(EDITOR_URL, height=1400, scrolling=True)
