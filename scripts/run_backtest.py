"""交易系統回測（在 GitHub Actions 上跑：雲端 Claude 環境連不到 Yahoo，Actions 可以）。

讀 data/backtest_request.json → 用 yfinance 抓日線 → 跑 utils/trading_system.backtest 的一組參數網格
→ 寫 data/backtest_results.json。只測「價格規則」；沒有歷史基本面資料，基本面濾網無法回測。

job 可選欄位（都不給 = 跟以前一樣：收盤價成交、無滑價、無額外條件）：
- exec_variants：[{"name": "...", "lag": 1, "slippage": 0.003}, ...]  成交假設（lag = 訊號後隔幾個交易日、用開盤價成交；slippage = 不利滑價）
- gates：["none", "spy_above_ma200", "ma200_rising", "rel20_vs_spy", "bounce5pct"]  新一輪首批進場的額外條件，一次測一個
結果每個 config 的 params 會記 exec 與 gate，方便對照。
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


_CACHE = {}


def download(symbols, period):
    """回傳 (收盤價 DataFrame, 開盤價 DataFrame)；同一次執行內相同參數只抓一次。"""
    import pandas as pd
    import yfinance as yf
    key = (tuple(symbols), period)
    if key in _CACHE:
        return _CACHE[key]
    closes, opens = [], []
    for i in range(0, len(symbols), 20):
        chunk = symbols[i:i + 20]
        raw = yf.download(chunk, period=period, auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            continue
        for field, bucket in (("Close", closes), ("Open", opens)):
            part = raw[field]
            if isinstance(part, pd.Series):
                part = part.to_frame(chunk[0])
            bucket.append(part)
    out = (pd.concat(closes, axis=1) if closes else pd.DataFrame(), pd.concat(opens, axis=1) if opens else pd.DataFrame())
    _CACHE[key] = out
    return out


def sma(vals, n):
    """簡單移動平均（前 n-1 天為 nan）。"""
    out, run = [], 0.0
    for i, v in enumerate(vals):
        run += v
        if i >= n:
            run -= vals[i - n]
        out.append(run / n if i >= n - 1 else float("nan"))
    return out


def build_gates(dates, close, spy_by_date):
    """回傳 {gate 名稱: 逐日 bool list}。spy_by_date：{日期字串: SPY 收盤}。條件都只用「當天收盤以前」的資料。"""
    n = len(close)
    spy = [spy_by_date.get(d) for d in dates]
    spy_ok = all(x is not None for x in spy)
    ma200 = sma(close, 200)
    low20 = [min(close[max(0, i - 19):i + 1]) for i in range(n)]
    g = {"none": [True] * n}
    g["ma200_rising"] = [i >= 220 and ma200[i] > ma200[i - 20] for i in range(n)]
    g["bounce5pct"] = [close[i] >= low20[i] * 1.05 for i in range(n)]
    if spy_ok:
        spy_ma = sma(spy, 200)
        g["spy_above_ma200"] = [spy_ma[i] == spy_ma[i] and spy[i] > spy_ma[i] for i in range(n)]
        g["rel20_vs_spy"] = [i >= 20 and (close[i] / close[i - 20] - 1) > (spy[i] / spy[i - 20] - 1) for i in range(n)]
    else:
        for k in ("spy_above_ma200", "rel20_vs_spy"):
            g[k] = [False] * n
    return g


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
        "avg_ret": sum(t.ret for t in trades) / len(trades) if trades else 0,
        "median_ret": sorted(t.ret for t in trades)[len(trades) // 2] if trades else 0,
        "ret_on_invested": sum(t.pnl for t in trades) / sum(t.invested for t in trades) if trades and sum(t.invested for t in trades) else 0,
        "worst_ret": min((t.ret for t in trades), default=0),
        "avg_days": sum(t.days for t in trades) / len(trades) if trades else 0,
        "peak_positions": pn, "peak_capital": pc,
    }


def run_job(req):
    symbols = load_symbols(req)
    period = req.get("period", "10y")
    prices, opens_df = download(symbols, period)
    spy_by_date = {}
    if req.get("gates"):
        spy_close, _ = download(["SPY"], period)
        if "SPY" in spy_close.columns:
            spy_by_date = {str(d.date()): float(x) for d, x in spy_close["SPY"].dropna().items()}
    series, coverage, opens = {}, {}, {}
    for s in symbols:
        if s in prices.columns:
            ser = prices[s].dropna()
            if len(ser) >= 120:
                series[s] = ([str(d.date()) for d in ser.index], [float(x) for x in ser.values])
                if s in opens_df.columns:
                    opens[s] = [float(x) if x == x else float("nan") for x in opens_df[s].reindex(ser.index).values]
                coverage[s] = {"from": str(ser.index[0].date()), "to": str(ser.index[-1].date()), "days": len(ser)}
    variants = req.get("exec_variants") or [{"name": "收盤成交", "lag": 0, "slippage": 0.0}]
    gate_names = req.get("gates") or ["none"]
    gate_cache = {s: build_gates(d, c, spy_by_date) for s, (d, c) in series.items()} if req.get("gates") else {}
    grid = req.get("grid", {})
    configs = []
    for tp, ed, stop, step, hw in product(grid.get("take_profit", [None, 0.5]), grid.get("entry_drop", [0.3]), grid.get("stop", [0.5]),
                                          grid.get("add_step", [Rules().add_step]), grid.get("high_window", [Rules().high_window])):
      for v, gname in product(variants, gate_names):
        r = Rules(entry_drop=ed, stop_from_first=stop, take_profit=tp, add_step=step, high_window=hw,
                  exec_lag=v.get("lag", 0), slippage=v.get("slippage", 0.0))
        alltr, by = [], {}
        for s, (d, c) in series.items():
            tr = backtest(s, d, c, r, opens=opens.get(s), gate=gate_cache.get(s, {}).get(gname))
            alltr += tr
            if tr:
                sm = summarize(tr)
                by[s] = {k: sm[k] for k in ("trades", "pnl", "stops", "win_rate", "worst")}
        params = {"take_profit": tp, "entry_drop": ed, "stop": stop, "add_step": step, "high_window": hw}
        if req.get("exec_variants"):
            params["exec"] = v.get("name")
            params["lag"], params["slippage"] = v.get("lag", 0), v.get("slippage", 0.0)
        if req.get("gates"):
            params["gate"] = gname
        cfg = {"params": params, "summary": summarize(alltr), "by_symbol": by}
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
