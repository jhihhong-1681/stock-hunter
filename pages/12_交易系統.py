import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="交易系統 - 阿紘的股票儀表板", page_icon="🧭", layout="wide")
from utils.styles import load_css
load_css()
from utils.fundamentals import FundRules, evaluate, fetch_quarterly, load_partnerships, load_profiles
from utils.trading_system import (OptionRules, Rules, backtest, check_option, check_position, entry_hint, hold_hint,
                                  read_positions, read_totals, read_trades, scan_symbol, summarize)

st.title("🧭 交易系統")
st.markdown("下跌才買、金字塔加碼、首批價再跌 50% 止損。止盈由阿紘自己判斷，系統不代替決定。價格訊號 + 基本面（成長／獲利／財務體質）。")

ROOT = Path(__file__).resolve().parent.parent

with st.sidebar:
    st.subheader("規則參數")
    entry_drop = st.slider("進場：距 52 週高點回檔 ≥", 20, 50, 30, 1, format="%d%%") / 100
    t1 = st.number_input("第 1 批 NT$", 0, 500000, 20000, 5000)
    t2 = st.number_input("第 2 批 NT$", 0, 500000, 30000, 5000)
    t3 = st.number_input("第 3 批 NT$", 0, 500000, 40000, 5000)
    add_step = st.slider("加碼：上一批價再跌", 5, 25, 12, 1, format="%d%%") / 100
    rebound = st.slider("加碼：上漲後從高點回落", 10, 40, 25, 1, format="%d%%") / 100
    stop = st.slider("止損：首批價再跌", 30, 70, 50, 1, format="%d%%") / 100

    with st.expander("基本面門檻"):
        f_growth = st.slider("成長型：營收年增率至少", 0, 150, 40, 5, format="%d%%") / 100
        f_gm = st.slider("成長型：毛利率至少", 0, 60, 20, 5, format="%d%%") / 100
        f_runway = st.slider("現金可撐月數：警示線", 6, 48, 24, 6)
        f_runway_x = st.slider("現金可撐月數：排除線", 3, 24, 12, 3)
        f_dil = st.slider("年化股本稀釋上限", 5, 100, 30, 5, format="%d%%") / 100

    with st.expander("期權規則（草案，待阿紘確認數字）"):
        o_dte = st.slider("買進時距到期至少（天）", 7, 120, 30, 1)
        o_otm = st.slider("行使價高於現價最多", 0, 30, 10, 1, format="%d%%") / 100
        o_cap = st.number_input("單筆權利金成本上限 NT$", 1000, 200000, 15000, 1000)
        o_total = st.slider("期權總成本占總資產上限", 5, 50, 20, 1, format="%d%%") / 100
        o_names = st.slider("期權同時持有檔數上限", 3, 30, 10, 1)

orules = OptionRules(min_dte=o_dte, max_otm=o_otm, per_trade_cap_ntd=float(o_cap), total_cap_pct=o_total, max_names=o_names)
frules = FundRules(min_rev_yoy_growth=f_growth, min_gross_margin=f_gm, runway_pass_months=f_runway,
                   runway_exclude_months=f_runway_x, max_annual_dilution=f_dil)
rules = Rules(entry_drop=entry_drop, tranches_ntd=(t1, t2, t3), add_step=add_step,
              rebound_pullback=rebound, stop_from_first=stop)

partners_all = load_partnerships()
profiles = load_profiles()


@st.cache_data(ttl=3600 * 12)
def load_fund(sym: str) -> dict:
    try:
        return fetch_quarterly(sym)
    except Exception:
        return {}


def fund_row(sym: str) -> dict:
    """單檔基本面判定（持股對照、進場掃描共用）。"""
    prof = profiles.get(sym, {})
    if prof.get("type") == "ETF":
        return {"類型": "ETF", "基本面": "不適用", "基本面原因": "ETF 沒有公司財報"}
    d = load_fund(sym)
    if not d:
        return {"類型": prof.get("type", "-"), "基本面": "資料不足", "基本面原因": "Yahoo 沒有回財報"}
    e = evaluate(d, partners_all.get(sym), frules, prof.get("type"))
    return {"類型": e.get("kind", "-"), "基本面": e["verdict"], "基本面原因": "；".join(e["reasons"] + e["notes"]) or "-"}


