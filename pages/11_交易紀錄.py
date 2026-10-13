import time
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="交易紀錄 - 阿紘的股票儀表板", page_icon="📝", layout="wide")
from utils.styles import load_css
load_css()
st.title("📝 交易紀錄")
st.markdown("期權下單前檢查（部位大小、剩餘天數、槓桿與停損換算）、金字塔加碼試算，以及自己的交易紀錄。紀錄存在這台電腦的瀏覽器，記得定期匯出備份。")

JOURNAL_URL = "https://jhihhong-1681.github.io/stock-hunter/portfolio-calendar/journal.html"

st.link_button("↗ 在新分頁開啟完整版", JOURNAL_URL)

components.iframe(f"{JOURNAL_URL}?v={int(time.time())}", height=1400, scrolling=True)
