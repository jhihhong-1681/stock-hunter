import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="報酬日曆 - 阿紘的股票儀表板", page_icon="📅", layout="wide")
from utils.styles import load_css
load_css()
st.title("📅 報酬日曆")
st.markdown("每個交易日自動更新的投資組合快照：月曆式每日損益、資產走勢、大盤對比、持股明細與主題曝險。")

CALENDAR_URL = "https://jhihhong-1681.github.io/portfolio-calendar/"

st.link_button("↗ 在新分頁開啟完整版", CALENDAR_URL)

components.iframe(CALENDAR_URL, height=1400, scrolling=True)