tab_rule, tab_hold, tab_scan, tab_fund, tab_opt, tab_bt, tab_hist = st.tabs(
    ["📐 規則", "📋 持股對照規則", "🔍 進場掃描", "🧬 基本面", "💹 期權檢查", "🧪 回測", "📊 歷史回測結果"])


def pct(x):
    return f"{x * 100:+.1f}%" if x is not None and x == x else "-"


# ── 規則 ─────────────────────────────────────────────────
with tab_rule:
    total = sum(rules.tranches_ntd)
    # 三批都買、跌到止損價時的最大虧損：第 1 批在 P、第 2 批在 P×(1-step)、第 3 批在 P×(1-step)²
    p = [1, 1 - rules.add_step, (1 - rules.add_step) ** 2]
    shares = sum(a / x for a, x in zip(rules.tranches_ntd, p))
    max_loss = total - shares * (1 - rules.stop_from_first)
    st.markdown(f"""
**進場**：現價距 52 週高點回檔 ≥ {rules.entry_drop:.0%}，買第 1 批 NT${rules.tranches_ntd[0]:,}。
**加碼（最多 3 批，金字塔）**：第 2 批 NT${rules.tranches_ntd[1]:,}、第 3 批 NT${rules.tranches_ntd[2]:,}。
下一批在「上一批價再跌 {rules.add_step:.0%}」，或「首批後上漲、再從高點回落 {rules.rebound_pullback:.0%}」時買。
**止損**：現價 ≤ 首批買入價 × {1 - rules.stop_from_first:.0%}，全部出清（中間不論加碼幾次）。
**止損後重新進場**：從「止損價」再跌 {rules.reentry_drop:.0%}，且基本面沒有太大改變，就當作新一輪（新的首批價、批數歸零）。
**止盈**：阿紘自己判斷。
**檔數目標**：正股、期權各同時持有 5–10 檔。

**單一標的最大虧損（三批都買、跌到止損價）**：約 NT${max_loss:,.0f}（投入 NT${total:,} 的 {max_loss / total:.0%}）。
每一檔最多虧這個數字，所以檔數、總風險都可以事先算出來。
""")
    st.caption("匯率固定 31。進場訊號看價格，基本面濾網在「基本面」分頁，持股對照與進場掃描可附上基本面判定。")

# ── 持股對照 ─────────────────────────────────────────────
with tab_hold:
    trades = read_trades()
    rows = [check_position(p, trades, rules) for p in read_positions() if not p.get("type")]
    df = pd.DataFrame(rows)
    hit = df[df["已觸發止損"]]
    near = df[(~df["已觸發止損"]) & (df["距止損價"] <= 0.15)]
    n_opt = sum(1 for p in read_positions() if p.get("type") == "option")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("正股檔數", len(df), help="目標 5–10 檔")
    c4.metric("期權檔數", n_opt, help="目標 5–10 檔")
    c2.metric("已觸發止損", len(hit), help="現價 ≤ 首批價 × 止損比例")
    c3.metric("距止損價 15% 內", len(near))
    if len(hit):
        st.error("已觸發止損：" + "、".join(f"{r.symbol}（首批 ${r.首批價:g} → 現價 ${r.現價:g}，{pct(r.距首批價)}）" for r in hit.itertuples()))
    if len(near):
        st.warning("接近止損價：" + "、".join(f"{r.symbol}（距止損價 {pct(r.距止損價)}）" for r in near.itertuples()))
    with_fund = st.checkbox("附上基本面判定（要抓財報，第一次約半分鐘，之後快取 12 小時）", key="hold_fund")
    cols = ["symbol", "name", "首批價", "現價", "距首批價", "止損價", "距止損價", "已觸發止損", "已買批數",
            "下一批加碼價", "下一批金額NT$", "止損後再進場價", "報酬率", "現值NT$", "備註"]
    if with_fund:
        fr = pd.DataFrame([fund_row(sy) for sy in df["symbol"]])
        df = pd.concat([df.reset_index(drop=True), fr], axis=1)
        df["對照"] = [hold_hint(bool(r["已觸發止損"]), r["基本面"], r["下一批加碼價"] is not None and r["下一批加碼價"] == r["下一批加碼價"], r["止損後再進場價"])
                    for _, r in df.iterrows()]
        cols = ["symbol", "name", "類型", "基本面", "對照", "首批價", "現價", "距首批價", "止損價", "距止損價", "已觸發止損",
                "已買批數", "下一批加碼價", "止損後再進場價", "報酬率", "現值NT$", "基本面原因", "備註"]
    show = df[cols].copy()
    show["距首批價"] = show["距首批價"].map(pct)
    show["距止損價"] = show["距止損價"].map(pct)
    show["報酬率"] = show["報酬率"].map(lambda x: f"{x:+.1f}%" if x is not None else "-")
    st.dataframe(show.sort_values("現值NT$", ascending=False), hide_index=True, use_container_width=True)
    st.caption("首批價、已買批數完全來自成交紀錄（portfolio-calendar/trades.js）。"
               "「一輪」= 上次全部賣光之後重新買進的第一批；同一天買進合併成一批。")

