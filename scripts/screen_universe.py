"""每日選股雷達 → data/screener.json（頁面只讀這個檔）。

在 GitHub Actions 上跑（雲端 Claude 環境連不到 Yahoo）：每次雲端快照把 holdings.js 推上 main 就接著跑。
流程：NASDAQ Trader 官方名單（美股普通股，排除 ETF/權證/特別股/SPAC）→ yfinance 日線 → 流動性門檻
→ 阿紘的價格規則（距 26 週高點回檔 ≥ 20%）→ 通過的才抓財報 → 用交易系統的基本面判定 → 排序。
排序：基本面通過 > 警示 > 排除 > 資料不足；同級依「回檔 ÷ 波動率」越負越前面。
財報快取在 data/fundamentals_cache.json（7 天內不重抓），避免每天打幾百次 Yahoo。
"""
import concurrent.futures
import json
import math
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.fundamentals import FundRules, evaluate, fetch_quarterly, load_partnerships, load_profiles  # noqa: E402
from utils.scoring import WEIGHTS, score_fundamental, score_flow, score_price  # noqa: E402
from utils.trading_system import Rules, read_positions, scan_symbol  # noqa: E402

OUT = ROOT / "data" / "screener.json"
CACHE = ROOT / "data" / "fundamentals_cache.json"
FLOW_CACHE = ROOT / "data" / "flow_cache.json"
HISTORY = ROOT / "data" / "score_history.json"
MIN_PRICE = 3.0              # 股價下限
MIN_DOLLAR_VOL = 5e6         # 近 50 日平均成交額下限（US$）
MIN_HISTORY = 250            # 至少一年日線（排除剛上市、財報不足的）
FUND_TTL_DAYS = 7
FLOW_TTL_DAYS = 3
FLOW_TOP = 80                # 只對預評分前 80 名抓分析師／內部人／空單／財報日（每檔要多打幾次 Yahoo）
MAX_FUND_FETCH = 1200        # 單日最多抓幾檔財報（大盤大跌時訊號暴增，按最超跌的優先）
TOP_N = 100                  # 每個類型（成長型／成熟型）輸出最多幾檔候選
LISTS = [("https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt", "Symbol"),
         ("https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt", "ACT Symbol")]
_NON_COMMON = re.compile(r"\b(warrants?|rights?|units?|preferred|notes?|debentures?|acquisition corp\w*|blank check|trust preferred)\b", re.I)


def clean(x):
    if isinstance(x, float):
        return None if (math.isnan(x) or math.isinf(x)) else x
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    return x


def load_universe() -> dict:
    """{代號: 公司名}。美股普通股（含 ADR），排除 ETF、Test Issue、權證/權利/Units/特別股/債券/SPAC。"""
    out = {}
    for url, symcol in LISTS:
        text = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8", "ignore")
        lines = [l for l in text.strip().splitlines() if l.strip()]
        header = lines[0].split("|")
        si, ni, ei, ti = header.index(symcol), header.index("Security Name"), header.index("ETF"), header.index("Test Issue")
        for line in lines[1:]:
            parts = line.split("|")
            if len(parts) <= max(si, ni, ei, ti):
                continue
            sym, name = parts[si].strip(), parts[ni].strip()
            if not sym or parts[ei].strip() == "Y" or parts[ti].strip() == "Y" or "$" in sym or "File Creation" in line:
                continue
            if _NON_COMMON.search(name):
                continue
            name = name.split(" - ")[0].strip()
            name = re.sub(r"\s+(Class [A-Z]\s+)?(Common Stock|Ordinary Shares?|American Depositary (Shares|Receipts?)|Common Shares|Shares of Beneficial Interest|Capital Stock).*$", "", name, flags=re.I)
            out[sym.replace(".", "-")] = name.strip()
    if len(out) < 2000:
        raise RuntimeError(f"股票名單異常：只有 {len(out)} 檔")
    return out


def download_chunk(tickers, tries=2):
    import yfinance as yf
    for k in range(tries):
        try:
            raw = yf.download(tickers, period="2y", auto_adjust=True, progress=False, threads=True)
            if raw is not None and not raw.empty:
                return raw
        except Exception:
            pass
        time.sleep(3)
    return None


