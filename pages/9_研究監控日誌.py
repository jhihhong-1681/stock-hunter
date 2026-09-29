import hashlib
import hmac
import html
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

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
    # Apps Script 先回 302 轉到 script.googleusercontent.com 的一次性結果網址，偶爾那一步會回 404
    # （同一個請求直接重打就好），所以自己處理轉址並重試幾次。
    last = None
    for _ in range(3):
        first = requests.get(API_URL, params={"key": API_KEY, **params}, timeout=90, allow_redirects=False)
        r = requests.get(first.headers["Location"], timeout=60) if first.is_redirect else first
        if r.status_code == 200:
            break
        last = r
    else:
        last.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data["error"])
    return data


@st.cache_data(ttl=600, show_spinner=False)
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


@st.cache_data(ttl=600, show_spinner=False)
def load_days(date_strs: tuple[str, ...]) -> dict[str, dict]:
    raw = _call({"action": "get", "dates": ",".join(date_strs)})["days"]
    return {d: merge_parts(d, parts) for d, parts in raw.items() if parts}


def load_statuses() -> dict:
    """標的總表的手動狀態，存在 Drive 資料夾的 _status.json。每個 session 讀一次，之後改動直接更新本地副本。"""
    if "rl_statuses" not in st.session_state:
        try:
            st.session_state["rl_statuses"] = _call({"action": "status"}).get("statuses", {})
        except Exception:
            st.session_state["rl_statuses"] = None  # 中繼還沒更新到有狀態功能的版本
    return st.session_state["rl_statuses"]


