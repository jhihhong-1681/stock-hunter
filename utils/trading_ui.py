"""交易系統頁的視覺元件：CSS、燈號、價格尺、迷你走勢、卡片。純字串，不依賴 streamlit 以外的東西。

顏色：股價漲跌照台股慣例（紅漲綠跌）；判定燈號用中性色（通過=藍、警示=琥珀、排除=紫、不足=灰），避免跟「紅=好」混淆。
"""
from __future__ import annotations

import html
import math

CSS = """
<style>
.tcard{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);border-left:4px solid rgba(255,255,255,0.18);
 border-radius:12px;padding:14px 16px 12px 16px;margin-bottom:14px;}
.tcard.stop{border-left-color:#ff7043;background:rgba(255,112,67,0.07);}
.tcard.near{border-left-color:#f5a623;background:rgba(245,166,35,0.06);}
.tcard.add,.tcard.entry{border-left-color:#5aa9ff;background:rgba(90,169,255,0.06);}
.tcard .th{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;}
.tcard .sym{font-size:1.25rem;font-weight:700;letter-spacing:.02em;}
.tcard .nm{font-size:.82rem;color:rgba(250,250,250,.55);}
.tcard .stats{display:flex;gap:18px;align-items:flex-end;margin:4px 0 2px 0;}
.tcard .st .l{font-size:.68rem;color:rgba(250,250,250,.5);letter-spacing:.04em;white-space:nowrap;}
.tcard .st .v{font-size:1.02rem;font-weight:700;white-space:nowrap;}
.tcard .st .big{font-size:1.5rem;line-height:1.15;}
.tcard .st.sp{margin-left:auto;}
.tcard .facts{display:flex;gap:14px;flex-wrap:wrap;font-size:.8rem;color:rgba(250,250,250,.62);margin-top:6px;}
.tcard .hint{font-size:.9rem;margin-top:8px;line-height:1.5;}
.tcard .why{font-size:.78rem;color:rgba(250,250,250,.5);margin-top:4px;line-height:1.45;}
.tcard .title{font-weight:700;font-size:1.02rem;margin-bottom:4px;}
.tcard .detail{font-size:.88rem;color:rgba(250,250,250,.78);line-height:1.5;}
.b{display:inline-block;padding:1px 9px;border-radius:999px;font-size:.74rem;font-weight:600;border:1px solid transparent;white-space:nowrap;}
.b-ok{color:#7ec0ff;background:rgba(90,169,255,.14);border-color:rgba(90,169,255,.35);}
.b-warn{color:#ffc560;background:rgba(245,166,35,.14);border-color:rgba(245,166,35,.35);}
.b-bad{color:#d3a8ff;background:rgba(178,122,255,.14);border-color:rgba(178,122,255,.35);}
.b-na{color:rgba(250,250,250,.6);background:rgba(255,255,255,.07);border-color:rgba(255,255,255,.15);}
.b-kind{color:rgba(250,250,250,.7);background:rgba(255,255,255,.06);border-color:rgba(255,255,255,.12);}
.up{color:#ff5a5f;} .down{color:#26c281;} .flat{color:rgba(250,250,250,.6);}
.ruler{position:relative;height:22px;margin:8px 6px 2px 6px;}
.ruler .track{position:absolute;left:0;right:0;top:7px;height:8px;border-radius:4px;background:rgba(255,255,255,.10);overflow:hidden;}
.ruler .danger{position:absolute;top:0;bottom:0;left:0;background:linear-gradient(90deg,rgba(255,112,67,.65),rgba(255,112,67,.25));}
.ruler .tick{position:absolute;top:3px;width:3px;height:16px;border-radius:1.5px;transform:translateX(-1.5px);}
.ruler .now{position:absolute;top:3px;width:14px;height:14px;border-radius:50%;background:#fff;border:2px solid #0e1117;transform:translateX(-7px);box-shadow:0 0 0 2px rgba(255,255,255,.55);}
.legend{display:flex;gap:12px;flex-wrap:wrap;font-size:.72rem;color:rgba(250,250,250,.62);margin:0 0 2px 2px;}
.legend i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px;vertical-align:baseline;}
.kpi{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);border-radius:12px;padding:12px 16px;}
.kpi .k{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:rgba(250,250,250,.5);}
.kpi .v{font-size:1.6rem;font-weight:700;line-height:1.25;}
.kpi .s{font-size:.78rem;color:rgba(250,250,250,.55);}
.banner{border-radius:12px;padding:14px 18px;font-size:1.05rem;font-weight:700;margin:6px 0 12px 0;}
.banner.ok{background:rgba(90,169,255,.12);border:1px solid rgba(90,169,255,.4);}
.banner.no{background:rgba(255,112,67,.10);border:1px solid rgba(255,112,67,.4);}
.chk{display:flex;gap:10px;padding:7px 4px;border-bottom:1px solid rgba(255,255,255,.07);font-size:.93rem;}
.chk .ic{width:1.6em;text-align:center;}
.chk .nm{font-weight:600;flex:0 0 17em;}
.chk .dt{color:rgba(250,250,250,.7);flex:1;}
.b-new{color:#0e1117;background:#ffd666;border-color:#ffd666;}
.plan{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;}
.plan span{font-size:.78rem;padding:3px 9px;border-radius:8px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);}
.plan b{font-weight:700;}
.empty{padding:26px;text-align:center;color:rgba(250,250,250,.55);border:1px dashed rgba(255,255,255,.18);border-radius:12px;}
</style>
"""


