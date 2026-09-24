import hmac
import html
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

st.set_page_config(page_title="研究監控日誌 - 阿紘的股票儀表板", page_icon="📰", layout="wide")
from utils.styles import load_css
load_css()
st.title("📰 研究監控日誌")

# 付費電子報內容只存在阿紘的私人 Google Drive 資料夾，這個 app 的 repo 是公開的，所以：
#   1. 資料由伺服器透過 Apps Script 中繼 API（scripts/research_log_relay.gs）帶金鑰讀取，
#      網址跟金鑰都只放在 Streamlit secrets，不會出現在公開 repo 或網頁原始碼裡。
#   2. 沒輸入密碼前完全不讀資料，瀏覽器拿不到任何內容。
# Cowork 的每小時監控排程（台北 21:30～03:30）每跑一次就在 Drive 資料夾新增一個小檔案
# （這次的執行紀錄＋這次新抓到的文章），同一天的多個檔案在這裡合併。
API_URL = st.secrets.get("RESEARCH_API_URL", "")
API_KEY = st.secrets.get("RESEARCH_API_KEY", "")
PASSWORD = st.secrets.get("RESEARCH_PASSWORD", "")
TAIPEI = timezone(timedelta(hours=8))

SITE_LABEL = {"paradigm": "PARADIGM PRESS", "oxford": "THE OXFORD CLUB", "banyan": "BANYAN HILL"}
WEEKDAY = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]


# ── 密碼鎖 ──────────────────────────────────────────────
if not (PASSWORD and API_URL and API_KEY):
    missing = [k for k, v in (("RESEARCH_PASSWORD", PASSWORD), ("RESEARCH_API_URL", API_URL), ("RESEARCH_API_KEY", API_KEY)) if not v]
    try:
        seen = list(st.secrets.keys())
    except Exception:
        seen = []
    # 只列設定「名稱」方便排查（例如被寫到某個 [區段] 底下），不顯示任何值。
    st.warning(
        f"尚未設定：{'、'.join(missing)}（Streamlit Cloud → Settings → Secrets）。\n\n"
        f"目前讀得到的最上層設定名稱：{'、'.join(seen) or '（無）'}"
    )
    st.stop()

if not st.session_state.get("research_unlocked"):
    with st.form("research_login"):
        pw = st.text_input("這頁包含付費電子報內容，請輸入密碼", type="password")
        if st.form_submit_button("解鎖"):
            if hmac.compare_digest(pw, PASSWORD):
                st.session_state["research_unlocked"] = True
                st.rerun()
            else:
                st.error("密碼錯誤")
    st.stop()


# ── 透過 Apps Script 中繼讀 Drive 資料夾 ─────────────────
def _call(params: dict) -> dict:
    r = requests.get(API_URL, params={"key": API_KEY, **params}, timeout=60)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data


@st.cache_data(ttl=120, show_spinner=False)
def list_dates() -> list[str]:
    return _call({"action": "list"})["dates"]


def merge_parts(date_str: str, parts: list[dict]) -> dict:
    """同一天可能有好幾個檔案（每次執行一個＋補舊資料的一個）：runs 依時間合併去重，
    articles 用 網址/標題＋發布時間 去重（75 分鐘的掃描窗口會讓同一篇在相鄰兩次執行都被抓到），保留最後寫入的版本。"""
    runs, articles = {}, {}
    for part in parts:
        for r in part.get("runs") or []:
            runs[r.get("ranAtUtc")] = r
        for a in part.get("articles") or []:
            articles[(a.get("url") or a.get("title"), a.get("publishedAtUtc"))] = a
    return {"date": date_str, "runs": list(runs.values()), "articles": list(articles.values())}


@st.cache_data(ttl=120, show_spinner=False)
def load_days(date_strs: tuple[str, ...]) -> dict[str, dict]:
    raw = _call({"action": "get", "dates": ",".join(date_strs)})["days"]
    return {d: merge_parts(d, parts) for d, parts in raw.items() if parts}


