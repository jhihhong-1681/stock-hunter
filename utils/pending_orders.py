"""Firstrade 未成交訂單追蹤（資料源 portfolio-calendar/pending_orders.js，由桌機本機排程寫入）。

研究監控日誌的「標的總表」旁邊用它列出還在追蹤的掛單，並對照 holdings.js 的現價算出距限價多遠。
手動「不再追蹤」跟以前一樣：把這筆的 key 經 scripts/journal_relay.gs 記到阿紘 Google Sheet 的「PendingRemoved」分頁，
讀取時套在 pending_orders.js 上遮掉（pending_orders.js 本身不動）。key 的格式要跟舊的報酬日曆網頁完全一致，
才不會讓先前已刪除的訂單又冒出來：date|time|symbol|side|description|limitPrice（null 當空字串，數字照 JavaScript 的寫法）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "portfolio-calendar"
OPT_KEY = re.compile(r"^(\w+)\s+(\d\d)/(\d\d)/(\d{2,4})\s+([\d.]+)\s+([CP])", re.I)


def _js_obj(line: str) -> dict:
    return json.loads(re.sub(r"([{,]\s*)([A-Za-z_]\w*):", r'\1"\2":', line.strip().rstrip(",")))


def _js_str(v) -> str:
    """跟 JavaScript Array.join 一致：null → 空字串，整數值的浮點數不帶 .0。"""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def order_key(o: dict) -> str:
    return "|".join(_js_str(o.get(k)) for k in ("date", "time", "symbol", "side", "description", "limitPrice"))


def option_key(desc: str | None) -> str | None:
    m = OPT_KEY.match(desc or "")
    if not m:
        return None
    sym, mm, dd, yy, strike, cp = m.groups()
    return f"{sym.upper()}|{mm}{dd}{yy[-2:]}|{float(strike):g}|{cp.upper()}"


def occ_symbol(o: dict) -> str | None:
    """期權合約的 OCC 代碼（例如 ONDS261106C00007000），拿去 Yahoo 查報價用；不是期權或解析不出來回 None。"""
    m = OPT_KEY.match(o.get("description") or "")
    if o.get("type") != "option" or not m:
        return None
    sym, mm, dd, yy, strike, cp = m.groups()
    return f"{sym.upper()}{yy[-2:]}{mm}{dd}{cp.upper()}{round(float(strike) * 1000):08d}"


def expiry(o: dict):
    """期權合約的到期日（date），不是期權或解析不出來回 None。"""
    from datetime import date
    m = OPT_KEY.match(o.get("description") or "")
    if o.get("type") != "option" or not m:
        return None
    _sym, mm, dd, yy, _strike, _cp = m.groups()
    y = int(yy) if len(yy) == 4 else 2000 + int(yy)
    try:
        return date(y, int(mm), int(dd))
    except ValueError:
        return None


def is_expired(o: dict, today) -> bool:
    """期權到期日已過（當天還算有效）。today 用美東日期。"""
    e = expiry(o)
    return e is not None and e < today


def is_buy(side: str | None) -> bool:
    return bool(re.search(r"buy|買", side or "", re.I))


def read_trades() -> list[dict]:
    try:
        lines = (DATA_DIR / "trades.js").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if line.strip().startswith("{ date"):
            try:
                out.append(_js_obj(line))
            except ValueError:
                pass
    return out


def split_filled(orders: list[dict], trades: list[dict]) -> tuple[list[dict], list[dict]]:
    """用成交紀錄（trades.js）再檢查一次：同方向、同商品（股票同代號；期權要同一個合約）、成交時間晚於掛單時間，就視為已成交。
    本機排程（FIRSTRADE_TASK.md 第 4 步）應該會幫掛單標 filled，但漏標過（成交沒對上時），這裡當保險。
    回傳（仍在追蹤, 其實已成交）。成交沒有時間（舊紀錄）時，只在成交日晚於掛單日才算。"""
    def when(d, t):
        return (d, t or "")

    pending, filled = [], []
    for o in orders:
        ok = False
        for t in trades:
            if is_buy(t.get("side")) != is_buy(o.get("side")) or t.get("type") != o.get("type") or t["symbol"] != o["symbol"]:
                continue
            if o.get("type") == "option" and option_key(t.get("description")) != option_key(o.get("description")):
                continue
            if t.get("time"):
                later = when(t["date"], t["time"]) > when(o["date"], o.get("time"))
            else:
                later = t["date"] > o["date"]
            if later:
                ok = True
                break
        (filled if ok else pending).append(o)
    return pending, filled


def dedupe_keep_best(orders: list[dict]) -> list[dict]:
    """同一個合約（股票就是同代號）、同方向的掛單只留一筆：買單留限價最高、賣單留限價最低（同價留最新）；
    市價單（沒限價）視為最差。回傳的順序與輸入一致。"""
    best: dict[tuple, dict] = {}
    for o in orders:
        k = (o.get("description") or o["symbol"], o["side"])
        lim = o.get("limitPrice")
        if is_buy(o["side"]):
            price_rank = lim if lim is not None else float("-inf")
        else:
            price_rank = -lim if lim is not None else float("-inf")
        rank = (price_rank, o["date"], o.get("time") or "")
        if k not in best or rank > best[k][0]:
            best[k] = (rank, o)
    keep = {id(v[1]) for v in best.values()}
    return [o for o in orders if id(o) in keep]


def short_label(o: dict) -> str:
    """標的欄用：股票就是代號；期權寫成「ONDS 11/06 7C」。"""
    m = OPT_KEY.match(o.get("description") or "")
    if o.get("type") != "option" or not m:
        return o["symbol"]
    sym, mm, dd, _yy, strike, cp = m.groups()
    return f"{sym.upper()} {mm}/{dd} {float(strike):g}{cp.upper()}"


def read_orders() -> list[dict]:
    """還在追蹤的訂單（排除已成交 filled 與資料檔標成 removed 的），檔案讀不到回空清單。"""
    try:
        lines = (DATA_DIR / "pending_orders.js").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        if not line.strip().startswith("{"):
            continue
        try:
            o = _js_obj(line)
        except ValueError:
            continue
        if not o.get("filled") and not o.get("removed"):
            out.append(o)
    return out


def current_prices() -> tuple[dict[str, float], dict[str, float]]:
    """（股票代號 → 現價, 期權合約 key → 權利金現價），來自每日快照 holdings.js；沒持有的標的沒有現價。"""
    stock, option = {}, {}
    try:
        text = (DATA_DIR / "holdings.js").read_text(encoding="utf-8").split("closedPositions")[0]
    except OSError:
        return stock, option
    for line in text.splitlines():
        if not line.strip().startswith("{symbol"):
            continue
        try:
            p = _js_obj(line)
        except ValueError:
            continue
        if p.get("type") == "option":
            k = option_key(p.get("name"))
            if k and p.get("price") is not None:
                option[k] = p["price"]
        elif p.get("price") is not None:
            stock[p["symbol"]] = p["price"]
    return stock, option


def fetch_removed(api_url: str, api_key: str) -> set[str]:
    import requests
    r = requests.get(api_url, params={"what": "removed", "key": api_key}, timeout=20)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "讀取失敗"))
    return set(data["keys"])


def remove_order(api_url: str, api_key: str, o: dict) -> None:
    import requests
    r = requests.post(api_url, data=json.dumps({"key": api_key, "action": "removePending", "pkey": order_key(o)}),
                      headers={"Content-Type": "text/plain"}, timeout=20)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "寫入失敗"))
