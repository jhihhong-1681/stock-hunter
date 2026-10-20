"""研究監控日誌的資料讀取與推薦解析（Streamlit 頁面共用）。

「研究監控日誌」頁和「交易紀錄」頁都要用：前者列出推薦總表，後者拿它來判斷新建倉位是哪個網站、哪位分析師推薦的。
網址、金鑰只放在 Streamlit secrets，repo 是公開的。
"""
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

API_URL = st.secrets.get("RESEARCH_API_URL", "")
API_KEY = st.secrets.get("RESEARCH_API_KEY", "")
TAIPEI = timezone(timedelta(hours=8))
SITE_LABEL = {"paradigm": "PARADIGM PRESS", "oxford": "THE OXFORD CLUB", "banyan": "BANYAN HILL"}


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
    ("Chris Cimorelli", r"Cimorelli|10X Trade Club"),
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


MONTH_RE = re.compile(r"(?:(\d{4})\s*[年/\-]\s*)?(\d{1,2})\s*月(?!\s*\d{1,2}\s*日)")


@st.cache_data(ttl=3600, show_spinner=False)
def listed_expiries(ticker: str) -> list[str]:
    """Yahoo 期權鏈目前有掛牌的到期日（YYYY-MM-DD）。查不到就回空清單。"""
    try:
        return list(yf.Ticker(ticker).options)
    except Exception:
        return []


def resolve_month_expiry(ticker: str, contract: str, published: str | None) -> str | None:
    """原文只寫「明年1月的 Call」「2027年1月到期」這種只有月份的推薦，去 Yahoo 期權鏈找那個月實際有的到期日
    （遠月通常只有一個；有好幾個就取該月第三個週五，也就是標準月選擇權）。沒寫年份就取推薦日之後最近的那個月份。"""
    m = MONTH_RE.search(contract or "")
    if not m:
        return None
    month = int(m.group(2))
    try:
        pub = datetime.fromisoformat((published or "").replace("Z", "+00:00"))
    except ValueError:
        pub = datetime.now(timezone.utc)
    year = int(m.group(1)) if m.group(1) else pub.year + (1 if month < pub.month or (month == pub.month and pub.day > 21) else 0)
    if "明年" in contract and not m.group(1):
        year = pub.year + 1
    cands = [e for e in listed_expiries(ticker) if e.startswith(f"{year}-{month:02d}-")]
    if len(cands) > 1:
        monthly = [e for e in cands if datetime.strptime(e, "%Y-%m-%d").weekday() == 4 and 15 <= int(e[-2:]) <= 21]
        cands = monthly or cands
    return cands[0] if cands else None


def option_symbol(ticker: str, contract: str | None, published: str | None = None) -> str | None:
    """期權合約的 Yahoo 代碼（OCC 格式，例如 RKLB261016C00072000）。原文有寫就直接用，
    沒寫就從「2026/10/16到期・履約價72美元 Call」拼出來；只寫月份（例如「1月到期」）就去 Yahoo 期權鏈
    查那個月份實際的到期日；查不到才放棄。"""
    if not contract:
        return None
    m = OCC_RE.search(contract)
    if m and m.group(1) == ticker:
        return m.group(0)
    strike = re.search(r"履約價\s*\$?\s*([\d.]+)|(?:strike\s*\$?|\$)\s*([\d.]+)\s*(?:Call|Put)|([\d.]+)\s*(?:美元\s*)?(?:Call|Put|買權|賣權)", contract, re.I)
    if not strike:
        return None
    strike_px = next(g for g in strike.groups() if g)
    exp = EXPIRY_RE.search(contract)
    if exp:
        y, mo, d = exp.group(1), int(exp.group(2)), int(exp.group(3))
    else:
        iso = resolve_month_expiry(ticker, contract, published)
        if not iso:
            return None
        y, mo, d = iso[:4], int(iso[5:7]), int(iso[8:])
    cp = "P" if re.search(r"Put|賣權", contract, re.I) else "C"
    return f"{ticker}{y[2:]}{mo:02d}{d:02d}{cp}{round(float(strike_px) * 1000):08d}"


def is_listed(r: dict) -> bool:
    """總表只列「有明確進場價位的建倉推薦」和「找得到對應買進、算得出漲跌幅的賣出／停損警報」。
    市價買進、調整停損、純評論、對應的買進早在監控開始前的賣出警報都不列
    （市價買進仍保留在 rows 裡，讓賣出警報往前找買進紀錄時用得到）。要先跑過 attach_returns。"""
    if is_exit(r["action"]):
        return not pd.isna(r.get("change", float("nan")))
    return (bool(r["entry_px"]) or (r.get("leg") == "stock" and bool(r["rec_price"]))) and "調整" not in r["action"]


def leg_segment(entry: str | None, leg: str | None) -> str | None:
    """「股票＋期權」的進場文字常是「股票限價X；Call限價Y」，依分段取出屬於這一腳的那段；
    分不出來時，唯一的一個價格當成權利金（期權腳），股票腳就沒有進場價（改用推薦當下正股價）。"""
    if not entry or not leg:
        return entry
    segs = [x.strip() for x in re.split(r"[；;]", entry) if x.strip()]
    stock_rx, opt_rx = re.compile(r"股票|正股|股價"), re.compile(r"期權|Call|Put|買權|賣權|權利金|合約", re.I)
    pick = [x for x in segs if (stock_rx if leg == "stock" else opt_rx).search(x) and not (leg == "stock" and opt_rx.search(x))]
    if pick:
        return "；".join(pick)
    return None if leg == "stock" else entry


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
                if "期權" in kind and not multi and not option_symbol(t, contract, a.get("publishedAtUtc")):
                    # 抓取欄位漏寫合約時，不再花 token 重抓：直接從這篇的備註／摘要／標題用規則補（單一標的才補，避免抓錯檔）。
                    extra = " ".join(str(x) for x in (e.get("note"), a.get("summary"), a.get("title")) if x)
                    merged = f"{contract or ''} {extra}".strip()
                    if option_symbol(t, merged, a.get("publishedAtUtc")):
                        contract = merged
                # 「股票＋期權」拆成兩列：股票用正股價算，期權用權利金算，互不混用。
                legs = [("stock", "股票"), ("option", "期權")] if kind == "股票＋期權" else [(None, kind)]
                for leg, lkind in legs:
                    lentry = leg_segment(entry, leg)
                    lcontract = contract if lkind == "期權" else None
                    occ = option_symbol(t, contract, a.get("publishedAtUtc")) if lkind == "期權" else None
                    key = (a.get("url") or a.get("title"), a.get("publishedAtUtc"), t, leg)
                    rows[key] = {
                        "ticker": t, "published": a.get("publishedAtUtc") or "", "leg": leg,
                        "kind": lkind, "action": e.get("action") or "", "entry": lentry, "contract": lcontract,
                        "site": a.get("site"), "analyst": detect_analyst(a), "url": a.get("url"), "title": a.get("title"),
                        "rec_price": rec_price_for(e.get("currentPrice"), t, multi),
                        # 計價標的：期權用合約本身（比權利金），股票用正股。
                        "symbol": occ or t, "entry_px": price_in(lentry),
                    }
    return sorted(rows.values(), key=lambda r: r["published"])

