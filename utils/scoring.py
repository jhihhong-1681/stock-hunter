"""選股評分（0–100）。四個面向加權，每個面向的得分與理由都攤開給阿紘看，不是黑箱。

權重（阿紘 2026-10-22 定）：基本面品質 40、價格位置與止跌 35、預期與資金 5、消息催化 20。
- 基本面品質：成長（年增率、加速）、獲利（毛利率/營業利益率的水準與趨勢）、體質（現金可撐、稀釋）；
  判定「警示」封頂 65 分、「排除」封頂 25 分。
- 價格位置與止跌：回檔 ÷ 波動率（超跌程度），加上止跌跡象（離近期低點反彈、近 10 日不再跳水、波動收斂）。
- 預期與資金：分析師升降評、內部人買賣、空單比例（Yahoo，客觀資料；取不到就中性 50）。
- 消息催化：雲端排程每日對前 20 名做新聞評分（data/news_scores.json，−10 ~ +10 → 0–100）；沒評到就中性 50 並標「未評」。
紅線（一票否決、排到最後）：基本面「排除」、新聞掃描發現 going concern／大量稀釋性增資／SEC 調查等（news 的 veto）。
財報日只標示，不扣分。

分數是判斷出來的權重，無法用歷史財報與新聞回測；data/score_history.json 會逐日記錄前幾名，之後用實際報酬檢驗。
純函式，不依賴網路。
"""
from __future__ import annotations

WEIGHTS = {"基本面": 0.40, "價格": 0.35, "預期資金": 0.05, "消息": 0.20}


