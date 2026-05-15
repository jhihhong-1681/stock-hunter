import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os
from datetime import datetime

import gspread
import gspread.utils
from google.oauth2.service_account import Credentials

# ══════════════════════════════════════════════
#  設定
# ══════════════════════════════════════════════
st.set_page_config(page_title="股票儀表板", layout="wide")

SHEET_ID = '1eaUErkLJUOH7aaIKhDWM5vQwAbE2Zrl0w9jI3KK-9yU'
SCOPES   = ['https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive']

COLS = ["市場","股票代號","股票名稱","股數","第一筆建倉","成本均價","幣別",
        "現價","總投入","現值","損益","報酬率","平倉","已實現損益"]
WATCHLIST_COLS = ["股票代號","股票名稱","P₀ (第一批進場價)","總資金 (USD)",
                  "T1已填","T2已填","T3已填","T4已填","T5已填","備註"]

TRANCHES = [
    {"name":"T1","price_ratio":1.00,"weight":0.35,"label":"第1批 (P₀)"},
    {"name":"T2","price_ratio":0.90,"weight":0.25,"label":"第2批 (-10%)"},
    {"name":"T3","price_ratio":0.80,"weight":0.20,"label":"第3批 (-20%)"},
    {"name":"T4","price_ratio":0.70,"weight":0.12,"label":"第4批 (-30%)"},
    {"name":"T5","price_ratio":0.62,"weight":0.08,"label":"第5批 (-38%)"},
]
STOP_RATIO   = 0.78
TARGET_RATIO = 2.00

# ══════════════════════════════════════════════
#  Google Sheets 連線
# ══════════════════════════════════════════════
def _build_spreadsheet():
    """建立新的 Google Sheets 連線"""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    except Exception:
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)

@st.cache_resource
def get_spreadsheet():
    return _build_spreadsheet()

def get_spreadsheet_safe():
    """取得連線；若連線已過期自動重建"""
    try:
        sh = get_spreadsheet()
        sh.fetch_sheet_metadata()   # 測試連線是否有效
        return sh
    except Exception:
        get_spreadsheet.clear()     # 清除快取，強制重建
        return _build_spreadsheet()

# ══════════════════════════════════════════════
#  資料讀取函式（帶快取）
# ══════════════════════════════════════════════
@st.cache_data(ttl=120)
def _load_portfolio_raw():
    sh = get_spreadsheet_safe()
    ws = sh.worksheet('美股持有庫存(每日更新)')
    data = ws.get_all_values()
    if len(data) <= 1:
        return pd.DataFrame(columns=COLS)
    df = pd.DataFrame(data[1:], columns=data[0]).fillna('')
    for col in COLS:
        if col not in df.columns:
            df[col] = ''
    return df[COLS]

@st.cache_data(ttl=120)
def _load_watchlist_raw():
    sh = get_spreadsheet_safe()
    try:
        ws = sh.worksheet('自選股監控')
        data = ws.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame(columns=WATCHLIST_COLS)
        df = pd.DataFrame(data[1:], columns=data[0]).fillna('')
        for col in WATCHLIST_COLS:
            if col not in df.columns:
                df[col] = ''
        return df[WATCHLIST_COLS]
    except Exception:
        return pd.DataFrame(columns=WATCHLIST_COLS)

@st.cache_data(ttl=120)
def _load_settings_raw():
    sh = get_spreadsheet_safe()
    try:
        ws = sh.worksheet('設定')
        data = ws.get_all_values()
        settings = {}
        for row in data[1:]:
            if len(row) >= 2:
                settings[row[0]] = row[1]
        return settings
    except Exception:
        return {}

# ══════════════════════════════════════════════
#  資料寫入函式
# ══════════════════════════════════════════════
def save_portfolio(df):
    # ⚠️ 保留此函式但不呼叫 — 不允許整表覆寫
    raise RuntimeError("禁止整表覆寫投資組合，請使用 update/add/delete_portfolio_row")

def _get_portfolio_ws():
    return get_spreadsheet().worksheet('美股持有庫存(每日更新)')

# 欄位對應 (1-based)
_COL = {'市場':1,'股票代號':2,'股票名稱':3,'股數':4,'第一筆建倉':5,
        '成本均價':6,'幣別':7,'現價':8,'總投入':9,'現值':10,
        '損益':11,'報酬率':12,'平倉':13,'已實現損益':14}
# 只允許從 App 更新這些欄位 (不包含公式欄)
SAFE_EDIT_COLS = ['股票名稱','股數','第一筆建倉','幣別','平倉']

def _find_ticker_row(ws, ticker: str):
    """找股票代號在工作表的列號 (1-based)，找不到回傳 None"""
    try:
        cell = ws.find(ticker, in_column=_COL['股票代號'])
        return cell.row
    except Exception:
        return None

def update_portfolio_row(ticker: str, updates: dict):
    """安全更新：只更新 SAFE_EDIT_COLS 欄位，公式欄完全不碰"""
    ws = _get_portfolio_ws()
    row = _find_ticker_row(ws, ticker)
    if not row:
        return False, f"找不到 {ticker}"
    batch = []
    for col, val in updates.items():
        if col not in SAFE_EDIT_COLS:
            continue
        col_idx = _COL[col]
        a1 = gspread.utils.rowcol_to_a1(row, col_idx)
        batch.append({'range': a1, 'values': [[val]]})
    if batch:
        ws.batch_update(batch)
    _load_portfolio_raw.clear()
    return True, "已更新"

