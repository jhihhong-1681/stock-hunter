"""交易系統的基本面濾網（v0）。優先看成長與獲利，其次財務體質，不看估值。

先分「公司類型」，再看「獲利狀態」：
- 成長型 / 成熟型：由市值、市佔、規模、產業判斷（data/company_profiles.json，人工+研究維護，附理由）。
  成長型的營收年增率至少要 40%（min_rev_yoy_growth）；成熟型只要求營收沒有衰退、利益率沒有惡化。
  沒有登記的標的，用營收年增率自動推定（≥25% 當成長型）並在備註註明。
- 獲利狀態：近四季營業利益 > 0 = 已獲利型；≤ 0 = 成長虧損型（不因為虧損排除，
  改看毛利率水位與趨勢、虧損有沒有收斂、現金還能撐多久、股本稀釋速度）。

巨頭合作（data/partnerships.json，人工維護、每筆附出處）：不是財報數字，作用是
「現金撐不夠久」這類財務體質問題可以從「排除」降一級成「警示」。

判定：通過 / 警示 / 排除。所有門檻在 FundRules，頁面側邊欄可調。
純函式部分（evaluate）不依賴網路；fetch_quarterly 才用 yfinance。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PARTNERS_FILE = Path(__file__).resolve().parent.parent / "data" / "partnerships.json"
PROFILES_FILE = Path(__file__).resolve().parent.parent / "data" / "company_profiles.json"


@dataclass
class FundRules:
    min_rev_yoy_growth: float = 0.40     # 成長型：營收年增率至少多少（阿紘定：至少 40%）
    min_gross_margin: float = 0.20       # 成長虧損型：毛利率至少多少（毛利率太低的成長不值錢）
    margin_drop_warn: float = 0.05       # 毛利率或營業利益率比一年前掉超過這個幅度 → 警示
    runway_pass_months: float = 24.0     # 現金撐得過這麼久 → 沒問題
    runway_exclude_months: float = 12.0  # 低於這個 → 排除（有巨頭合作則降成警示）
    max_annual_dilution: float = 0.30    # 年化股本稀釋超過這個 → 警示
    max_debt_to_cash: float = 2.0        # 總負債 / 現金超過這個 → 警示


def load_partnerships(path: Path = PARTNERS_FILE) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, list)}


def load_profiles(path: Path = PROFILES_FILE) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, dict)}


def _ratio(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def _yoy(series: list, k: int = 0):
    """series 由舊到新；k=0 是最新一季相對 4 季前。資料不足回 None。"""
    n = len(series)
    i, j = n - 1 - k, n - 5 - k
    if j < 0:
        return None
    return _ratio(series[i], series[j]) - 1 if _ratio(series[i], series[j]) is not None else None


def quality_flags(d: dict, m: dict, track: str, yoy) -> list[str]:
    """獲利品質與趨勢的「提示」：只寫進 metrics 與 notes（前綴 ⚠），不影響通過／警示／排除，也不影響評分。
    1. 單季營收年增率 vs 前幾季：避免單一季度（基期、交付時點）決定整家公司的印象。
    2. 賺錢但自由現金流為負：營業利益為正不代表現金真的進帳。
    3. 應收帳款成長遠快於營收：可能是營收品質問題（賒銷、收款變慢）。
    資料不足就不提示，不猜。"""
    out = []
    rev, fcf, ar = d.get("rev") or [], d.get("fcf") or [], d.get("ar") or []
    ys = [y for y in (_yoy(rev, k) for k in range(4)) if y is not None]    # 最新在前
    if len(ys) >= 2:
        m["近4季營收年增率"] = ys
        others = ys[1:]
        avg_prev = sum(others) / len(others)
        if yoy is not None and yoy - avg_prev > 0.40:
            out.append(f"⚠ 最新一季營收年增率 {yoy:+.0%} 遠高於前幾季平均 {avg_prev:+.0%}，可能是單季異常（交付時點、低基期），別只看最新一季")
        elif yoy is not None and avg_prev - yoy > 0.40:
            out.append(f"⚠ 營收年增率從前幾季平均 {avg_prev:+.0%} 放緩到 {yoy:+.0%}")
    vals = [x for x in fcf[-4:] if x is not None]
    if len(vals) >= 3:
        ttm_fcf = sum(vals) * 4 / len(vals)        # 缺一季就按比例放大
        m["近四季自由現金流"] = ttm_fcf
        if track == "已獲利型" and ttm_fcf < 0:
            out.append(f"⚠ 帳上獲利但近四季自由現金流為負（約 {ttm_fcf / 1e6:,.0f}M 美元），獲利品質待確認")
    if len(ar) >= 5 and len(rev) >= 5 and ar[-1] and ar[-5] and rev[-1] and rev[-5]:
        ar_g, rev_g = ar[-1] / ar[-5] - 1, rev[-1] / rev[-5] - 1
        m["應收帳款年增率"] = ar_g
        if ar_g > 0.30 and ar_g - rev_g > 0.30:
            out.append(f"⚠ 應收帳款年增 {ar_g:+.0%}，遠快於營收年增 {rev_g:+.0%}，留意收款變慢或營收品質")
    return out


def evaluate(d: dict, partners: list | None, r: FundRules, kind: str | None = None) -> dict:
    """kind：「成長型」/「成熟型」，None = 由營收年增率自動推定。
    d：由舊到新的季度序列（缺值為 None）。
    rev, gross, opinc, fcf, shares（各 list），cash, debt（最新一季數字），dates（季末日 list）。
    回傳 {track, verdict, metrics, reasons(扣分原因), notes}。"""
    rev, gross, opinc = d.get("rev") or [], d.get("gross") or [], d.get("opinc") or []
    fcf, shares = d.get("fcf") or [], d.get("shares") or []
    cash, debt = d.get("cash"), d.get("debt")
    m, reasons, notes = {}, [], []

    if len(rev) < 4 or all(x is None for x in rev):
        return {"track": "-", "kind": kind or "-", "verdict": "資料不足", "metrics": m, "reasons": ["財報資料不足（少於 4 季營收）"], "notes": notes,
                "partners": partners or []}

    ttm_op = sum(x for x in opinc[-4:] if x is not None) if opinc else None
    track = "已獲利型" if (ttm_op is not None and ttm_op > 0) else "成長虧損型"

    # 成長
    yoy = _yoy(rev)
    yoy_prev = _yoy(rev, 1)
    m["營收年增率"] = yoy
    m["營收年增率(前一季)"] = yoy_prev
    seq = [_ratio(rev[i], rev[i - 1]) for i in range(len(rev) - 3, len(rev)) if i > 0]
    m["近3季季增為正"] = sum(1 for x in seq if x is not None and x > 1)
    # 毛利率 / 營業利益率
    gm = _ratio(gross[-1], rev[-1]) if gross and rev else None
    gm_old = _ratio(gross[-5], rev[-5]) if len(gross) >= 5 and len(rev) >= 5 else (_ratio(gross[0], rev[0]) if gross else None)
    om = _ratio(opinc[-1], rev[-1]) if opinc else None
    om_old = _ratio(opinc[-5], rev[-5]) if len(opinc) >= 5 and len(rev) >= 5 else (_ratio(opinc[0], rev[0]) if opinc else None)
    m["毛利率"], m["毛利率(一年前)"], m["營業利益率"], m["營業利益率(一年前)"] = gm, gm_old, om, om_old
    # 財務體質
    burn = None
    if fcf and any(x is not None for x in fcf[-2:]):
        vals = [x for x in fcf[-2:] if x is not None]
        burn = -sum(vals) / len(vals) if sum(vals) < 0 else 0.0   # 每季燒錢（正數 = 燒）
    runway = None
    if cash is not None:
        runway = float("inf") if burn == 0 else (cash / burn * 3 if burn else None)
    m["每季燒錢"], m["現金"], m["可撐月數"] = burn, cash, runway
    m["負債/現金"] = _ratio(debt, cash) if debt else 0.0 if cash else None
    dil = None
    pts = [(i, x) for i, x in enumerate(shares) if x]       # 季度報表的股數常有缺值：取最早與最新的有效值
    if len(pts) >= 2 and pts[-1][0] > pts[0][0]:
        qs = pts[-1][0] - pts[0][0]
        dil = (pts[-1][1] / pts[0][1]) ** (4 / qs) - 1
    m["年化股本稀釋"] = dil

    # 只採計實質程度「高/中」的合作；「低」（產品整合、意向、路徑）不算保障
    partners_ok = [p for p in (partners or []) if p.get("strength", "高") in ("高", "中")]
    has_partner = bool(partners_ok)
    level = 0  # 0 通過 / 1 警示 / 2 排除

    def bump(to, text):
        nonlocal level
        level = max(level, to)
        reasons.append(text)

    auto = kind is None
    if auto:
        kind = "成長型" if (yoy is not None and yoy >= 0.25) else "成熟型"
        notes.append(f"類型為自動推定（{kind}），建議在 company_profiles.json 登記")

    if kind == "成長型":
        if yoy is None:
            bump(1, "營收年增率算不出來（不足 5 季）")
        elif yoy < 0:
            bump(2, f"成長型但營收年增率為負（{yoy:+.0%}），成長故事不成立")
        elif yoy < r.min_rev_yoy_growth:
            bump(1, f"成長型營收年增率只有 {yoy:+.0%}，低於 {r.min_rev_yoy_growth:.0%}")
        if track == "成長虧損型":
            if gm is not None and gm < r.min_gross_margin:
                bump(1, f"毛利率只有 {gm:.0%}，低於 {r.min_gross_margin:.0%}")
            if gm is not None and gm_old is not None and gm_old - gm > r.margin_drop_warn:
                bump(1, f"毛利率比一年前掉 {(gm_old - gm) * 100:.0f} 個百分點")
            if om is not None and om_old is not None and om < om_old - r.margin_drop_warn and om < 0:
                bump(1, "虧損擴大（營業利益率比一年前更差）")
            elif om is not None and om_old is not None and om > om_old:
                notes.append("虧損在收斂（營業利益率比一年前改善）")
        elif om is not None and om_old is not None and om_old - om > r.margin_drop_warn:
            bump(1, f"營業利益率比一年前掉 {(om_old - om) * 100:.0f} 個百分點")
    else:
        if yoy is not None and yoy < 0:
            bump(1, f"營收年增率轉負（{yoy:+.0%}）")
        if yoy is not None and yoy_prev is not None and yoy < 0 and yoy_prev < 0:
            bump(2, "營收年增率連兩季為負")
        if track == "成長虧損型":
            bump(1, "成熟型公司卻還在虧損")
        if om is not None and om_old is not None and om_old - om > r.margin_drop_warn:
            bump(1, f"營業利益率比一年前掉 {(om_old - om) * 100:.0f} 個百分點")

    # 財務體質（兩軌共用）
    # 現金可撐月數只用在營業利益為負的公司；賺錢的公司單季自由現金流為負（訴訟付款、營運資金時間差）不代表撐不住
    if track == "成長虧損型" and runway is not None and runway != float("inf"):
        if runway < r.runway_exclude_months:
            if has_partner:
                bump(1, f"現金只夠撐約 {runway:.0f} 個月（有巨頭合作，降為警示）")
            else:
                bump(2, f"現金只夠撐約 {runway:.0f} 個月，又沒有巨頭合作背書")
        elif runway < r.runway_pass_months:
            bump(1, f"現金約可撐 {runway:.0f} 個月，低於 {r.runway_pass_months:.0f} 個月")
    if dil is not None and dil > r.max_annual_dilution:
        bump(1, f"年化股本稀釋 {dil:.0%}")
    dc = m["負債/現金"]
    # 負債/現金只用在營業利益為負的公司：賺錢的公司（JLL、CAG 這類）本來就有債，用現金去比沒有意義
    if track == "成長虧損型" and dc is not None and dc > r.max_debt_to_cash and burn:
        bump(1, f"總負債是現金的 {dc:.1f} 倍")
    notes += quality_flags(d, m, track, yoy)
    if has_partner:
        notes.append("有巨頭合作：" + "、".join(p.get("partner", "?") for p in partners_ok))
    elif partners:
        notes.append("有合作但實質程度低，不採計：" + "、".join(p.get("partner", "?") for p in partners))
    return {"track": track, "kind": kind, "verdict": ["通過", "警示", "排除"][level], "metrics": m, "reasons": reasons,
            "notes": notes, "partners": partners or []}


# ── 抓資料（yfinance；雲端 Streamlit 才抓得到） ─────────────────
def _row(df, names):
    for n in names:
        if n in df.index:
            return [None if x != x else float(x) for x in df.loc[n].tolist()][::-1]  # 由舊到新
    return []


def _shares_series(t, n_points: int = 5):
    """由 get_shares_full 取近一年的流通股數，抽成 n_points 個約每季一點（由舊到新）。
    季度資產負債表常缺股數或只有 5 季，這條路徑較完整；取不到回 []。"""
    import pandas as pd
    try:
        start = (pd.Timestamp.now() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
        sf = t.get_shares_full(start=start)
    except Exception:
        return []
    if sf is None or len(sf) < 2:
        return []
    sf = sf.dropna()
    if getattr(sf.index, "tz", None) is not None:
        sf.index = sf.index.tz_localize(None)
    sf = sf.sort_index()
    end = sf.index[-1]
    out = []
    for k in range(n_points - 1, -1, -1):          # 最新、−90、−180、−270、−360 天；取「該時點之前最近一筆」
        target = end - pd.Timedelta(days=90 * k)
        pos = sf.index.searchsorted(target, side="right") - 1
        if pos < 0:
            if sf.index[0] - target > pd.Timedelta(days=45):    # 最舊的資料離目標太遠就放棄
                return []
            pos = 0
        out.append(float(sf.iloc[pos]))
    return out


def fetch_quarterly(symbol: str) -> dict:
    import yfinance as yf
    t = yf.Ticker(symbol)
    inc, bs, cf = t.quarterly_income_stmt, t.quarterly_balance_sheet, t.quarterly_cashflow
    if inc is None or inc.empty:
        return {}
    has_bs = bs is not None and not bs.empty
    has_cf = cf is not None and not cf.empty
    cash = _row(bs, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents", "Cash Financial"]) if has_bs else []
    debt = _row(bs, ["Total Debt", "Long Term Debt And Capital Lease Obligation", "Long Term Debt"]) if has_bs else []
    fcf = _row(cf, ["Free Cash Flow"]) if has_cf else []
    if has_cf and not any(x is not None for x in fcf[-2:]):
        # 沒有現成的自由現金流：營業現金流 + 資本支出（資本支出為負數）
        ocf = _row(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"])
        capex = _row(cf, ["Capital Expenditure", "Purchase Of PPE"])
        n = min(len(ocf), len(capex)) if capex else len(ocf)
        fcf = [(ocf[i] + (capex[i] or 0.0)) if ocf[i] is not None else None for i in range(len(ocf) - n, len(ocf))] if n else ocf
    ar = _row(bs, ["Accounts Receivable", "Receivables", "Gross Accounts Receivable"]) if has_bs else []
    shares = _shares_series(t)
    shares_src = "get_shares_full"
    if len(shares) < 2:
        shares = _row(bs, ["Ordinary Shares Number", "Share Issued"]) if has_bs else []
        shares_src = "balance_sheet"
    return {
        "v": 2,
        "dates": [str(c.date()) for c in inc.columns][::-1],
        "rev": _row(inc, ["Total Revenue", "Operating Revenue"]),
        "gross": _row(inc, ["Gross Profit"]),
        "opinc": _row(inc, ["Operating Income", "Total Operating Income As Reported"]),
        "fcf": fcf,
        "ar": ar,
        "shares": shares,
        "shares_src": shares_src,
        "cash": cash[-1] if cash else None,
        "debt": debt[-1] if debt else None,
    }
