"""模擬帳戶「價格版」回測：近兩年報酬率 vs 大盤（SPY、QQQ）。在 GitHub Actions 上跑（需要 Yahoo）。

只重現模擬帳戶裡「看得到歷史資料」的部分，詳細限制見輸出 JSON 的 notes：
- 進場：距 26 週高點回檔 ≥ 20%、流動性（股價 ≥ $3、20 日均成交額 ≥ $500 萬）、價格分（utils.scoring.score_price）≥ MIN_SCORE，
  由高到低補位，最多 MAX_NAMES 檔；每檔目標金額 = 總資產 / MAX_NAMES，分三批 2:3:4。
- 加碼／止損：跟模擬帳戶、交易系統完全同一套（上一批價再跌 20% 或上漲後回落 25%；首批價再跌 50% 收盤止損，
  止損後從止損價再跌 30% 才重新進場）。不做止盈。
- 成交：訊號收盤後產生，隔個交易日開盤成交，買進 +0.3%、賣出 −0.3% 滑價，無手續費。
- 沒有：基本面判定、新聞分、汰弱（體質分）、類型改判、同產業限制（歷史資料不可得）。
- 母體 = S&P 500 現在的成分股 + 阿紘成交紀錄裡的正股 → 有嚴重的倖存者偏差（下跌後被剔除的公司不在名單內），絕對報酬偏樂觀。
輸出 data/backtest_paper.json。用法：python scripts/backtest_paper.py [年數，預設 2]
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.scoring import score_price  # noqa: E402
from utils.trading_system import Rules  # noqa: E402

CAPITAL = 1_000_000.0       # 以 NT$ 計，匯率固定 31，報酬率與美元計價相同
MAX_NAMES = 10              # 模擬帳戶成長 7 + 成熟 3
MIN_SCORE = 50.0            # 價格分門檻（模擬帳戶總分門檻 60 含基本面，這裡只有價格那一塊）
RATIO = (2, 3, 4)
SLIP = 0.003
MIN_PRICE, MIN_DOLLAR_VOL = 3.0, 5_000_000
HIGH_WIN = 130
RULES = Rules()


def universe():
    import csv
    import io
    import urllib.request
    url = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    rows = csv.DictReader(io.StringIO(urllib.request.urlopen(url, timeout=60).read().decode("utf-8")))
    syms = {r["Symbol"].replace(".", "-") for r in rows}
    try:
        from utils.trading_system import read_trades
        syms |= {t["symbol"] for t in read_trades() if t.get("type") == "stock"}
    except Exception as e:  # noqa: BLE001
        print("read_trades 失敗：", e)
    return sorted(syms)


def download(symbols, period):
    import yfinance as yf
    cl, op, vo = [], [], []
    for i in range(0, len(symbols), 25):
        chunk = symbols[i:i + 25]
        raw = yf.download(chunk, period=period, auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            continue
        for field, bucket in (("Close", cl), ("Open", op), ("Volume", vo)):
            part = raw[field]
            if isinstance(part, pd.Series):
                part = part.to_frame(chunk[0])
            bucket.append(part)
    return pd.concat(cl, axis=1), pd.concat(op, axis=1), pd.concat(vo, axis=1)


def price_score(close, i, vol):
    """第 i 天收盤的價格分與距高點；資料不足回 None。close 為 numpy 一維陣列。"""
    if i < 130 or np.isnan(close[i]):
        return None
    win = close[i - HIGH_WIN + 1:i + 1]
    if np.isnan(win).any():
        return None
    dd = close[i] / win.max() - 1
    if dd > -RULES.entry_drop:
        return None
    r = np.diff(close[max(0, i - 251):i + 1]) / close[max(0, i - 251):i]
    sig = np.nanstd(r, ddof=1) * np.sqrt(252) if len(r) > 2 else None
    dd_vol = dd / sig if sig else None
    low20 = np.nanmin(close[i - 19:i + 1])
    v10, v60 = np.nanmean(vol[i - 9:i + 1]), np.nanmean(vol[i - 59:i + 1])
    c = {"dd": dd, "dd_vol": dd_vol, "stab": {"bounce20": close[i] / low20 - 1, "r10": close[i] / close[i - 10] - 1,
                                                "vol_ratio": (v10 / v60) if v60 else None}}
    return score_price(c)[0], dd


def run(close, opn, volu, start_idx, symbols):
    dates = [d.strftime("%Y-%m-%d") for d in close.index]
    C = {s: close[s].to_numpy(float) for s in symbols}
    O = {s: opn[s].to_numpy(float) if s in opn else C[s] for s in symbols}
    V = {s: volu[s].to_numpy(float) if s in volu else np.zeros(len(dates)) for s in symbols}
    cash, pos, pending, reentry = CAPITAL, {}, [], {}
    cooldown = {}
    eq, trades = [], []

    def equity(i):
        t = cash
        for s, p in pos.items():
            px = C[s][i]
            t += p["shares"] * (px if not np.isnan(px) else p["last"])
        return t

    for i in range(start_idx, len(dates)):
        # 1. 開盤：先賣後買，執行昨天預約的單
        for o in sorted(pending, key=lambda o: o["side"] != "sell"):
            s, px0 = o["sym"], O[o["sym"]][i]
            if np.isnan(px0):
                continue
            if o["side"] == "sell" and s in pos:
                px = px0 * (1 - SLIP)
                p = pos.pop(s)
                cash += p["shares"] * px
                trades.append({"date": dates[i], "symbol": s, "side": "賣", "price": round(px, 4), "pnl": round(p["shares"] * px - p["cost"], 2), "why": o["why"]})
                if o.get("stop"):
                    reentry[s] = o["reentry_px"]
                else:
                    cooldown[s] = i
            elif o["side"] == "buy":
                px = px0 * (1 + SLIP)
                sh = int(min(o["usd"], cash) / px)
                if sh <= 0:
                    continue
                cash -= sh * px
                p = pos.setdefault(s, {"shares": 0, "cost": 0.0, "tr": [], "target": o["target"], "peak": px, "last": px})
                p["shares"] += sh
                p["cost"] += sh * px
                p["tr"].append(px)
                p["target"] = o["target"] if len(p["tr"]) == 1 else p["target"]
                trades.append({"date": dates[i], "symbol": s, "side": "買", "price": round(px, 4), "why": o["why"]})
                reentry.pop(s, None)
        pending = []
        # 2. 收盤：止損與加碼（價格規則）
        for s, p in list(pos.items()):
            px = C[s][i]
            if np.isnan(px):
                continue
            p["last"] = px
            p["peak"] = max(p["peak"], px)
            first, last = p["tr"][0], p["tr"][-1]
            avg = p["cost"] / p["shares"]
            if px <= first * (1 - RULES.stop_from_first):
                pending.append({"sym": s, "side": "sell", "why": "止損", "stop": True,
                                "reentry_px": first * (1 - RULES.stop_from_first) * (1 - RULES.reentry_drop)})
                continue
            n = len(p["tr"])
            if n < 3:
                by_step = px <= last * (1 - RULES.add_step)
                by_rebound = p["peak"] >= avg * (1 + RULES.rebound_min_gain) and px <= p["peak"] * (1 - RULES.rebound_pullback)
                if by_step or by_rebound:
                    pending.append({"sym": s, "side": "buy", "usd": p["target"] * RATIO[n] / 9, "target": p["target"],
                                    "why": f"加碼第{n + 1}批"})
        # 3. 收盤：補位（最新一天才有名額就補）
        queued = {o["sym"] for o in pending}
        free = MAX_NAMES - len([s for s in pos if not any(o["sym"] == s and o["side"] == "sell" for o in pending)]) - \
            len([o for o in pending if o["side"] == "buy" and o["sym"] not in pos])
        if free > 0:
            eqv = equity(i)
            target = eqv / MAX_NAMES
            cands = []
            for s in symbols:
                if s in pos or s in queued:
                    continue
                px = C[s][i]
                if np.isnan(px) or px < MIN_PRICE or i < 130:
                    continue
                dv = np.nanmean(V[s][i - 19:i + 1] * C[s][i - 19:i + 1])
                if not dv >= MIN_DOLLAR_VOL:
                    continue
                if s in cooldown and i - cooldown[s] < 30:
                    continue
                if s in reentry and px > reentry[s]:
                    continue
                r = price_score(C[s], i, V[s])
                if r and r[0] >= MIN_SCORE:
                    cands.append((r[0], s))
            for sc, s in sorted(cands, reverse=True)[:free]:
                pending.append({"sym": s, "side": "buy", "usd": target * RATIO[0] / 9, "target": target, "why": f"補位：價格分 {sc:.0f}"})
        eq.append((dates[i], equity(i), len(pos)))
    return eq, trades


def stats(series):
    v = np.array([x for _, x in series], float)
    ret = v[1:] / v[:-1] - 1
    years = len(v) / 252
    peak = np.maximum.accumulate(v)
    return {"total_return": round(v[-1] / v[0] - 1, 4), "cagr": round((v[-1] / v[0]) ** (1 / years) - 1, 4),
            "max_drawdown": round(float((v / peak - 1).min()), 4),
            "vol": round(float(ret.std(ddof=1) * np.sqrt(252)), 4),
            "sharpe": round(float(ret.mean() / ret.std(ddof=1) * np.sqrt(252)), 2) if ret.std() else None}


def main():
    years = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    syms = universe()
    print("母體", len(syms))
    close, opn, volu = download(syms + ["SPY", "QQQ"], f"{years + 2}y")
    close = close.sort_index().ffill(limit=3)
    opn, volu = opn.reindex(close.index), volu.reindex(close.index).fillna(0)
    avail = [s for s in syms if s in close and close[s].notna().sum() > 300]
    print("有資料", len(avail))
    last = close.index[-1]
    start = close.index.searchsorted(last - pd.DateOffset(years=years))
    eq, trades = run(close, opn, volu, start, avail)
    out_dates = [d for d, _, _ in eq]
    rows = {"策略": [v for _, v, _ in eq]}
    for b in ("SPY", "QQQ"):
        px = close[b].reindex(close.index).iloc[start:].to_numpy(float)
        rows[b] = list(CAPITAL * px / px[0])
    result = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "years": years,
              "start": out_dates[0], "end": out_dates[-1], "universe": len(avail), "capital": CAPITAL,
              "params": {"max_names": MAX_NAMES, "min_price_score": MIN_SCORE, "slippage": SLIP, "high_window": HIGH_WIN},
              "stats": {k: stats(list(zip(out_dates, v))) for k, v in rows.items()},
              "by_year": {},
              "trades_summary": {"買進": sum(t["side"] == "買" for t in trades), "止損": sum(t["why"] == "止損" for t in trades),
                                 "賣出筆數": sum(t["side"] == "賣" for t in trades),
                                 "賣出勝率": round(sum(t.get("pnl", 0) > 0 for t in trades if t["side"] == "賣") / max(1, sum(t["side"] == "賣" for t in trades)), 3)},
              "equity": {"dates": out_dates, **{k: [round(x) for x in v] for k, v in rows.items()}, "持股檔數": [n for _, _, n in eq]},
              "trades": trades[-300:],
              "notes": ["只回測價格規則（進場區、價格分、三批加碼、止損）；沒有基本面、新聞、汰弱、類型分配、同產業限制，這些歷史資料取不到。",
                        "母體是 S&P 500 現在的成分股加阿紘買過的正股，有嚴重的倖存者偏差，絕對報酬偏樂觀；較可信的是跟 SPY／QQQ 的相對比較與最大回撤。",
                        "成交：訊號隔日開盤、買賣各 0.3% 滑價、無手續費；不做止盈；匯率固定 31（報酬率與美元計價相同）。",
                        "價格分門檻 50、10 檔等權目標是回測用的設定，不是模擬帳戶的總分 60 / 評分權重。"]}
    for y in sorted({d[:4] for d in out_dates}):
        idx = [k for k, d in enumerate(out_dates) if d[:4] == y]
        a, b = max(idx[0] - 1, 0), idx[-1]
        result["by_year"][y] = {k: round(v[b] / v[a] - 1, 4) for k, v in rows.items()}
    (ROOT / "data" / "backtest_paper.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"stats": result["stats"], "by_year": result["by_year"], "trades": result["trades_summary"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
