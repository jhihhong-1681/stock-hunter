"""模擬帳戶（紙上交易）v2：滾動式調整、依評分決定投入金額、每天如實記錄損益與每筆交易的理由。純函式，不依賴網路。

設定（阿紘 2026-10-22 定）：資金 NT$100 萬；成長型約 70%、成熟型約 30%；依選股雷達的排行買進，之後每天依價格、基本面、新聞滾動調整，不必死守 2/3/4 萬。

【每天做什麼】（scripts/paper_trade.py 呼叫；價格規則會補算每個交易日，基本面／新聞／排行的判斷在最新一天做）
1. 止損（硬規則）：收盤 ≤ 首批價 × 50% → 全出；跌到「止損價再跌 30%」且基本面通過、無紅線 → 開新一輪。
2. 汰弱：基本面「排除」或新聞紅線 → 全出；體質分 < 45 → 全出；基本面「警示」且新聞偏空（新聞分 ≤ 30）→ 減碼一半（每檔一次）；
   單檔市值 > 總資產 30% → 減到 25%。
3. 加碼：(a) 價格規則照舊（上一批價再跌 20%，或上漲後回落 25%），但基本面要是「通過」才加；
   (b) 評分加碼：總分升到 72 以上、還有批數、現價不比上一批高 10% 以上（不追高）、距上次買進 ≥ 10 天 → 加下一批。
4. 補位：成長型最多 7 檔、成熟型最多 3 檔；空出來的名額，由該類型排行（總分 ≥ 60、基本面通過、無紅線）由高到低補。
5. 金額依評分：每類型預算 = 類型比重 × 目前總資產；各檔「目標總額」∝ max(總分 − 55, 5)，單檔不超過等權的 2 倍；
   每檔仍分三批（2:3:4），第一批 = 目標 × 2/9。分數越高買越多，分數降了之後的加碼會變小。
6. 止盈不做（阿紘自己判斷）；收盤價成交、整股、不含手續費；匯率固定 31。對照組：同一天 100 萬全買 SPY 不動。
7. 每天寫進 state：淨值與當日損益、每檔持股當日漲跌、每筆交易的理由、當天的操作日誌。
"""
from __future__ import annotations

from datetime import date

from utils.scoring import score_news, total_score
from utils.trading_system import Rules

CAPITAL_NTD = 1_000_000
SLEEVES = {"成長型": 0.70, "成熟型": 0.30}
MAX_NAMES = {"成長型": 7, "成熟型": 3}
RATIO = (2, 3, 4)                # 三批比例（原 2/3/4 萬）
BASE_SCORE, MIN_W = 55, 5        # 目標金額 ∝ max(總分 − 55, 5)
MIN_ENTRY_SCORE = 60
CONVICTION_ADD_SCORE = 72
EXIT_HEALTH = 45
CONC_TRIGGER, CONC_TARGET = 0.30, 0.25


def new_state(start_date: str, spy_px: float, capital: float = CAPITAL_NTD) -> dict:
    return {"version": 2, "start_date": start_date, "capital": capital, "fx": Rules().usd_twd, "cash": capital,
            "positions": {}, "reentry": {}, "trades": [], "equity": [], "daily": [], "journal": [],
            "spy_start": spy_px, "last_date": start_date}


def rank_candidates(cands: list, news_all: dict, today: date) -> list:
    """合併新聞分後的總分排序（跟頁面 enrich() 同一個算法）。"""
    out = []
    for c in cands:
        if "pillars" not in c:
            continue
        n = fresh_news(news_all, c["symbol"], today)
        pct, _, nveto = score_news(n)
        tot = total_score({**c["pillars"], "消息": pct})
        out.append({**c, "total": tot, "news_pct": pct, "news": n, "veto_final": c.get("veto") or nveto})
    out.sort(key=lambda c: (bool(c["veto_final"]), -c["total"]))
    return out


def fresh_news(news_all: dict, sym: str, today: date):
    n = (news_all.get("scores") or {}).get(sym)
    if n and n.get("asof") and (today - date.fromisoformat(n["asof"])).days > 14:
        return None
    return n


