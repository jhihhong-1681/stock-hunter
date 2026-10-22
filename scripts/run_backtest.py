"""交易系統回測（在 GitHub Actions 上跑：雲端 Claude 環境連不到 Yahoo，Actions 可以）。

讀 data/backtest_request.json → 用 yfinance 抓日線 → 跑 utils/trading_system.backtest 的一組參數網格
→ 寫 data/backtest_results.json。只測「價格規則」；沒有歷史基本面資料，基本面濾網無法回測。
"""
import json
import sys
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.trading_system import Rules, backtest, read_trades  # noqa: E402


def load_symbols(req):
    if req.get("symbols") == "sp500":
        import csv
        import io
        import urllib.request
        url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
        rows = csv.DictReader(io.StringIO(urllib.request.urlopen(url, timeout=60).read().decode("utf-8")))
        return sorted({r["Symbol"].replace(".", "-") for r in rows})
    if req.get("symbols") == "from_trades":
        return sorted({t["symbol"] for t in read_trades() if t.get("type") == "stock"})
    return sorted(set(req["symbols"]))


def download(symbols, period):
    import pandas as pd
    import yfinance as yf
    frames = []
    for i in range(0, len(symbols), 20):
        chunk = symbols[i:i + 20]
        raw = yf.download(chunk, period=period, auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            continue
        close = raw["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(chunk[0])
        frames.append(close)
    return pd.concat(frames, axis=1) if frames else pd.DataFrame()


def concurrency(trades):
    """同時持有的最大檔數與最大投入金額（以每筆最終投入金額估，偏保守）。"""
    ev = []
    for t in trades:
        ev.append((t.entry, 1, t.invested))
        ev.append((t.exit, -1, -t.invested))
    ev.sort(key=lambda e: (e[0], e[1]))  # 同一天先出後進
    n = cap = peak_n = peak_cap = 0
    for _, dn, dc in ev:
        n += dn
        cap += dc
        peak_n, peak_cap = max(peak_n, n), max(peak_cap, cap)
    return peak_n, peak_cap


def summarize(trades):
    done = [t for t in trades if t.reason != "持有中"]
    wins = [t for t in done if t.pnl > 0]
    losses = [t for t in done if t.pnl <= 0]
    pn, pc = concurrency(trades)
    return {
        "trades": len(trades), "done": len(done), "open": len(trades) - len(done),
        "win_rate": len(wins) / len(done) if done else None,
        "avg_win": sum(t.pnl for t in wins) / len(wins) if wins else 0,
        "avg_loss": sum(t.pnl for t in losses) / len(losses) if losses else 0,
        "stops": sum(t.reason == "止損" for t in done),
        "pnl": sum(t.pnl for t in trades), "invested": sum(t.invested for t in trades),
        "worst": min((t.pnl for t in trades), default=0),
        "avg_days": sum(t.days for t in trades) / len(trades) if trades else 0,
        "peak_positions": pn, "peak_capital": pc,
    }


def run_job(req):
    symbols = load_symbols(req)
    prices = download(symbols, req.get("period", "10y"))
    series, coverage = {}, {}
    for s in symbols:
        if s in prices.columns:
            ser = prices[s].dropna()
            if len(ser) >= 120:
                series[s] = ([str(d.date()) for d in ser.index], [float(x) for x in ser.values])
                coverage[s] = {"from": str(ser.index[0].date()), "to": str(ser.index[-1].date()), "days": len(ser)}
    grid = req.get("grid", {})
    configs = []
    for tp, ed, stop, step, hw in product(grid.get("take_profit", [None, 0.5]), grid.get("entry_drop", [0.3]), grid.get("stop", [0.5]),
                                          grid.get("add_step", [Rules().add_step]), grid.get("high_window", [Rules().high_window])):
        r = Rules(entry_drop=ed, stop_from_first=stop, take_profit=tp, add_step=step, high_window=hw)
        alltr, by = [], {}
        for s, (d, c) in series.items():
            tr = backtest(s, d, c, r)
            alltr += tr
            if tr:
                sm = summarize(tr)
                by[s] = {k: sm[k] for k in ("trades", "pnl", "stops", "win_rate", "worst")}
        cfg = {"params": {"take_profit": tp, "entry_drop": ed, "stop": stop, "add_step": step, "high_window": hw}, "summary": summarize(alltr), "by_symbol": by}
        if tp == grid.get("detail_tp", "x") and ed == 0.3 and stop == 0.5:
            cfg["trades"] = [t.__dict__ for t in alltr]
        configs.append(cfg)
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "period": req.get("period", "10y"),
           "symbols_requested": len(symbols), "symbols_with_data": len(series), "coverage": coverage, "configs": configs}
    (ROOT / "data" / req.get("output", "backtest_results.json")).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{req.get('output', 'backtest_results.json')}: {len(series)}/{len(symbols)} symbols, {len(configs)} configs")


def main():
    req = json.loads((ROOT / "data" / "backtest_request.json").read_text(encoding="utf-8"))
    for job in req["jobs"]:
        run_job(job)


if __name__ == "__main__":
    main()