# ── 畫面 ────────────────────────────────────────────────
st.markdown("""
<style>
.rl-day { margin: 0.4rem 0 1.6rem; }
.rl-dayhead { display:flex; justify-content:space-between; align-items:baseline; gap:12px; margin-bottom:6px; }
.rl-daytitle { font-weight:700; font-size:1.02rem; }
.rl-daycount { color:rgba(250,250,250,0.55); font-size:0.82rem; }
.rl-dots { display:flex; gap:3px; flex-wrap:wrap; margin-bottom:10px; }
.rl-dot { width:10px; height:10px; border-radius:2px; background:#3a3f4a; }
.rl-dot.ok { background:#2fbf6a; } .rl-dot.fail { background:#ff5c5c; } .rl-dot.partial { background:#d9a24b; }
.rl-card { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.09); border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.rl-top { display:flex; align-items:center; gap:8px; margin-bottom:8px; flex-wrap:wrap; }
.rl-site { font-size:0.68rem; font-weight:700; letter-spacing:0.05em; padding:2px 8px; border-radius:20px; border:1px solid rgba(255,255,255,0.15); color:#f0c37e; }
.rl-time { margin-left:auto; font-size:0.72rem; color:rgba(250,250,250,0.45); font-family:monospace; }
.rl-trade { display:flex; align-items:center; gap:10px; row-gap:6px; flex-wrap:wrap; border-radius:9px; padding:9px 12px; margin-bottom:9px; }
.rl-trade.buy { background:rgba(47,191,106,0.12); border:1.5px solid #2fbf6a; }
.rl-trade.sell { background:rgba(217,162,75,0.10); border:1.5px solid #d9a24b; }
.rl-trade.stop { background:rgba(255,92,92,0.12); border:1.5px solid #ff5c5c; }
.rl-ticker { font-family:monospace; font-weight:700; font-size:1.25rem; }
.rl-trade.buy .rl-ticker { color:#5fd48c; } .rl-trade.sell .rl-ticker { color:#f0c37e; } .rl-trade.stop .rl-ticker { color:#ff8a8a; }
.rl-price { font-family:monospace; font-size:0.74rem; color:rgba(250,250,250,0.6); }
.rl-action { font-size:0.74rem; font-weight:600; padding:2px 9px; border-radius:20px; border:1px solid rgba(255,255,255,0.15); }
.rl-entry { margin-left:auto; text-align:right; }
.rl-entry .lbl { display:block; font-size:0.62rem; color:rgba(250,250,250,0.55); }
.rl-entry .val { font-family:monospace; font-weight:700; font-size:1.02rem; }
.rl-contract { flex-basis:100%; font-family:monospace; font-size:0.74rem; color:rgba(250,250,250,0.7); }
.rl-card h4 { margin:0 0 4px; font-size:1rem; }
.rl-card h4 a { color:#fafafa; text-decoration:none; } .rl-card h4 a:hover { text-decoration:underline; }
.rl-summary { color:rgba(250,250,250,0.7); font-size:0.87rem; margin:0 0 8px; }
.rl-chips { display:flex; gap:6px; flex-wrap:wrap; }
.rl-chip { font-family:monospace; font-size:0.74rem; padding:3px 8px; border-radius:6px; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); }
.rl-chip b { color:#f0c37e; }
.rl-fail { font-size:0.78rem; color:#ff8a8a; background:rgba(255,92,92,0.1); border-radius:6px; padding:5px 10px; display:inline-block; }
</style>
""", unsafe_allow_html=True)


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def fmt_taipei(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TAIPEI).strftime("%H:%M") + " 台北"
    except ValueError:
        return iso


def day_title(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.year}年{d.month}月{d.day}日（{WEEKDAY[d.weekday()]}）"


def run_cls(run: dict) -> str:
    results = run.get("results") or []
    ok = sum(1 for r in results if r.get("ok"))
    return "" if not results else "ok" if ok == len(results) else "fail" if ok == 0 else "partial"


def trade_box(e: dict | None) -> str:
    if not e or not e.get("ticker"):
        return ""
    action = e.get("action") or ""
    cls = "buy" if "買進" in action else "stop" if "停損" in action else "sell"
    price = f'<span class="rl-price">正股現價 <b>{esc(e["currentPrice"])}</b>（{esc(fmt_taipei(e.get("priceAsOfUtc")))}）</span>' if e.get("currentPrice") else ""
    act = f'<span class="rl-action">{esc(action)}{" · " + esc(e["instrument"]) if e.get("instrument") else ""}</span>' if action else ""
    entry = f'<span class="rl-entry"><span class="lbl">{"進場價" if cls == "buy" else "出場價"}</span><span class="val">{esc(e["entry"])}</span></span>' if e.get("entry") else ""
    contract = f'<span class="rl-contract">{esc(e["contract"])}</span>' if e.get("contract") else ""
    return f'<div class="rl-trade {cls}"><div><div class="rl-ticker">{esc(e["ticker"])}</div>{price}</div>{act}{entry}{contract}</div>'