def health(fund: float | None, news_pct: float) -> float | None:
    """持股的體質分：基本面與消息面照原權重（40:20）重新正規化。"""
    return None if fund is None else round((0.4 * fund + 0.2 * news_pct) / 0.6, 1)


def weights(items: list, cap_mult: float = 2.0) -> dict:
    """items = [(代號, 總分)] → 各檔占該類型預算的比重；單檔不超過等權的 cap_mult 倍。"""
    if not items:
        return {}
    raw = {s: max(sc - BASE_SCORE, MIN_W) for s, sc in items}
    tot = sum(raw.values())
    cap = cap_mult / len(items)
    return {s: min(v / tot, cap) for s, v in raw.items()}


def tranche_ntd(p: dict, n: int) -> float:
    return p["target"] * RATIO[n] / sum(RATIO)


def equity_now(state: dict) -> float:
    return state["cash"] + sum(p["shares"] * (p.get("last_px") or p["tranches"][-1]["price"]) * state["fx"] for p in state["positions"].values())


# ── 買賣 ─────────────────────────────────────────────────
def _buy(state: dict, kind: str, sym: str, d: str, px: float, ntd: float, why: str) -> bool:
    fx = state["fx"]
    shares = int(ntd / fx / px)
    cost = shares * px * fx
    if shares <= 0 or cost > state["cash"] + 1e-6:
        return False
    state["cash"] -= cost
    p = state["positions"].setdefault(sym, {"kind": kind, "tranches": [], "shares": 0, "cost_ntd": 0.0})
    p["tranches"].append({"date": d, "price": px, "shares": shares})
    p["shares"] += shares
    p["cost_ntd"] += cost
    p["last_px"] = px
    state["trades"].append({"date": d, "symbol": sym, "side": "買", "price": round(px, 4), "shares": shares, "ntd": round(cost), "why": why})
    return True


def _sell(state: dict, sym: str, d: str, px: float, why: str, frac: float = 1.0) -> dict:
    p = state["positions"][sym]
    shares = p["shares"] if frac >= 1 else max(int(p["shares"] * frac), 1)
    cost_part = p["cost_ntd"] * shares / p["shares"]
    proceeds = shares * px * state["fx"]
    state["cash"] += proceeds
    state["trades"].append({"date": d, "symbol": sym, "side": "賣" if frac >= 1 else "減碼", "price": round(px, 4), "shares": shares,
                            "ntd": round(proceeds), "why": why, "pnl": round(proceeds - cost_part)})
    p["shares"] -= shares
    p["cost_ntd"] -= cost_part
    if p["shares"] <= 0:
        return state["positions"].pop(sym)
    return p


# ── 每個交易日的價格規則（止損、加碼） ─────────────────────
def step_day(state: dict, d: str, closes: dict, rules: Rules, add_ok: set):
    """closes = {代號: 收盤價}。止損一律執行；加碼只對 add_ok（基本面通過、無紅線）裡的代號。"""
    for sym in list(state["positions"]):
        px = closes.get(sym)
        if px is None:
            continue
        p = state["positions"][sym]
        p["last_px"] = px
        first, last = p["tranches"][0]["price"], p["tranches"][-1]["price"]
        p["peak"] = max(p.get("peak", last), px)
        avg = p["cost_ntd"] / state["fx"] / p["shares"]
        if px <= first * (1 - rules.stop_from_first):
            old = _sell(state, sym, d, px, f"止損：收盤 ${px:g} ≤ 首批價 ${first:g} 的 50%")
            state["reentry"][sym] = {"kind": old["kind"], "px": round(first * (1 - rules.stop_from_first) * (1 - rules.reentry_drop), 4), "stop_date": d}
            continue
        n = len(p["tranches"])
        if n < len(RATIO) and sym in add_ok and p.get("target"):
            by_step = px <= last * (1 - rules.add_step)
            by_rebound = p["peak"] >= avg * (1 + rules.rebound_min_gain) and px <= p["peak"] * (1 - rules.rebound_pullback)
            if by_step or by_rebound:
                why = (f"加碼第 {n + 1} 批：收盤 ${px:g} 較上一批價 ${last:g} 再跌 {1 - px / last:.0%}" if by_step
                       else f"加碼第 {n + 1} 批：上漲後從高點 ${p['peak']:g} 回落 {1 - px / p['peak']:.0%}")
                if _buy(state, p["kind"], sym, d, px, tranche_ntd(p, n), why):
                    p["peak"] = px