# ── 進場掃描 ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_closes(tickers: tuple, period: str) -> pd.DataFrame:
    raw = yf.download(list(tickers), period=period, auto_adjust=True, progress=False, threads=True)
    if raw is None or raw.empty:
        return pd.DataFrame()
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close.dropna(how="all")


with tab_scan:
    watch = json.loads((ROOT / "data" / "watchlist.json").read_text(encoding="utf-8"))
    held = [p["symbol"] for p in read_positions() if not p.get("type")]
    default = sorted(set(watch) | set(held))
    extra = st.text_input("再加入的代號（空白或逗號分隔）", "")
    syms = sorted(set(default) | {s.strip().upper() for s in extra.replace(",", " ").split() if s.strip()})
    st.caption(f"掃描 {len(syms)} 檔：自選股 + 目前持股" + (" + 手動加入" if extra.strip() else ""))
    closes = load_closes(tuple(syms), "2y")
    if closes.empty:
        st.warning("抓不到股價（Yahoo Finance 暫時沒有回應），稍後重新整理。")
    else:
        out = []
        for s in syms:
            if s in closes.columns:
                r = scan_symbol(closes[s].dropna(), rules)
                if r:
                    out.append({"代號": s, **r})
        if out:
            sc = pd.DataFrame(out).sort_values("距高點")
            n_in = int(sc["進場區"].sum())
            with_fund_s = st.checkbox("對進場區的標的附上基本面判定", key="scan_fund")
            if with_fund_s:
                fr = {s_: fund_row(s_) for s_ in sc.loc[sc["進場區"], "代號"]}
                sc["類型"] = sc["代號"].map(lambda x: fr[x]["類型"] if x in fr else "")
                sc["基本面"] = sc["代號"].map(lambda x: fr[x]["基本面"] if x in fr else "")
                sc["結論"] = [entry_hint(bool(r["進場區"]), r["基本面"]) for _, r in sc.iterrows()]
                sc["基本面原因"] = sc["代號"].map(lambda x: fr[x]["基本面原因"] if x in fr else "")
                ok = int((sc["基本面"] == "通過").sum())
                m1, m2 = st.columns(2)
                m1.metric("進場區（距高點回檔達標）", n_in)
                m2.metric("進場區且基本面通過", ok)
                lead = ["代號", "結論", "類型", "基本面", "進場區", "現價", "52週高點", "距高點"]
                sc = sc[lead + [c for c in sc.columns if c not in lead]]
            else:
                st.metric("進場區（距高點回檔達標）", n_in)
            conv_file = ROOT / "data" / "conviction.json"
            conv = set(json.loads(conv_file.read_text(encoding="utf-8")).get("symbols", [])) if conv_file.exists() else set()
            sc["高信念"] = sc["代號"].map(lambda x: "★" if x in conv else "")
            vorder = {"通過": 0, "警示": 1, "排除": 2, "資料不足": 3, "不適用": 3}
            sc["_v"] = sc["基本面"].map(lambda x: vorder.get(x, 4)) if "基本面" in sc.columns else 0
            sc["_z"] = ~sc["進場區"]
            sc = sc.sort_values(["_z", "_v", "距高點", "高信念"], ascending=[True, True, True, False])
            sc["優先序"] = [str(i + 1) if not z else "" for i, z in enumerate(sc["_z"])]
            sc = sc.drop(columns=["_v", "_z"])
            sc = sc[["優先序", "代號", "高信念"] + [c for c in sc.columns if c not in ("優先序", "代號", "高信念")]]
            view = sc.copy()
            view["距高點"] = view["距高點"].map(pct)
            st.dataframe(view, hide_index=True, use_container_width=True)
            st.caption("加碼價、止損價以「現價當第 1 批」估算；實際以你真正買進的價格為準。"
                       "進場區內的優先序：基本面「通過」> 跌幅更深 > 高信念（★，在 data/conviction.json 標記）。"
                       "沒勾「附上基本面判定」時只依跌幅排序。")

