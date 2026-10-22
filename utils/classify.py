"""成長型／成熟型的自動分類（選股雷達裡沒登記過的標的用）。

阿紘的標準：市佔、增長、市值、規模。其中市佔沒有可靠的免費資料，用「市值＋營收規模＋產業」當代理；
已登記在 data/company_profiles.json 的標的以登記為準（那裡可以手動標龍頭）。

做法：算「成長分」與「成熟分」，成長分 − 成熟分 ≥ 1 才是成長型。
- 成長分：營收年增率（≥100% +4、≥40% +3、≥25% +2、≥15% +1、<0 −1）、連續 3 季季增 +1、虧損中但年增 ≥25% +1。
- 成熟分：市值（≥$500 億 +3、≥$100 億 +2、≥$30 億 +1）、近四季營收（≥$100 億 +2、≥$50 億 +1、<$2 億 −1）、
  防禦型產業（公用事業、必需消費、不動產）+1。
靠近分界的（把握度低）沿用前一次的分類，避免同一檔每天在兩種類型之間跳動。
純函式，不依賴網路。
"""
from __future__ import annotations

DEFENSIVE = {"Utilities", "Consumer Defensive", "Real Estate"}


def classify(yoy, seq, track, rev_ttm, mcap, sector, prev: str | None = None) -> dict:
    g, m, why = 0, 0, []
    if yoy is not None:
        g += 4 if yoy >= 1.0 else 3 if yoy >= 0.4 else 2 if yoy >= 0.25 else 1 if yoy >= 0.15 else -1 if yoy < 0 else 0
        why.append(f"營收年增 {yoy:+.0%}")
        if track == "成長虧損型" and yoy >= 0.25:
            g += 1
    if seq == 3:
        g += 1
    if rev_ttm is not None and rev_ttm < 2e7 and (mcap or 0) >= 3e8:
        g += 3          # 幾乎還沒有營收但已有市值（估值靠未來）：成長型
        why.append("尚無實質營收")
    if mcap:
        m += 3 if mcap >= 50e9 else 2 if mcap >= 10e9 else 1 if mcap >= 3e9 else 0
        why.append(f"市值 ${mcap / 1e9:.0f}B" if mcap >= 1e9 else f"市值 ${mcap / 1e6:.0f}M")
    if rev_ttm:
        m += 2 if rev_ttm >= 10e9 else 1 if rev_ttm >= 5e9 else -1 if rev_ttm < 2e8 else 0
        why.append(f"近四季營收 ${rev_ttm / 1e9:.1f}B" if rev_ttm >= 1e9 else f"近四季營收 ${rev_ttm / 1e6:.0f}M")
    if sector in DEFENSIVE:
        m += 1
    net = g - m
    kind = "成長型" if net >= 1 else "成熟型"
    gap = abs(net - 0.5)
    conf = "高" if gap >= 3 else "中" if gap >= 1.5 else "低"
    if mcap is None or yoy is None:
        conf = "低"
    if conf == "低" and prev in ("成長型", "成熟型"):
        kind = prev
        why.append("靠近分界，沿用前次分類")
    return {"kind": kind, "confidence": conf, "growth_pts": g, "maturity_pts": m, "why": "、".join(why)}
