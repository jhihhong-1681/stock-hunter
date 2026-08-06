import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="資產淨值 - 阿紘的股票儀表板", page_icon="💰", layout="wide")
from utils.styles import load_css
load_css()
st.title("💰 資產淨值")
st.markdown("每月資產淨值總表，複製自原本 Google Sheet 的月結紀錄：美股部位、國泰/中信/玉山現金、期貨、加密貨幣與總資產走勢。")

NETWORTH_URL = "https://jhihhong-1681.github.io/portfolio-calendar/networth.html"

st.link_button("↗ 在新分頁開啟完整版", NETWORTH_URL)

components.iframe(NETWORTH_URL, height=1400, scrolling=True)
