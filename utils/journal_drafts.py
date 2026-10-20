"""交易紀錄頁的「新建倉位待補紀錄」。

報酬日曆每天的快照（portfolio-calendar/holdings.js、positions_history.js）能看出哪些部位是最近才出現的，
研究監控日誌（utils/research_log.py）知道哪個網站、哪位分析師在什麼時候推薦了哪一檔，
兩邊對起來就能預填交易紀錄：買進日、標的、合約、類別、標的價、買進價、數量、來源。
預填的內容只是草稿，要在頁面上確認（可以改）後才會寫進 Google Sheet 的 Journal 分頁；
沒有對到推薦的新倉一律當成「自己買」。
"""
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
import streamlit as st

from utils.research_log import (
    API_KEY as RESEARCH_KEY,
    API_URL as RESEARCH_URL,
    SITE_LABEL,
    TAIPEI,
    build_rows,
    is_buy,
    list_dates,
    load_days,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "portfolio-calendar"
NEW_WITHIN_DAYS = 14   # 首次出現在快照的日期離今天幾天內才算「新倉」
MATCH_BEFORE_DAYS = 21  # 往前找幾天內發佈的推薦
CLASSES = ["價內方向單", "價平/輕微價外", "短天期價外樂透", "長天期價外樂透", "股票"]
OPT_NAME = re.compile(r"^([A-Z.\-]+)\s+(\d{2})/(\d{2})/(\d{2,4})\s+([\d.]+)\s+(Call|Put)$", re.I)


# ── 快照資料 ────────────────────────────────────────────
def _js_obj(line: str) -> dict:
    """holdings.js 每筆持股一行，key 沒有引號；補上引號後就是 JSON。"""
    return json.loads(re.sub(r"([{,]\s*)([A-Za-z_]\w*):", r'\1"\2":', line.strip().rstrip(",")))


def read_positions() -> list[dict]:
    text = (DATA_DIR / "holdings.js").read_text(encoding="utf-8").split("closedPositions")[0]
    return [_js_obj(line) for line in text.splitlines() if line.strip().startswith("{symbol:")]


def read_history() -> dict[str, set[tuple[str, str]]]:
    """positions_history.js：{日期: {(symbol, name), ...}}。"""
    text = (DATA_DIR / "positions_history.js").read_text(encoding="utf-8")
    parts = re.split(r'"(\d{4}-\d{2}-\d{2})":\s*\{', text)
    out = {}
    for d, block in zip(parts[1::2], parts[2::2]):
        out[d] = set(re.findall(r'symbol:\s*"([^"]+)",\s*name:\s*"([^"]+)"', block))
    return out


def first_seen_dates() -> dict[tuple[str, str], str]:
    """每個目前還在的部位，連續出現的第一天。史上第一天就有的部位看不出是什麼時候買的，不列入。"""
    hist = read_history()
    dates = sorted(hist)
    out = {}
    for sym, name in hist[dates[-1]]:
        i = len(dates) - 1
        while i > 0 and (sym, name) in hist[dates[i - 1]]:
            i -= 1
        if i > 0:
            out[(sym, name)] = dates[i]
    return out


# ── 草稿 ────────────────────────────────────────────────
def _occ(sym: str, y: int, m: int, d: int, cp: str, strike: float) -> str:
    return f"{sym}{y % 100:02d}{m:02d}{d:02d}{cp}{round(strike * 1000):08d}"


def draft_from_position(p: dict, seen: str) -> dict:
    """把一筆新部位換成交易紀錄的欄位（還沒有來源、停損、目標價）。"""
    buy_day = date.fromisoformat(seen)
    base = {"date": seen, "sym": p["symbol"], "stop": None, "tgt": None, "by": None, "occ": None}
    m = OPT_NAME.match(p["name"]) if p.get("type") == "option" else None
    if not m:
        return {**base, "con": "", "cls": "股票", "S": p.get("price"), "P": p.get("avgCost"), "n": p.get("shares")}
    mo, d, y, strike, cp = int(m.group(2)), int(m.group(3)), int(m.group(4)), float(m.group(5)), m.group(6)[0].upper()
    y = 2000 + y if y < 100 else y
    S = p.get("underlyingPrice")
    dte = (date(y, mo, d) - buy_day).days
    if not S:
        cls = "長天期價外樂透" if dte >= 60 else "短天期價外樂透"
    else:
        otm = (strike - S) / S if cp == "C" else (S - strike) / S  # 正數 = 價外
        cls = "價內方向單" if otm < 0 else "價平/輕微價外" if otm <= 0.05 else ("長天期價外樂透" if dte >= 60 else "短天期價外樂透")
    return {
        **base, "con": f"{mo:02d}/{d:02d}/{y % 100:02d} {strike:g}{cp}", "cls": cls, "S": S,
        "P": p.get("avgCost"), "n": int(p["shares"] // 100) or 1,
        "occ": _occ(p["symbol"], y, mo, d, cp, strike),
    }


def match_source(draft: dict, rows: list[dict]) -> tuple[dict | None, str]:
    """找這筆新倉對應的買進推薦。回傳（推薦, 吻合程度）：
    exact＝同合約；same＝同標的同類型（股票對股票、期權對期權）；weak＝同標的但類型不同（只提示，不預填）。"""
    lo = datetime.combine(date.fromisoformat(draft["date"]), datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=MATCH_BEFORE_DAYS)
    hi = lo + timedelta(days=MATCH_BEFORE_DAYS + 2)
    is_opt = draft["cls"] != "股票"
    best = None
    for r in rows:
        if r["ticker"] != draft["sym"] or not is_buy(r["action"]):
            continue
        try:
            pub = datetime.fromisoformat(r["published"].replace("Z", "+00:00"))
        except ValueError:
            continue
        if not lo <= pub <= hi:
            continue
        level = 3 if is_opt and draft["occ"] and r["symbol"] == draft["occ"] else 2 if is_opt == ("期權" in r["kind"]) else 1
        if best is None or (level, pub) > best[0]:
            best = ((level, pub), r)
    if not best:
        return None, ""
    return best[1], {3: "exact", 2: "same", 1: "weak"}[best[0][0]]


def short_name(analyst: str) -> str:
    if not analyst or analyst == "未標示":
        return ""
    return "、".join(n.strip() for n in analyst.split("、"))


def why_text(rec: dict | None, draft: dict) -> str:
    if not rec:
        return "自己買｜"
    what = rec.get("contract") or draft["con"] or "股票"
    who = short_name(rec["analyst"])
    head = f'{SITE_LABEL.get(rec["site"], rec["site"])}｜{who + " " if who else ""}建議 {what}'
    return "\n".join(x for x in (head, rec.get("title"), rec.get("url")) if x)


# ── 研究日誌 / 交易紀錄 Sheet ────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def recent_research_rows() -> list[dict]:
    dates = list_dates()[:40]
    days = {}
    for i in range(0, len(dates), 30):
        days.update(load_days(tuple(dates[i:i + 30])))
    return build_rows(days)


def relay(url: str, key: str, payload: dict | None = None) -> dict:
    """Apps Script 中繼：GET 要自己處理一次性轉址（偶爾 404，重打就好）；POST 用 text/plain 送 JSON。"""
    last = None
    for _ in range(3):
        if payload is None:
            first = requests.get(url, params={"key": key}, timeout=60, allow_redirects=False)
            r = requests.get(first.headers["Location"], timeout=60) if first.is_redirect else first
        else:
            body = json.dumps({"key": key, **payload}).encode("utf-8")
            r = requests.post(url, data=body, headers={"Content-Type": "text/plain;charset=utf-8"}, timeout=60)
        if r.status_code == 200:
            data = r.json()
            if not data.get("ok"):
                raise RuntimeError(data.get("error") or "unknown")
            return data
        last = r
    last.raise_for_status()


def _norm_con(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).upper()


def pending_drafts(journal_rows: list[dict]) -> list[dict]:
    """最近才出現、而且交易紀錄裡還沒有的新倉。"""
    today = datetime.now(TAIPEI).date()
    pos = {(p["symbol"], p["name"]): p for p in read_positions()}
    drafts = []
    for key, seen in sorted(first_seen_dates().items(), key=lambda kv: kv[1], reverse=True):
        if key not in pos or (today - date.fromisoformat(seen)).days > NEW_WITHIN_DAYS:
            continue
        d = draft_from_position(pos[key], seen)
        floor = date.fromisoformat(seen) - timedelta(days=7)
        if any(r.get("sym") == d["sym"] and _norm_con(r.get("con")) == _norm_con(d["con"]) and (r.get("date") or "") >= floor.isoformat()
               for r in journal_rows):
            continue
        d["id"] = f'auto-{seen}-{d["sym"]}-{_norm_con(d["con"]) or "stock"}'.replace("/", "")
        drafts.append(d)
    return drafts


def render_drafts(api_url: str, api_key: str) -> bool:
    """畫在交易紀錄頁上方。回傳這次有沒有新增（呼叫端據此讓下面的 iframe 重新載入）。"""
    try:
        journal_rows = relay(api_url, api_key)["rows"]
        drafts = pending_drafts(journal_rows)
    except Exception as e:
        st.warning(f"新建倉位草稿讀取失敗：{e}")
        return False
    skipped = st.session_state.setdefault("draft_skipped", set())
    drafts = [d for d in drafts if d["id"] not in skipped]
    if not drafts:
        return False

    rows, research_err = [], None
    if RESEARCH_URL and RESEARCH_KEY:
        try:
            with st.spinner("對照研究監控日誌的推薦中…"):
                rows = recent_research_rows()
        except Exception as e:
            research_err = str(e)
    else:
        research_err = "沒有設定研究監控日誌的 secrets"

    added = False
    with st.expander(f"📥 最近的新建倉位，還沒記進交易紀錄（{len(drafts)} 筆）", expanded=True):
        st.caption("從報酬日曆快照偵測到的新部位。來源是拿「研究監控日誌」的買進推薦（同標的、買進日前 3 週內）去對；"
                   "對不到就預設「自己買」。價格是 Sheet 的成本均價（加碼會被平均），停損價、目標價、最晚出場日要你自己補。")
        if research_err:
            st.warning(f"研究監控日誌讀不到（{research_err}），來源沒有比對，全部預設「自己買」，請自己改。")
        for d in drafts:
            rec, level = match_source(d, rows) if rows else (None, "")
            prefill = why_text(rec if level in ("exact", "same") else None, d)
            title = f'{d["date"]}　{d["sym"]} {d["con"] or "股票"}'
            with st.form(f'draft_{d["id"]}'):
                st.markdown(f"**{title}**")
                if level == "exact":
                    st.caption(f'✅ 對到同合約的推薦：{SITE_LABEL.get(rec["site"], rec["site"])}')
                elif level == "same":
                    st.caption(f'☑️ 對到同標的的推薦（合約可能不同）：{SITE_LABEL.get(rec["site"], rec["site"])}，請確認')
                elif level == "weak":
                    st.caption(f'⚠️ 有同標的但類型不同的推薦（{SITE_LABEL.get(rec["site"], rec["site"])}：{rec["kind"]}），沒有預填，是的話請自己改來源')
                c = st.columns(5)
                cls = c[0].selectbox("類別", CLASSES, index=CLASSES.index(d["cls"]))
                S = c[1].number_input("買進時標的價", value=float(d["S"] or 0), step=0.01, format="%.2f")
                P = c[2].number_input("買進權利金/股價", value=float(d["P"] or 0), step=0.01, format="%.2f")
                n = c[3].number_input("口數/股數", value=int(d["n"] or 1), step=1, min_value=1)
                stop = c[4].number_input("標的停損價（選填）", value=0.0, step=0.01, format="%.2f")
                why = st.text_area("買進理由／來源（第一行｜之前是來源分組）", value=prefill)
                b1, b2 = st.columns(2)
                go = b1.form_submit_button("加入交易紀錄", type="primary")
                skip = b2.form_submit_button("略過（這次連線不再顯示）")
            if skip:
                skipped.add(d["id"])
                st.rerun()
            if go:
                row = {"id": d["id"], "date": d["date"], "sym": d["sym"], "con": d["con"], "cls": cls, "S": S or None,
                       "P": P, "n": int(n), "stop": stop or None, "tgt": None, "by": None, "why": why.strip(),
                       "exitDate": None, "exitP": None, "mae": None}
                try:
                    relay(api_url, api_key, {"action": "upsert", "row": row})
                except Exception as e:
                    st.error(f"寫入失敗：{e}")
                else:
                    added = True
                    st.session_state["journal_rev"] = st.session_state.get("journal_rev", 0) + 1
                    st.rerun()
    return added
