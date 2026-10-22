import importlib
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="交易系統 - 阿紘的股票儀表板", page_icon="🧭", layout="wide")
from utils.styles import load_css
load_css()

import utils.fundamentals as _fund_mod
import utils.option_parse as _parse_mod
import utils.trading_system as _ts_mod
import utils.trading_ui as _ui_mod
# Streamlit Cloud 部署新版後，行程裡的 utils 模組可能還是舊版快取，匯入新增的名稱會 ImportError；每次載入都重新載入
for _m in (_fund_mod, _parse_mod, _ts_mod, _ui_mod):
    importlib.reload(_m)
from utils.fundamentals import FundRules, evaluate, fetch_quarterly, load_partnerships, load_profiles
from utils.option_parse import parse_option_text
from utils.trading_system import OptionRules, Rules, backtest, check_option, entry_hint, read_positions, read_totals, summarize
from utils.trading_ui import CSS, action_card, check_row, holding_card, kpi

st.markdown(CSS, unsafe_allow_html=True)
ROOT = Path(__file__).resolve().parent.parent
SIG_FILE = ROOT / "data" / "trading_signals.json"
rules, orules, frules = Rules(), OptionRules(), FundRules()
USD_TWD = rules.usd_twd


@st.cache_data(ttl=600)
def load_signals(mtime: float) -> dict:
    return json.loads(SIG_FILE.read_text(encoding="utf-8"))


