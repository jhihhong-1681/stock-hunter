import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="交易系統 - 阿紘的股票儀表板", page_icon="🧭", layout="wide")
from utils.styles import load_css
load_css()
from utils.fundamentals import FundRules, evaluate, fetch_quarterly, load_partnerships, load_profiles
from utils.trading_system import Rules, backtest, check_position, read_positions, read_trades, scan_symbol, summarize

st.title("🧭 交易系統")
st.markdown("下跌才買、金字塔加碼、首批價再跌 50% 止損。止盈由阿紘自己判斷，系統不代替決定。（v0：還沒有基本面濾網）")

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

frules = FundRules(min_rev_yoy_growth=f_growth, min_gross_margin=f_gm, runway_pass_months=f_runway,
                   runway_exclude_months=f_runway_x, max_annual_dilution=f_dil)
rules = Rules(entry_drop=entry_drop, tranches_ntd=(t1, t2, t3), add_step=add_step,
              rebound_pullback=rebound, stop_from_first=stop)

tab_rule, tab_hold, tab_scan, tab_fund, tab_bt = st.tabs(["📐 規則", "📋 持股對照規則", "🔍 進場掃描", "🧬 基本面", "🧪 回測"])


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
**止盈**：阿紘自己判斷。

**單一標的最大虧損（三批都買、跌到止損價）**：約 NT${max_loss:,.0f}（投入 NT${total:,} 的 {max_loss / total:.0%}）。
每一檔最多虧這個數字，所以檔數、總風險都可以事先算出來。
""")
    st.caption("匯率固定 31。基本面濾網（營收、毛利率、現金流、估值）下一版加入，目前進場訊號只看價格。")

# ── 持股對照 ─────────────────────────────────────────────
with tab_hold:
    trades = read_trades()
    rows = [check_position(p, trades, rules) for p in read_positions() if not p.get("type")]
    df = pd.DataFrame(rows)
    hit = df[df["已觸發止損"]]
    near = df[(~df["已觸發止損"]) & (df["距止損價"] <= 0.15)]
    c1, c2, c3 = st.columns(3)
    c1.metric("正股檔數", len(df))
    c2.metric("已觸發止損", len(hit), help="現價 ≤ 首批價 × 止損比例")
    c3.metric("距止損價 15% 內", len(near))
    if len(hit):
        st.error("已觸發止損：" + "、".join(f"{r.symbol}（首批 ${r.首批價:g} → 現價 ${r.現價:g}，{pct(r.距首批價)}）" for r in hit.itertuples()))
    if len(near):
        st.warning("接近止損價：" + "、".join(f"{r.symbol}（距止損價 {pct(r.距止損價)}）" for r in near.itertuples()))
    show = df[["symbol", "name", "首批價", "現價", "距首批價", "止損價", "距止損價", "已觸發止損", "已買批數",
               "下一批加碼價", "下一批金額NT$", "報酬率", "現值NT$", "備註"]].copy()
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
            st.metric("進場區（距高點回檔達標）", n_in)
            view = sc.copy()
            view["距高點"] = view["距高點"].map(pct)
            st.dataframe(view, hide_index=True, use_container_width=True)
            st.caption("加碼價、止損價以「現價當第 1 批」估算；實際以你真正買進的價格為準。")

# ── 基本面 ───────────────────────────────────────────────
@st.cache_data(ttl=3600 * 12)
def load_fund(sym: str) -> dict:
    try:
        return fetch_quarterly(sym)
    except Exception:
        return {}


with tab_fund:
    st.markdown("""
**兩條軌道**：近四季營業利益為正走「已獲利型」（看營收是否成長、利益率有沒有惡化）；
為負走「成長虧損型」（不因虧損排除，改看營收年增率、毛利率、虧損有沒有收斂、現金可撐多久、股本稀釋）。
**巨頭合作**記在 `data/partnerships.json`（人工維護、附出處），現金撐不夠久時可把「排除」降成「警示」。不看估值。
""")
    partners = load_partnerships()
    profiles = load_profiles()
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