def add_portfolio_row(data: dict):
    """新增一列到最後一筆股票行的下一行，公式欄自動帶入"""
    ws = _get_portfolio_ws()
    all_vals = ws.get_all_values()
    # 找最後一列有 市場 資料的行
    last_row = 1
    for i, row in enumerate(all_vals):
        if row and row[0].strip() in ['美股','台股']:
            last_row = i + 1
    insert_at = last_row + 1
    ticker  = str(data.get('股票代號','')).strip().upper()
    shares  = data.get('股數', 0)
    avg     = data.get('成本均價', 0)
    market  = data.get('市場', '美股')
    currency = data.get('幣別', 'USD')
    rate    = 31 if currency == 'USD' else 1
    r = insert_at
    new_row = [
        market,                                         # A 市場
        ticker,                                         # B 股票代號
        data.get('股票名稱', ''),                        # C 股票名稱
        shares,                                         # D 股數
        data.get('第一筆建倉', ''),                      # E 第一筆建倉
        avg,                                            # F 成本均價 (純數字)
        currency,                                       # G 幣別
        f'=GOOGLEFINANCE(B{r},"price")',                # H 現價
        f'=D{r}*F{r}*{rate}',                          # I 總投入
        f'=D{r}*H{r}*{rate}',                          # J 現值
        f'=J{r}-I{r}',                                 # K 損益
        f'=K{r}/I{r}',                                 # L 報酬率
        data.get('平倉', ''),                            # M 平倉
        '',                                             # N 已實現損益
    ]
    ws.insert_row(new_row, insert_at, value_input_option='USER_ENTERED')
    _load_portfolio_raw.clear()
    return True, f"{ticker} 已新增至第 {insert_at} 行"

def delete_portfolio_row(ticker: str):
    """刪除整列 (只刪股票代號匹配的那列)"""
    ws = _get_portfolio_ws()
    row = _find_ticker_row(ws, ticker)
    if not row:
        return False, f"找不到 {ticker}"
    ws.delete_rows(row)
    _load_portfolio_raw.clear()
    return True, f"{ticker} 已刪除"

# ══════════════════════════════════════════════
#  交易引擎
# ══════════════════════════════════════════════
USD_RATE = 31  # 固定匯率，與原試算表公式一致

def get_position_info(ticker: str):
    """讀取目前持股數與均價（取公式計算結果，非公式本身）"""
    ws = _get_portfolio_ws()
    row = _find_ticker_row(ws, ticker)
    if not row:
        return None
    data = ws.get(f'A{row}:N{row}', value_render_option='UNFORMATTED_VALUE')
    if not data or not data[0]:
        return None
    r = data[0]
    def _f(idx):
        try: return float(r[idx]) if r[idx] != '' else 0.0
        except: return 0.0
    return {
        'row': row,
        'market':   r[0] if len(r) > 0 else '美股',
        'name':     r[2] if len(r) > 2 else '',
        'shares':   _f(3),
        'avg_cost': _f(5),
        'currency': r[6] if len(r) > 6 else 'USD',
        'realized': _f(13),
    }

def _ensure_log_sheet():
    """建立交易紀錄分頁（若不存在）"""
    sh = get_spreadsheet_safe()
    try:
        return sh.worksheet('交易紀錄')
    except Exception:
        ws = sh.add_worksheet(title='交易紀錄', rows=1000, cols=9)
        ws.update([['日期','操作','股票代號','股票名稱',
                    '股數','成交價($)','均價後($)','現金變動(TWD)','備註']])
        return ws

def _append_log(action, ticker, name, shares, price, avg_after, cash_chg, note=''):
    ws = _ensure_log_sheet()
    ws.append_row([
        datetime.now().strftime('%Y-%m-%d %H:%M'),
        action, ticker, name,
        round(float(shares), 4), round(float(price), 4),
        round(float(avg_after), 4), round(float(cash_chg), 0), note
    ], value_input_option='USER_ENTERED')

def execute_buy(ticker: str, shares: float, price: float,
                name: str = '', market: str = '美股', currency: str = 'USD'):
    """
    買入：
    · 已有持股 → 加權平均更新 D(股數)、F(均價純數字)
    · 新持股   → 新增一列（含 GOOGLEFINANCE 公式）
    · 不碰其他任何欄位或列
    """
    ws   = _get_portfolio_ws()
    pos  = get_position_info(ticker)
    rate = USD_RATE if currency == 'USD' else 1
    cost_ntd = round(shares * price * rate, 0)

    if pos:
        old_s, old_avg = pos['shares'], pos['avg_cost']
        new_s   = old_s + shares
        new_avg = round((old_avg * old_s + price * shares) / new_s, 4)
        row = pos['row']
        ws.batch_update([
            {'range': gspread.utils.rowcol_to_a1(row, 4), 'values': [[new_s]]},
            {'range': gspread.utils.rowcol_to_a1(row, 6), 'values': [[new_avg]]},
        ], value_input_option='USER_ENTERED')
        used_name = pos['name'] or name
    else:
        add_portfolio_row({
            '市場': market, '股票代號': ticker, '股票名稱': name,
            '股數': shares, '成本均價': price, '第一筆建倉': price,
            '幣別': currency,
        })
        new_avg, new_s, used_name = price, shares, name

    # 現金扣除
    s = dict(st.session_state.settings)
    s['cash_balance'] = str(round(float(s.get('cash_balance', 0)) - cost_ntd, 0))
    save_settings(s); st.session_state.settings = s

    _append_log('買', ticker, used_name, shares, price, new_avg, -cost_ntd)
    _load_portfolio_raw.clear()
    return True, f"買入 {shares} 股 {ticker} @ ${price}，新均價 ${new_avg:.4f}"

def execute_sell(ticker: str, shares_sold: float, sell_price: float):
    """
    賣出：
    · 更新 D(剩餘股數)、M(平倉備註)、N(累計已實現損益)
    · 不動 F(均價) 及任何公式欄
    """
    pos = get_position_info(ticker)
    if not pos:
        return False, f"找不到 {ticker} 的持股"
    if shares_sold > pos['shares'] + 0.0001:
        return False, f"賣出股數({shares_sold}) 超過持有({pos['shares']:.4f})"

    ws   = _get_portfolio_ws()
    row  = pos['row']
    rate = USD_RATE if pos['currency'] == 'USD' else 1

    remaining = round(pos['shares'] - shares_sold, 4)
    realized  = round((sell_price - pos['avg_cost']) * shares_sold * rate, 2)
    new_total = round(pos['realized'] + realized, 2)
    proceeds  = round(shares_sold * sell_price * rate, 0)

    # 平倉備註：附加到現有文字
    try:
        cur = ws.get(f'M{row}', value_render_option='FORMATTED_VALUE')
        cur_note = cur[0][0] if cur and cur[0] else ''
    except Exception:
        cur_note = ''
    new_note = (cur_note + f' / {sell_price}賣出{shares_sold}股').strip(' /')

    ws.batch_update([
        {'range': gspread.utils.rowcol_to_a1(row,  4), 'values': [[remaining]]},
        {'range': gspread.utils.rowcol_to_a1(row, 13), 'values': [[new_note]]},
        {'range': gspread.utils.rowcol_to_a1(row, 14), 'values': [[new_total]]},
    ], value_input_option='USER_ENTERED')

    # 現金加回
    s = dict(st.session_state.settings)
    s['cash_balance'] = str(round(float(s.get('cash_balance', 0)) + proceeds, 0))
    save_settings(s); st.session_state.settings = s

    _append_log('賣', ticker, pos['name'], shares_sold, sell_price,
                pos['avg_cost'], proceeds, f"已實現損益 NT${realized:+,.0f}")
    _load_portfolio_raw.clear()
    return True, f"賣出 {shares_sold} 股 {ticker} @ ${sell_price}，已實現 NT${realized:+,.0f}"

