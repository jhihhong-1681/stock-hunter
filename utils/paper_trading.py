"""模擬帳戶（紙上交易）：把選股雷達的排行真的「買下去」，往後逐日追蹤，用來驗證這套策略。純函式，不依賴網路。

設定（阿紘 2026-10-22 定）：資金 NT$100 萬；成長型 70%、成熟型 30%；依選股雷達前幾名買進。
- 每個部位照交易系統規則：金字塔三批 NT$2/3/4 萬（共 9 萬），下一批在上一批價再跌 20%（或上漲後回落 25%），
  首批價再跌 50% 全出，止損價再跌 30% 且基本面「通過」才開新一輪。
- 持股檔數 = 該類型資金 ÷ 9 萬（成長型 700k → 7 檔、成熟型 300k → 3 檔），每檔三批都買滿剛好用完資金，不會借錢。
- 進場選誰：該類型排行（含新聞分）裡，基本面「通過」、沒有紅線、尚未持有、不在止損等待名單的，由高分到低分。
- **不做止盈**（止盈是阿紘自己判斷，系統不替他決定）：績效是「一直抱著、只靠止損出場」的結果，會比實際操作保守或激進視行情而定。
- 以收盤價成交、整股、不含手續費與滑價；匯率固定 31。
- 對照組：同一天把 100 萬全買 SPY 不動。
"""
from __future__ import annotations

from datetime import date

from utils.scoring import score_news, total_score
from utils.trading_system import Rules

CAPITAL_NTD = 1_000_000
SLEEVES = {"成長型": 0.70, "成熟型": 0.30}


def full_budget(rules: Rules) -> int:
    return sum(rules.tranches_ntd)