def _std(xs):
    if len(xs) < 3:
        return None
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def stab_metrics(vals):
    """止跌跡象：近 10 日報酬、離近 20 日低點的反彈幅度、近 10 日 / 近 60 日波動比。"""
    out = {"r10": None, "bounce20": None, "vol_ratio": None}
    if len(vals) >= 61:
        out["r10"] = vals[-1] / vals[-11] - 1
        out["bounce20"] = vals[-1] / min(vals[-20:]) - 1
        rets = [vals[i] / vals[i - 1] - 1 for i in range(len(vals) - 60, len(vals))]
        v10, v60 = _std(rets[-10:]), _std(rets)
        if v10 is not None and v60:
            out["vol_ratio"] = v10 / v60
    return out


def scan_prices(universe: dict, rules: Rules, held: set):
    """回傳 (候選 dict 列表, 統計)。候選＝通過流動性門檻且進入進場區、尚未持有。"""
    syms = sorted(universe)
    stats = {"universe": len(syms), "with_data": 0, "liquid": 0, "in_zone": 0, "held_in_zone": 0, "failed_chunks": 0}
    cands = []
    for i in range(0, len(syms), 150):
        chunk = syms[i:i + 150]
        raw = download_chunk(chunk)
        if raw is None:
            stats["failed_chunks"] += 1
            continue
        close = raw["Close"] if "Close" in raw else None
        vol = raw["Volume"] if "Volume" in raw else None
        if close is None:
            continue
        if not hasattr(close, "columns"):
            close = close.to_frame(chunk[0])
            vol = vol.to_frame(chunk[0])
        for sym in close.columns:
            ser = close[sym].dropna()
            if len(ser) < MIN_HISTORY:
                continue
            stats["with_data"] += 1
            last = float(ser.iloc[-1])
            dv = float((close[sym] * vol[sym]).dropna().iloc[-50:].mean()) if vol is not None and sym in vol.columns else 0.0
            if last < MIN_PRICE or not dv or dv < MIN_DOLLAR_VOL:
                continue
            stats["liquid"] += 1
            sc = scan_symbol([float(x) for x in ser.values], rules)
            if not sc or not sc["進場區"]:
                continue
            if sym in held:
                stats["held_in_zone"] += 1
                continue
            stats["in_zone"] += 1
            vals = [float(x) for x in ser.values]
            cands.append({"stab": stab_metrics(vals), "rev_ttm": None, "symbol": sym, "name": universe.get(sym, sym), "price": last, "high_ref": sc["區間高點"], "dd": sc["距高點"],
                          "vol": sc["年化波動率"], "dd_vol": sc["回檔/波動率"], "dollar_vol": dv,
                          "spark": [round(float(x), 2) for x in ser.iloc[-60:].values], "last_date": str(ser.index[-1].date())})
        print(f"  價格 {min(i + 150, len(syms))}/{len(syms)}，候選累計 {len(cands)}", flush=True)
    return cands, stats


def fetch_flow(sym):
    """分析師升降評（30 天）、內部人買賣（90 天）、空單比例、下次財報日。每項獨立 try，取不到就略過。"""
    import yfinance as yf
    import pandas as pd
    t = yf.Ticker(sym)
    out = {}
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    try:
        ud = t.upgrades_downgrades
        if ud is not None and len(ud):
            idx = pd.to_datetime(ud.index).tz_localize(None) if getattr(ud.index, "tz", None) is not None else pd.to_datetime(ud.index)
            rec = ud[idx >= now - pd.Timedelta(days=30)]
            act = rec["Action"].astype(str).str.lower() if "Action" in rec.columns else []
            out["up30"] = int((act == "up").sum()) if len(rec) else 0
            out["down30"] = int((act == "down").sum()) if len(rec) else 0
    except Exception:
        pass
    try:
        it = t.insider_transactions
        if it is not None and len(it):
            dcol = "Start Date" if "Start Date" in it.columns else it.columns[0]
            d = pd.to_datetime(it[dcol], errors="coerce")
            rec = it[d >= now - pd.Timedelta(days=90)]
            txt = (rec["Transaction"] if "Transaction" in rec.columns else rec.get("Text", pd.Series([], dtype=str))).astype(str).str.lower()
            out["insider_buy"] = int(txt.str.contains("purchase").sum())
            out["insider_sell"] = int(txt.str.contains("sale").sum())
    except Exception:
        pass
    try:
        sp = (t.info or {}).get("shortPercentOfFloat")
        if sp is not None:
            out["short_pct"] = float(sp)
    except Exception:
        pass
    try:
        cal = t.calendar
        ed = cal.get("Earnings Date") if isinstance(cal, dict) else None
        if ed:
            days = [(pd.Timestamp(x).tz_localize(None) - now).days for x in ed]
            days = [x for x in days if x >= -1]
            if days:
                out["earnings_days"] = int(min(days))
    except Exception:
        pass
    return out