@st.cache_data(ttl=3600)
def load_closes(tickers: tuple, period: str) -> pd.DataFrame:
    raw = yf.download(list(tickers), period=period, auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        return pd.DataFrame()
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close.dropna(how="all")


@st.cache_data(ttl=3600 * 12)
def load_fund(sym: str) -> dict:
    try:
        return fetch_quarterly(sym)
    except Exception:
        return {}


st.title("🧭 交易系統")
if not SIG_FILE.exists():
    st.warning("還沒有計算結果（data/trading_signals.json）。每天快照推上後會自動產生；也可以到 GitHub Actions 手動執行 Compute Trading Signals。")
    st.stop()
sig = load_signals(SIG_FILE.stat().st_mtime)
stocks = sig["stocks"]
by_sym = {s["symbol"]: s for s in stocks}
held = [s for s in stocks if s.get("held")]
actions = sig["actions"]
st.caption(f"價格資料日期 {sig['price_date']}（前一個美股收盤）　·　每天雲端快照後自動更新　·　最後計算 {sig['generated'][:16].replace('T', ' ')} UTC")

n_stop = sum(1 for a in actions if a["kind"] == "stop")
n_near = sum(1 for a in actions if a["kind"] == "near")
n_entry = sum(1 for a in actions if a["kind"] == "entry")
n_add = sum(1 for a in actions if a["kind"] == "add")
c = st.columns(5)
c[0].markdown(kpi("正股檔數", f"{len(held)}", "目標 5–10 檔"), unsafe_allow_html=True)
c[1].markdown(kpi("已觸發止損", f'<span style="color:#ff7043">{n_stop}</span>' if n_stop else "0", "規則：出清"), unsafe_allow_html=True)
c[2].markdown(kpi("接近止損價", f"{n_near}", "距止損價 15% 內"), unsafe_allow_html=True)
c[3].markdown(kpi("可加碼／進場", f"{n_add} / {n_entry}", "加碼提示 / 進場候選"), unsafe_allow_html=True)
c[4].markdown(kpi("期權檔數", f"{len(sig['options'])}", "目標 5–10 檔，現有不處理"), unsafe_allow_html=True)
st.write("")

tab_today, tab_hold, tab_scan, tab_opt, tab_adv = st.tabs(["🎯 今日", "📋 持股", "🔍 掃描", "💹 期權檢查", "⚙️ 進階"])


def grid(cards: list, ncol: int = 2):
    cols = st.columns(ncol)
    for i, html_ in enumerate(cards):
        cols[i % ncol].markdown(html_, unsafe_allow_html=True)


# ── 今日 ─────────────────────────────────────────────────
with tab_today:
    if not actions:
        st.markdown('<div class="empty">今天沒有需要處理的動作 👌</div>', unsafe_allow_html=True)
    for title, kinds in [("需要處理", ("stop", "near")), ("加碼提示", ("add",)), ("進場候選（依優先序）", ("entry",))]:
        items = [a for a in actions if a["kind"] in kinds]
        if items:
            st.subheader(title)
            grid([action_card(a, by_sym.get(a["symbol"], {}).get("verdict")) for a in items], 2)
    st.caption("規則：距 52 週高點回檔 ≥ 20% 進場 → 金字塔三批 → 首批價再跌 50% 全出 → 止損價再跌 30% 且基本面沒大變就開新一輪。"
               "止盈由你自己判斷。進場優先序：基本面通過 > 跌幅更深。")

# ── 持股 ─────────────────────────────────────────────────
with tab_hold:
    def hold_key(s):
        p = s["position"]
        return (0 if p["已觸發止損"] else 1 if p["距止損價"] <= 0.15 else 2, -p["現值NT$"])

    st.markdown("**價格尺**：橘色區是止損價以下，白點是現價；標橘色的先處理。")
    grid([holding_card(s) for s in sorted(held, key=hold_key)], 2)
    opts = sig["options"]
    if opts:
        with st.expander(f"期權持倉（{len(opts)} 檔，提示用，現有部位不處理）"):
            otab = pd.DataFrame([{"合約": o["name"], "距到期(天)": o["dte"], "權利金損益": f"{o['pct']:+.1f}%",
                                  "狀態": "已達出場線（虧 60%）" if o["exit_hit"] else "2 天內到期" if (o["dte"] is not None and o["dte"] <= 2) else "",
                                  "現值NT$": o["value"]} for o in opts]).sort_values("距到期(天)")
            st.dataframe(otab, hide_index=True, use_container_width=True)

# ── 掃描 ─────────────────────────────────────────────────
with tab_scan:
    sc = [s for s in stocks if s.get("dd") is not None]
    vorder = {"通過": 0, "警示": 1, "排除": 2}
    sc.sort(key=lambda s: s["dd"])
    colors = []
    for s in sc:
        if not s["in_zone"]:
            colors.append("rgba(255,255,255,0.22)")
        else:
            colors.append({"通過": "#5aa9ff", "警示": "#f5a623", "排除": "#b27aff"}.get(s["verdict"], "#9aa0a6"))
    fig = go.Figure(go.Bar(
        y=[("★ " if s["held"] else "") + s["symbol"] for s in sc], x=[s["dd"] * 100 for s in sc], orientation="h", marker_color=colors,
        text=[f"{s['dd']:+.0%}" for s in sc], textposition="outside", cliponaxis=False,
        customdata=[[s["verdict"], s["vol"] * 100 if s.get("vol") else 0, (s.get("dd_vol") or 0)] for s in sc],
        hovertemplate="%{y}<br>距高點 %{x:.1f}%<br>基本面 %{customdata[0]}<br>年化波動率 %{customdata[1]:.0f}%<br>回檔/波動率 %{customdata[2]:.1f}<extra></extra>"))
    fig.add_vline(x=-rules.entry_drop * 100, line_dash="dash", line_color="#5aa9ff",
                  annotation_text=f"進場線 -{rules.entry_drop:.0%}", annotation_position="top")
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=max(360, 26 * len(sc) + 80),
                      margin=dict(l=10, r=40, t=30, b=10), xaxis=dict(title="距 52 週高點（%）", zeroline=False), yaxis=dict(autorange="reversed"),
                      showlegend=False)
    st.markdown("**距 52 週高點的回檔**　藍＝進場區且基本面通過、琥珀＝基本面警示、紫＝基本面排除、灰＝還沒到進場區　（★ 已持有）")
    st.plotly_chart(fig, use_container_width=True)
    zone = [s for s in sc if s["in_zone"]]
    zone.sort(key=lambda s: (s["held"], vorder.get(s["verdict"], 3), s["dd"]))   # 還沒持有的候選排前面
    cands = [s for s in zone if not s["held"]]
    rows, k = [], 0
    for s in zone:
        if not s["held"]:
            k += 1
        rows.append({"優先序": str(k) if not s["held"] else "", "代號": s["symbol"], "狀態": "已持有" if s["held"] else "候選",
                     "結論": "已持有（見「持股」分頁）" if s["held"] else entry_hint(True, s["verdict"]),
                     "距高點": f"{s['dd']:+.0%}", "年化波動率": f"{s['vol']:.0%}" if s.get("vol") else "-",
                     "回檔/波動率": f"{s['dd_vol']:.1f}" if s.get("dd_vol") else "-", "基本面": s["verdict"], "類型": s.get("type", "-"),
                     "主要原因": "；".join((s.get("reasons") or [])[:2]) or "-"})
    st.markdown(f"**進場候選 {len(cands)} 檔**（還沒持有、已進入進場區；優先序：基本面通過 > 跌幅更深）　·　已持有且在進場區 {len(zone) - len(cands)} 檔")
    if not cands:
        st.markdown(f'<div class="empty">目前沒有「還沒持有」的標的進入進場區。掃描範圍是自選股清單 + 目前持股，共 {len(sc)} 檔；想多看哪幾檔，把代號加進「自選股清單」頁。</div>',
                    unsafe_allow_html=True)
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("「回檔 ÷ 波動率」越負，代表相對這檔自己的波動越超跌；進場與否由你依波動率判斷，系統只給參考。")