def chips(e: dict | None) -> str:
    if not e:
        return ""
    out = [f'<span class="rl-chip">{label} <b>{esc(e[k])}</b></span>' for k, label in (("exit", "出場"), ("target", "目標價"), ("stop", "停損")) if e.get(k)]
    if e.get("note"):
        out.append(f'<span class="rl-chip">{esc(e["note"])}</span>')
    return f'<div class="rl-chips">{"".join(out)}</div>' if out else ""


def article_card(a: dict) -> str:
    title = f'<a href="{esc(a["url"])}" target="_blank" rel="noopener">{esc(a.get("title"))}</a>' if a.get("url") else esc(a.get("title"))
    summary = f'<p class="rl-summary">{esc(a["summary"])}</p>' if a.get("summary") else ""
    return (
        f'<div class="rl-card"><div class="rl-top"><span class="rl-site">{esc(SITE_LABEL.get(a.get("site"), a.get("site")))}</span>'
        f'<span class="rl-time">{esc(fmt_taipei(a.get("publishedAtUtc")))}</span></div>'
        f'{trade_box(a.get("entryExit"))}<h4>{title}</h4>{summary}{chips(a.get("entryExit"))}</div>'
    )


def render_day(day: dict) -> None:
    runs = sorted(day.get("runs") or [], key=lambda r: r.get("ranAtUtc") or "")
    articles = sorted(day.get("articles") or [], key=lambda a: a.get("publishedAtUtc") or "", reverse=True)
    dots = "".join(f'<span class="rl-dot {run_cls(r)}" title="{esc(fmt_taipei(r.get("ranAtUtc")))}"></span>' for r in runs)
    fails = sorted({f'{SITE_LABEL.get(x.get("site"), x.get("site"))}：{x["error"]}' for r in runs for x in (r.get("results") or []) if not x.get("ok") and x.get("error")})
    body = "".join(article_card(a) for a in articles) or '<div class="rl-daycount">這天沒有新文章</div>'
    fail_html = f'<div class="rl-fail">檢查失敗：{"；".join(esc(f) for f in fails)}</div>' if fails else ""
    st.markdown(
        f'<div class="rl-day"><div class="rl-dayhead"><span class="rl-daytitle">{esc(day_title(day["date"]))}</span>'
        f'<span class="rl-daycount">{len(articles)} 篇新文章 · {len(runs)} 次檢查</span></div>'
        f'<div class="rl-dots">{dots}</div>{body}{fail_html}</div>',
        unsafe_allow_html=True,
    )


st.markdown("Paradigm Press／The Oxford Club／Banyan Hill，交易日台北 21:30～03:30 每小時自動掃描。🟩 成功　🟥 失敗　🟨 部分失敗")

try:
    dates = list_dates()
except Exception as e:
    st.error(f"讀取監控資料失敗：{e}")
    st.stop()

if not dates:
    st.info("還沒有任何監控紀錄。")
    st.stop()

c1, c2, c3 = st.columns([2, 2, 1])
mode = c1.radio("顯示", ["最近幾天", "指定日期"], horizontal=True, label_visibility="collapsed")
if c3.button("🔄 重新整理"):
    st.cache_data.clear()
    st.rerun()

if mode == "最近幾天":
    n = c2.selectbox("天數", [3, 7, 14, 30], index=1, format_func=lambda x: f"最近 {x} 個交易日", label_visibility="collapsed")
    show = dates[:n]
else:
    show = [c2.selectbox("日期", dates, format_func=day_title, label_visibility="collapsed")]

try:
    loaded = load_days(tuple(show))
except Exception as e:
    st.error(f"讀取監控資料失敗：{e}")
    st.stop()
for d in show:
    if d in loaded:
        render_day(loaded[d])

st.caption(f"資料每 2 分鐘快取一次 · 讀取時間 {datetime.now(TAIPEI):%H:%M} 台北")