def esc(x) -> str:
    return html.escape(str(x))


def verdict_badge(v: str | None) -> str:
    v = v or "資料不足"
    cls = {"通過": "b-ok", "警示": "b-warn", "排除": "b-bad"}.get(v, "b-na")
    icon = {"通過": "✅ ", "警示": "⚠️ ", "排除": "⛔ "}.get(v, "")
    return f'<span class="b {cls}">{icon}基本面{esc(v)}</span>' if v in ("通過", "警示", "排除") else f'<span class="b b-na">基本面{esc(v)}</span>'


def kind_badge(t: str | None) -> str:
    return f'<span class="b b-kind">{esc(t)}</span>' if t and t != "-" else ""


def signed(x, digits=1, suffix="%", scale=100) -> str:
    """台股慣例：紅漲綠跌。"""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return '<span class="flat">-</span>'
    v = x * scale
    cls = "up" if v > 0 else "down" if v < 0 else "flat"
    return f'<span class="{cls}">{v:+.{digits}f}{suffix}</span>'


def sparkline(vals: list[float], w=96, h=28) -> str:
    if not vals or len(vals) < 3:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * (w - 2) / (len(vals) - 1) + 1:.1f},{h - 2 - (v - lo) / span * (h - 4):.1f}" for i, v in enumerate(vals))
    col = "#ff5a5f" if vals[-1] >= vals[0] else "#26c281"
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><polyline fill="none" stroke="{col}" stroke-width="1.6" points="{pts}"/></svg>'


def ruler(price: float, stop: float, first: float, next_add: float | None = None, reentry: float | None = None) -> str:
    """價格尺（對數刻度）：只畫標記（止損價/首批價/下一批加碼價/再進場價）與現價白點，數值放在下方圖例，避免標籤重疊。
    止損價以下是橘色危險區。"""
    marks = [("止損價", stop, "#ff7043"), ("首批價", first, "#9aa0a6")]
    if next_add:
        marks.append(("下一批加碼", next_add, "#5aa9ff"))
    if reentry and price <= stop:
        marks.append(("再進場", reentry, "#b27aff"))
    vals = [v for v in [m[1] for m in marks] + [price] if v and v > 0]
    lo, hi = min(vals) * 0.85, max(vals) * 1.08
    pos = lambda v: max(1.0, min(99.0, (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo)) * 100))
    out = [f'<div class="ruler"><div class="track"><div class="danger" style="width:{pos(stop):.1f}%"></div></div>']
    for _, v, col in marks:
        out.append(f'<div class="tick" style="left:{pos(v):.1f}%;background:{col}"></div>')
    out.append(f'<div class="now" style="left:{pos(price):.1f}%"></div></div>')
    out.append('<div class="legend">' + "".join(f'<span><i style="background:{col}"></i>{name} ${v:g}</span>' for name, v, col in sorted(marks, key=lambda m: m[1]))
               + '</div>')
    return "".join(out)


def kpi(label: str, value: str, sub: str = "") -> str:
    return f'<div class="kpi"><div class="k">{esc(label)}</div><div class="v">{value}</div><div class="s">{esc(sub)}</div></div>'


def card_hint(p: dict, verdict: str | None, n_batches: int) -> str:
    """卡片上的一句話（比 JSON 裡的 對照 精簡，再進場價已在價格尺圖例裡）。"""
    if p["已觸發止損"]:
        tail = "基本面仍通過，到再進場價可開新一輪" if verdict == "通過" else f"基本面{verdict}，再進場前先確認" if verdict in ("警示", "排除") else ""
        return "⛔ 已觸發止損，規則：出清" + (f"　·　{tail}" if tail else "")
    if verdict == "排除":
        return "基本面排除：不再加碼"
    if n_batches > 3:
        return "批數已超過 3 批（舊部位），不再加碼" + ("　·　基本面警示" if verdict == "警示" else "")
    if verdict == "警示":
        return "基本面警示：加碼前先複查"
    return "可依規則加碼" if p.get("下一批加碼價") else ""