# ── 期權檢查 ─────────────────────────────────────────────
def payoff_chart(kind, strike, prem, qty, spot):
    xs = np.linspace(spot * 0.5, spot * 1.8, 160)
    intrinsic = np.maximum(xs - strike, 0) if kind == "Call" else np.maximum(strike - xs, 0)
    pnl = (intrinsic - prem) * 100 * qty * USD_TWD
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=np.where(pnl >= 0, pnl, 0), fill="tozeroy", mode="none", fillcolor="rgba(255,90,95,0.30)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=np.where(pnl < 0, pnl, 0), fill="tozeroy", mode="none", fillcolor="rgba(38,194,129,0.30)", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=xs, y=pnl, mode="lines", line=dict(color="#fafafa", width=2),
                             hovertemplate="到期時股價 $%{x:.2f}<br>損益 NT$%{y:,.0f}<extra></extra>"))
    be = strike + prem if kind == "Call" else strike - prem
    fig.add_vline(x=spot, line_dash="dot", line_color="#9aa0a6", annotation_text=f"現價 ${spot:.2f}", annotation_position="top left")
    fig.add_vline(x=be, line_dash="dash", line_color="#5aa9ff", annotation_text=f"損益兩平 ${be:.2f}", annotation_position="top right")
    fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=300, showlegend=False,
                      margin=dict(l=10, r=10, t=30, b=10), xaxis_title="到期時的股價（US$）", yaxis_title="損益（NT$）")
    return fig


