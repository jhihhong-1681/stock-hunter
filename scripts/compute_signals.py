"""每日計算交易系統訊號 → data/trading_signals.json（頁面只讀這個檔，不用現場抓 Yahoo）。

在 GitHub Actions 上跑（雲端 Claude 環境連不到 Yahoo）：每次雲端快照把 holdings.js 推上 main 就接著跑。
內容：自選股＋持股的價格訊號（回檔、波動率）、基本面判定、持股對照規則、期權持倉提示、今日行動清單。
財報抓不到時沿用上一份的判定（標註沿用日期），不會變成「資料不足」。
"""
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.fundamentals import FundRules, evaluate, fetch_quarterly, load_partnerships, load_profiles  # noqa: E402
from utils.trading_system import (OptionRules, Rules, check_position, hold_hint, option_dte, read_positions,  # noqa: E402
                                  read_trades, scan_symbol)

OUT = ROOT / "data" / "trading_signals.json"


def clean(x):
    """JSON 不能放 inf / nan。"""
    if isinstance(x, float):
        return None if (math.isnan(x) or math.isinf(x)) else x
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def download(symbols, period="2y"):
    import pandas as pd
    import yfinance as yf
    frames = []
    for i in range(0, len(symbols), 20):
        raw = yf.download(symbols[i:i + 20], period=period, auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            continue
        close = raw["Close"]
        if isinstance(close, pd.Series):
            close = close.to_frame(symbols[i])
        frames.append(close)
    return pd.concat(frames, axis=1) if frames else pd.DataFrame()


def main():
    rules, orules, frules = Rules(), OptionRules(), FundRules()
    profiles, partners = load_profiles(), load_partnerships()
    positions = read_positions()
    stocks = [p for p in positions if not p.get("type")]
    options = [p for p in positions if p.get("type") == "option"]
    trades = read_trades()
    watch = json.loads((ROOT / "data" / "watchlist.json").read_text(encoding="utf-8"))
    symbols = sorted(set(watch) | {p["symbol"] for p in stocks})
    prev = {}
    if OUT.exists():
        try:
            prev = {s["symbol"]: s for s in json.loads(OUT.read_text(encoding="utf-8")).get("stocks", [])}
        except ValueError:
            prev = {}
    prices = download(symbols)
    today = date.today()
    held = {p["symbol"]: p for p in stocks}
    out_stocks, fund_errors = [], []
    last_dates = []
    for sym in symbols:
        prof = profiles.get(sym, {})
        rec = {"symbol": sym, "name": (held.get(sym) or {}).get("name") or prof.get("name") or sym, "held": sym in held,
               "type": prof.get("type", "-")}
        # 價格訊號
        if sym in prices.columns:
            ser = prices[sym].dropna()
            sc = scan_symbol(ser, rules)
            if sc:
                rec.update(price=sc["現價"], high_ref=sc["區間高點"], dd=sc["距高點"], vol=sc["年化波動率"], dd_vol=sc["回檔/波動率"],
                           in_zone=bool(sc["進場區"]), spark=[round(float(x), 2) for x in ser.iloc[-90:].values])
                last_dates.append(str(ser.index[-1].date()))
        # 基本面
        if prof.get("type") == "ETF":
            rec.update(verdict="不適用", reasons=["ETF 沒有公司財報"], notes=[], track="-", metrics={}, partners=[])
        else:
            try:
                d = fetch_quarterly(sym)
            except Exception:
                d = {}
            if d:
                e = evaluate(d, partners.get(sym), frules, prof.get("type"))
                m = dict(e["metrics"])
                if m.get("可撐月數") == float("inf"):
                    m["不燒錢"] = True
                rec.update(verdict=e["verdict"], kind=e["kind"], track=e["track"], reasons=e["reasons"], notes=e["notes"],
                           metrics=m, partners=e["partners"], fund_asof=str(today))
            elif sym in prev and prev[sym].get("verdict") not in (None, "資料不足"):
                old = prev[sym]
                rec.update({k: old.get(k) for k in ("verdict", "kind", "track", "reasons", "notes", "metrics", "partners")})
                rec["fund_asof"] = old.get("fund_asof")
                rec["notes"] = list(rec.get("notes") or []) + [f"財報這次抓不到，沿用 {old.get('fund_asof', '之前')} 的判定"]
                fund_errors.append(sym)
            else:
                rec.update(verdict="資料不足", reasons=["Yahoo 沒有回財報"], notes=[], track="-", metrics={}, partners=partners.get(sym, []))
                fund_errors.append(sym)
        # 持股對照
        if sym in held:
            c = check_position(held[sym], trades, rules)
            adds_left = c.get("下一批加碼價") is not None
            rec["position"] = {**{k: c[k] for k in ("首批價", "現價", "成本均價", "已買批數", "距首批價", "止損價", "距止損價", "已觸發止損",
                                                     "止損後再進場價", "報酬率", "現值NT$", "備註")},
                               "下一批加碼價": c.get("下一批加碼價"), "下一批金額NT$": c.get("下一批金額NT$"),
                               "對照": hold_hint(bool(c["已觸發止損"]), rec["verdict"], adds_left, c["止損後再進場價"])}
        out_stocks.append(rec)

    # 期權持倉（提示用，現有部位照阿紘的意思不處理）
    opt_rows = []
    for p in options:
        dte = option_dte(p["name"], today)
        opt_rows.append({"name": p["name"], "symbol": p["symbol"], "dte": dte, "pct": p["pct"], "value": p["value"],
                         "exit_hit": p["pct"] <= -orules.exit_loss * 100})

    # 今日行動清單
    actions = []
    order = {"通過": 0, "警示": 1, "排除": 2}
    for r in out_stocks:
        pos = r.get("position")
        if pos and pos["已觸發止損"]:
            actions.append({"kind": "stop", "prio": 0, "symbol": r["symbol"], "title": f"{r['symbol']} 已觸發止損",
                            "detail": f"首批 ${pos['首批價']:g} → 現價 ${pos['現價']:g}（{pos['距首批價']:+.0%}）。規則：出清。基本面：{r['verdict']}。再進場價 ${pos['止損後再進場價']:g}"})
        elif pos and pos["距止損價"] <= 0.15:
            actions.append({"kind": "near", "prio": 1, "symbol": r["symbol"], "title": f"{r['symbol']} 接近止損價",
                            "detail": f"現價 ${pos['現價']:g}，止損價 ${pos['止損價']:g}（距 {pos['距止損價']:+.0%}）"})
        elif pos and pos.get("下一批加碼價") and pos["現價"] <= pos["下一批加碼價"] and r["verdict"] != "排除":
            actions.append({"kind": "add", "prio": 2, "symbol": r["symbol"], "title": f"{r['symbol']} 到下一批加碼價",
                            "detail": f"現價 ${pos['現價']:g} ≤ 加碼價 ${pos['下一批加碼價']:g}，第 {pos['已買批數'] + 1} 批 NT${pos['下一批金額NT$']:,}；基本面：{r['verdict']}"})
    cands = [r for r in out_stocks if r.get("in_zone") and not r["held"] and r.get("verdict") != "排除"]
    cands.sort(key=lambda r: (order.get(r.get("verdict"), 3), r["dd"]))
    for i, r in enumerate(cands, 1):
        actions.append({"kind": "entry", "prio": 3, "symbol": r["symbol"], "title": f"{r['symbol']} 進入進場區（優先序 {i}）",
                        "detail": f"距 26 週高點 {r['dd']:+.0%}，波動率 {r['vol']:.0%}；基本面：{r['verdict']}"})

    actions.sort(key=lambda a: a["prio"])
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "price_date": max(last_dates) if last_dates else None,
           "rules": {"進場回檔": rules.entry_drop, "止損": rules.stop_from_first, "再進場": rules.reentry_drop,
                     "批次NT$": list(rules.tranches_ntd), "期權距到期至少": orules.min_dte, "期權出場虧損": orules.exit_loss},
           "stocks": out_stocks, "options": opt_rows, "actions": actions, "fund_errors": fund_errors}
    OUT.write_text(json.dumps(clean(out), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"signals: {len(out_stocks)} stocks, {len(actions)} actions, fund_errors={fund_errors}")


if __name__ == "__main__":
    main()