def holding_card(s: dict) -> str:
    p = s["position"]
    n = p["已買批數"]
    state = "stop" if p["已觸發止損"] else "near" if p["距止損價"] <= 0.15 else ""
    batches = f"已買 {n} 批" + ("（舊部位）" if n > 3 else " / 最多 3 批")
    why = "；".join((s.get("reasons") or [])[:2]) or "；".join(s.get("notes") or [])
    hint = card_hint(p, s.get("verdict"), n)
    return (f'<div class="tcard {state}"><div class="th"><span class="sym">{esc(s["symbol"])}</span><span class="nm">{esc(s["name"])}</span>'
            f'{kind_badge(s.get("type"))}{verdict_badge(s.get("verdict"))}</div>'
            f'<div class="stats"><div class="st"><div class="l">現價</div><div class="v big">${p["現價"]:g}</div></div>'
            f'<div class="st"><div class="l">距首批價</div><div class="v">{signed(p["距首批價"], 0)}</div></div>'
            f'<div class="st"><div class="l">帳面報酬</div><div class="v">{signed(p.get("報酬率"), 1, "%", 1)}</div></div>'
            f'<div class="st sp">{sparkline(s.get("spark") or [])}</div></div>'
            + ruler(p["現價"], p["止損價"], p["首批價"], p.get("下一批加碼價"), p.get("止損後再進場價"))
            + (f'<div class="hint">{esc(hint)}</div>' if hint else "")
            + (f'<div class="why">{esc(why)}</div>' if why else "")
            + f'<div class="facts"><span>首批價 ${p["首批價"]:g}</span><span>{esc(batches)}</span><span>市值 NT${p["現值NT$"]:,}</span></div></div>')


def action_card(a: dict, verdict: str | None = None) -> str:
    icon = {"stop": "⛔", "near": "⚠️", "add": "➕", "entry": "🎯"}.get(a["kind"], "")
    badge = verdict_badge(verdict) if verdict else ""
    return (f'<div class="tcard {a["kind"]}"><div class="title">{icon} {esc(a["title"])} {badge}</div>'
            f'<div class="detail">{esc(a["detail"])}</div></div>')


def check_row(ok, name: str, detail: str) -> str:
    ic = "✅" if ok is True else "❌" if ok is False else "ℹ️" if ok == "note" else "❓"
    return f'<div class="chk"><div class="ic">{ic}</div><div class="nm">{esc(name)}</div><div class="dt">{esc(detail)}</div></div>'


def candidate_card(c: dict) -> str:
    """選股雷達的候選卡：價格訊號、基本面燈號、關鍵財務數字、依規則算出的進場計畫。"""
    m = c.get("metrics") or {}
    pl = c.get("plan") or {}
    why = "；".join((c.get("reasons") or [])[:2]) or "；".join((c.get("notes") or [])[:1])
    facts = []
    if m.get("營收年增率") is not None:
        facts.append(f'營收年增 {signed(m["營收年增率"], 0)}')
    if m.get("毛利率") is not None:
        facts.append(f'毛利率 {m["毛利率"]:.0%}')
    if m.get("營業利益率") is not None:
        facts.append(f'營業利益率 {m["營業利益率"]:.0%}')
    if c.get("track") == "成長虧損型":      # 現金可撐月數只對虧損中的公司有意義
        if m.get("不燒錢"):
            facts.append("不燒錢")
        elif m.get("可撐月數") is not None:
            facts.append(f'現金可撐 {m["可撐月數"]:.0f} 個月')
    elif c.get("track") == "已獲利型":
        facts.append("已獲利")
    if m.get("年化股本稀釋") is not None and m["年化股本稀釋"] > 0.05:
        facts.append(f'稀釋 {m["年化股本稀釋"]:+.0%}/年')
    if c.get("partners"):
        facts.append("巨頭合作：" + "、".join(c["partners"]))
    new = '<span class="b b-new">NEW</span>' if c.get("is_new") else ""
    dv = c.get("dollar_vol") or 0
    return (f'<div class="tcard entry"><div class="th"><span class="sym">{esc(c["symbol"])}</span><span class="nm">{esc(c.get("name", ""))}</span>'
            f'{kind_badge(c.get("kind"))}{verdict_badge(c.get("verdict"))}{new}</div>'
            f'<div class="stats"><div class="st"><div class="l">現價</div><div class="v big">${c["price"]:.2f}</div></div>'
            f'<div class="st"><div class="l">距 26 週高點</div><div class="v">{signed(c["dd"], 0)}</div></div>'
            f'<div class="st"><div class="l">年化波動率</div><div class="v">{c["vol"]:.0%}</div></div>'
            f'<div class="st"><div class="l">回檔÷波動率</div><div class="v">{(c.get("dd_vol") or 0):.1f}</div></div>'
            f'<div class="st sp">{sparkline(c.get("spark") or [])}</div></div>'
            + (f'<div class="facts">{"　·　".join(facts)}</div>' if facts else "")
            + (f'<div class="plan"><span>首批 NT${pl.get("首批NT$", 0):,} ≈ <b>{pl.get("首批股數", 0)}</b> 股</span>'
               f'<span>第 2 批 <b>${pl.get("第2批價", 0):g}</b></span><span>第 3 批 <b>${pl.get("第3批價", 0):g}</b></span>'
               f'<span style="border-color:rgba(255,112,67,.5)">止損 <b>${pl.get("止損價", 0):g}</b></span>'
               f'<span>日均成交 ${dv / 1e6:.0f}M</span></div>' if pl else "")
            + (f'<div class="why">{esc(why)}</div>' if why else "") + '</div>')