with tab_opt:
    st.markdown("把報牌的文字整段貼上來（英文、中文、或只有 `RIG270617C00004000` 這種代碼都可以），系統會自動解析並對照規則。")
    text = st.text_area("報牌內容", key="o_text", height=130, label_visibility="collapsed",
                        placeholder="例如：The symbol is RIG270617C00004000 ... Choose the $4 strike price ... Use a limit of $2.50")
    defaults = {"o_sym": "", "o_kind": "Call", "o_strike": 0.0, "o_exp": date.today() + timedelta(days=60), "o_prem": 0.0, "o_qty": 1}
    if text != st.session_state.get("o_parsed_text"):
        parsed = parse_option_text(text)
        for k, v in defaults.items():
            st.session_state[k] = v
        for k, pk in (("o_sym", "symbol"), ("o_kind", "kind"), ("o_strike", "strike"), ("o_exp", "expiry"), ("o_prem", "premium"), ("o_qty", "qty")):
            if parsed[pk] is not None:
                st.session_state[k] = parsed[pk]
        st.session_state["o_parsed_text"] = text
        st.session_state["o_missing"] = ([lab for lab, pk in (("標的", "symbol"), ("行使價", "strike"), ("到期日", "expiry"), ("限價", "premium"))
                                          if parsed[pk] is None] if text.strip() else [])
    missing = st.session_state.get("o_missing", [])
    with st.expander("解析結果（需要時修改）" + (f"　⚠️ 沒解析到：{'、'.join(missing)}" if missing else ""), expanded=bool(missing)):
        a1, a2, a3, a4, a5, a6 = st.columns(6)
        o_sym = a1.text_input("標的", key="o_sym").strip().upper()
        o_kind = a2.selectbox("類型", ["Call", "Put"], key="o_kind")
        o_strike = a3.number_input("行使價", 0.0, 100000.0, step=0.5, key="o_strike")
        o_exp = a4.date_input("到期日", key="o_exp")
        o_prem = a5.number_input("權利金（每股 US$）", 0.0, 10000.0, step=0.05, key="o_prem")
        o_qty = a6.number_input("口數", 1, 1000, key="o_qty")
        b1, b2 = st.columns(2)
        o_spot_m = b1.number_input("現價（解析或抓價失敗時才需要）", 0.0, 100000.0, 0.0, 0.5, key="o_spot")
        o_high_m = b2.number_input("52 週高點（同上）", 0.0, 100000.0, 0.0, 0.5, key="o_high")
    if o_sym and o_strike > 0 and o_prem > 0:
        known = by_sym.get(o_sym)
        spot, high52, verdict, why, src = o_spot_m or None, o_high_m or None, None, "", ""
        if known and known.get("price"):
            spot = spot or known["price"]
            high52 = high52 or known["high52"]
            verdict, why, src = known["verdict"], "；".join(known.get("reasons") or []), f"股價與基本面取自每日計算（{sig['price_date']} 收盤）"
        if spot is None or high52 is None:
            cl = load_closes((o_sym,), "2y")
            if not cl.empty and o_sym in cl.columns:
                ser = cl[o_sym].dropna()
                spot = spot or float(ser.iloc[-1])
                high52 = high52 or float(ser.iloc[-252:].max())
                src = "股價取自 Yahoo Finance"
        if verdict is None:
            d = load_fund(o_sym)
            if d:
                e = evaluate(d, load_partnerships().get(o_sym), frules, load_profiles().get(o_sym, {}).get("type"))
                verdict, why = e["verdict"], "；".join(e["reasons"])
            else:
                verdict = "資料不足"
        if spot is None:
            st.error("抓不到這檔的股價，請在上面「解析結果」裡手動填現價（和 52 週高點）。")
        else:
            tot = read_totals()
            opts_now = [p for p in read_positions() if p.get("type") == "option"]
            res = check_option(spot=spot, high52=high52, strike=o_strike, dte=(o_exp - date.today()).days, premium=o_prem, qty=int(o_qty),
                               total_assets=tot.get("totalAssets", 1), option_cost_now=sum(p["invested"] for p in opts_now),
                               option_names_now=len({p["symbol"] for p in opts_now}), is_new_name=o_sym not in {p["symbol"] for p in opts_now},
                               verdict=verdict, rules=rules, orules=orules, kind=o_kind)
            title = f"{o_sym} {o_exp:%m/%d/%y} ${o_strike:g} {o_kind} × {int(o_qty)}　限價 ${o_prem:g}"
            if res["pass"]:
                st.markdown(f'<div class="banner ok">✅ 符合進場規則　<span style="font-weight:400;font-size:.9rem">{title}</span></div>', unsafe_allow_html=True)
            else:
                bad = [c_[0] for c_ in res["checks"] if c_[1] is False]
                unk = [c_[0] for c_ in res["checks"] if c_[1] is None]
                msg = ("不符合：" + "、".join(bad)) if bad else ""
                msg += (("　" if msg else "") + "資料不足：" + "、".join(unk)) if unk else ""
                st.markdown(f'<div class="banner no">⚠️ 不完全符合　{msg}<br><span style="font-weight:400;font-size:.9rem">{title}</span></div>',
                            unsafe_allow_html=True)
            left, right = st.columns([1.15, 1])
            with left:
                st.markdown("".join(check_row(ok, n, d_) for n, ok, d_ in res["checks"]), unsafe_allow_html=True)
                st.caption(f"{src}　基本面：{verdict}" + (f"（{why}）" if why else ""))
            with right:
                i = res["info"]
                k1, k2 = st.columns(2)
                k1.markdown(kpi("成本（最大虧損）", f"NT${i['成本NT$']:,.0f}", f"占總資產 {i['占總資產']:.1%}" if i["占總資產"] else ""), unsafe_allow_html=True)
                k2.markdown(kpi("價外程度", i["價外程度"], f"損益兩平 ${i['損益兩平價']:.2f}（{i['損益兩平距現價']:+.1%}）"), unsafe_allow_html=True)
                st.write("")
                k3, k4 = st.columns(2)
                k3.markdown(kpi(f"出場權利金（虧 {orules.exit_loss:.0%}）", f"${i['出場權利金']:.2f}", "權利金跌到這裡就出場"), unsafe_allow_html=True)
                k4.markdown(kpi("現價 / 52 週高點", f"${spot:.2f}", f"{spot / high52 - 1:+.1%}" if high52 else ""), unsafe_allow_html=True)
            st.plotly_chart(payoff_chart(o_kind, o_strike, o_prem, int(o_qty), spot), use_container_width=True)
            st.caption("上圖是「到期當天」的損益：紅＝賺、綠＝賠（台股慣例）。到期前的損益還會受時間價值與波動率影響。")
    elif text.strip():
        st.info("至少需要標的、行使價和限價才能檢查，缺的請在上面「解析結果」補上。")

