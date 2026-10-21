"""阿紘的交易系統（v0）：下跌才買、金字塔加碼、首批價再跌 50% 止損。

規則（阿紘 2026-10 對話定案）：
- 進場：股價從 52 週高點回檔 ≥ 30%，買第一批。
- 加碼：金字塔往下，第 1/2/3 批各 NT$2 萬 / 3 萬 / 4 萬，最多 3 批；
  下一批在「上一批價再跌 10–15%」，或「首批後上漲、再從高點回落 20–30%」時買。
- 止損：現價 ≤ 首批買入價 × 50% 就全部出清（中間不論加碼幾次）。
- 止盈：阿紘自己判斷，系統不替他決定；回測才需要一個假設，所以用 take_profit 參數。
- 基本面濾網：v0 還沒有，下一版補。

純函式，不依賴 streamlit；頁面（pages/12_交易系統.py）負責抓資料和顯示。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "portfolio-calendar"


# ── 讀快照 ─────────────────────────────────────────────────
def _js_obj(line: str) -> dict:
    """holdings.js / trades.js 每筆一行，key 沒有引號；補上引號後就是 JSON。"""
    return json.loads(re.sub(r"([{,]\s*)([A-Za-z_]\w*):", r'\1"\2":', line.strip().rstrip(",")))


def read_positions() -> list[dict]:
    text = (DATA_DIR / "holdings.js").read_text(encoding="utf-8").split("closedPositions")[0]
    return [_js_obj(line) for line in text.splitlines() if line.strip().startswith("{symbol:")]


def read_trades() -> list[dict]:
    try:
        text = (DATA_DIR / "trades.js").read_text(encoding="utf-8")
    except OSError:
        return []
    return [_js_obj(line) for line in text.splitlines() if line.strip().startswith("{")]


@dataclass
class Rules:
    entry_drop: float = 0.30
    tranches_ntd: tuple = (20000, 30000, 40000)
    add_step: float = 0.12           # 上一批價再跌多少加碼（阿紘說 10–15%）
    rebound_pullback: float = 0.25   # 上漲後從高點回落多少加碼（阿紘說 20–30%）
    rebound_min_gain: float = 0.10   # 回落加碼要先離均價漲過這麼多才算「上漲過」
    stop_from_first: float = 0.50    # 首批價再跌多少止損
    take_profit: float | None = 0.50  # 僅回測用的假設：相對均價漲多少全出；None = 不止盈
    cooldown_days: int = 40          # 回測：出場後多久內不重新進場
    usd_twd: float = 31.0


# ── 持股對照規則 ───────────────────────────────────────────
def episodes(trades: list[dict], symbol: str) -> list[dict]:
    """成交紀錄切成「波段」：從空手買進到賣光。回傳每波段的買進清單與是否仍持有。"""
    # 同一天、成交紀錄沒有時間時，先算買再算賣：否則「當天先加碼後賣出」會被誤判成先賣光再重新開始
    rows = sorted((t for t in trades if t.get("symbol") == symbol and t.get("type") == "stock"),
                  key=lambda t: (t["date"], t.get("time") or "", "買" not in t["side"]))
    out, cur, qty = [], None, 0.0
    for t in rows:
        if "買" in t["side"]:
            if qty <= 0:
                cur = {"symbol": symbol, "buys": [], "open": True}
                out.append(cur)
                qty = 0.0
            cur["buys"].append({"date": t["date"], "price": t["price"], "qty": t["qty"]})
            qty += t["qty"]
        elif cur is not None:
            qty -= t["qty"]
            if qty <= 0:
                cur["open"] = False
                qty = 0.0
    return out


def tranche_groups(buys: list[dict]) -> list[dict]:
    """同一天的買進併成一「批」，算加權均價與數量。"""
    by = {}
    for b in buys:
        g = by.setdefault(b["date"], {"date": b["date"], "qty": 0.0, "cost": 0.0})
        g["qty"] += b["qty"]
        g["cost"] += b["qty"] * b["price"]
    return [{"date": g["date"], "qty": g["qty"], "price": g["cost"] / g["qty"]} for g in sorted(by.values(), key=lambda g: g["date"])]


def check_position(pos: dict, trades: list[dict], rules: Rules) -> dict:
    """一檔目前持股對照規則。pos 是 holdings.js 的一筆。
    首批價完全以成交紀錄為準：目前這一輪（上次全部賣光之後重新買進）的第一批買進價。
    成交紀錄找不到這一輪時才退回成本均價並在備註標示。"""
    sym, price = pos["symbol"], pos["price"]
    eps = [e for e in episodes(trades, sym) if e["open"]]
    note = ""
    groups = tranche_groups(eps[-1]["buys"]) if eps else []
    n = max(len(groups), 1)
    last = groups[-1]["price"] if groups else pos["avgCost"]
    if groups:
        first = groups[0]["price"]
    else:
        first = pos["avgCost"]
        note = "成交紀錄找不到這一輪的買進，首批價用成本均價估"
    stop = first * (1 - rules.stop_from_first)
    out = {
        "symbol": sym, "name": pos["name"], "現價": price, "首批價": round(first, 2), "成本均價": pos["avgCost"],
        "已買批數": n, "距首批價": price / first - 1, "止損價": round(stop, 2), "距止損價": price / stop - 1,
        "已觸發止損": price <= stop, "報酬率": pos.get("pct"), "現值NT$": pos["value"], "備註": note,
    }
    if n < len(rules.tranches_ntd):
        out["下一批加碼價"] = round(last * (1 - rules.add_step), 2)
        out["下一批金額NT$"] = rules.tranches_ntd[n]
        out["下一批股數"] = int(rules.tranches_ntd[n] / rules.usd_twd / max(last * (1 - rules.add_step), 0.01))
    else:
        out["下一批加碼價"] = None
    return out


# ── 進場掃描 ───────────────────────────────────────────────
def scan_symbol(close: list[float] | "pd.Series", rules: Rules) -> dict | None:
    """最新收盤價相對近 252 個交易日高點的回檔，與三批的建議買進價位（以首批 = 現價估算）。"""
    vals = [float(x) for x in close if x == x]
    if len(vals) < 60:
        return None
    window = vals[-252:]
    high, last = max(window), vals[-1]
    dd = last / high - 1
    first = last
    return {
        "現價": last, "52週高點": high, "距高點": dd, "進場區": dd <= -rules.entry_drop,
        "進場價(距高點-30%)": round(high * (1 - rules.entry_drop), 2),
        "加碼價2(再-%d%%)" % round(rules.add_step * 100): round(first * (1 - rules.add_step), 2),
        "加碼價3": round(first * (1 - rules.add_step) ** 2, 2),
        "止損價(首批-50%)": round(first * (1 - rules.stop_from_first), 2),
    }


# ── 回測 ───────────────────────────────────────────────────
@dataclass
class Trade:
    symbol: str
    entry: str
    exit: str
    reason: str
    tranches: int
    invested: float  # NT$
    pnl: float       # NT$
    days: int
    first_price: float = 0.0
    exit_price: float = 0.0
    ret: float = field(init=False)

    def __post_init__(self):
        self.ret = self.pnl / self.invested if self.invested else 0.0


def backtest(symbol: str, dates: list, close: list[float], rules: Rules) -> list[Trade]:
    """單一標的、獨立回測（收盤價成交、不含手續費與滑價）。
    回傳已結束的交易；回測終點仍持有的以最後收盤價結算，reason 標「持有中」。"""
    trades: list[Trade] = []
    n = len(close)
    state = None
    cool_until = -1
    for i in range(n):
        px = close[i]
        if px != px:
            continue
        if state is None:
            if i < 60 or i < cool_until:
                continue
            high = max(c for c in close[max(0, i - 251):i + 1] if c == c)
            if px <= high * (1 - rules.entry_drop):
                amt = rules.tranches_ntd[0]
                state = {"first": px, "last": px, "peak": px, "shares": amt / rules.usd_twd / px,
                         "cost": amt, "n": 1, "entry_i": i}
            continue
        s = state
        avg = s["cost"] / rules.usd_twd / s["shares"]
        s["peak"] = max(s["peak"], px)
        reason = None
        if px <= s["first"] * (1 - rules.stop_from_first):
            reason = "止損"
        elif rules.take_profit is not None and px >= avg * (1 + rules.take_profit):
            reason = "止盈(假設)"
        if reason:
            value = s["shares"] * px * rules.usd_twd
            trades.append(Trade(symbol, str(dates[s["entry_i"]])[:10], str(dates[i])[:10], reason, s["n"],
                                s["cost"], value - s["cost"], i - s["entry_i"], s["first"], px))
            state = None
            cool_until = i + rules.cooldown_days
            continue
        if s["n"] < len(rules.tranches_ntd):
            by_step = px <= s["last"] * (1 - rules.add_step)
            by_rebound = s["peak"] >= avg * (1 + rules.rebound_min_gain) and px <= s["peak"] * (1 - rules.rebound_pullback)
            if by_step or by_rebound:
                amt = rules.tranches_ntd[s["n"]]
                s["shares"] += amt / rules.usd_twd / px
                s["cost"] += amt
                s["n"] += 1
                s["last"] = px
                s["peak"] = px
    if state is not None:
        s = state
        last_px = close[-1]
        value = s["shares"] * last_px * rules.usd_twd
        trades.append(Trade(symbol, str(dates[s["entry_i"]])[:10], str(dates[-1])[:10], "持有中", s["n"],
                            s["cost"], value - s["cost"], n - 1 - s["entry_i"], s["first"], last_px))
    return trades


def summarize(trades: list[Trade]) -> dict:
    done = [t for t in trades if t.reason != "持有中"]
    allt = trades
    if not allt:
        return {}
    wins = [t for t in done if t.pnl > 0]
    losses = [t for t in done if t.pnl <= 0]
    return {
        "交易數": len(allt), "已結束": len(done), "持有中": len(allt) - len(done),
        "勝率(已結束)": len(wins) / len(done) if done else None,
        "平均賺NT$": sum(t.pnl for t in wins) / len(wins) if wins else 0.0,
        "平均賠NT$": sum(t.pnl for t in losses) / len(losses) if losses else 0.0,
        "止損次數": sum(t.reason == "止損" for t in done),
        "總損益NT$": sum(t.pnl for t in allt),
        "總投入NT$": sum(t.invested for t in allt),
        "最大單筆虧損NT$": min(t.pnl for t in allt),
    }


# ── 價格訊號 × 基本面判定 ─────────────────────────────────────
def hold_hint(stop_hit: bool, verdict: str, adds_left: bool) -> str:
    """持股：價格止損 + 基本面判定的對照。系統只提示，止盈與最後決定仍由阿紘判斷。"""
    if stop_hit:
        if verdict == "通過":
            return "已觸發止損：規則是出清；基本面仍通過，可列入重新進場觀察"
        if verdict in ("警示", "排除"):
            return f"已觸發止損：規則是出清；基本面也{verdict}"
        return "已觸發止損：規則是出清"
    if verdict == "排除":
        return "基本面排除：不再加碼"
    if verdict == "警示":
        return "基本面警示：加碼前先複查" if adds_left else "基本面警示"
    if verdict == "通過":
        return "可依規則加碼" if adds_left else "批數已滿，不再加碼"
    return "基本面資料不足" if verdict == "資料不足" else ""


def entry_hint(in_zone: bool, verdict: str) -> str:
    """進場掃描：價格進場區 × 基本面。"""
    if not in_zone:
        return ""
    return {"通過": "符合進場（價格 + 基本面）", "警示": "價格到位，基本面警示：小心", "排除": "價格到位，但基本面排除：不進",
            "資料不足": "價格到位，基本面資料不足", "不適用": "價格到位（ETF，無基本面）"}.get(verdict, "")
