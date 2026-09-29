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


# ── 標的總表：每一則推薦一列，賣出警報往前找買進紀錄算漲跌幅 ─────────
TICKER_SPLIT = re.compile(r"[／/、,，]")

# 分析師：新資料由 Cowork 直接寫 analyst 欄位；舊資料沒有，就從標題／摘要／備註裡認出名字或專欄名稱。
ANALYSTS = [
    ("Marc Lichtenfeld", r"Lichtenfeld|Trigger Event Trader|Technical Pattern Profits|23謎題|Enigma"),
    ("Alexander Green", r"Alexander Green|亞歷山大[·・]?格林|Oxford Microcap Trader|Insider Alert"),
    ("Mark Skousen", r"Skousen|史庫森"),
    ("Kristin Orman", r"Kristin Orman"),
    ("Jim Rickards", r"Rickards|瑞卡茲|Strategic Intelligence|內部情報"),
    ("Dan Amoss", r"Dan Amoss|丹[·・]?阿莫斯"),
    ("Matt Badiali", r"Badiali"),
    ("Ray Blanco", r"Ray Blanco"),
    ("Enrique Abeyta", r"Abeyta"),
    ("Alan Knuckman", r"Knuckman|Project Prophecy"),
    ("Mason Sexton", r"Mason Sexton|梅森[·・]?塞克斯頓|The Map"),
    ("Ronan McMahon", r"McMahon|Real Estate Trend Alert"),
    ("Tim Sykes", r"Tim Sykes|XGPT"),
    ("Jon Najarian", r"Najarian|納吉安|TRADEMONSTER|TradeMonster|MONSTER\.ai"),
    ("Ian Dyer", r"Ian Dyer|伊恩[·・]?戴爾|TRADEMONSTER|TradeMonster|MONSTER\.ai"),
    ("Ian King", r"Ian King"),
    ("Adam O'Dell", r"O'Dell"),
    ("Ted Bauman", r"Bauman"),
    ("James Altucher", r"Altucher(?!'s Investment Network)"),
    ("Zach Scheidt", r"Scheidt"),
    ("Byron King", r"Byron King"),
]
ANALYST_RES = [(name, re.compile(p, re.I)) for name, p in ANALYSTS]


def detect_analyst(a: dict) -> str:
    if a.get("analyst"):
        return a["analyst"]
    text = " ".join(str(x or "") for x in (a.get("title"), a.get("summary"), (a.get("entryExit") or {}).get("note")))
    found = [name for name, rx in ANALYST_RES if rx.search(text)]
    return "、".join(found) if found else "未標示"