@st.cache_data(ttl=30)
def load_transaction_log():
    try:
        ws = _ensure_log_sheet()
        data = ws.get_all_values()
        if len(data) <= 1:
            return pd.DataFrame(columns=['日期','操作','股票代號','股票名稱',
                                         '股數','成交價($)','均價後($)','現金變動(TWD)','備註'])
        return pd.DataFrame(data[1:], columns=data[0])
    except Exception:
        return pd.DataFrame()

def save_watchlist(df):
    sh = get_spreadsheet_safe()
    try:
        ws = sh.worksheet('自選股監控')
    except Exception:
        ws = sh.add_worksheet(title='自選股監控', rows=200, cols=15)
    ws.clear()
    ws.update([df.columns.tolist()] + df.fillna('').values.tolist())
    _load_watchlist_raw.clear()

def save_settings(settings_dict):
    sh = get_spreadsheet_safe()
    try:
        ws = sh.worksheet('設定')
    except Exception:
        ws = sh.add_worksheet(title='設定', rows=20, cols=5)
    rows = [['key','value']] + [[k, str(v)] for k,v in settings_dict.items()]
    ws.clear()
    ws.update(rows)
    _load_settings_raw.clear()

# ══════════════════════════════════════════════
#  Session State 初始化
# ══════════════════════════════════════════════
if 'initialized' not in st.session_state:
    st.session_state.portfolio_df = _load_portfolio_raw()
    st.session_state.watchlist_df = _load_watchlist_raw()
    st.session_state.settings     = _load_settings_raw()
    st.session_state.initialized  = True

def get_setting(key, default):
    val = st.session_state.settings.get(key, default)
    if isinstance(default, float):
        try: return float(val)
        except: return default
    if isinstance(default, int):
        try: return int(val)
        except: return default
    if isinstance(default, bool):
        return str(val).lower() in ['true','1','yes']
    return val

# ══════════════════════════════════════════════
#  工具函式
# ══════════════════════════════════════════════
def clean_val(v):
    if pd.isna(v) or str(v).strip() == '': return 0.0
    s = str(v).replace('NT$','').replace('$','').replace(',','').replace('%','').strip()
    try: return float(s)
    except: return 0.0

@st.cache_data(ttl=120)
def fetch_price(ticker: str):
    """抓即時股價：先試 Yahoo Finance v8，失敗改用 yfinance，再失敗回傳 None"""
    # 方法 1：Yahoo Finance 非官方 API
    try:
        for base in ["https://query1.finance.yahoo.com", "https://query2.finance.yahoo.com"]:
            url = f"{base}/v8/finance/chart/{ticker}?interval=1d&range=5d"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if r.status_code == 200:
                data = r.json()
                closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
                closes = [c for c in closes if c is not None]
                if closes:
                    return round(closes[-1], 2)
    except Exception:
        pass

    # 方法 2：yfinance 官方套件（備援）
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].dropna().iloc[-1]), 2)
    except Exception:
        pass

    return None

def calc_tranches(p0: float, budget_usd: float, filled: list):
    rows = []
    total_cost = 0.0
    total_shares = 0.0
    for i, t in enumerate(TRANCHES):
        price_target = round(p0 * t["price_ratio"], 2)
        alloc_usd    = round(budget_usd * t["weight"], 2)
        shares       = round(alloc_usd / price_target, 4) if price_target > 0 else 0
        is_filled    = filled[i] if i < len(filled) else False
        if is_filled:
            total_cost   += price_target * shares
            total_shares += shares
        rows.append({
            "批次": t["name"], "說明": t["label"],
            "進場價": price_target, "佔比": f"{t['weight']*100:.0f}%",
            "配置金額": alloc_usd, "預計股數": shares, "已填": is_filled,
        })
    avg_cost  = round(total_cost / total_shares, 2) if total_shares > 0 else None
    stop_loss = round(avg_cost * STOP_RATIO, 2)    if avg_cost else None
    target    = round(avg_cost * TARGET_RATIO, 2)  if avg_cost else None
    all_cost   = sum(p0*t["price_ratio"]*(budget_usd*t["weight"]/(p0*t["price_ratio"])) for t in TRANCHES)
    all_shares = sum((budget_usd*t["weight"])/(p0*t["price_ratio"]) for t in TRANCHES)
    full_avg   = round(all_cost / all_shares, 2)
    summary = {
        "avg_cost": avg_cost, "stop_loss": stop_loss, "target": target,
        "full_avg": full_avg,
        "full_stop": round(full_avg * STOP_RATIO, 2),
        "full_target": round(full_avg * TARGET_RATIO, 2),
    }
    return rows, summary

# ══════════════════════════════════════════════
#  主頁面
# ══════════════════════════════════════════════
st.title("📈 我的專屬股票儀表板")

tab1, tab2, tab3 = st.tabs(["📊 投資組合", "🎯 分批買入模板", "💼 交易"])