# ── 最新一天的滾動調整 ──────────────────────────────────
def rebalance(state: dict, d: str, ranked: list, info: dict, rules: Rules) -> list:
    """info = {持股代號: {verdict, veto, news_pct, fund, health, total(可無), price}}。回傳當天操作日誌（文字列表）。"""
    lines = []
    by_sym = {c["symbol"]: c for c in ranked}
    # 1. 汰弱（今天賣出的不會當天又買回）
    for sym in list(state["positions"]):
        p, h = state["positions"][sym], info.get(sym)
        if not h:
            continue
        px = h["price"]
        p["last_px"] = px
        if h.get("veto") or h["verdict"] == "排除":
            why = f"紅線出場：{h['veto']}" if h.get("veto") else "基本面判定「排除」，出清"
            _sell(state, sym, d, px, why)
            lines.append(f"賣出 {sym}：{why}")
        elif h.get("health") is not None and h["health"] < EXIT_HEALTH:
            why = f"體質分 {h['health']} < {EXIT_HEALTH}，出清"
            _sell(state, sym, d, px, why)
            lines.append(f"賣出 {sym}：{why}")
        elif h["verdict"] == "警示" and h["news_pct"] <= 30 and not p.get("trimmed"):
            why = f"基本面警示且新聞偏空（新聞分 {h['news_pct']:.0f}），減碼一半"
            _sell(state, sym, d, px, why, 0.5)
            state["positions"][sym]["trimmed"] = True
            lines.append(f"減碼 {sym}：{why}")
    eq = equity_now(state)
    for sym in list(state["positions"]):                 # 集中度
        p = state["positions"][sym]
        val = p["shares"] * p["last_px"] * state["fx"]
        if val > CONC_TRIGGER * eq:
            frac = 1 - CONC_TARGET * eq / val
            why = f"單檔占總資產 {val / eq:.0%} > {CONC_TRIGGER:.0%}，減到 {CONC_TARGET:.0%}"
            _sell(state, sym, d, p["last_px"], why, frac)
            lines.append(f"減碼 {sym}：{why}")
    # 2. 分數與目標金額（每類型：持有的 + 補位候選）
    eq = equity_now(state)
    sold_today = {t["symbol"] for t in state["trades"] if t["date"] == d and t["side"] != "買"}
    held_by_kind = {k: [s for s, p in state["positions"].items() if p["kind"] == k] for k in SLEEVES}
    plan = {}
    for kind, w in SLEEVES.items():
        for s in held_by_kind[kind]:
            c = by_sym.get(s)
            if c:
                state["positions"][s]["score"] = c["total"]
                state["positions"][s]["name"] = c.get("name", s)
        items = [(s, state["positions"][s].get("score", 65.0)) for s in held_by_kind[kind]]
        free = MAX_NAMES[kind] - len(items)
        picks = []
        for c in ranked:
            if len(picks) >= free:
                break
            if c["kind"] == kind and c["verdict"] == "通過" and not c["veto_final"] and c["total"] >= MIN_ENTRY_SCORE \
                    and c["symbol"] not in state["positions"] and c["symbol"] not in state["reentry"] and c["symbol"] not in sold_today:
                picks.append(c)
        # 止損後再進場（價格到再進場價、基本面通過）
        for s, r in list(state["reentry"].items()):
            c = by_sym.get(s)
            if r["kind"] == kind and c and len(picks) < free and c["price"] <= r["px"] and c["verdict"] == "通過" and not c["veto_final"]:
                picks.append({**c, "_reentry": True})
        wts = weights(items + [(c["symbol"], c["total"]) for c in picks])
        for s, _ in items:
            state["positions"][s]["target"] = round(w * eq * wts[s])
        plan[kind] = (picks, wts, w * eq)
    # 3. 評分加碼
    for sym, p in list(state["positions"].items()):
        c = by_sym.get(sym)
        n = len(p["tranches"])
        if not c or n >= len(RATIO) or c["verdict"] != "通過" or c["veto_final"] or c["total"] < CONVICTION_ADD_SCORE:
            continue
        last_buy = date.fromisoformat(p["tranches"][-1]["date"])
        if (date.fromisoformat(d) - last_buy).days < 10 or c["price"] > p["tranches"][-1]["price"] * 1.10:
            continue
        why = f"評分加碼第 {n + 1} 批：總分 {c['total']} ≥ {CONVICTION_ADD_SCORE}，現價未追高"
        if _buy(state, p["kind"], sym, d, c["price"], tranche_ntd(p, n), why):
            lines.append(f"買進 {sym}：{why}")
    # 4. 補位
    for kind, (picks, wts, budget) in plan.items():
        for c in picks:
            target = round(budget * wts[c["symbol"]])
            p_tmp = {"target": target}
            why = (f"止損後再進場：價格 ${c['price']:g} 已到再進場價，基本面通過" if c.get("_reentry")
                   else f"依{kind}排行補位：總分 {c['total']}，目標總額 NT${target:,}（占{kind}預算 {wts[c['symbol']]:.0%}）")
            if _buy(state, kind, c["symbol"], d, c["price"], tranche_ntd(p_tmp, 0), why):
                p = state["positions"][c["symbol"]]
                p.update(name=c.get("name", c["symbol"]), score=c["total"], target=target, opened=d)
                state["reentry"].pop(c["symbol"], None)
                lines.append(f"買進 {c['symbol']}：{why}")
    return lines