# ── 基本面 ───────────────────────────────────────────────
with tab_fund:
    st.markdown("""
**兩條軌道**：近四季營業利益為正走「已獲利型」（看營收是否成長、利益率有沒有惡化）；
為負走「成長虧損型」（不因虧損排除，改看營收年增率、毛利率、虧損有沒有收斂、現金可撐多久、股本稀釋）。
**巨頭合作**記在 `data/partnerships.json`（人工維護、附出處），現金撐不夠久時可把「排除」降成「警示」。不看估值。
""")
    partners = partners_all
    fin = st.text_input("分析的代號（空白或逗號分隔）", " ".join(sorted(set(json.loads((ROOT / "data" / "watchlist.json").read_text(encoding="utf-8"))))))
    fsyms = sorted({x.strip().upper() for x in fin.replace(",", " ").split() if x.strip()})
    if st.button("分析基本面", type="primary"):
        rows, detail = [], {}
        prog = st.progress(0.0)
        for i, sym in enumerate(fsyms):
            d = load_fund(sym)
            e = evaluate(d, partners.get(sym), frules, profiles.get(sym, {}).get("type")) if d else {"track": "-", "verdict": "資料不足", "metrics": {}, "reasons": ["Yahoo 沒有回財報"], "notes": [], "partners": []}
            m = e["metrics"]
            rows.append({"代號": sym, "判定": e["verdict"], "類型": e.get("kind", "-"), "軌道": e["track"],
                         "營收年增率": pct(m.get("營收年增率")), "毛利率": pct(m.get("毛利率")).replace("+", ""),
                         "營業利益率": pct(m.get("營業利益率")).replace("+", ""),
                         "現金可撐(月)": ("不燒錢" if m.get("可撐月數") == float("inf") else f"{m['可撐月數']:.0f}") if m.get("可撐月數") is not None else "-",
                         "年化稀釋": pct(m.get("年化股本稀釋")), "巨頭合作": "、".join(p.get("partner", "?") + ("" if p.get("strength", "高") in ("高", "中") else "(低)") for p in e["partners"]) or "-",
                         "原因": "；".join(e["reasons"] + e["notes"])})
            prog.progress((i + 1) / len(fsyms))
        order = {"通過": 0, "警示": 1, "排除": 2, "資料不足": 3}
        fdf = pd.DataFrame(rows).sort_values("判定", key=lambda c: c.map(order))
        c = st.columns(4)
        for k, lab in enumerate(["通過", "警示", "排除", "資料不足"]):
            c[k].metric(lab, int((fdf["判定"] == lab).sum()))
        st.dataframe(fdf, hide_index=True, use_container_width=True)
        st.caption("財報來自 Yahoo Finance，通常只有最近 4–5 季；不足 5 季算不出年增率會標註。"
                   "最新一季的毛利率、營業利益率與一年前比較；現金可撐月數 = 現金 ÷ 近兩季平均每季自由現金流燒錢 × 3。")

