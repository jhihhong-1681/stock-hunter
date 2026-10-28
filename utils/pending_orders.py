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
