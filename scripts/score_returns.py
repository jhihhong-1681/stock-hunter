"""評分驗證 → data/score_returns.json：用 data/score_history/ 的每日完整候選，補算後續 5／20／60／120 個交易日報酬，
比較各種評分版本（消融）：只有價格、只有基本面、價格＋基本面、完整（含預期資金）、完整＋新聞。

怎麼看：每個快照日、每個類型，把候選依該版本的分數分成 5 組，看「最高分組」vs「最低分組」後續超額報酬（對 SPY）的差距，
再跨日平均。另算分數與後續報酬的等級相關（IC）。樣本天數太少（< 10 個快照日）時結果不可靠，頁面會標示。
價格用快照日收盤價（= 訊號日）當起點；這裡只衡量分數的排序力，不含交易成本。
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from utils.score_history import load_all  # noqa: E402

OUT = ROOT / "data" / "score_returns.json"
HORIZONS = (5, 20, 60, 120)
VARIANTS = {
    "只有價格": lambda r: r["pr"],
    "只有基本面": lambda r: r["f"],
    "價格＋基本面": lambda r: (0.40 * r["f"] + 0.35 * r["pr"]) / 0.75 if r["f"] is not None and r["pr"] is not None else None,
    "完整（不含新聞）": lambda r: r["q"],
    "完整＋新聞": lambda r: (r["q"] + 0.20 * (r["news_pct"] - 50)) if r["q"] is not None else None,
}


def download(symbols):
    import yfinance as yf
    frames = []
    for i in range(0, len(symbols), 150):
        raw = yf.download(symbols[i:i + 150], period="2y", auto_adjust=True, progress=False, threads=True)
        if raw is None or raw.empty:
            continue
        c = raw["Close"]
        frames.append(c if hasattr(c, "columns") else c.to_frame(symbols[i]))
    return pd.concat(frames, axis=1).ffill() if frames else pd.DataFrame()


def main():
    docs = load_all()
    if not docs:
        print("還沒有歷史檔")
        return
    syms = sorted({c["s"] for d in docs for c in d["cands"]} | {"SPY"})
    px = download(syms)
    idx = [str(i.date()) for i in px.index]
    pos = {d: i for i, d in enumerate(idx)}
    rows = []
    for d in docs:
        if d["date"] not in pos:
            continue
        i0 = pos[d["date"]]
        for c in d["cands"]:
            if c["s"] not in px.columns:
                continue
            n = d.get("news", {}).get(c["s"])
            r = {**c, "date": d["date"], "news_pct": 50.0 if not n else (0.0 if n["veto"] else max(0.0, min(100.0, (n["score"] + 10) * 5))), "vt": c["vt"] or bool(n and n["veto"])}
            p0, s0 = px[c["s"]].iloc[i0], px["SPY"].iloc[i0]
            for h in HORIZONS:
                if i0 + h < len(px):
                    p1, s1 = px[c["s"]].iloc[i0 + h], px["SPY"].iloc[i0 + h]
                    r[f"r{h}"] = float(p1 / p0 - 1) if p0 == p0 and p1 == p1 else None
                    r[f"x{h}"] = r[f"r{h}"] - float(s1 / s0 - 1) if r[f"r{h}"] is not None else None
            rows.append(r)
    df = pd.DataFrame(rows)
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "snapshots": len(docs), "first": docs[0]["date"], "last": docs[-1]["date"],
           "rows": len(df), "horizons": {}}
    for h in HORIZONS:
        col = f"x{h}"
        res = {}
        if col not in df.columns:
            out["horizons"][str(h)] = {"snapshot_days": 0, "variants": {}}
            continue
        sub = df[df[col].notna()]
        res["snapshot_days"] = int(sub["date"].nunique())
        res["variants"] = {}
        for name, fn in VARIANTS.items():
            tops, bots, ics, wins = [], [], [], []
            for (_, kind), g in sub.groupby(["date", "k"]):
                g = g[~g["vt"]].copy()
                g["sc"] = [fn(r) for r in g.to_dict("records")]
                g = g[g["sc"].notna()]
                if len(g) < 10:
                    continue
                q = pd.qcut(g["sc"].rank(method="first"), 5, labels=False)
                tops.append(g.loc[q == 4, col].mean())
                bots.append(g.loc[q == 0, col].mean())
                wins.append((g.loc[q == 4, col] > 0).mean())
                ics.append(g["sc"].rank().corr(g[col].rank()))      # 等級相關（Spearman），不依賴 scipy
            if tops:
                res["variants"][name] = {"n_groups": len(tops), "top": float(np.nanmean(tops)), "bottom": float(np.nanmean(bots)),
                                         "spread": float(np.nanmean(tops) - np.nanmean(bots)), "top_win": float(np.nanmean(wins)), "ic": float(np.nanmean(ics))}
        out["horizons"][str(h)] = res
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完成：{len(docs)} 個快照日、{len(df)} 筆", flush=True)


if __name__ == "__main__":
    main()