# ── 回測 ─────────────────────────────────────────────────
with tab_bt:
    st.markdown("用歷史收盤價，把上面的規則套在每一檔上獨立回測（收盤價成交、不含手續費與滑價）。")
    bt_in = st.text_input("回測標的（空白或逗號分隔）", "ALAB NVTS VRT RKLB ASTS SMR UUUU MP")
    cc1, cc2, cc3 = st.columns(3)
    period = cc1.selectbox("期間", ["2y", "5y", "10y", "max"], index=1)
    tp_on = cc2.checkbox("加入止盈假設", value=True, help="系統本身不替你止盈；回測需要一個出場，才算得出報酬")
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
                m[1].metric("勝率(已結束)", pct(sm["勝率(已結束)"]).replace("+", "") if sm["勝率(已結束)"] is not None else "-")
                m[2].metric("止損次數", sm["止損次數"])
                m[3].metric("總損益 NT$", f"{sm['總損益NT$']:,.0f}")
                m[4].metric("最大單筆虧損 NT$", f"{sm['最大單筆虧損NT$']:,.0f}")
                tdf = pd.DataFrame([t.__dict__ for t in allt]).rename(columns={
                    "symbol": "代號", "entry": "進場", "exit": "出場", "reason": "原因", "tranches": "批數",
                    "invested": "投入NT$", "pnl": "損益NT$", "days": "天數", "first_price": "首批價", "exit_price": "出場價", "ret": "報酬率"})
                tdf["報酬率"] = tdf["報酬率"].map(pct)
                st.dataframe(tdf.sort_values("進場"), hide_index=True, use_container_width=True)
                st.caption("提醒：只回測現在還在市場上的標的，有倖存者偏差；沒有基本面濾網，"
                           "所以也會買進「便宜但持續惡化」的公司。結果是規則的上限參考，不是績效預測。")

# ── 期權檢查 ─────────────────────────────────────────────
with tab_opt:
    st.markdown("""
收到報牌資訊時填在這裡，系統對照規則逐項檢查：標的是不是已經跌深、基本面有沒有被排除、到期日夠不夠遠、
價外程度、單筆金額、期權總成本占比、檔數。期權規則目前是**草案**，數字在側邊欄「期權規則」可調，確認後我再寫死。
""")
    o1, o2, o3, o4, o5 = st.columns(5)
    o_sym = o1.text_input("標的代號", "", key="o_sym").strip().upper()
    o_kind = o2.selectbox("類型", ["Call", "Put"], key="o_kind")
    o_strike = o3.number_input("行使價", 0.0, 100000.0, 0.0, 0.5, key="o_strike")
    o_exp = o4.date_input("到期日", value=date.today() + timedelta(days=60), key="o_exp")
    o_prem = o5.number_input("權利金（每股 US$）", 0.0, 10000.0, 0.0, 0.05, key="o_prem")
    q1, q2, q3 = st.columns(3)
    o_qty = q1.number_input("口數", 1, 1000, 1, key="o_qty")
    o_spot_m = q2.number_input("現價（抓不到股價時手動填，0 = 自動）", 0.0, 100000.0, 0.0, 0.5, key="o_spot")
    o_high_m = q3.number_input("52 週高點（抓不到時手動填，0 = 自動）", 0.0, 100000.0, 0.0, 0.5, key="o_high")
    if st.button("檢查這筆期權", type="primary", key="o_go"):
        if not o_sym or o_strike <= 0 or o_prem <= 0:
            st.warning("請填標的代號、行使價、權利金。")
        else:
            spot, high52 = o_spot_m or None, o_high_m or None
            if spot is None or high52 is None:
                cl = load_closes((o_sym,), "2y")
                if not cl.empty and o_sym in cl.columns:
                    ser = cl[o_sym].dropna()
                    spot = spot or float(ser.iloc[-1])
                    high52 = high52 or float(ser.iloc[-252:].max())
            if spot is None:
                st.error("抓不到這檔的股價，請在上面手動填現價（和 52 週高點）再檢查。")
            else:
                pos_all = read_positions()
                opt = [p for p in pos_all if p.get("type") == "option"]
                tot = read_totals()
                fr = fund_row(o_sym)
                res = check_option(spot=spot, high52=high52, strike=o_strike, dte=(o_exp - date.today()).days, premium=o_prem,
                                   qty=int(o_qty), total_assets=tot.get("totalAssets", 1), option_cost_now=sum(p["invested"] for p in opt),
                                   option_names_now=len({p["symbol"] for p in opt}), is_new_name=o_sym not in {p["symbol"] for p in opt},
                                   verdict=fr["基本面"], rules=rules, orules=orules, kind=o_kind)
                if res["pass"]:
                    st.success("符合全部規則。")
                else:
                    st.error(f"不符合 {res['n_bad']} 項" + (f"，另有 {res['n_unknown']} 項資料不足" if res["n_unknown"] else ""))
                for name, ok, detail in res["checks"]:
                    st.markdown(f"{'✅' if ok else '❌' if ok is False else '❓'} **{name}**：{detail}")
                i = res["info"]
                mm = st.columns(4)
                mm[0].metric("成本 NT$", f"{i['成本NT$']:,.0f}", help="這筆最大虧損 = 全部權利金")
                mm[1].metric("損益兩平價", f"${i['損益兩平價']:.2f}", f"{i['損益兩平距現價']:+.1%} 距現價")
                mm[2].metric("權利金占股價", f"{i['權利金占股價']:.1%}")
                mm[3].metric("現價 / 52週高點", f"${spot:.2f}", f"{(spot / high52 - 1):+.1%}" if high52 else "")
                if fr["基本面原因"] and fr["基本面原因"] != "-":
                    st.caption("基本面：" + fr["基本面原因"])