def save_status(entry_id: str, status: str) -> bool:
    try:
        payload = {"action": "setStatus", "id": entry_id, "status": status}
        first = requests.post(API_URL, params={"key": API_KEY, **payload}, json=payload, timeout=60, allow_redirects=False)
        r = requests.get(first.headers["Location"], timeout=60) if first.is_redirect else first
        ok = r.status_code == 200 and r.json().get("ok")
    except Exception:
        ok = False
    if ok and st.session_state.get("rl_statuses") is not None:
        st.session_state["rl_statuses"][entry_id] = {"status": status, "updatedAtUtc": datetime.now(timezone.utc).isoformat()}
    return bool(ok)


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
.pt-head { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; }
.pt-ticker { font-family:monospace; font-weight:700; font-size:1.3rem; }
.pt-price { font-family:monospace; font-size:0.85rem; color:rgba(250,250,250,0.7); }
.pt-price b { color:#fafafa; }
.pt-count { margin-left:auto; font-size:0.78rem; color:rgba(250,250,250,0.5); }
.pt-badge { font-size:0.68rem; font-weight:700; padding:1px 8px; border-radius:20px; background:rgba(255,92,92,0.15); color:#ff8a8a; }
.pt-badge.neutral { background:rgba(255,255,255,0.06); color:rgba(250,250,250,0.65); border:1px solid rgba(255,255,255,0.12); }
.pt-entry { border-top:1px solid rgba(255,255,255,0.08); padding-top:8px; margin-top:6px; }
.pt-entry.inactive { opacity:0.5; }
.pt-top { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:4px; }
.pt-date { font-family:monospace; font-size:0.72rem; color:rgba(250,250,250,0.45); }
.pt-act { font-size:0.72rem; font-weight:700; padding:1px 9px; border-radius:20px; border:1px solid rgba(255,255,255,0.15); }
.pt-act.buy { color:#5fd48c; border-color:#2fbf6a; background:rgba(47,191,106,0.12); }
.pt-act.sell { color:#f0c37e; border-color:#d9a24b; }
.pt-act.stop { color:#ff8a8a; border-color:#ff5c5c; background:rgba(255,92,92,0.12); }
.pt-title a { color:#fafafa; text-decoration:none; font-size:0.9rem; } .pt-title a:hover { text-decoration:underline; }
.pt-rec { font-family:monospace; font-size:0.74rem; color:rgba(250,250,250,0.6); margin:3px 0 5px; }
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


# ── 標的總表：把文章裡的交易建議依標的分組 ───────────────
STATUS_VALUES = ["未處理", "已進場", "已出場", "忽略"]
TICKER_SPLIT = re.compile(r"[／/、,，]")
EXPIRY_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})\s*到期")


def pick_segment(text: str | None, ticker: str, multi: bool) -> str | None:
    """同一篇推薦好幾檔時，contract/entry/stop 常寫成「RKLB：…；APPS：…」或「ELMT限價…／BMM限價…」，
    只取這一檔的那段。先用分號切（「5.15美元／口」這種斜線不是分隔），切不出來再用全形斜線切。"""
    if not text or not multi:
        return text
    head = re.compile(rf"{re.escape(ticker)}(?![A-Za-z])")
    for sep in (r"[；;]", r"／"):
        segs = re.split(sep, text)
        if len(segs) < 2:
            continue
        for seg in segs:
            if head.match(seg.strip()):
                return seg.strip()
    return text


def rec_price_for(text: str | None, ticker: str, multi: bool) -> float | None:
    if not text:
        return None
    m = re.search(rf"{re.escape(ticker)}\s*\$([\d,]+(?:\.\d+)?)", text) if multi else re.search(r"\$([\d,]+(?:\.\d+)?)", text)
    return float(m.group(1).replace(",", "")) if m else None


def action_cls(action: str) -> str:
    return "buy" if "買進" in action else "stop" if "停損" in action else "sell"


def build_positions(days: dict[str, dict]) -> list[dict]:
    # 接近午夜發布的文章可能同時出現在相鄰兩天的紀錄裡，用 id 去重（也避免狀態選單的 key 重複）。
    rows = {}
    for day in days.values():
        for a in day.get("articles") or []:
            e = a.get("entryExit") or {}
            tickers = [t.strip() for t in TICKER_SPLIT.split(e.get("ticker") or "") if t.strip()]
            multi = len(tickers) > 1
            for t in tickers:
                contract = pick_segment(e.get("contract"), t, multi)
                m = EXPIRY_RE.search(contract or "")
                raw_id = f'{a.get("url") or a.get("title")}|{a.get("publishedAtUtc")}|{t}'
                entry_id = hashlib.sha1(raw_id.encode("utf-8")).hexdigest()[:16]
                rows[entry_id] = {
                    "id": entry_id,
                    "ticker": t, "display": e.get("ticker"), "multi": multi,
                    "site": a.get("site"), "title": a.get("title"), "url": a.get("url"),
                    "published": a.get("publishedAtUtc") or "",
                    "action": e.get("action") or "", "instrument": e.get("instrument"),
                    "entry": pick_segment(e.get("entry"), t, multi), "contract": contract,
                    "target": pick_segment(e.get("target"), t, multi), "stop": pick_segment(e.get("stop"), t, multi),
                    "note": e.get("note"),
                    "rec_price": rec_price_for(e.get("currentPrice"), t, multi),
                    "expiry": f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else None,
                }
    return list(rows.values())


@st.cache_data(ttl=600, show_spinner=False)
def latest_prices(tickers: tuple[str, ...]) -> dict[str, float]:
    valid = [t for t in tickers if re.fullmatch(r"[A-Z][A-Z.\-]{0,6}", t)]
    if not valid:
        return {}
    try:
        df = yf.download(valid, period="5d", interval="1d", progress=False, auto_adjust=False, threads=True)["Close"]
    except Exception:
        return {}
    if isinstance(df, pd.Series):
        df = df.to_frame(valid[0])
    out = {}
    for t in valid:
        if t in df.columns:
            s = df[t].dropna()
            if not s.empty:
                out[t] = float(s.iloc[-1])
    return out


def fmt_dt_taipei(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TAIPEI).strftime("%m/%d %H:%M")
    except ValueError:
        return iso


def on_status_change(entry_id: str) -> None:
    status = st.session_state[f"rl_st_{entry_id}"]
    if save_status(entry_id, status):
        st.toast(f"已儲存：{status}")
    else:
        st.toast("狀態儲存失敗，請稍後再試", icon="⚠️")


def render_positions(dates: list[str]) -> None:
    try:
        with st.spinner(f"彙整最近 {min(len(dates), 30)} 個交易日的推薦標的中…（第一次開啟約需 10～30 秒）"):
            days = load_days(tuple(dates[:30]))
    except Exception as e:
        st.error(f"讀取監控資料失敗：{e}")
        return
    rows = build_positions(days)
    if not rows:
        st.info("最近 30 個交易日沒有帶具體標的的交易建議。")
        return

    statuses = load_statuses()
    if statuses is None:
        st.warning("狀態功能還沒啟用：請照說明更新 Apps Script（管理部署作業 → 編輯 → 新版本）。目前先以「未處理」顯示、無法儲存。")
    status_of = lambda r: ((statuses or {}).get(r["id"]) or {}).get("status", "未處理")
    today = datetime.now(TAIPEI).strftime("%Y-%m-%d")
    expired = lambda r: bool(r["expiry"] and r["expiry"] < today)
    inactive = lambda r: expired(r) or status_of(r) in ("已出場", "忽略")

    f1, f2, f3, f4 = st.columns([2, 2, 1.4, 1.4])
    term = f1.text_input("搜尋代號", placeholder="搜尋代號或標題…", label_visibility="collapsed").strip().upper()
    sites = f2.multiselect("網站", list(SITE_LABEL), format_func=SITE_LABEL.get, placeholder="全部網站", label_visibility="collapsed")
    hide_inactive = f3.checkbox("隱藏已出場／忽略／到期", value=True)
    buy_only = f4.checkbox("只看有買進訊號的標的")

    groups: dict[str, list[dict]] = {}
    for r in rows:
        if sites and r["site"] not in sites:
            continue
        if term and term not in r["ticker"].upper() and term not in (r["title"] or "").upper():
            continue
        groups.setdefault(r["ticker"], []).append(r)
    for lst in groups.values():
        lst.sort(key=lambda r: r["published"], reverse=True)
    items = sorted(groups.items(), key=lambda kv: kv[1][0]["published"], reverse=True)
    if hide_inactive:
        items = [(t, lst) for t, lst in items if not inactive(lst[0])]
    if buy_only:
        items = [(t, lst) for t, lst in items if any("買進" in r["action"] for r in lst)]
    if not items:
        st.info("沒有符合條件的標的。")
        return

    prices = latest_prices(tuple(sorted(t for t, _ in items)))
    st.caption(f"共 {len(items)} 檔標的 · 現價為 yfinance 最近收盤（每 10 分鐘更新）· 狀態會存在你的私人 Drive")

    for ticker, lst in items:
        latest = lst[0]
        price = prices.get(ticker)
        price_html = f'現價 <b>${price:,.2f}</b>' if price else "現價查無資料"
        if price and latest["rec_price"]:
            chg = (price - latest["rec_price"]) / latest["rec_price"] * 100
            price_html += f'（較最新推薦時 {chg:+.1f}%）'
        badge = '<span class="pt-badge">最新一筆已到期</span>' if expired(latest) else ""
        with st.container(border=True):
            st.markdown(
                f'<div class="pt-head"><span class="pt-ticker">{esc(ticker)}</span><span class="pt-price">{price_html}</span>'
                f'{badge}<span class="pt-count">{len(lst)} 筆紀錄</span></div>', unsafe_allow_html=True)
            for r in lst:
                cls = action_cls(r["action"])
                tags = ""
                if expired(r):
                    tags += '<span class="pt-badge">已到期</span>'
                if r["multi"]:
                    tags += f'<span class="pt-badge neutral">同文多檔：{esc(r["display"])}</span>'
                title = f'<a href="{esc(r["url"])}" target="_blank" rel="noopener">{esc(r["title"])}</a>' if r["url"] else esc(r["title"])
                rec = f' · 推薦時正股 ${r["rec_price"]:,.2f}' if r["rec_price"] else ""
                detail = {"entry": "進場／出場", "contract": None, "target": "目標", "stop": "停損", "note": None}
                chip_html = "".join(
                    f'<span class="rl-chip">{label + " " if label else ""}<b>{esc(r[k])}</b></span>' if label else f'<span class="rl-chip">{esc(r[k])}</span>'
                    for k, label in detail.items() if r[k])
                st.markdown(
                    f'<div class="pt-entry{" inactive" if inactive(r) else ""}"><div class="pt-top">'
                    f'<span class="pt-date">{esc(fmt_dt_taipei(r["published"]))}</span>'
                    f'<span class="rl-site">{esc(SITE_LABEL.get(r["site"], r["site"]))}</span>'
                    f'<span class="pt-act {cls}">{esc(r["action"])}{" · " + esc(r["instrument"]) if r["instrument"] else ""}</span>{tags}</div>'
                    f'<div class="pt-title">{title}</div><div class="pt-rec">{esc(rec.lstrip(" ·"))}</div>'
                    f'<div class="rl-chips">{chip_html}</div></div>', unsafe_allow_html=True)
                key = f"rl_st_{r['id']}"
                if key not in st.session_state:
                    st.session_state[key] = status_of(r)
                st.selectbox("狀態", STATUS_VALUES, key=key, disabled=statuses is None,
                             on_change=on_status_change, args=(r["id"],))


st.markdown("Paradigm Press／The Oxford Club／Banyan Hill，交易日台北 21:30～03:30 每小時自動掃描。🟩 成功　🟥 失敗　🟨 部分失敗")

try:
    with st.spinner("讀取監控資料中…"):
        dates = list_dates()
except Exception as e:
    st.error(f"讀取監控資料失敗：{e}")
    st.stop()

if not dates:
    st.info("還沒有任何監控紀錄。")
    st.stop()

v1, v2 = st.columns([4, 1])
view = v1.radio("檢視", ["📋 監控日誌", "🎯 標的總表"], horizontal=True, label_visibility="collapsed")
if v2.button("🔄 重新整理"):
    st.cache_data.clear()
    st.session_state.pop("rl_statuses", None)
    st.rerun()

if view == "🎯 標的總表":
    render_positions(dates)
else:
    c1, c2 = st.columns([2, 2])
    mode = c1.radio("顯示", ["最近幾天", "指定日期"], horizontal=True, label_visibility="collapsed")
    if mode == "最近幾天":
        n = c2.selectbox("天數", [3, 7, 14, 30], index=1, format_func=lambda x: f"最近 {x} 個交易日", label_visibility="collapsed")
        show = dates[:n]
    else:
        show = [c2.selectbox("日期", dates, format_func=day_title, label_visibility="collapsed")]

    try:
        with st.spinner(f"讀取 {len(show)} 天的監控紀錄中…（第一次開啟約需 10～30 秒）"):
            loaded = load_days(tuple(show))
    except Exception as e:
        st.error(f"讀取監控資料失敗：{e}")
        st.stop()
    for d in show:
        if d in loaded:
            render_day(loaded[d])

st.caption(f"資料每 10 分鐘快取一次，要看最新請按「重新整理」 · 讀取時間 {datetime.now(TAIPEI):%H:%M} 台北")
