"""模擬帳戶每日更新 → data/paper_portfolio.json（規則與設定見 utils/paper_trading.py）。

在 GitHub Actions 上跑（要抓 Yahoo 收盤價）。第一次執行：用當時的選股排行建倉；之後每次：
補算 last_date 之後每個交易日的止損／加碼，再用最新排行補滿空出來的名額，寫入淨值曲線（對照 SPY）。
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.paper_trading import enter_positions, mark, new_state, rank_candidates, step_day  # noqa: E402
from utils.trading_system import Rules  # noqa: E402

OUT = ROOT / "data" / "paper_portfolio.json"
SCR = ROOT / "data" / "screener.json"
NEWS = ROOT / "data" / "news_scores.json"


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


def main():
    rules = Rules()
    scr = load_json(SCR, {})
    if not scr.get("candidates"):
        raise RuntimeError("沒有 screener.json，無法建倉")
    news = load_json(NEWS, {})
    price_date = scr["price_date"]
    ranked = rank_candidates(scr["candidates"], news, date.today())
    state = load_json(OUT, None)

    syms = ["SPY"] + (list(state["positions"]) + list(state["reentry"]) if state else [])
    close = download(sorted(set(syms)))
    if state is None:
        state = new_state(price_date, float(close["SPY"].dropna().loc[:price_date].iloc[-1]))
    else:
        dates = [str(i.date()) for i in close.index if str(i.date()) > state["last_date"] and str(i.date()) <= price_date]
        for d in dates:
            row = close.loc[d]
            closes = {s: float(row[s]) for s in close.columns if s != "SPY" and row[s] == row[s]}
            step_day(state, d, closes, rules)
            mark(state, d, closes, float(row["SPY"]))
    bought = enter_positions(state, price_date, ranked, rules)
    # 最新一天：用 screener 的現價標記（新買進的也在內）
    px = {c["symbol"]: c["price"] for c in scr["candidates"]}
    last_closes = {s: float(close[s].dropna().iloc[-1]) for s in close.columns if s != "SPY" and close[s].notna().any()}
    last_closes.update({s: p for s, p in px.items() if s in state["positions"] and s not in last_closes})
    spy_now = float(close["SPY"].dropna().loc[:price_date].iloc[-1])
    mark(state, price_date, last_closes, spy_now)
    state["generated"] = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成 {price_date}：持股 {len(state['positions'])} 檔，本次買進 {bought}，淨值 {state['equity'][-1]}", flush=True)


if __name__ == "__main__":
    main()
