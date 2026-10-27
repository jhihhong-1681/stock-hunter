"""抓公開財務原始資料（SEC EDGAR XBRL + yfinance），給選股分類與基本面查核用。

為什麼要有這支：分類原本只靠 screener 的單季年增率，一次性收入（授權金、里程碑款、併購、口徑變動）會把成長灌高，
而雲端 Claude 連不到 SEC/Yahoo、只能靠搜尋摘要推論。這支跑在 GitHub Actions 上，直接抓原始數字：

- SEC EDGAR companyfacts：近 8 季單季營收／毛利／營業利益／淨利（Q4 由年度扣前三季推算並標示）、現金、營業現金流、流通股數。
- yfinance：同樣的季報（第二來源）、市值、股數、產業。
- 兩來源最新一季營收差 > 5% 會標 `cross_check.flag`。
- 衍生指標：各季年增率、最新一季佔近四季比重（spike > 0.4 疑似一次性）、成長是否靠單季暴衝。

輸出 data/company_facts.json。外國公司（20-F/6-K）SEC 沒有季度 XBRL，只有 yfinance 一個來源，會註明。
標的 = data/company_profiles.json 的代號 ∪ data/screener.json 的候選。
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "company_facts.json"
UA = {"User-Agent": "stock-hunter research 267276527+jhihhong-1681@users.noreply.github.com", "Accept-Encoding": "gzip, deflate"}

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
    "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueGoodsNet", "RevenuesNetOfInterestExpense",
]
FIELDS = {
    "revenue": REVENUE_TAGS,
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "op_cashflow": ["NetCashProvidedByUsedInOperatingActivities"],
}


def get_json(url, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 200:
                return r.json()
            print(f"  GET {url[-60:]} -> HTTP {r.status_code}", flush=True)
            if r.status_code in (403, 404):
                return None
        except requests.RequestException as e:
            print(f"  GET {url[-60:]} -> {type(e).__name__}", flush=True)
        time.sleep(1.5 * (i + 1))
    return None


def days(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def pick_series(facts, tags):
    """依 tag 優先順序取第一個有資料的 USD 序列。"""
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        units = gaap.get(tag, {}).get("units", {}).get("USD")
        if units:
            return tag, units
    return None, []


def quarterly_from_facts(units):
    """回傳 {季末日: {"value", "derived", "filed"}}：單季 80–100 天直接取，Q4 用年度 − 前三季（同財年）推算。"""
    q, annual = {}, []
    for u in units:
        if "start" not in u or "end" not in u:
            continue
        d = days(u["start"], u["end"])
        if 80 <= d <= 100:
            prev = q.get(u["end"])
            if not prev or u["filed"] > prev["filed"]:      # 同一季有重編／更正時取最新申報
                q[u["end"]] = {"value": u["val"], "derived": False, "filed": u["filed"]}
        elif 350 <= d <= 380 and u.get("form", "").startswith("10-K"):
            annual.append(u)
    for a in annual:
        ends = sorted(e for e in q if a["start"] < e < a["end"] and days(e, a["end"]) > 50)
        if a["end"] in q or len(ends) < 3:
            continue
        three = ends[-3:]
        if days(a["start"], three[0]) > 120:
            continue
        q[a["end"]] = {"value": a["val"] - sum(q[e]["value"] for e in three), "derived": True, "filed": a["filed"]}
    return q


def sec_block(cik, facts):
    out = {}
    for name, tags in FIELDS.items():
        tag, units = pick_series(facts, tags)
        if not units:
            continue
        q = quarterly_from_facts(units)
        out[name] = {"tag": tag, "q": {k: q[k] for k in sorted(q)[-9:]}}
    # 現金與流通股數（時點值）
    gaap = facts.get("facts", {}).get("us-gaap", {})
    for name, tag in (("cash", "CashAndCashEquivalentsAtCarryingValue"),):
        u = gaap.get(tag, {}).get("units", {}).get("USD")
        if u:
            last = max(u, key=lambda x: x["end"])
            out[name] = {"value": last["val"], "asof": last["end"]}
    sh = facts.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {}).get("units", {}).get("shares")
    if sh:
        last = max(sh, key=lambda x: x["end"])
        out["shares_outstanding"] = {"value": last["val"], "asof": last["end"]}
        hist = sorted({(x["end"], x["val"]) for x in sh})[-6:]
        out["shares_history"] = [{"asof": a, "value": v} for a, v in hist]
    return out


def yf_block(sym):
    import yfinance as yf
    import pandas as pd
    t = yf.Ticker(sym)
    out = {}
    try:
        df = t.quarterly_income_stmt
        if df is not None and not df.empty:
            rows = {"revenue": "Total Revenue", "gross_profit": "Gross Profit", "operating_income": "Operating Income", "net_income": "Net Income"}
            q = {}
            for col in sorted(df.columns)[-9:]:
                end = pd.Timestamp(col).strftime("%Y-%m-%d")
                q[end] = {}
                for k, r in rows.items():
                    if r in df.index and pd.notna(df.loc[r, col]):
                        q[end][k] = float(df.loc[r, col])
            out["q"] = q
    except Exception as e:  # noqa: BLE001
        out["q_error"] = str(e)[:120]
    info = {}
    for attempt in range(3):
        try:
            info = t.info or {}
        except Exception:  # noqa: BLE001
            info = {}
        if info.get("marketCap") or info.get("sector"):
            break
        time.sleep(1.5 * (attempt + 1))
    mc = info.get("marketCap")
    if not mc:
        try:
            mc = t.fast_info.get("marketCap")
        except Exception:  # noqa: BLE001
            mc = None
    out["market_cap"] = float(mc) if mc else None
    for k_out, k_in in (("shares_outstanding", "sharesOutstanding"), ("sector", "sector"), ("industry", "industry"),
                        ("total_cash", "totalCash"), ("total_debt", "totalDebt"), ("country", "country"),
                        ("quote_type", "quoteType")):
        if info.get(k_in) is not None:
            out[k_out] = info[k_in]
    return out


def derive(q_by_end):
    """由 {季末: 營收} 算近 4 季、各季年增、最新一季佔近四季比重（spike）。"""
    ends = sorted(q_by_end)
    if not ends:
        return {}
    vals = [q_by_end[e] for e in ends]
    d = {"quarters": [{"end": e, "revenue": q_by_end[e]} for e in ends[-8:]]}
    yoy = {}
    for e in ends:
        want = (date.fromisoformat(e) - timedelta(days=364))
        cands = [x for x in ends if abs((date.fromisoformat(x) - want).days) <= 15]
        if cands and q_by_end[cands[0]]:
            yoy[e] = round(q_by_end[e] / q_by_end[cands[0]] - 1, 4)
    d["yoy"] = {e: yoy[e] for e in sorted(yoy)[-6:]}
    if len(vals) >= 4:
        ttm = sum(vals[-4:])
        d["ttm_revenue"] = ttm
        d["latest_share_of_ttm"] = round(vals[-1] / ttm, 3) if ttm else None
        prior = vals[-5:-1] if len(vals) >= 5 else vals[:-1]
        if prior and sum(prior) > 0:
            d["latest_vs_prior_avg"] = round(vals[-1] / (sum(prior) / len(prior)), 2)
        d["seq_up_streak"] = _streak(vals)
        # 疑似一次性：最新一季超過前四季平均 2 倍，或單季佔近四季 > 40%
        d["spike_flag"] = bool((d.get("latest_vs_prior_avg") or 0) >= 2.0 or (d.get("latest_share_of_ttm") or 0) > 0.40)
    return d


def _streak(vals):
    n = 0
    for i in range(len(vals) - 1, 0, -1):
        if vals[i] > vals[i - 1]:
            n += 1
        else:
            break
    return n


def symbols():
    syms = []
    prof = ROOT / "data" / "company_profiles.json"
    if prof.exists():
        syms += [k for k in json.loads(prof.read_text(encoding="utf-8")) if not k.startswith("_")]
    scr = ROOT / "data" / "screener.json"
    if scr.exists():
        syms += [c["symbol"] for c in json.loads(scr.read_text(encoding="utf-8")).get("candidates", [])]
    seen, out = set(), []
    for s in syms:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def main():
    syms = symbols()
    print(f"標的 {len(syms)} 檔", flush=True)
    tick = get_json("https://www.sec.gov/files/company_tickers.json") or {}
    cik_of = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in tick.values()}
    print(f"SEC 代號表 {len(cik_of)} 筆", flush=True)

    result, stats = {}, {"sec_ok": 0, "sec_none": 0, "yf_ok": 0, "flagged": 0}
    for k, sym in enumerate(syms, 1):
        rec = {"symbol": sym}
        cik = cik_of.get(sym.upper().replace(".", "-")) or cik_of.get(sym.upper())
        if cik:
            facts = get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")
            time.sleep(0.15)                       # SEC 限 10 req/s
            if facts:
                rec["sec"] = {"cik": cik, "entity": facts.get("entityName"), **sec_block(cik, facts)}
                stats["sec_ok"] += 1
        if "sec" not in rec:
            rec["sec_note"] = "SEC 無季度 XBRL（外國公司／ETF／代號對不到）"
            stats["sec_none"] += 1
        try:
            rec["yf"] = yf_block(sym)
            if rec["yf"].get("q") or rec["yf"].get("market_cap"):
                stats["yf_ok"] += 1
        except Exception as e:  # noqa: BLE001
            rec["yf"] = {"error": str(e)[:120]}
        time.sleep(0.2)

        # 衍生指標：優先 SEC，否則 yfinance
        sec_rev = {e: v["value"] for e, v in rec.get("sec", {}).get("revenue", {}).get("q", {}).items()}
        yf_rev = {e: v["revenue"] for e, v in rec.get("yf", {}).get("q", {}).items() if "revenue" in v}
        src = "sec" if len(sec_rev) >= 5 else "yf"
        rec["derived"] = {"source": src, **derive(sec_rev if src == "sec" else yf_rev)}
        # 第二來源比對最新一季營收
        if sec_rev and yf_rev:
            e_sec = max(sec_rev)
            near = [e for e in yf_rev if abs((date.fromisoformat(e) - date.fromisoformat(e_sec)).days) <= 10]
            if near and sec_rev[e_sec]:
                diff = yf_rev[near[0]] / sec_rev[e_sec] - 1
                rec["cross_check"] = {"quarter": e_sec, "sec": sec_rev[e_sec], "yf": yf_rev[near[0]], "diff": round(diff, 4), "flag": abs(diff) > 0.05}
                if abs(diff) > 0.05:
                    stats["flagged"] += 1
        result[sym] = rec
        if k % 25 == 0:
            print(f"  {k}/{len(syms)}  {stats}", flush=True)

    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stats": stats,
               "說明": "SEC EDGAR XBRL + yfinance 原始季報。sec.revenue.q 的 derived=true 為年度扣前三季推算的 Q4。cross_check.flag=兩來源最新一季營收差>5%。derived.spike_flag=疑似一次性收入。",
               "companies": result}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=0), encoding="utf-8")
    print("完成", stats, flush=True)


if __name__ == "__main__":
    sys.exit(main())
