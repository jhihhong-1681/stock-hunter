"""每日抓持有期權的收盤成交價 → data/option_prices.json。

給 SNAPSHOT_TASK.md 第 3 步用：阿紘沒更新 Sheet 期權現值的日子，快照改用這裡抓到的成交價。
讀 portfolio-calendar/holdings.js 的期權部位（name 例如 "XOM 12/18/26 170 Call"），
用 yfinance 查該到期日的 option chain，取成交價 lastPrice（跟 TradingView 一致）；
最後成交太舊（超過 3 個日曆天）或沒成交價時退回買賣中間值並標 stale。
抓不到的（已到期、找不到合約）標 error，快照會沿用 Sheet 的數字。
只在 GitHub Actions 跑（雲端 Claude 連不到 Yahoo）。
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "option_prices.json"
KEEP_DAYS = 30
NAME_RE = re.compile(r"^(?P<sym>[A-Z.]+)\s+(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{2,4})\s+(?P<k>[\d.]+)\s+(?P<cp>C|P)", re.I)


def load_option_positions():
    src = (ROOT / "portfolio-calendar" / "holdings.js").read_text(encoding="utf8")
    body = src[src.index("window.HOLDINGS") :]
    body = body[body.index("{") :].rstrip().rstrip(";")
    body = re.sub(r"(\{|,)\s*([A-Za-z_]\w*)\s*:", r'\1 "\2":', body)   # 裸 key 補引號
    data = json.loads(body)
    return [p for p in data["positions"] if p.get("type") == "option"], data.get("asOf")


def parse(name):
    m = NAME_RE.match(name.strip())
    if not m:
        return None
    y = int(m["y"])
    y = y + 2000 if y < 100 else y
    return m["sym"].upper(), date(y, int(m["m"]), int(m["d"])), float(m["k"]), m["cp"].upper()


def main():
    import yfinance as yf
    import pandas as pd

    now_et = datetime.now(ZoneInfo("America/New_York"))
    asof = now_et.date()
    if now_et.hour < 16:               # 還沒收盤（手動觸發）就算前一天
        asof -= timedelta(days=1)
    while asof.weekday() >= 5:
        asof -= timedelta(days=1)

    positions, holdings_asof = load_option_positions()
    chains, result = {}, {}
    for p in positions:
        key = f"{p['symbol']}|{p['name']}"
        parsed = parse(p["name"])
        if not parsed:
            result[key] = {"error": "名稱解析失敗"}
            continue
        sym, exp, strike, cp = parsed
        if exp < asof:
            result[key] = {"error": "已到期"}
            continue
        try:
            ck = (sym, exp)
            if ck not in chains:
                tk = yf.Ticker(sym)
                if exp.isoformat() not in (tk.options or ()):
                    chains[ck] = None
                else:
                    ch = tk.option_chain(exp.isoformat())
                    chains[ck] = (ch.calls, ch.puts)
            if chains[ck] is None:
                result[key] = {"error": "找不到該到期日"}
                continue
            df = chains[ck][0 if cp == "C" else 1]
            row = df[(df["strike"] - strike).abs() < 1e-6]
            if row.empty:
                result[key] = {"error": "找不到履約價"}
                continue
            r = row.iloc[0]
            last = float(r["lastPrice"]) if pd.notna(r["lastPrice"]) else 0.0
            bid = float(r["bid"]) if pd.notna(r["bid"]) else 0.0
            ask = float(r["ask"]) if pd.notna(r["ask"]) else 0.0
            mid = round((bid + ask) / 2, 4) if bid > 0 and ask > 0 else None
            ltd = r.get("lastTradeDate")
            last_trade = pd.Timestamp(ltd).strftime("%Y-%m-%d") if ltd is not None and pd.notna(ltd) else None
            fresh = last_trade is not None and (asof - date.fromisoformat(last_trade)).days <= 3
            if last > 0 and fresh:
                price, source = last, "last"
            elif mid is not None:
                price, source = mid, "mid"
            elif last > 0:
                price, source = last, "last_stale"
            else:
                result[key] = {"error": "沒有報價"}
                continue
            result[key] = {"price": round(price, 4), "source": source, "last": last or None, "bid": bid or None,
                           "ask": ask or None, "lastTrade": last_trade, "stale": source != "last"}
        except Exception as e:  # noqa: BLE001
            result[key] = {"error": f"{type(e).__name__}: {str(e)[:80]}"}

    ok = sum(1 for v in result.values() if "price" in v)
    print(f"asof {asof}: {ok}/{len(result)} 檔取得報價")
    for k, v in result.items():
        print(" ", k, v)
    if ok == 0:
        print("全部失敗，不寫檔")
        sys.exit(1)

    old = json.loads(OUT.read_text(encoding="utf8")) if OUT.exists() else {}
    by_date = old.get("by_date", {})
    by_date[asof.isoformat()] = result
    cutoff = (asof - timedelta(days=KEEP_DAYS)).isoformat()
    by_date = {d: v for d, v in sorted(by_date.items()) if d >= cutoff}
    out = {"generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"), "asof": asof.isoformat(),
           "note": "價格＝每股權利金（USD），來源 yfinance；source: last=成交價, mid=買賣中間值, last_stale=成交價但已過時", "by_date": by_date}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf8")


if __name__ == "__main__":
    main()