def lin(x, pts):
    """分段線性插值；pts = [(x0, y0), (x1, y1), ...]，x 遞增；超出範圍取端點。"""
    if x is None:
        return None
    if x <= pts[0][0]:
        return float(pts[0][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return float(pts[-1][1])


def _avg(items):
    """items = [(score, weight)]，略過 None，權重重新正規化。"""
    ok = [(s, w) for s, w in items if s is not None]
    if not ok:
        return None
    tw = sum(w for _, w in ok)
    return sum(s * w for s, w in ok) / tw


# ── 基本面品質 ────────────────────────────────────────────
def score_fundamental(c: dict) -> tuple[float, list[str]]:
    """c：選股候選（verdict, kind, track, metrics{營收年增率, 毛利率, 毛利率(一年前), 營業利益率, 營業利益率(一年前),
    可撐月數, 不燒錢, 年化股本稀釋, 近3季季增為正}）。回傳 (0–100, 理由)。"""
    m = c.get("metrics") or {}
    kind, track, verdict = c.get("kind"), c.get("track"), c.get("verdict")
    why = []
    yoy = m.get("營收年增率")
    if kind == "成長型":
        g = lin(yoy, [(-0.2, 0), (0, 10), (0.25, 35), (0.4, 55), (0.6, 75), (1.0, 92), (2.0, 100)])
    else:
        g = lin(yoy, [(-0.15, 0), (0, 35), (0.05, 55), (0.12, 75), (0.25, 92), (0.4, 100)])
    seq = m.get("近3季季增為正")
    if g is not None and seq is not None:
        g = max(0.0, min(100.0, g + 4 * (seq - 1)))
    ttm = c.get("rev_ttm")
    if g is not None and ttm is not None and yoy is not None and yoy > 0.4:
        if ttm < 5e7:
            g *= 0.6     # 小基期的高成長可信度低（授權收入、剛開始商業化）
            why.append(f"營收規模小（近四季 US${ttm / 1e6:.0f}M），成長率打折")
        elif ttm < 2e8:
            g *= 0.85
    if yoy is not None:
        why.append(f"營收年增 {yoy:+.0%}" + ("（連續季增）" if seq == 3 else ""))
    om, om_old, gm, gm_old = m.get("營業利益率"), m.get("營業利益率(一年前)"), m.get("毛利率"), m.get("毛利率(一年前)")
    om_s = lin(om, [(-1.0, 0), (-0.3, 25), (0, 45), (0.1, 70), (0.2, 88), (0.35, 100)])
    gm_s = lin(gm, [(0, 0), (0.2, 35), (0.4, 65), (0.6, 90), (0.8, 100)])
    trends = [lin(a - b, [(-0.1, 0), (0, 50), (0.1, 100)]) for a, b in ((om, om_old), (gm, gm_old)) if a is not None and b is not None]
    trend_s = sum(trends) / len(trends) if trends else None
    p = _avg([(om_s, 0.35), (gm_s, 0.25), (trend_s, 0.40)])
    if gm is not None:
        why.append(f"毛利率 {gm:.0%}" + (f"（較一年前 {gm - gm_old:+.0%}）" if gm_old is not None else ""))
    if om is not None and om_old is not None and om > om_old:
        why.append("營業利益率改善" if om > 0 else "虧損在收斂")
    # 體質
    if track == "成長虧損型":
        runway = 100.0 if m.get("不燒錢") else lin(m.get("可撐月數"), [(0, 0), (12, 20), (24, 70), (36, 100)])
        if m.get("可撐月數") is not None and not m.get("不燒錢"):
            why.append(f"現金可撐 {m['可撐月數']:.0f} 個月")
    else:
        runway = 85.0 if track == "已獲利型" else None
    dil = m.get("年化股本稀釋")
    dil_s = lin(dil, [(0, 100), (0.05, 90), (0.15, 60), (0.3, 25), (0.6, 0)]) if dil is not None else None
    if dil is not None and dil > 0.1:
        why.append(f"股本稀釋 {dil:+.0%}/年")
    safe = _avg([(runway, 0.6), (dil_s, 0.4)])
    score = _avg([(g, 0.4), (p, 0.3), (safe, 0.3)])
    if score is None:
        score = 30.0
        why.append("財報資料不足")
    if c.get("sector") == "Financial Services":
        score = min(score, 60.0)     # 銀行、保險、房貸、信託：營收含投資收益，年增率與毛利率不可比
        why.append("金融股：營收與毛利率不可比，基本面分數保守（封頂 60）")
    if verdict == "警示":
        score = min(score, 65.0)
    elif verdict == "排除":
        score = min(score, 25.0)
    elif verdict == "資料不足":
        score = min(score, 30.0)
    return round(score, 1), why


# ── 價格位置與止跌 ────────────────────────────────────────
def score_price(c: dict) -> tuple[float, list[str]]:
    why = []
    dv = c.get("dd_vol")
    depth = lin(-dv if dv is not None else None, [(0.2, 5), (0.5, 25), (0.8, 50), (1.1, 75), (1.5, 95), (2.0, 100)])   # dd_vol 為負值，越負越超跌
    if c.get("dd") is not None:
        why.append(f"距 26 週高點 {c['dd']:+.0%}（約 {abs(dv or 0):.1f} 倍波動）")
    st = c.get("stab") or {}
    bounce = lin(st.get("bounce20"), [(0, 10), (0.03, 45), (0.08, 80), (0.15, 90), (0.3, 60), (0.6, 30)])
    r10 = lin(st.get("r10"), [(-0.15, 0), (-0.05, 35), (0, 60), (0.05, 85), (0.15, 70)])
    vr = lin(st.get("vol_ratio"), [(0.5, 100), (0.9, 70), (1.3, 40), (2.0, 10)])
    stab = _avg([(bounce, 0.45), (r10, 0.35), (vr, 0.20)])
    if st.get("bounce20") is not None:
        why.append(f"離 20 日低點 {st['bounce20']:+.0%}" + ("（仍在探底）" if st["bounce20"] < 0.02 else "（有止跌跡象）" if st["bounce20"] >= 0.05 else ""))
    score = _avg([(depth, 0.55), (stab, 0.45)])
    return round(score if score is not None else 30.0, 1), why


# ── 預期與資金 ────────────────────────────────────────────
def score_flow(flow: dict | None) -> tuple[float, list[str]]:
    """flow：{up30, down30, insider_buy, insider_sell, short_pct}；沒有資料就中性 50。"""
    if not flow:
        return 50.0, []
    s, why = 50.0, []
    up, down = flow.get("up30") or 0, flow.get("down30") or 0
    if up or down:
        s += max(-25, min(25, 10 * (up - down)))
        why.append(f"分析師近 30 天 升評 {up}／降評 {down}")
    ib, isell = flow.get("insider_buy") or 0, flow.get("insider_sell") or 0
    if ib > 0:
        s += 15
        why.append(f"內部人近 90 天買進 {ib} 筆")
    elif isell >= 3:
        s -= 10
        why.append(f"內部人近 90 天賣出 {isell} 筆")
    sp = flow.get("short_pct")
    if sp is not None and sp > 0.15:
        s -= 10 if sp > 0.25 else 5
        why.append(f"空單比例 {sp:.0%}")
    return round(max(0.0, min(100.0, s)), 1), why


# ── 消息催化 ──────────────────────────────────────────────
def score_news(news: dict | None) -> tuple[float, list[str], str | None]:
    """news：{score: −10~+10, summary, veto}。回傳 (0–100, 理由, 否決理由)；沒評到就中性 50。"""
    if not news:
        return 50.0, ["消息面未評"], None
    veto = news.get("veto")
    sc = news.get("score")
    pct = 50.0 if sc is None else max(0.0, min(100.0, (sc + 10) * 5))
    why = [news["summary"]] if news.get("summary") else []
    return (0.0 if veto else round(pct, 1)), why, veto


def total_score(pillars: dict) -> float:
    return round(sum(WEIGHTS[k] * pillars[k] for k in WEIGHTS), 1)


def label(score: float) -> str:
    return "很強" if score >= 80 else "不錯" if score >= 65 else "普通" if score >= 50 else "偏弱"