def slots(rules: Rules, capital: float = CAPITAL_NTD) -> dict:
    return {k: int(capital * w // full_budget(rules)) for k, w in SLEEVES.items()}


def new_state(start_date: str, spy_px: float, capital: float = CAPITAL_NTD) -> dict:
    return {"start_date": start_date, "capital": capital, "fx": Rules().usd_twd,
            "cash": {k: capital * w for k, w in SLEEVES.items()}, "positions": {}, "reentry": {}, "trades": [],
            "equity": [], "spy_start": spy_px, "last_date": start_date}


def rank_candidates(cands: list, news_all: dict, today: date) -> list:
    """合併新聞分後的總分排序（跟頁面 enrich() 同一個算法）；沒有 pillars 的舊格式略過。"""
    out = []
    for c in cands:
        if "pillars" not in c:
            continue
        n = (news_all.get("scores") or {}).get(c["symbol"])
        if n and n.get("asof") and (today - date.fromisoformat(n["asof"])).days > 14:
            n = None
        pct, _, nveto = score_news(n)
        tot = total_score({**c["pillars"], "消息": pct})
        out.append({**c, "total": tot, "veto_final": c.get("veto") or nveto})
    out.sort(key=lambda c: (bool(c["veto_final"]), -c["total"]))
    return out


def _buy(state: dict, kind: str, sym: str, d: str, px: float, ntd: float, reason: str) -> bool:
    fx = state["fx"]
    shares = int(ntd / fx / px)
    cost_ntd = shares * px * fx
    if shares <= 0 or cost_ntd > state["cash"][kind] + 1e-6:
        return False
    state["cash"][kind] -= cost_ntd
    p = state["positions"].setdefault(sym, {"kind": kind, "tranches": [], "shares": 0, "cost_ntd": 0.0})
    p["tranches"].append({"date": d, "price": px, "shares": shares})
    p["shares"] += shares
    p["cost_ntd"] += cost_ntd
    state["trades"].append({"date": d, "symbol": sym, "side": "買", "price": round(px, 4), "shares": shares,
                            "ntd": round(cost_ntd), "reason": reason})
    return True


def _sell_all(state: dict, sym: str, d: str, px: float, reason: str):
    p = state["positions"].pop(sym)
    proceeds = p["shares"] * px * state["fx"]
    state["cash"][p["kind"]] += proceeds
    state["trades"].append({"date": d, "symbol": sym, "side": "賣", "price": round(px, 4), "shares": p["shares"],
                            "ntd": round(proceeds), "reason": reason, "pnl": round(proceeds - p["cost_ntd"])})
    return p


def step_day(state: dict, d: str, closes: dict, rules: Rules):
    """用當天收盤價檢查每檔持股：止損、加碼。closes = {代號: 收盤價}；沒有報價的當天略過該檔。"""
    for sym in list(state["positions"]):
        px = closes.get(sym)
        if px is None:
            continue
        p = state["positions"][sym]
        first, last = p["tranches"][0]["price"], p["tranches"][-1]["price"]
        p["peak"] = max(p.get("peak", last), px)
        avg = p["cost_ntd"] / state["fx"] / p["shares"]
        if px <= first * (1 - rules.stop_from_first):
            old = _sell_all(state, sym, d, px, "止損（首批價 −50%）")
            state["reentry"][sym] = {"kind": old["kind"], "px": round(first * (1 - rules.stop_from_first) * (1 - rules.reentry_drop), 4),
                                     "stop_date": d}
            continue
        n = len(p["tranches"])
        if n < len(rules.tranches_ntd):
            by_step = px <= last * (1 - rules.add_step)
            by_rebound = p["peak"] >= avg * (1 + rules.rebound_min_gain) and px <= p["peak"] * (1 - rules.rebound_pullback)
            if by_step or by_rebound:
                if _buy(state, p["kind"], sym, d, px, rules.tranches_ntd[n], f"加碼第 {n + 1} 批（" + ("上一批價 −20%" if by_step else "上漲後回落") + "）"):
                    p["peak"] = px


def mark(state: dict, d: str, closes: dict, spy_px: float) -> dict:
    """當天淨值快照（現金 + 持股市值）。沒有報價的持股用最近一次已知價。"""
    fx = state["fx"]
    val = 0.0
    for sym, p in state["positions"].items():
        px = closes.get(sym) or p.get("last_px") or p["tranches"][-1]["price"]
        p["last_px"] = px
        val += p["shares"] * px * fx
    cash = sum(state["cash"].values())
    row = {"date": d, "equity": round(cash + val), "cash": round(cash), "invested": round(val),
           "spy": round(state["capital"] * spy_px / state["spy_start"])}
    state["equity"] = [r for r in state["equity"] if r["date"] != d] + [row]
    state["last_date"] = d
    return row


def enter_positions(state: dict, d: str, ranked: list, rules: Rules) -> list:
    """最新一天：空出來的名額用排行補滿（含止損後跌到再進場價且基本面通過的）。回傳這次買進的代號。"""
    bought = []
    by_sym = {c["symbol"]: c for c in ranked}
    cap = slots(rules, state["capital"])
    for kind in SLEEVES:
        def n_held():
            return sum(1 for p in state["positions"].values() if p["kind"] == kind)
        # 止損後的再進場：價格跌到再進場價 + 基本面通過 + 沒紅線
        for sym, r in list(state["reentry"].items()):
            c = by_sym.get(sym)
            if r["kind"] != kind or n_held() >= cap[kind] or not c:
                continue
            if c["price"] <= r["px"] and c["verdict"] == "通過" and not c["veto_final"]:
                if _buy(state, kind, sym, d, c["price"], rules.tranches_ntd[0], "止損後再進場（止損價再跌 30%，基本面通過）"):
                    del state["reentry"][sym]
                    bought.append(sym)
        for c in ranked:
            if n_held() >= cap[kind]:
                break
            if c["kind"] != kind or c["verdict"] != "通過" or c["veto_final"]:
                continue
            if c["symbol"] in state["positions"] or c["symbol"] in state["reentry"]:
                continue
            if _buy(state, kind, c["symbol"], d, c["price"], rules.tranches_ntd[0], f"依排行買進第 1 批（總分 {c['total']}）"):
                state["positions"][c["symbol"]]["name"] = c.get("name", c["symbol"])
                state["positions"][c["symbol"]]["score_at_entry"] = c["total"]
                bought.append(c["symbol"])
    for sym, p in state["positions"].items():
        p.setdefault("name", sym)
    return bought