def get_flows(symbols, today):
    cache = {}
    if FLOW_CACHE.exists():
        try:
            cache = json.loads(FLOW_CACHE.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    need = [x for x in symbols if not (x in cache and (today - date.fromisoformat(cache[x]["asof"])).days <= FLOW_TTL_DAYS)]

    def one(sym):
        try:
            d = fetch_flow(sym)
        except Exception:
            d = {}
        time.sleep(0.3)
        return sym, d

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for sym, d in ex.map(one, need):
            cache[sym] = {"asof": str(today), "data": d}
    keep = {k: v for k, v in cache.items() if (today - date.fromisoformat(v["asof"])).days <= 14}
    FLOW_CACHE.write_text(json.dumps(clean(keep), ensure_ascii=False), encoding="utf-8")
    return {x: cache[x]["data"] for x in symbols if x in cache}


def get_fundamentals(cands, today):
    cache = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    need = []
    for c in cands:
        e = cache.get(c["symbol"])
        if not (e and e.get("data") and (today - date.fromisoformat(e["asof"])).days <= FUND_TTL_DAYS):
            need.append(c["symbol"])
    need = need[:MAX_FUND_FETCH]

    def one(sym):
        try:
            d = fetch_quarterly(sym)
        except Exception:
            d = {}
        time.sleep(0.2)
        return sym, d

    failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        for k, (sym, d) in enumerate(ex.map(one, need), 1):
            if d:
                cache[sym] = {"asof": str(today), "data": d}
            else:
                failed += 1
            if k % 100 == 0:
                print(f"  財報 {k}/{len(need)}", flush=True)
    keep = {s: v for s, v in cache.items() if (today - date.fromisoformat(v["asof"])).days <= 60}
    CACHE.write_text(json.dumps(clean(keep), ensure_ascii=False), encoding="utf-8")
    return cache, len(need), failed


def main():
    rules, frules = Rules(), FundRules()
    profiles, partners = load_profiles(), load_partnerships()
    held = {p["symbol"] for p in read_positions() if not p.get("type")}
    today = date.today()
    prev = set()
    if OUT.exists():
        try:
            prev = {c["symbol"] for c in json.loads(OUT.read_text(encoding="utf-8")).get("candidates", [])}
        except ValueError:
            prev = set()
    universe = load_universe()
    print(f"名單 {len(universe)} 檔", flush=True)
    cands, stats = scan_prices(universe, rules, held)
    if stats["with_data"] < 1000:
        raise RuntimeError(f"價格資料太少（{stats['with_data']} 檔），不更新結果：{stats}")
    cands.sort(key=lambda c: (c["dd_vol"] or 0))          # 最超跌的先抓財報
    cache, n_fetch, n_failed = get_fundamentals(cands, today)
    order = {"通過": 0, "警示": 1, "排除": 2, "資料不足": 3}
    counts = {"通過": 0, "警示": 0, "排除": 0, "資料不足": 0}
    for c in cands:
        ent = cache.get(c["symbol"])
        prof = profiles.get(c["symbol"], {})
        if ent and ent.get("data"):
            e = evaluate(ent["data"], partners.get(c["symbol"]), frules, prof.get("type"))
            m = dict(e["metrics"])
            if m.get("可撐月數") == float("inf"):
                m["不燒錢"] = True
            keep = {k: m.get(k) for k in ("營收年增率", "毛利率", "毛利率(一年前)", "營業利益率", "營業利益率(一年前)", "可撐月數", "不燒錢",
                                           "年化股本稀釋", "近3季季增為正")}
            rev = [x for x in (ent["data"].get("rev") or [])[-4:] if x is not None]
            c["rev_ttm"] = sum(rev) if len(rev) == 4 else None
            c.update(verdict=e["verdict"], kind=e["kind"], track=e["track"], reasons=e["reasons"], notes=e["notes"], metrics=keep,
                     partners=[p.get("partner") for p in e["partners"] if p.get("strength", "高") in ("高", "中")], fund_asof=ent["asof"])
        else:
            c.update(verdict="資料不足", kind=prof.get("type", "-"), track="-", reasons=["Yahoo 沒有回財報"], notes=[], metrics={}, partners=[], fund_asof=None)
        counts[c["verdict"]] += 1
        # 基本面、價格兩個面向（不需要額外網路）
        a, aw = score_fundamental(c)
        b, bw = score_price(c)
        c["pillars"] = {"基本面": a, "價格": b}
        c["why"] = {"基本面": aw, "價格": bw}
        c["pre"] = WEIGHTS["基本面"] * a + WEIGHTS["價格"] * b + (WEIGHTS["預期資金"] + WEIGHTS["消息"]) * 50
    # 預期與資金：只對預評分前 FLOW_TOP 名抓（分析師、內部人、空單、財報日）
    top = sorted(cands, key=lambda c: -c["pre"])[:FLOW_TOP]
    flows = get_flows([c["symbol"] for c in top], today)
    for c in cands:
        fl = flows.get(c["symbol"])
        f_score, fw = score_flow(fl)
        c["pillars"]["預期資金"] = f_score
        c["why"]["預期資金"] = fw
        c["earnings_days"] = (fl or {}).get("earnings_days")
        c["veto"] = "基本面排除" if c["verdict"] == "排除" else None
        # 量化分數：消息面先給中性 50，頁面再把雲端排程的新聞評分合併進去
        c["quant_score"] = round(WEIGHTS["基本面"] * c["pillars"]["基本面"] + WEIGHTS["價格"] * c["pillars"]["價格"]
                                 + WEIGHTS["預期資金"] * f_score + WEIGHTS["消息"] * 50, 1)
        c.pop("pre", None)
        amt = rules.tranches_ntd[0]
        p1 = c["price"]
        c["plan"] = {"首批股數": int(amt / rules.usd_twd / p1), "首批NT$": amt, "第2批價": round(p1 * (1 - rules.add_step), 2),
                     "第3批價": round(p1 * (1 - rules.add_step) ** 2, 2), "止損價": round(p1 * (1 - rules.stop_from_first), 2)}
        c["is_new"] = c["symbol"] not in prev
    cands.sort(key=lambda c: (c["veto"] is not None, -c["quant_score"]))
    by_kind = {}
    for c in cands:
        by_kind.setdefault(c["kind"], []).append(c)
    kept = [c for k, lst in by_kind.items() for c in lst[:(TOP_N if k in ("成長型", "成熟型") else 30)]]
    kept.sort(key=lambda c: (c["veto"] is not None, -c["quant_score"]))
    kind_counts = {k: {v: sum(1 for c in lst if c["verdict"] == v) for v in order} for k, lst in by_kind.items()}
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "price_date": max((c["last_date"] for c in cands), default=None),
           "weights": WEIGHTS,
           "filters": {"最低股價": MIN_PRICE, "最低日均成交額US$": MIN_DOLLAR_VOL, "最少日線數": MIN_HISTORY, "進場回檔": rules.entry_drop,
                       "參考高點交易日": rules.high_window},
           "stats": {**stats, "fund_fetched": n_fetch, "fund_failed": n_failed, "verdicts": counts, "by_kind": kind_counts,
                     "capped": len(kept) < len(cands)},
           "candidates": kept}
    OUT.write_text(json.dumps(clean(out), ensure_ascii=False, indent=1), encoding="utf-8")
    # 逐日記錄前 30 名的量化分數與價格，之後用實際報酬檢驗分數有沒有用
    hist = []
    if HISTORY.exists():
        try:
            hist = json.loads(HISTORY.read_text(encoding="utf-8"))
        except ValueError:
            hist = []
    hist = [h for h in hist if h.get("date") != out["price_date"]]
    hist.append({"date": out["price_date"], "top": [{"symbol": c["symbol"], "kind": c["kind"], "price": round(c["price"], 2), "score": c["quant_score"]}
                                                    for c in kept if c["veto"] is None][:30]})
    HISTORY.write_text(json.dumps(clean(hist[-400:]), ensure_ascii=False), encoding="utf-8")
    print(f"完成：進場區候選 {len(cands)} 檔（輸出 {len(kept)}），基本面 {counts}", flush=True)


if __name__ == "__main__":
    main()