# ── 進階 ─────────────────────────────────────────────────
with tab_adv:
    t_rule, t_fund, t_hist, t_bt = st.tabs(["規則說明", "基本面明細", "歷史回測結果", "現場回測"])
    with t_rule:
        total = sum(rules.tranches_ntd)
        p_ = [1, 1 - rules.add_step, (1 - rules.add_step) ** 2]
        shares = sum(a / x for a, x in zip(rules.tranches_ntd, p_))
        max_loss = total - shares * (1 - rules.stop_from_first)
        st.markdown(f"""
**正股**
- **進場**：現價距 52 週高點回檔 ≥ {rules.entry_drop:.0%}（可依個股波動率自行判斷），買第 1 批 NT\\${rules.tranches_ntd[0]:,}。
- **加碼（最多 3 批，金字塔）**：第 2 批 NT\\${rules.tranches_ntd[1]:,}、第 3 批 NT\\${rules.tranches_ntd[2]:,}。下一批在「上一批價再跌 {rules.add_step:.0%}」，或「首批後上漲、再從高點回落 {rules.rebound_pullback:.0%}」時買。
- **止損**：現價 ≤ 首批買入價 × {1 - rules.stop_from_first:.0%}，全部出清。
- **止損後重新進場**：從止損價再跌 {rules.reentry_drop:.0%}，且基本面沒有太大改變，就當作新一輪。
- **止盈**：自己判斷。
- **單一標的最大虧損**（三批都買、跌到止損價）約 NT\\${max_loss:,.0f}（投入 NT\\${total:,} 的 {max_loss / total:.0%}）。
- **檔數目標**：正股、期權各同時持有 5–10 檔；批數超過 3 批的舊部位不處理。

**期權**（獨立的短線工具，一樣建立在「再跌深」的前提上）
- 標的要在進場區、基本面不是「排除」；買進時距到期至少 {orules.min_dte} 天；
- 價外程度、單筆金額、期權總成本占比**不設上限**（價外樂透可以）；同時最多 {orules.max_names} 檔；
- **權利金虧損達 {orules.exit_loss:.0%} 就出場**；現有的期權部位不處理。

**基本面**：成長型營收年增率至少 {frules.min_rev_yoy_growth:.0%}，成熟型要求不衰退且利益率不惡化；虧損中的公司另看毛利率、現金可撐月數、股本稀釋；
實質程度「高／中」的巨頭合作可把「排除」降成「警示」；不看估值。類型與巨頭合作記在 `data/company_profiles.json`、`data/partnerships.json`。

**資料**：持股與成交來自每日快照與 Firstrade 成交紀錄；價格訊號與基本面由 GitHub Actions 在每次快照推上後自動計算。
""")
    with t_fund:
        frows = []
        for s in sorted(stocks, key=lambda s: {"通過": 0, "警示": 1, "排除": 2}.get(s["verdict"], 3)):
            m = s.get("metrics") or {}
            runway = "不燒錢" if m.get("不燒錢") else (f"{m['可撐月數']:.0f}" if m.get("可撐月數") is not None else "-")
            f_ = lambda v: "-" if v is None else f"{v:+.0%}"
            frows.append({"代號": s["symbol"], "判定": s["verdict"], "類型": s.get("kind") or s.get("type", "-"), "軌道": s.get("track", "-"),
                          "營收年增率": f_(m.get("營收年增率")), "毛利率": "-" if m.get("毛利率") is None else f"{m['毛利率']:.0%}",
                          "營業利益率": "-" if m.get("營業利益率") is None else f"{m['營業利益率']:.0%}", "現金可撐(月)": runway,
                          "年化稀釋": f_(m.get("年化股本稀釋")), "原因": "；".join((s.get("reasons") or []) + (s.get("notes") or [])) or "-"})
        st.dataframe(pd.DataFrame(frows), hide_index=True, use_container_width=True)
        prow = []
        for sym, lst in load_partnerships().items():
            for p_ in lst:
                prow.append({"代號": sym, "合作對象": p_.get("partner"), "關係": p_.get("type"), "實質程度": p_.get("strength"),
                             "說明": p_.get("note"), "出處": p_.get("source"), "查證": p_.get("asof")})
        if prow:
            st.markdown("**巨頭合作清單**（人工維護，附出處；實質程度「高／中」才會影響判定）")
            st.dataframe(pd.DataFrame(prow), hide_index=True, use_container_width=True,
                         column_config={"出處": st.column_config.LinkColumn("出處", display_text="開啟")})
    with t_hist:
        st.markdown("在 GitHub 上用 10 年日線跑的回測（`scripts/run_backtest.py`）。**只測價格規則**，基本面濾網無法回測。")

        def hist_table(fname, title):
            f = ROOT / "data" / fname
            if not f.exists():
                return
            r = json.loads(f.read_text(encoding="utf-8"))
            rows = []
            for c_ in r["configs"]:
                p, sm = c_["params"], c_["summary"]
                rows.append({"止盈": "不止盈（抱到現在）" if p["take_profit"] is None else f"+{p['take_profit']:.0%}", "進場跌幅": f"-{p['entry_drop']:.0%}",
                             "止損": "無" if p["stop"] >= 0.95 else f"首批價 -{p['stop']:.0%}",
                             "加碼間距": f"-{p['add_step']:.0%}" if p.get("add_step") else "-12%（舊）", "交易數": sm["trades"], "已結束": sm["done"],
                             "勝率": "-" if sm["win_rate"] is None else f"{sm['win_rate']:.0%}", "止損次數": sm["stops"],
                             "平均賺NT$": round(sm["avg_win"]), "平均賠NT$": round(sm["avg_loss"]),
                             "報酬率(損益/投入)": f"{sm['pnl'] / sm['invested']:.0%}" if sm["invested"] else "-",
                             "最差單筆NT$": round(sm["worst"]), "同時最多檔數": sm["peak_positions"]})
            st.subheader(title)
            st.caption(f"{r['symbols_with_data']}/{r['symbols_requested']} 檔有資料，期間 {r['period']}，更新 {r['generated'][:10]}")
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        hist_table("backtest_add_step.json", "加碼間距比較（12% vs 20%）：你交易過的正股")
        hist_table("backtest_add_step_sp500.json", "加碼間距比較（12% vs 20%）：S&P 500")
        hist_table("backtest_results.json", "較早的回測（加碼間距 12%）：你交易過的正股，含止損／進場深度比較")
        hist_table("backtest_results_sp500.json", "較早的回測（加碼間距 12%）：S&P 500")
        st.caption("絕對報酬偏樂觀（倖存者偏差；你的標的集中在近年強勢族群），比較可信的是相對比較：止損 vs 不止損、止盈寬度、進場深度。"
                   "「同時最多檔數」代表訊號會在大盤大跌時集中出現，所以需要排序與檔數上限。")
    with t_bt:
        st.markdown("用 Yahoo 的歷史收盤價現場回測（收盤價成交、不含手續費與滑價）。")
        bt_in = st.text_input("回測標的（空白或逗號分隔）", "ALAB NVTS VRT RKLB ASTS SMR UUUU MP")
        cc1, cc2, cc3 = st.columns(3)
        period = cc1.selectbox("期間", ["2y", "5y", "10y", "max"], index=1)
        tp_on = cc2.checkbox("加入止盈假設", value=True, help="系統不替你止盈；回測需要一個出場，才算得出報酬")
        tp = cc3.slider("止盈：相對均價漲", 10, 300, 50, 10, format="%d%%") / 100
        if st.button("開始回測", type="primary"):
            bsyms = tuple(sorted({s.strip().upper() for s in bt_in.replace(",", " ").split() if s.strip()}))
            cl = load_closes(bsyms, period)
            if cl.empty:
                st.warning("抓不到股價，稍後重試。")
            else:
                r2 = Rules(**{**rules.__dict__, "take_profit": tp if tp_on else None})
                allt = []
                for s in bsyms:
                    if s in cl.columns:
                        ser = cl[s].dropna()
                        allt += backtest(s, list(ser.index), [float(x) for x in ser.values], r2)
                if not allt:
                    st.info("這段期間沒有任何標的觸發進場條件。")
                else:
                    sm = summarize(allt)
                    m = st.columns(5)
                    m[0].metric("交易數", sm["交易數"])
                    m[1].metric("勝率(已結束)", "-" if sm["勝率(已結束)"] is None else f"{sm['勝率(已結束)']:.0%}")
                    m[2].metric("止損次數", sm["止損次數"])
                    m[3].metric("總損益 NT$", f"{sm['總損益NT$']:,.0f}")
                    m[4].metric("最大單筆虧損 NT$", f"{sm['最大單筆虧損NT$']:,.0f}")
                    tdf = pd.DataFrame([t.__dict__ for t in allt]).rename(columns={
                        "symbol": "代號", "entry": "進場", "exit": "出場", "reason": "原因", "tranches": "批數", "invested": "投入NT$",
                        "pnl": "損益NT$", "days": "天數", "first_price": "首批價", "exit_price": "出場價", "ret": "報酬率"})
                    tdf["報酬率"] = tdf["報酬率"].map(lambda x: f"{x:+.1%}")
                    st.dataframe(tdf.sort_values("進場"), hide_index=True, use_container_width=True)
