import hmac
import time
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="報酬日曆 - 阿紘的股票儀表板", page_icon="📅", layout="wide")
from utils.styles import load_css
load_css()
st.title("📅 報酬日曆")
st.markdown("每個交易日自動更新的投資組合快照：月曆式每日損益、資產走勢、大盤對比、持股明細與主題曝險。")

CALENDAR_URL = "https://jhihhong-1681.github.io/stock-hunter/portfolio-calendar/"

st.link_button("↗ 在新分頁開啟完整版", CALENDAR_URL)

# 「未成交訂單追蹤」的 ✕ 刪除要寫進阿紘的 Google Sheet（跟交易紀錄頁共用同一支 Apps Script 中繼 scripts/journal_relay.gs）。
# repo 是公開的，網址和金鑰只放在 Streamlit secrets；輸入交易紀錄頁同一組密碼解鎖後，才會把它們帶進 iframe 的 # 參數
# （# 後面不會送到 GitHub Pages 伺服器）。沒解鎖也能看日曆，只是沒有 ✕。
API_URL = st.secrets.get("JOURNAL_API_URL", "")
API_KEY = st.secrets.get("JOURNAL_API_KEY", "")
PASSWORD = st.secrets.get("JOURNAL_PASSWORD", "")

frag = ""
if PASSWORD and API_URL and API_KEY:
    if st.session_state.get("journal_unlocked"):
        frag = f"#api={quote(API_URL, safe='')}&key={quote(API_KEY, safe='')}"
    else:
        with st.expander("🔓 解鎖後可刪除未成交訂單追蹤"):
            with st.form("calendar_unlock"):
                pw = st.text_input("密碼（同交易紀錄頁）", type="password")
                if st.form_submit_button("解鎖"):
                    if hmac.compare_digest(pw, PASSWORD):
                        st.session_state["journal_unlocked"] = True
                        st.rerun()
                    else:
                        st.error("密碼錯誤")

# 加上時間戳查詢參數，避免 GitHub Pages CDN 或瀏覽器把 iframe 內容快取住，
# 導致改版後這裡還顯示舊畫面。
components.iframe(f"{CALENDAR_URL}?v={int(time.time() // 300)}{frag}", height=1400, scrolling=True)