# ── 歷史回測結果 ─────────────────────────────────────────
with tab_hist:
    st.markdown("""
在 GitHub 上用 10 年日線跑的回測（`scripts/run_backtest.py`，結果在 `data/backtest_results*.json`；
想重跑就改 `data/backtest_request.json` 再推上去）。**只測價格規則**：沒有歷史基本面資料，基本面濾網無法回測。
""")
    def hist_table(fname, title):
        f = ROOT / "data" / fname
        if not f.exists():
            return
        r = json.loads(f.read_text(encoding="utf-8"))
        rows = []
        for c in r["configs"]:
            p, sm = c["params"], c["summary"]
            rows.append({"止盈": "不止盈（抱到現在）" if p["take_profit"] is None else f"+{p['take_profit']:.0%}",
                         "進場跌幅": f"-{p['entry_drop']:.0%}", "止損": "無" if p["stop"] >= 0.95 else f"首批價 -{p['stop']:.0%}",
                         "交易數": sm["trades"], "已結束": sm["done"], "持有中": sm["open"],
                         "勝率": "-" if sm["win_rate"] is None else f"{sm['win_rate']:.0%}", "止損次數": sm["stops"],
                         "平均賺NT$": round(sm["avg_win"]), "平均賠NT$": round(sm["avg_loss"]),
                         "報酬率(損益/投入)": f"{sm['pnl'] / sm['invested']:.0%}" if sm["invested"] else "-",
                         "最差單筆NT$": round(sm["worst"]), "同時最多檔數": sm["peak_positions"], "平均持有天": round(sm["avg_days"])})
        st.subheader(title)
        st.caption(f"{r['symbols_with_data']}/{r['symbols_requested']} 檔有資料，期間 {r['period']}，更新 {r['generated'][:10]}")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    hist_table("backtest_results.json", "你交易過的正股（約 100 檔）")
    hist_table("backtest_results_sp500.json", "對照組：S&P 500 成分股")
    st.caption("**怎麼讀**：絕對報酬偏樂觀（兩組都是「現在還在交易」的公司，倖存者偏差；你的標的又集中在近年強勢的族群），"
               "比較可信的是相對比較：止損 vs 不止損、止盈寬度、進場深度。「不止盈」的損益多半是還沒賣的帳面數字。"
               "同時最多檔數代表訊號會在大盤大跌時集中出現，所以需要排序與檔數上限。")