def pick_segment(text: str | None, ticker: str, multi: bool) -> str | None:
    """同一篇推薦好幾檔時，contract/entry 常寫成「RKLB：…；APPS：…」或「ELMT限價…／BMM限價…」，
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
    """推薦當下 Cowork 查到的正股價格（currentPrice 欄位）。"""
    if not text:
        return None
    m = re.search(rf"{re.escape(ticker)}\s*\$([\d,]+(?:\.\d+)?)", text) if multi else re.search(r"\$([\d,]+(?:\.\d+)?)", text)
    return float(m.group(1).replace(",", "")) if m else None


def price_in(text: str | None) -> float | None:
    """從「65.50美元或更低」「限價不高於$3.20／股」這類文字抓出進場價（只認 $ 或 美元 旁邊的數字）。
    轉倉這種「賣出舊倉限價7.70；買進新倉限價20.00」只看買進那段；停損價、履約價不算進場價；有「限價」就優先取限價。"""
    if not text:
        return None
    segs = re.split(r"[；;]", text)
    buys = [s for s in segs if "買進" in s]
    text = "；".join(buys) if buys and len(segs) > 1 else text
    text = re.sub(r"停損[^，,；;。]*", "", text)
    text = re.sub(r"履約價\s*\$?\s*[\d,.]+\s*(?:美元)?", "", text)
    num = r"([\d,]+(?:\.\d+)?)"
    m = re.search(rf"限價[^\d$，,；;]{{0,6}}\$?\s*{num}", text) or re.search(rf"\$\s*{num}|{num}\s*美元", text)
    if not m:
        return None
    return float(next(g for g in m.groups() if g).replace(",", ""))


def company_name(a: dict, ticker: str) -> str:
    """摘要裡常寫「Magnite（MGNI）」「Rocket Lab（RKLB）」，抓括號前的名稱。"""
    text = f'{a.get("title") or ""} {a.get("summary") or ""}'
    tail = rf"\s*[（(]\s*(?:[A-Za-z]+\s*[:：]\s*)?{re.escape(ticker)}\s*[）)，,]"
    for m in re.finditer(rf"([A-Za-z][A-Za-z0-9 .&'\-]{{2,40}}){tail}", text):
        name = m.group(1).strip()
        if not re.fullmatch(r"[A-Z]{1,4}", name):  # 排除「ETF」這種不是名稱的縮寫
            return name
    # 中文名稱前面要是標點或開頭，才不會把「調整艾克森美孚」「賣出火箭實驗室」的動詞一起抓進來。
    m = re.search(rf"(?:^|[\s，。、：；「『（(])([一-鿿]{{2,8}}){tail}", text)
    return re.sub(r"^(調整|賣出|買進|放空|出清|停損)", "", m.group(1)) if m else ""


def kind_of(e: dict, contract: str | None) -> str:
    inst = e.get("instrument") or ""
    opt = bool(contract) or bool(re.search(r"Call|Put|買權|賣權|選擇權", inst, re.I))
    stock = bool(re.search(r"股票|ETF", inst))
    return "股票＋期權" if opt and stock else "期權" if opt else "股票"


def is_buy(action: str) -> bool:
    return "買進" in action


def is_exit(action: str) -> bool:
    # 「買進（同時賣出舊倉位轉倉）」「調整停損」「賣出（放空）」「賣出開倉」都不是出場警報。
    if any(k in action for k in ("買進", "調整", "放空", "開倉")):
        return False
    return any(k in action for k in ("賣出", "停損", "出場", "了結"))


OCC_RE = re.compile(r"\b([A-Z]{1,6})(\d{6})([CP])(\d{8})\b")
EXPIRY_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})\s*到期")


def option_symbol(ticker: str, contract: str | None) -> str | None:
    """期權合約的 Yahoo 代碼（OCC 格式，例如 RKLB261016C00072000）。原文有寫就直接用，
    沒寫就從「2026/10/16到期・履約價72美元 Call」拼出來；缺到期日（例如只寫「1月到期」）就放棄。"""
    if not contract:
        return None
    m = OCC_RE.search(contract)
    if m and m.group(1) == ticker:
        return m.group(0)
    exp = EXPIRY_RE.search(contract)
    strike = re.search(r"履約價\s*\$?\s*([\d.]+)", contract)
    if not exp or not strike:
        return None
    cp = "P" if re.search(r"Put|賣權", contract, re.I) else "C"
    return f"{ticker}{exp.group(1)[2:]}{int(exp.group(2)):02d}{int(exp.group(3)):02d}{cp}{round(float(strike.group(1)) * 1000):08d}"


def build_rows(days: dict[str, dict]) -> list[dict]:
    # 接近午夜發布的文章可能同時出現在相鄰兩天的紀錄裡，用 網址＋時間＋代號 去重。
    rows = {}
    for day in days.values():
        for a in day.get("articles") or []:
            e = a.get("entryExit") or {}
            tickers = [t.strip() for t in TICKER_SPLIT.split(e.get("ticker") or "") if t.strip()]
            multi = len(tickers) > 1
            for t in tickers:
                contract = pick_segment(e.get("contract"), t, multi)
                entry = pick_segment(e.get("entry"), t, multi)
                kind = kind_of(e, contract)
                occ = option_symbol(t, contract) if kind == "期權" else None
                key = (a.get("url") or a.get("title"), a.get("publishedAtUtc"), t)
                rows[key] = {
                    "ticker": t, "name": company_name(a, t), "published": a.get("publishedAtUtc") or "",
                    "kind": kind, "action": e.get("action") or "", "entry": entry, "contract": contract,
                    "site": a.get("site"), "analyst": detect_analyst(a), "url": a.get("url"),
                    "rec_price": rec_price_for(e.get("currentPrice"), t, multi),
                    # 計價標的：期權用合約本身（比權利金），股票（含「股票＋期權」）用正股。
                    "symbol": occ or t, "entry_px": price_in(entry),
                }
    return sorted(rows.values(), key=lambda r: r["published"])


@st.cache_data(ttl=600, show_spinner=False)
def daily_closes(symbols: tuple[str, ...]) -> pd.DataFrame:
    """股票與期權合約近 6 個月的日收盤（yfinance；期權用 OCC 代碼，已到期的合約會抓不到）。"""
    valid = [s for s in symbols if re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,20}", s)]
    if not valid:
        return pd.DataFrame()
    try:
        df = yf.download(valid, period="6mo", interval="1d", progress=False, auto_adjust=False, threads=True)["Close"]
    except Exception:
        return pd.DataFrame()
    if isinstance(df, pd.Series):
        df = df.to_frame(valid[0])
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def close_on(closes: pd.DataFrame, symbol: str, iso: str | None = None) -> float | None:
    """某標的在某個時間點（美東日期）當天或之前最後一筆收盤；iso 為空就是最新收盤。"""
    if symbol not in closes.columns:
        return None
    s = closes[symbol].dropna()
    if iso:
        et_day = (datetime.fromisoformat(iso.replace("Z", "+00:00")) - timedelta(hours=4)).date()
        s = s[s.index.date <= et_day]
    return float(s.iloc[-1]) if not s.empty else None


def attach_returns(rows: list[dict], closes: pd.DataFrame) -> None:
    """漲跌幅：
    - 買進推薦：推薦時的進場價 → 最新收盤（期權比權利金，股票比股價）。
    - 賣出／停損警報：往前找同一檔最近一次買進推薦（同合約優先，再來同網站），買進進場價 → 出場價
      （原文有寫出場價就用，沒寫就用出場當天的收盤）。
    期權合約抓不到報價（例如已到期或原文沒寫完整到期日）時，改用推薦當下與現在的正股價格，並標明「正股」。"""
    for i, r in enumerate(rows):
        r["change"], r["basis"] = float("nan"), ""
        unit = "權利金" if r["symbol"] != r["ticker"] else "股價"
        if is_buy(r["action"]):
            buy_px = r["entry_px"] or (r["rec_price"] if unit == "股價" else None)
            now_px = close_on(closes, r["symbol"])
            if not (buy_px and now_px) and r["rec_price"]:
                buy_px, now_px, unit = r["rec_price"], close_on(closes, r["ticker"]), "正股"
            if buy_px and now_px:
                r["change"] = (now_px - buy_px) / buy_px * 100
                r["basis"] = f"進場 ${buy_px:,.2f} → 最新收盤 ${now_px:,.2f}（{unit}）"
            continue
        if not is_exit(r["action"]):
            continue
        earlier = [b for b in rows[:i] if b["ticker"] == r["ticker"] and is_buy(b["action"]) and b["published"] < r["published"]]
        if not earlier:
            r["basis"] = "查無先前買進紀錄"
            continue
        b = ([x for x in earlier if x["symbol"] == r["symbol"]] or [x for x in earlier if x["site"] == r["site"]] or earlier)[-1]
        sym = b["symbol"]
        unit = "權利金" if sym != b["ticker"] else "股價"
        buy_px = b["entry_px"] or (b["rec_price"] if unit == "股價" else None)
        exit_px = r["entry_px"] or close_on(closes, sym, r["published"])
        if not (buy_px and exit_px) and b["rec_price"] and r["rec_price"]:
            buy_px, exit_px, unit = b["rec_price"], r["rec_price"], "正股"
        when = fmt_dt_taipei(b["published"])
        if buy_px and exit_px:
            r["change"] = (exit_px - buy_px) / buy_px * 100
            r["basis"] = f"{when} 買進 ${buy_px:,.2f} → 出場 ${exit_px:,.2f}（{unit}）"
        else:
            r["basis"] = f"{when} 買進，但缺少價格無法計算"


def fmt_dt_taipei(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TAIPEI).strftime("%m/%d %H:%M")
    except ValueError:
        return iso


def color_change(v) -> str:
    if pd.isna(v) or round(v, 1) == 0:  # 顯示成 0.0% 的就不上色（避免「-0.0%」變紅）
        return ""
    return "color: #2fbf6a; font-weight: 700" if v > 0 else "color: #ff5c5c; font-weight: 700"


def render_positions(dates: list[str]) -> None:
    # 賣出警報要往前找買進紀錄，所以讀最多 90 個交易日（中繼一次最多 31 天，分批讀）。
    span = dates[:90]
    try:
        with st.spinner(f"彙整最近 {len(span)} 個交易日的推薦中…（第一次開啟約需 10～60 秒）"):
            days = {}
            for i in range(0, len(span), 30):
                days.update(load_days(tuple(span[i:i + 30])))
    except Exception as e:
        st.error(f"讀取監控資料失敗：{e}")
        return
    rows = build_rows(days)
    if not rows:
        st.info("還沒有帶具體標的的推薦。")
        return
    with st.spinner("抓取最新收盤價中…"):
        closes = daily_closes(tuple(sorted({r["symbol"] for r in rows} | {r["ticker"] for r in rows})))
    attach_returns(rows, closes)

    f1, f2, f3 = st.columns(3)
    sites = f1.multiselect("網站", list(SITE_LABEL), format_func=SITE_LABEL.get, placeholder="全部網站")
    analysts = sorted({n for r in rows for n in r["analyst"].split("、")})
    picked = f2.multiselect("分析師", analysts, placeholder="全部分析師")
    term = f3.text_input("搜尋代號", placeholder="例如 RKLB").strip().upper()

    shown = [r for r in rows
             if (not sites or r["site"] in sites)
             and (not picked or any(n in picked for n in r["analyst"].split("、")))
             and (not term or term in r["ticker"].upper())]
    if not shown:
        st.info("沒有符合條件的推薦。")
        return

    df = pd.DataFrame([{
        "日期": fmt_dt_taipei(r["published"]),
        "標的": r["ticker"],
        "名稱": r["name"],
        "類型": r["kind"],
        "動作": r["action"],
        "進場點位": " ｜ ".join(x for x in (r["entry"], r["contract"]) if x),
        "網站": SITE_LABEL.get(r["site"], r["site"]),
        "分析師": r["analyst"],
        "漲跌幅": r["change"],
        "計算依據": r["basis"],
        "原文": r["url"],
    } for r in reversed(shown)])

    st.caption(f"共 {len(df)} 則推薦（最近 {len(span)} 個交易日）· 買進：進場價 → 最新收盤；賣出／停損：往前找買進進場價 → 出場價 · "
               "期權比權利金，股票比股價 · 🟩 上漲　🟥 下跌")
    df["漲跌幅"] = df["漲跌幅"].round(1) + 0.0  # +0.0 把 -0.0 變成 0.0
    styled = df.style.map(color_change, subset=["漲跌幅"]).format({"漲跌幅": "{:+.1f}%"}, na_rep="")
    st.dataframe(
        styled, hide_index=True, use_container_width=True, height=min(38 * len(df) + 40, 720),
        column_config={
            "進場點位": st.column_config.TextColumn(width="large"),
            "計算依據": st.column_config.TextColumn(width="medium"),
            "原文": st.column_config.LinkColumn(display_text="開啟"),
        },
    )


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
