import time
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="報酬日曆 - 阿紘的股票儀表板", page_icon="📅", layout="wide")
from utils.styles import load_css
load_css()
st.title("📅 報酬日曆")
st.markdown("每個交易日自動更新的投資組合快照：月曆式每日損益、資產走勢、大盤對比、持股明細與主題曝險。")

CALENDAR_URL = "https://jhihhong-1681.github.io/stock-hunter/portfolio-calendar/"

st.link_button("↗ 在新分頁開啟完整版", CALENDAR_URL)

# 加上時間戳查詢參數，避免 GitHub Pages CDN 或瀏覽器把 iframe 內容快取住，
# 導致改版後這裡還顯示舊畫面。
components.iframe(f"{CALENDAR_URL}?v={int(time.time())}", height=1400, scrolling=True)
