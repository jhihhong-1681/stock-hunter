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
from utils.fundamentals import FundRules, evaluate, fetch_quarterly, load_partnerships  # noqa: E402
from utils.paper_trading import (add_journal, fresh_news, health, new_state, rank_candidates, rebalance, snapshot, step_day)  # noqa: E402
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
    import yfinance as yf
    raw = yf.download(symbols, period="3mo", auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        raise RuntimeError("抓不到收盤價")
    close = raw["Close"]
    if not hasattr(close, "columns"):
        close = close.to_frame(symbols[0])
    return close.ffill()


def held_info(state, ranked, news, close, today):
    """每檔持股目前的基本面判定、體質分、新聞分。在選股名單裡的直接用；不在的用快取或現抓財報重算。"""
    by_sym = {c["symbol"]: c for c in ranked}
    cache, partners, frules = load_json(FUND_CACHE, {}), load_partnerships(), FundRules()
    info = {}
    for sym, p in state["positions"].items():
        px = float(close[sym].dropna().iloc[-1]) if sym in close.columns and close[sym].notna().any() else p.get("last_px")
        c = by_sym.get(sym)
        if c:
            info[sym] = {"verdict": c["verdict"], "veto": c["veto_final"], "news_pct": c["news_pct"], "fund": c["pillars"]["基本面"],
                         "health": health(c["pillars"]["基本面"], c["news_pct"]), "total": c["total"], "price": px or c["price"]}
            continue
        data = (cache.get(sym) or {}).get("data")
        if not data:
            try:
                data = fetch_quarterly(sym)
            except Exception:
                data = {}
        n_pct, _, n_veto = score_news(fresh_news(news, sym, today))
        if not data:
            info[sym] = {"verdict": "資料不足", "veto": n_veto, "news_pct": n_pct, "fund": None, "health": None, "price": px}
            continue
        ev = evaluate(data, partners.get(sym), frules, p["kind"])
        rev = [x for x in (data.get("rev") or [])[-4:] if x is not None]
        fund, _ = score_fundamental({"metrics": ev["metrics"], "kind": p["kind"], "track": ev["track"], "verdict": ev["verdict"],
                                     "rev_ttm": sum(rev) if len(rev) == 4 else None, "sector": None})
        info[sym] = {"verdict": ev["verdict"], "veto": n_veto, "news_pct": n_pct, "fund": fund, "health": health(fund, n_pct), "price": px}
    return info


def main():
    rules = Rules()
    scr = load_json(SCR, {})
    if not scr.get("candidates"):
        raise RuntimeError("沒有 screener.json，無法建倉")
    news = load_json(NEWS, {})
    price_date, today = scr["price_date"], date.today()
    ranked = rank_candidates(scr["candidates"], news, today)
    state = load_json(OUT, None)
    if state is not None and state.get("version") != 2:
        state = None                                   # 舊版（固定 2/3/4 萬）重建
    names = list(state["positions"]) + list(state["reentry"]) if state else []
    close = download(sorted(set(["SPY"] + names)))
    spy = lambda d: float(close["SPY"].dropna().loc[:d].iloc[-1])  # noqa: E731
    fresh = state is None
    if fresh:
        state = new_state(price_date, spy(price_date))
    info = held_info(state, ranked, news, close, today)
    add_ok = {s for s, h in info.items() if h["verdict"] == "通過" and not h["veto"]}
    if not fresh:
        dates = [str(i.date()) for i in close.index if state["last_date"] < str(i.date()) < price_date]
        for d in dates:
            row = close.loc[d]
            closes = {s: float(row[s]) for s in close.columns if s != "SPY" and row[s] == row[s]}
            step_day(state, d, closes, rules, add_ok)
            r = snapshot(state, d, closes, float(row["SPY"]))
            add_journal(state, d, [t["side"] + " " + t["symbol"] + "：" + t["why"] for t in state["trades"] if t["date"] == d], r)
    # 最新一天：價格規則（止損、加碼）用最新收盤，再做滾動調整
    last_row = close.loc[:price_date].iloc[-1] if len(close) else None
    closes = {}
    if last_row is not None:
        closes = {s: float(last_row[s]) for s in close.columns if s != "SPY" and last_row[s] == last_row[s]}
    if not fresh and state["last_date"] < price_date:
        step_day(state, price_date, closes, rules, add_ok)
    lines = [t["side"] + " " + t["symbol"] + "：" + t["why"] for t in state["trades"] if t["date"] == price_date]
    n_before = len(state["trades"])
    lines += rebalance(state, price_date, ranked, {s: {**h, "price": closes.get(s, h["price"])} for s, h in info.items()}, rules)
    for c in ranked:                                      # 新買進的用 screener 現價
        if c["symbol"] in state["positions"]:
            closes.setdefault(c["symbol"], c["price"])
    row = snapshot(state, price_date, closes, spy(price_date))
    add_journal(state, price_date, ([f"建倉：NT${state['capital']:,.0f}，成長型約 70%／成熟型約 30%，依排行與評分決定金額"] if fresh else []) + lines, row)
    state["generated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成 {price_date}：持股 {len(state['positions'])} 檔，新增交易 {len(state['trades']) - n_before} 筆，淨值 {row}", flush=True)


if __name__ == "__main__":
    main()