# ══════════════════════════════════════════════
#  TAB 1: 投資組合
# ══════════════════════════════════════════════
with tab1:
    df_raw = st.session_state.portfolio_df.copy()
    # 過濾掉 Google Sheet 底部的彙總列（CASH、Total 等非股票列）
    VALID_MARKETS = ['美股', '台股', 'US', 'TW']
    df = df_raw[
        df_raw['市場'].str.strip().isin(VALID_MARKETS) &
        df_raw['股票代號'].str.strip().ne('') &
        ~df_raw['股票代號'].str.upper().str.strip().isin(['CASH', 'TOTAL'])
    ].copy()

    saved_cash = get_setting('cash_balance', 0.0)

    # 現金餘額輸入（只存到「設定」分頁，不動投資組合）
    cash_col, refresh_col, _ = st.columns([2, 1, 3])
    with cash_col:
        cash_in = st.number_input("💵 目前現金餘額 (台幣)：", min_value=0.0, value=saved_cash)
    with refresh_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 儲存現金餘額"):
            new_settings = dict(st.session_state.settings)
            new_settings['cash_balance'] = str(cash_in)
            with st.spinner("儲存中…"):
                save_settings(new_settings)
                st.session_state.settings = new_settings
            st.success("✅ 已儲存！")

    st.info("📋 投資組合資料從 Google Sheets 讀取，請直接在試算表中編輯。點「🔄 重新載入」可抓取最新資料。")

    reload_col, _ = st.columns([1, 5])
    with reload_col:
        if st.button("🔄 重新載入投資組合"):
            _load_portfolio_raw.clear()
            st.session_state.portfolio_df = _load_portfolio_raw()
            st.rerun()

    # KPI 計算
    calc = df.copy()
    calc['n_總投入'] = calc['總投入'].apply(clean_val)
    calc['n_現值']   = calc['現值'].apply(clean_val)
    calc['n_已實現'] = calc['已實現損益'].apply(clean_val)
    calc['n_損益']   = calc['n_現值'] - calc['n_總投入']
    active = calc[calc['n_總投入'] > 0].copy()

    t_cost     = active['n_總投入'].sum()
    t_unprofit = active['n_損益'].sum()
    t_reprofit = calc['n_已實現'].sum()
    t_assets   = active['n_現值'].sum() + cash_in
    t_rate     = (t_unprofit + t_reprofit) / t_cost * 100 if t_cost > 0 else 0

    st.markdown(f"<h1 style='text-align:center;color:#1E88E5;'>總資產 NT${t_assets:,.0f}</h1>",
                unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("💰 投入成本",   f"{t_cost:,.0f}")
    m2.metric("📉 未實現損益", f"{t_unprofit:,.0f}", delta=f"{t_unprofit:,.0f}", delta_color="inverse")
    m3.metric("🧧 已實現損益", f"{t_reprofit:,.0f}", delta=f"{t_reprofit:,.0f}", delta_color="inverse")
    m4.metric("💵 目前現金",   f"{cash_in:,.0f}")
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.metric("📊 整體報酬率", f"{t_rate:.2f}%", delta=f"{t_rate:.2f}%", delta_color="inverse")

    st.subheader("📋 持倉明細表")
    def style_profit(val):
        v = clean_val(val)
        color = '#FF3131' if v > 0 else ('#00FF42' if v < 0 else 'white')
        return f'color:{color};font-weight:bold'
    if not active.empty:
        display_cols = [c for c in COLS if c in active.columns]
        st.dataframe(active[display_cols].style.map(style_profit,
            subset=['損益','報酬率','已實現損益']), use_container_width=True)

    # ── 持倉管理 ──────────────────────────────────────────
    st.divider()
    with st.expander("✏️ 持倉管理（新增 / 編輯 / 刪除）", expanded=False):
        action = st.radio("選擇操作", ["➕ 新增持股", "✏️ 編輯持股", "🗑️ 刪除持股"],
                          horizontal=True, key="mgmt_action")

        if action == "➕ 新增持股":
            st.caption("📌 成本均價請填入你的實際均價，現價與計算欄會自動帶入 Google Finance 公式")
            c1,c2,c3,c4 = st.columns(4)
            with c1: add_market   = st.selectbox("市場", ["美股","台股"], key="add_mkt")
            with c2: add_ticker   = st.text_input("股票代號", key="add_ticker").upper().strip()
            with c3: add_name     = st.text_input("股票名稱", key="add_name")
            with c4: add_currency = st.selectbox("幣別", ["USD","TWD"], key="add_currency")
            c5,c6,c7 = st.columns(3)
            with c5: add_shares   = st.number_input("股數", min_value=0.0, value=0.0, key="add_shares")
            with c6: add_cost     = st.number_input("成本均價 ($)", min_value=0.0, value=0.0, key="add_cost")
            with c7: add_first    = st.number_input("第一筆建倉 ($)", min_value=0.0, value=0.0, key="add_first")
            if st.button("✅ 新增到 Google Sheets", key="btn_add"):
                if not add_ticker:
                    st.warning("請填入股票代號")
                elif add_shares <= 0 or add_cost <= 0:
                    st.warning("股數與成本均價不能為 0")
                else:
                    with st.spinner("新增中…"):
                        ok, msg = add_portfolio_row({
                            '市場': add_market, '股票代號': add_ticker,
                            '股票名稱': add_name, '股數': add_shares,
                            '成本均價': add_cost, '第一筆建倉': add_first,
                            '幣別': add_currency,
                        })
                        st.session_state.portfolio_df = _load_portfolio_raw()
                    if ok: st.success(f"✅ {msg}")
                    else:  st.error(msg)

        elif action == "✏️ 編輯持股":
            tickers_list = df['股票代號'].tolist()
            if not tickers_list:
                st.info("目前無持股資料")
            else:
                sel = st.selectbox("選擇要編輯的股票", tickers_list, key="edit_sel")
                row_data = df[df['股票代號'] == sel].iloc[0] if sel else None
                if row_data is not None:
                    st.caption(f"⚠️ 成本均價、現價、總投入等公式欄不可在此修改，請直接在 Google Sheets 編輯")
                    e1,e2,e3 = st.columns(3)
                    with e1:
                        e_name   = st.text_input("股票名稱", value=str(row_data.get('股票名稱','')), key="e_name")
                    with e2:
                        e_shares = st.number_input("股數", value=float(clean_val(row_data.get('股數',0))), key="e_shares")
                    with e3:
                        e_first  = st.number_input("第一筆建倉 ($)", value=float(clean_val(row_data.get('第一筆建倉',0))), key="e_first")
                    e4,e5 = st.columns([1,2])
                    with e4:
                        e_curr   = st.selectbox("幣別", ["USD","TWD"],
                                                index=0 if row_data.get('幣別','USD')=='USD' else 1, key="e_curr")
                    with e5:
                        e_closedpos = st.text_input("平倉備註", value=str(row_data.get('平倉','')), key="e_closed")
                    if st.button("💾 儲存變更", key="btn_edit"):
                        with st.spinner("更新中…"):
                            ok, msg = update_portfolio_row(sel, {
                                '股票名稱': e_name, '股數': e_shares,
                                '第一筆建倉': e_first, '幣別': e_curr,
                                '平倉': e_closedpos,
                            })
                            st.session_state.portfolio_df = _load_portfolio_raw()
                        if ok: st.success(f"✅ {sel} 已更新")
                        else:  st.error(msg)

        elif action == "🗑️ 刪除持股":
            tickers_list = df['股票代號'].tolist()
            if not tickers_list:
                st.info("目前無持股資料")
            else:
                del_sel = st.selectbox("選擇要刪除的股票", tickers_list, key="del_sel")
                st.warning(f"⚠️ 確定要從 Google Sheets 刪除 **{del_sel}** 整列嗎？此操作無法復原。")
                if st.button(f"🗑️ 確認刪除 {del_sel}", key="btn_del", type="primary"):
                    with st.spinner("刪除中…"):
                        ok, msg = delete_portfolio_row(del_sel)
                        st.session_state.portfolio_df = _load_portfolio_raw()
                    if ok: st.success(f"✅ {msg}")
                    else:  st.error(msg)

    st.divider()

    # 兩張圖共用同一批有效持股：有投入成本 且 有損益資料
    chart_data = active[active['n_總投入'] > 0].copy()
    chart_data['n_rate'] = chart_data['n_損益'] / chart_data['n_總投入'] * 100

    l_col, r_col = st.columns([1, 1.2])
    with l_col:
        st.subheader("🥧 資產配置 (成本)")
        pie_data = chart_data[['股票代號','n_總投入']].copy()
        if cash_in > 0:
            pie_data = pd.concat([pie_data,
                pd.DataFrame([{'股票代號':'現金','n_總投入':cash_in}])])
        if not pie_data.empty:
            # 計算百分比，決定是否在切片內顯示標籤
            total_val = pie_data['n_總投入'].sum()
            pie_data['pct'] = pie_data['n_總投入'] / total_val * 100

            fig_pie = px.pie(pie_data, values='n_總投入', names='股票代號', hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Alphabet)
            # 小切片（<3%）不顯示文字，靠圖例辨識
            text_labels = [
                f"<b>{row['股票代號']}</b><br>{row['pct']:.1f}%"
                if row['pct'] >= 3 else ""
                for _, row in pie_data.iterrows()
            ]
            fig_pie.update_traces(
                text=text_labels,
                textinfo='text',
                textposition='inside',
                insidetextorientation='auto',
                insidetextfont=dict(size=13),
            )
            fig_pie.update_layout(
                showlegend=True,
                legend=dict(
                    orientation='v',
                    x=1.02, y=0.5,
                    font=dict(size=12),
                ),
                height=560,
                margin=dict(l=0, r=150, t=20, b=20),
            )
            st.plotly_chart(fig_pie, use_container_width=True)

    with r_col:
        st.subheader("📊 個股報酬率排行 (%)")
        if not chart_data.empty:
            bar_p = chart_data.sort_values(by='n_rate', ascending=True)
            fig_bar = px.bar(bar_p, x="n_rate", y="股票代號", orientation='h',
                             text_auto='.2f', color="股票代號",
                             color_discrete_sequence=px.colors.qualitative.Alphabet)
            fig_bar.update_layout(
                height=max(550, len(bar_p)*35),
                xaxis_title="報酬率 (%)", yaxis_title=None,
                showlegend=False, font=dict(size=15))
            fig_bar.update_traces(textposition='outside', textfont=dict(size=14))
            st.plotly_chart(fig_bar, use_container_width=True)


# ══════════════════════════════════════════════
#  TAB 2: 分批買入模板
# ══════════════════════════════════════════════
with tab2:
    st.markdown("## 🎯 分批買入策略看板")
    st.markdown("""
    > **策略邏輯：** 在目標股票達到不同跌幅時依序進場，共5批次。
    > 全部填滿後均成本 ≈ P₀ × 0.87，停損設在均成本 -22%，目標為均成本 ×2（R:R ≈ 1:4.5）。
    """)
    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.info("**T1** P₀ → 35% 資金")
    col_info2.info("**T2** -10% → 25% | **T3** -20% → 20%")
    col_info3.info("**T4** -30% → 12% | **T5** -38% → 8%")

    # ── Discord 設定 ──────────────────────────────────────
    disc_webhook  = get_setting('webhook_url', '')
    disc_interval = get_setting('check_interval_minutes', 5)
    disc_cooldown = get_setting('cooldown_hours', 4)
    disc_t1       = get_setting('alert_t1', False)
    disc_stop     = get_setting('alert_stop', True)

    # 若 Streamlit secrets 有設定，優先使用
    try:
        disc_webhook = st.secrets.get("discord_webhook", disc_webhook)
    except Exception:
        pass

    with st.expander("🔔 Discord 即時通知設定", expanded=not bool(disc_webhook)):
        st.markdown("""
        **設定後，在本機執行 `啟動監控.bat` 即可在背景自動偵測，股價一到就傳 Discord 給你。**

        取得 Webhook URL 步驟：
        1. 打開 Discord → 進入你要接收通知的頻道
        2. 頻道設定 ⚙️ → 整合 → Webhook → 新建 Webhook → 複製 URL
        """)
        wh_col, int_col, cd_col = st.columns([3,1,1])
        with wh_col:
            new_webhook = st.text_input("Discord Webhook URL",
                value=disc_webhook, type="password",
                placeholder="https://discord.com/api/webhooks/...",
                key="disc_webhook")
        with int_col:
            new_interval = st.number_input("檢查間隔 (分鐘)", min_value=1, max_value=60,
                value=int(disc_interval), key="disc_interval")
        with cd_col:
            new_cooldown = st.number_input("通知冷卻 (小時)", min_value=1, max_value=24,
                value=int(disc_cooldown), key="disc_cooldown")

        opt_col1, opt_col2 = st.columns(2)
        with opt_col1:
            new_alert_t1 = st.checkbox("通知 T1 進場點（第一批）",
                value=disc_t1, key="disc_t1")
        with opt_col2:
            new_alert_stop = st.checkbox("通知停損跌破警告",
                value=disc_stop, key="disc_stop")

        save_col, test_col = st.columns(2)
        with save_col:
            if st.button("💾 儲存通知設定", key="save_discord"):
                new_settings = dict(st.session_state.settings)
                new_settings.update({
                    'webhook_url':             new_webhook,
                    'check_interval_minutes':  new_interval,
                    'cooldown_hours':          new_cooldown,
                    'alert_t1':                new_alert_t1,
                    'alert_stop':              new_alert_stop,
                })
                with st.spinner("儲存中…"):
                    save_settings(new_settings)
                    st.session_state.settings = new_settings
                st.success("✅ 設定已儲存！")
        with test_col:
            if st.button("📨 傳送測試通知", key="test_discord"):
                test_wh = new_webhook or disc_webhook
                if not test_wh:
                    st.warning("請先填入 Webhook URL")
                else:
                    test_payload = {"embeds": [{"title": "✅ 股票監控系統 — 連線測試",
                        "description": "通知設定成功！當股價觸及分批進場點位，你會在這裡收到提醒。",
                        "color": 0x00AA44,
                        "fields": [
                            {"name":"監控間隔","value":f"每 {new_interval} 分鐘","inline":True},
                            {"name":"通知冷卻","value":f"{new_cooldown} 小時內不重複","inline":True},
                        ],
                        "footer": {"text": f"測試時間：{__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}"}
                    }]}
                    try:
                        r = requests.post(test_wh, json=test_payload, timeout=8)
                        if r.status_code in [200, 204]:
                            st.success("📨 測試通知已發出，請查看 Discord！")
                        else:
                            st.error(f"發送失敗 (HTTP {r.status_code})")
                    except Exception as e:
                        st.error(f"發送失敗：{e}")

        if disc_webhook:
            st.success("🟢 Discord 通知已設定。請執行「啟動監控.bat」開啟背景監控。")
        else:
            st.warning("🔴 尚未設定 Webhook URL，背景監控無法發送通知。")

    st.divider()

    # ── 新增自選股 ────────────────────────────────────────
    with st.expander("➕ 新增自選股到看板", expanded=False):
        na_col1, na_col2, na_col3, na_col4 = st.columns(4)
        with na_col1: new_ticker = st.text_input("股票代號 (e.g. SMR)", key="new_ticker").upper().strip()
        with na_col2: new_name   = st.text_input("股票名稱", key="new_name")
        with na_col3: new_p0     = st.number_input("P₀ 第一批進場價 ($)", min_value=0.01, value=100.0, key="new_p0")
        with na_col4: new_budget = st.number_input("總資金分配 (USD)", min_value=100.0, value=5000.0, key="new_budget")
        new_note = st.text_input("備註（選填）", key="new_note")

        if st.button("✅ 加入看板"):
            if new_ticker:
                new_row = {
                    "股票代號": new_ticker, "股票名稱": new_name,
                    "P₀ (第一批進場價)": str(new_p0), "總資金 (USD)": str(new_budget),
                    "T1已填":"False","T2已填":"False","T3已填":"False",
                    "T4已填":"False","T5已填":"False", "備註": new_note,
                }
                wl_df = pd.concat([st.session_state.watchlist_df,
                                   pd.DataFrame([new_row])], ignore_index=True)
                with st.spinner("儲存中…"):
                    save_watchlist(wl_df)
                    st.session_state.watchlist_df = wl_df
                st.success(f"✅ {new_ticker} 已加入看板！")
                st.rerun()
            else:
                st.warning("請輸入股票代號")

    # ── 自選股看板 ────────────────────────────────────────
    wl_df = st.session_state.watchlist_df.copy()

    if wl_df.empty or len(wl_df) == 0:
        st.info("👆 目前看板為空，請先新增自選股。")
    else:
        refresh_col, save_col, _ = st.columns([1, 1, 3])
        with refresh_col:
            if st.button("🔄 更新即時股價"):
                fetch_price.clear()
                st.rerun()
        with save_col:
            save_wl_btn = st.button("💾 儲存看板變更")

        st.markdown("---")
        filled_map = {}   # idx → filled_updated list

        for idx, row in wl_df.iterrows():
            ticker     = str(row.get("股票代號","")).strip()
            name       = str(row.get("股票名稱","")).strip()
            p0_raw     = str(row.get("P₀ (第一批進場價)","0")).replace("$","").replace(",","").strip()
            budget_raw = str(row.get("總資金 (USD)","0")).replace("$","").replace(",","").strip()
            note       = str(row.get("備註","")).strip()
            try:    p0     = float(p0_raw)
            except: p0     = 0.0
            try:    budget = float(budget_raw)
            except: budget = 0.0

            filled = [
                str(row.get("T1已填","False")).strip().lower() in ["true","1","yes","✓"],
                str(row.get("T2已填","False")).strip().lower() in ["true","1","yes","✓"],
                str(row.get("T3已填","False")).strip().lower() in ["true","1","yes","✓"],
                str(row.get("T4已填","False")).strip().lower() in ["true","1","yes","✓"],
                str(row.get("T5已填","False")).strip().lower() in ["true","1","yes","✓"],
            ]
            if not ticker or p0 <= 0:
                continue

            current_price = fetch_price(ticker)
            tranche_rows, summary = calc_tranches(p0, budget, filled)

            title_col, del_col = st.columns([6, 1])
            with title_col:
                price_display = f"**現價 ${current_price:.2f}**" if current_price else "**現價 取得失敗**"
                change_pct    = ((current_price - p0) / p0 * 100) if current_price else None
                change_str    = f"（較P₀ {change_pct:+.1f}%）" if change_pct is not None else ""
                if current_price and current_price <= p0 * TRANCHES[4]["price_ratio"]:   icon = "🔴"
                elif current_price and current_price <= p0 * TRANCHES[3]["price_ratio"]: icon = "🟠"
                elif current_price and current_price <= p0 * TRANCHES[2]["price_ratio"]: icon = "🟡"
                elif current_price and current_price <= p0 * TRANCHES[1]["price_ratio"]: icon = "🟢"
                else: icon = "⚪"
                st.markdown(f"### {icon} {ticker}  {name}　　{price_display} {change_str}")
                if note:
                    st.caption(f"備註：{note}")
            with del_col:
                if st.button("🗑️ 刪除", key=f"del_{idx}_{ticker}"):
                    wl_df = wl_df.drop(index=idx).reset_index(drop=True)
                    with st.spinner("刪除中…"):
                        save_watchlist(wl_df)
                        st.session_state.watchlist_df = wl_df
                    st.success(f"{ticker} 已刪除")
                    st.rerun()

            t_cols = st.columns([1.2,2,1.5,1.5,1.8,1.5,1.2])
            for col_h, header in zip(t_cols, ["批次","說明","進場價","配置 (USD)","預計股數","狀態","已填"]):
                col_h.markdown(f"**{header}**")

            filled_updated = list(filled)
            for i, t in enumerate(tranche_rows):
                price_target = t["進場價"]
                is_active = current_price is not None and current_price <= price_target * 1.005
                if filled[i]:          status = "✅ 已進場"
                elif is_active:        status = "🚨 **進場點到！**"
                else:                  status = "⏳ 等待中"
                row_cols = st.columns([1.2,2,1.5,1.5,1.8,1.5,1.2])
                row_cols[0].write(t["批次"])
                row_cols[1].write(t["說明"])
                row_cols[2].write(f"**${price_target:.2f}**")
                row_cols[3].write(f"${t['配置金額']:,.0f}")
                row_cols[4].write(f"{t['預計股數']:.2f} 股")
                row_cols[5].markdown(status)
                new_fill = row_cols[6].checkbox("", value=filled[i], key=f"fill_{ticker}_{i}_{idx}")
                filled_updated[i] = new_fill

            filled_map[idx] = filled_updated

            rows_updated, summary_updated = calc_tranches(p0, budget, filled_updated)
            st.markdown("")
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            kpi1.metric("📊 均成本（已填）",   f"${summary_updated['avg_cost']:.2f}" if summary_updated['avg_cost'] else "—")
            kpi2.metric("🛑 停損位 (-22%)",   f"${summary_updated['stop_loss']:.2f}" if summary_updated['stop_loss'] else "—")
            kpi3.metric("🎯 目標價 (×2)",     f"${summary_updated['target']:.2f}" if summary_updated['target'] else "—")
            kpi4.metric("📐 全滿均成本",        f"${summary_updated['full_avg']:.2f}", help="假設5批全部填滿的理論均成本")
            kpi5.metric("📐 全滿停損",          f"${summary_updated['full_stop']:.2f}")

            if current_price and summary_updated['stop_loss'] and current_price <= summary_updated['stop_loss']:
                st.error(f"⚠️ **{ticker} 現價已跌破停損位 ${summary_updated['stop_loss']:.2f}！請確認是否執行停損。**")
            st.divider()

        # 儲存看板變更
        if save_wl_btn:
            for idx, fu in filled_map.items():
                for i in range(5):
                    wl_df.at[idx, f"T{i+1}已填"] = str(fu[i])
            with st.spinner("同步到 Google Sheets…"):
                save_watchlist(wl_df)
                st.session_state.watchlist_df = wl_df
            st.success("✅ 看板已儲存！")

    with st.expander("📖 策略說明與計算方式"):
        st.markdown("""
        ### 5批次買入模板說明

        | 批次 | 進場條件 | 資金佔比 | 說明 |
        |------|----------|----------|------|
        | T1   | P₀（第一批價格）| 35% | 主要倉位，趨勢初步確認 |
        | T2   | P₀ × 0.90 (-10%) | 25% | 小幅回調加碼 |
        | T3   | P₀ × 0.80 (-20%) | 20% | 中幅修正加碼 |
        | T4   | P₀ × 0.70 (-30%) | 12% | 深度修正加碼 |
        | T5   | P₀ × 0.62 (-38%) | 8%  | 極限加碼（小量） |

        **全部填滿後：**
        - 理論均成本 ≈ P₀ × 0.869
        - 停損位 = 均成本 × 0.78（約 -22%）
        - 目標價 = 均成本 × 2.0
        - **風報比 ≈ 1 : 4.5**（損22%賺100%）
        - 損益平衡勝率 = 18%

        **顏色圖示說明：**
        - ⚪ 股價在T1之上（尚未觸發）
        - 🟢 股價觸及T2區間（-10%）
        - 🟡 股價觸及T3區間（-20%）
        - 🟠 股價觸及T4區間（-30%）
        - 🔴 股價觸及T5區間（-38%）

        > 股價資料來源：Yahoo Finance，每 2 分鐘自動更新。
        """)


# ══════════════════════════════════════════════
#  TAB 3: 交易
# ══════════════════════════════════════════════
with tab3:
    st.markdown("## 💼 交易操作")

    buy_tab, sell_tab, log_tab = st.tabs(["📈 買入", "📉 賣出", "📋 交易紀錄"])

    # ── 買入 ──────────────────────────────────
    with buy_tab:
        st.markdown("### 📈 買入股票")
        st.caption("執行後會更新 Google Sheets 的股數與均價，並扣除現金餘額")

        existing_tickers = st.session_state.portfolio_df['股票代號'].tolist() if not st.session_state.portfolio_df.empty else []

        buy_mode = st.radio("股票", ["現有持股", "新股票"], horizontal=True, key="buy_mode")

        if buy_mode == "現有持股":
            if not existing_tickers:
                st.info("目前無持股資料")
            else:
                b_ticker = st.selectbox("選擇股票", existing_tickers, key="b_ticker_exist")
                pos_info = get_position_info(b_ticker) if b_ticker else None
                if pos_info:
                    st.info(f"目前持有：**{pos_info['shares']:.2f} 股**，均價 **${pos_info['avg_cost']:.4f}**")
        else:
            bc1, bc2, bc3 = st.columns(3)
            with bc1: b_ticker = st.text_input("股票代號", key="b_ticker_new").upper().strip()
            with bc2: b_name   = st.text_input("股票名稱", key="b_name_new")
            with bc3: b_market = st.selectbox("市場", ["美股","台股"], key="b_market_new")
            b_currency = st.selectbox("幣別", ["USD","TWD"], key="b_curr_new")
            pos_info = None

        st.markdown("---")
        input_by = st.radio("輸入方式", ["依股數", "依金額"], horizontal=True, key="buy_input_by")
        rate = USD_RATE if (pos_info and pos_info.get('currency','USD')=='USD') or buy_mode=="新股票" else 1

        bi1, bi2 = st.columns(2)
        with bi1:
            b_price = st.number_input("成交價 ($)", min_value=0.01, value=10.0, step=0.01, key="b_price")
        with bi2:
            if input_by == "依股數":
                b_shares = st.number_input("買入股數", min_value=0.01, value=10.0, step=1.0, key="b_shares")
                b_amount = b_shares * b_price
            else:
                b_amount_input = st.number_input("投入金額 (USD)", min_value=1.0, value=1000.0, step=100.0, key="b_amount")
                b_shares = round(b_amount_input / b_price, 4) if b_price > 0 else 0
                b_amount = b_amount_input

        # 預覽
        st.markdown("---")
        prev1, prev2, prev3, prev4 = st.columns(4)
        prev1.metric("買入股數", f"{b_shares:.4f} 股")
        prev2.metric("成交金額 (USD)", f"${b_amount:,.2f}")
        prev3.metric("成交金額 (TWD)", f"NT${b_amount * USD_RATE:,.0f}")
        if pos_info and pos_info['shares'] > 0:
            new_s = pos_info['shares'] + b_shares
            new_avg = round((pos_info['avg_cost'] * pos_info['shares'] + b_price * b_shares) / new_s, 4)
            prev4.metric("買後均價", f"${new_avg:.4f}",
                         delta=f"{new_avg - pos_info['avg_cost']:+.4f}")
        else:
            prev4.metric("買後均價", f"${b_price:.4f}")

        if st.button("✅ 確認買入", type="primary", key="confirm_buy"):
            if not b_ticker:
                st.error("請填入股票代號")
            elif b_shares <= 0 or b_price <= 0:
                st.error("股數與成交價不能為 0")
            else:
                curr = 'USD'
                if buy_mode == "現有持股" and pos_info:
                    curr = pos_info.get('currency', 'USD')
                    n_name, n_market = pos_info.get('name',''), pos_info.get('market','美股')
                else:
                    n_name, n_market = b_name, b_market
                with st.spinner("更新中…"):
                    ok, msg = execute_buy(b_ticker, b_shares, b_price, n_name, n_market, curr)
                    st.session_state.portfolio_df = _load_portfolio_raw()
                if ok:
                    st.success(f"✅ {msg}")
                    load_transaction_log.clear()
                else:
                    st.error(msg)

    # ── 賣出 ──────────────────────────────────
    with sell_tab:
        st.markdown("### 📉 賣出股票")
        st.caption("執行後會更新股數、記錄平倉備註、累加已實現損益，並加回現金餘額")

        active_tickers = st.session_state.portfolio_df[
            st.session_state.portfolio_df['股數'].apply(lambda x: clean_val(x) > 0)
        ]['股票代號'].tolist()

        if not active_tickers:
            st.info("目前無持股")
        else:
            s_ticker = st.selectbox("選擇要賣出的股票", active_tickers, key="s_ticker")
            s_pos = get_position_info(s_ticker) if s_ticker else None

            if s_pos:
                si1, si2, si3 = st.columns(3)
                si1.metric("目前持股", f"{s_pos['shares']:.4f} 股")
                si2.metric("均價", f"${s_pos['avg_cost']:.4f}")
                si3.metric("已實現損益", f"NT${s_pos['realized']:+,.0f}")

                st.markdown("---")
                sc1, sc2 = st.columns(2)
                with sc1:
                    s_price = st.number_input("賣出價格 ($)", min_value=0.01,
                                              value=round(s_pos['avg_cost'], 2),
                                              step=0.01, key="s_price")
                with sc2:
                    s_shares = st.number_input("賣出股數", min_value=0.01,
                                               max_value=float(s_pos['shares']),
                                               value=float(s_pos['shares']),
                                               step=1.0, key="s_shares")

                # 預覽損益
                rate = USD_RATE if s_pos.get('currency','USD') == 'USD' else 1
                realized_preview = round((s_price - s_pos['avg_cost']) * s_shares * rate, 0)
                remaining_preview = s_pos['shares'] - s_shares

                st.markdown("---")
                sp1, sp2, sp3, sp4 = st.columns(4)
                sp1.metric("賣出金額 (USD)", f"${s_shares * s_price:,.2f}")
                sp2.metric("賣出金額 (TWD)", f"NT${s_shares * s_price * rate:,.0f}")
                color = "normal" if realized_preview >= 0 else "inverse"
                sp3.metric("本次已實現損益", f"NT${realized_preview:+,.0f}",
                           delta=f"NT${realized_preview:+,.0f}", delta_color=color)
                sp4.metric("賣後剩餘股數", f"{remaining_preview:.4f} 股")

                if st.button("✅ 確認賣出", type="primary", key="confirm_sell"):
                    with st.spinner("更新中…"):
                        ok, msg = execute_sell(s_ticker, s_shares, s_price)
                        st.session_state.portfolio_df = _load_portfolio_raw()
                    if ok:
                        st.success(f"✅ {msg}")
                        load_transaction_log.clear()
                    else:
                        st.error(msg)

    # ── 交易紀錄 ──────────────────────────────
    with log_tab:
        st.markdown("### 📋 交易紀錄")
        if st.button("🔄 重新整理", key="refresh_log"):
            load_transaction_log.clear()

        log_df = load_transaction_log()
        if log_df.empty:
            st.info("尚無交易紀錄。執行買入或賣出後，紀錄會自動出現在這裡。")
        else:
            # 最新的在上面
            log_df = log_df.iloc[::-1].reset_index(drop=True)
            def color_action(val):
                if val == '買': return 'color: #4CAF50; font-weight: bold'
                if val == '賣': return 'color: #FF5252; font-weight: bold'
                return ''
            def color_cash(val):
                try:
                    v = float(str(val).replace(',',''))
                    return 'color: #4CAF50' if v > 0 else 'color: #FF5252'
                except: return ''
            st.dataframe(
                log_df.style
                    .map(color_action, subset=['操作'])
                    .map(color_cash, subset=['現金變動(TWD)']),
                use_container_width=True, height=500
            )
            st.caption(f"共 {len(log_df)} 筆紀錄")
