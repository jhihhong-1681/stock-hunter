import hmac
import time
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="交易紀錄 - 阿紘的股票儀表板", page_icon="📝", layout="wide")
from utils.styles import load_css
load_css()
st.title("📝 交易紀錄")
st.markdown("期權下單前檢查（部位大小、剩餘天數、槓桿與停損換算）和自己的交易紀錄。紀錄存在你自己的 Google Sheet，不同電腦、瀏覽器看到的是同一份。")

# 紀錄存在阿紘自己的 Google Sheet，透過 Apps Script 中繼（scripts/journal_relay.gs）讀寫。
# repo 是公開的，所以網址、金鑰、密碼都只放在 Streamlit secrets；沒輸入密碼前不會把金鑰交給瀏覽器。
API_URL = st.secrets.get("JOURNAL_API_URL", "")
API_KEY = st.secrets.get("JOURNAL_API_KEY", "")
PASSWORD = st.secrets.get("JOURNAL_PASSWORD", "")
JOURNAL_URL = "https://jhihhong-1681.github.io/stock-hunter/portfolio-calendar/journal.html"

if not (PASSWORD and API_URL and API_KEY):
    missing = [k for k, v in (("JOURNAL_PASSWORD", PASSWORD), ("JOURNAL_API_URL", API_URL), ("JOURNAL_API_KEY", API_KEY)) if not v]
    st.warning(
        f"尚未設定：{'、'.join(missing)}（Streamlit Cloud → Settings → Secrets），"
        "設定步驟寫在 `scripts/journal_relay.gs` 開頭。設定完成前，下面的紀錄只會存在這個瀏覽器。"
    )
    components.iframe(f"{JOURNAL_URL}?v={int(time.time() // 300)}", height=1400, scrolling=True)
    st.stop()

if not st.session_state.get("journal_unlocked"):
    with st.form("journal_login"):
        pw = st.text_input("請輸入密碼", type="password")
        if st.form_submit_button("解鎖"):
            if hmac.compare_digest(pw, PASSWORD):
                st.session_state["journal_unlocked"] = True
                st.rerun()
            else:
                st.error("密碼錯誤")
    st.stop()

# 網址 # 後面的參數不會送到 GitHub Pages 伺服器，只有瀏覽器裡的頁面讀得到。
components.iframe(
    f"{JOURNAL_URL}?v={int(time.time() // 300)}#api={quote(API_URL, safe='')}&key={quote(API_KEY, safe='')}",
    height=1400,
    scrolling=True,
)
