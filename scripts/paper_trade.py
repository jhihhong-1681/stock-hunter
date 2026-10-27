"""模擬帳戶每日更新 → data/paper_portfolio.json（規則與設定見 utils/paper_trading.py 開頭）。

在 GitHub Actions 上跑（要抓 Yahoo 收盤價與持股財報）。每次執行：
1. 持股的基本面判定與體質分（在選股名單裡直接用；不在的用快取或現抓財報重算）＋新聞分。
2. 補算 last_date 之後每個交易日的價格規則（止損、加碼）並記錄當日損益。
3. 最新一天做滾動調整（汰弱、減碼、評分加碼、補位、依評分決定金額）。
4. 寫入淨值曲線（對照 SPY）、每檔持股當日漲跌、每筆交易的理由、當天操作日誌。
"""
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.fundamentals import FundRules, evaluate, fetch_quarterly, load_partnerships, load_profiles  # noqa: E402
from utils.market_clock import drop_partial_bar  # noqa: E402
from utils.paper_trading import (VERSION, add_journal, execute_pending, fresh_news, health, new_state, rank_candidates, rebalance, snapshot, step_day)  # noqa: E402
from utils.score_history import attach_news  # noqa: E402
from utils.scoring import score_fundamental, score_news  # noqa: E402
from utils.trading_system import Rules  # noqa: E402

OUT = ROOT / "data" / "paper_portfolio.json"
SCR = ROOT / "data" / "screener.json"
NEWS = ROOT / "data" / "news_scores.json"
FUND_CACHE = ROOT / "data" / "fundamentals_cache.json"


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def download(symbols):
    """回傳 (收盤價, 開盤價)。收盤價前值填補；開盤價不填補（NaN = 那天沒成交）。"""
    import yfinance as yf
    raw = yf.download(symbols, period="3mo", auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        raise RuntimeError("抓不到價格")
    raw = drop_partial_bar(raw)
    out = []
    for k in ("Close", "Open"):
        df = raw[k]
        out.append(df if hasattr(df, "columns") else df.to_frame(symbols[0]))
    return out[0].ffill(), out[1]


def held_info(state, ranked, news, close, today):
    """每檔持股目前的基本面判定、體質分、新聞分。在選股名單裡的直接用；不在的用快取或現抓財報重算。"""
    by_sym = {c["symbol"]: c for c in ranked}
    cache, partners, frules = load_json(FUND_CACHE, {}), load_partnerships(), FundRules()
    registered = load_profiles()                       # 人工登記的公司類型（自動推定不採用，避免邊界雜訊造成來回換）
    info = {}
    for sym, p in state["positions"].items():
        kind_now = (registered.get(sym) or {}).get("type")
        px = float(close[sym].dropna().iloc[-1]) if sym in close.columns and close[sym].notna().any() else p.get("last_px")
        c = by_sym.get(sym)
        if c:
            info[sym] = {"verdict": c["verdict"], "veto": c["veto_final"], "news_pct": c["news_pct"], "fund": c["pillars"]["基本面"],
                         "health": health(c["pillars"]["基本面"], c["news_pct"]), "total": c["total"], "price": px or c["price"], "kind_now": kind_now}
            continue
        data = (cache.get(sym) or {}).get("data")
        if not data:
            try:
                data = fetch_quarterly(sym)
            except Exception:
                data = {}
        n_pct, _, n_veto = score_news(fresh_news(news, sym, today))
        if not data:
            info[sym] = {"verdict": "資料不足", "veto": n_veto, "news_pct": n_pct, "fund": None, "health": None, "price": px, "kind_now": kind_now}
            continue
        ev = evaluate(data, partners.get(sym), frules, p["kind"])
        rev = [x for x in (data.get("rev") or [])[-4:] if x is not None]
        fund, _ = score_fundamental({"metrics": ev["metrics"], "kind": p["kind"], "track": ev["track"], "verdict": ev["verdict"],
                                     "rev_ttm": sum(rev) if len(rev) == 4 else None, "sector": None})
        info[sym] = {"verdict": ev["verdict"], "veto": n_veto, "news_pct": n_pct, "fund": fund, "health": health(fund, n_pct), "price": px, "kind_now": kind_now}
    return info


def row_dict(df, d, skip=("SPY",)):
    r = df.loc[d]
    return {c: float(r[c]) for c in df.columns if c not in skip and r[c] == r[c]}


def main():
    rules = Rules()
    scr = load_json(SCR, {})
    if not scr.get("candidates"):
        raise RuntimeError("沒有 screener.json，無法建倉")
    news = load_json(NEWS, {})
    price_date, today = scr["price_date"], date.today()
    ranked = rank_candidates(scr["candidates"], news, today)
    attach_news(price_date, {k: v for k, v in (news.get("scores") or {}).items() if fresh_news(news, k, today)})                    # 新聞分補進當天的歷史檔（供日後驗證新聞有沒有用）
    state = load_json(OUT, None)
    if state is not None and state.get("version") != VERSION:
        state = None                                   # 舊版（成交假設不同）重建
    names = (list(state["positions"]) + list(state["reentry"]) + [o["sym"] for o in state["pending"]]) if state else []
    close, opn = download(sorted(set(["SPY"] + names)))
    spy = lambda d: float(close["SPY"].dropna().loc[:d].iloc[-1])  # noqa: E731
    fresh = state is None
    if fresh:
        state = new_state(price_date, spy(price_date))
    dates = [] if fresh else [str(i.date()) for i in close.index if state["last_date"] < str(i.date()) <= price_date]
    n_before = len(state["trades"])
    info = held_info(state, ranked, news, close, today)
    add_ok = {s: h for s, h in info.items() if h["verdict"] == "通過" and not h["veto"]}
    for d in dates:
        lines = []
        execute_pending(state, d, row_dict(opn, d), lines)
        closes = row_dict(close, d)
        step_day(state, d, closes, rules, set(add_ok), lines)
        if d == price_date:
            info = held_info(state, ranked, news, close, today)
            lines += rebalance(state, d, ranked, {s: {**h, "price": closes.get(s, h["price"])} for s, h in info.items()}, rules)
        row = snapshot(state, d, closes, float(close.loc[d, "SPY"]))
        add_journal(state, d, lines, row)
    if not dates:                                      # 第一次建倉，或同一天重跑
        closes = row_dict(close, close.loc[:price_date].index[-1]) if len(close) else {}
        prev = [j for j in state["journal"] if j["date"] == price_date]
        keep = [a for a in (prev[0]["actions"] if prev else []) if not a.startswith("[調整]") and a != "今天沒有調整"]
        state["pending"] = [o for o in state["pending"] if not (o["origin"] == "rebalance" and o["created"] == price_date)]
        lines = rebalance(state, price_date, ranked, {s: {**h, "price": closes.get(s, h["price"])} for s, h in info.items()}, rules)
        row = snapshot(state, price_date, closes, spy(price_date))
        head = [f"建倉：NT${state['capital']:,.0f}，成長型約 70%／成熟型約 30%，依排行與評分決定金額；收盤後預約、隔日開盤成交"] if fresh else []
        add_journal(state, price_date, head + keep + lines, row)
    state["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成 {price_date}：持股 {len(state['positions'])} 檔，預約 {len(state['pending'])} 張，新增成交 {len(state['trades']) - n_before} 筆，淨值 {row}", flush=True)


if __name__ == "__main__":
    main()