# ── 淨值與每日損益 ──────────────────────────────────────
def snapshot(state: dict, d: str, closes: dict, spy_px: float) -> dict:
    """當天收盤後的淨值、當日損益、每檔持股報酬。同一天重跑會覆蓋。"""
    fx = state["fx"]
    prev_eq = [r for r in state["equity"] if r["date"] < d]
    prev_daily = [r for r in state["daily"] if r["date"] < d]
    prev_px = {x["symbol"]: x["price"] for x in prev_daily[-1]["positions"]} if prev_daily else {}
    rows, val, cost = [], 0.0, 0.0
    for sym, p in state["positions"].items():
        px = closes.get(sym) or p.get("last_px") or p["tranches"][-1]["price"]
        p["last_px"] = px
        v = p["shares"] * px * fx
        val += v
        cost += p["cost_ntd"]
        rows.append({"symbol": sym, "kind": p["kind"], "shares": p["shares"], "price": px, "value": round(v),
                     "ret": round(v / p["cost_ntd"] - 1, 4), "day_ret": round(px / prev_px[sym] - 1, 4) if sym in prev_px else None})
    total = state["cash"] + val
    base = prev_eq[-1]["equity"] if prev_eq else state["capital"]
    spy_val = state["capital"] * spy_px / state["spy_start"]
    spy_prev = prev_eq[-1]["spy"] if prev_eq else state["capital"]
    realized = sum(t.get("pnl", 0) for t in state["trades"])
    row = {"date": d, "equity": round(total), "cash": round(state["cash"]), "invested": round(val),
           "day_pnl": round(total - base), "day_ret": round(total / base - 1, 5), "spy": round(spy_val), "spy_day_ret": round(spy_val / spy_prev - 1, 5),
           "unrealized": round(val - cost), "realized": round(realized)}
    state["equity"] = [r for r in state["equity"] if r["date"] != d] + [row]
    state["daily"] = [r for r in state["daily"] if r["date"] != d] + [{"date": d, "positions": rows}]
    state["last_date"] = d
    return row


def add_journal(state: dict, d: str, lines: list, row: dict):
    head = f"當日損益 NT${row['day_pnl']:+,}（{row['day_ret']:+.2%}），SPY {row['spy_day_ret']:+.2%}；淨值 NT${row['equity']:,}，持股 {len(state['positions'])} 檔"
    state["journal"] = [j for j in state["journal"] if j["date"] != d] + [{"date": d, "summary": head, "actions": lines or ["今天沒有調整"]}]
