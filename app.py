import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os

import gspread
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
@st.cache_resource
def get_spreadsheet():
    try:
        # Streamlit Cloud: 從 secrets 讀取
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    except Exception:
        # 本機開發: 從 credentials.json 讀取
        creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)

# ══════════════════════════════════════════════
#  資料讀取函式（帶快取）
# ══════════════════════════════════════════════
@st.cache_data(ttl=120)
def _load_portfolio_raw():
    sh = get_spreadsheet()
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
    sh = get_spreadsheet()
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
    sh = get_spreadsheet()
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
    sh = get_spreadsheet()
    ws = sh.worksheet('美股持有庫存(每日更新)')
    ws.clear()
    ws.update([df.columns.tolist()] + df.fillna('').values.tolist())
    _load_portfolio_raw.clear()

def save_watchlist(df):
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet('自選股監控')
    except Exception:
        ws = sh.add_worksheet(title='自選股監控', rows=200, cols=15)
    ws.clear()
    ws.update([df.columns.tolist()] + df.fillna('').values.tolist())
    _load_watchlist_raw.clear()

def save_settings(settings_dict):
    sh = get_spreadsheet()
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
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        return round(closes[-1], 2) if closes else None
    except Exception:
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

tab1, tab2 = st.tabs(["📊 投資組合", "🎯 分批買入模板"])

# ══════════════════════════════════════════════
#  TAB 1: 投資組合
# ══════════════════════════════════════════════
with tab1:
    df = st.session_state.portfolio_df.copy()
    saved_cash = get_setting('cash_balance', 0.0)

    col_edit, col_cash_input = st.columns([3, 1])
    with col_cash_input:
        cash_in = st.number_input("💵 目前現金餘額 (台幣)：", min_value=0.0, value=saved_cash)

    st.subheader("✍️ 數據編輯區")
    edit_df = st.data_editor(df[COLS], num_rows="dynamic", use_container_width=True)

    if st.button("💾 儲存並更新數據"):
        tmp = edit_df.copy()
        for i in range(len(tmp)):
            rate = 31.0 if "USD" in str(tmp.at[i,'幣別']).upper() else 1.0
            s   = clean_val(tmp.at[i,'股數'])
            cp  = clean_val(tmp.at[i,'成本均價'])
            np_ = clean_val(tmp.at[i,'現價'])
            if s > 0:
                inv = s * cp * rate
                val = s * np_ * rate
                tmp.at[i,'總投入'] = f"{inv:.0f}"
                tmp.at[i,'現值']   = f"{val:.0f}"
                diff = val - inv
                tmp.at[i,'損益']   = f"{diff:.2f}"
                tmp.at[i,'報酬率'] = f"{(diff/inv*100):.2f}%" if inv != 0 else "0.00%"
            else:
                for c in ['總投入','現值','損益','報酬率']:
                    tmp.at[i, c] = ""

        with st.spinner("💾 同步到 Google Sheets…"):
            save_portfolio(tmp)
            new_settings = dict(st.session_state.settings)
            new_settings['cash_balance'] = str(cash_in)
            save_settings(new_settings)
            st.session_state.portfolio_df = tmp
            st.session_state.settings = new_settings

        st.success("✅ 數據已成功同步到 Google Sheets！")
        st.rerun()

    # KPI 計算
    calc = edit_df.copy()
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
        st.dataframe(active[COLS].style.applymap(style_profit,
            subset=['損益','報酬率','已實現損益']), use_container_width=True)

    st.divider()
    l_col, r_col = st.columns([1, 1.2])
    with l_col:
        st.subheader("🥧 資產配置 (成本)")
        pie_data = active[['股票代號','n_總投入']].copy()
        if cash_in > 0:
            pie_data = pd.concat([pie_data,
                pd.DataFrame([{'股票代號':'現金','n_總投入':cash_in}])])
        if not pie_data.empty:
            fig_pie = px.pie(pie_data, values='n_總投入', names='股票代號', hole=0.4,
                             color_discrete_sequence=px.colors.qualitative.Alphabet)
            fig_pie.update_traces(
                textinfo='percent+label',
                texttemplate='<b>%{label}</b><br>%{percent:.1%}',
                insidetextfont=dict(size=18), outsidetextfont=dict(size=18))
            fig_pie.update_layout(showlegend=False, height=550)
            st.plotly_chart(fig_pie, use_container_width=True)

    with r_col:
        st.subheader("📊 個股報酬率排行 (%)")
        if not active.empty:
            active['n_rate'] = active['n_損益'] / active['n_總投入'] * 100
            bar_p = active.sort_values(by='n_rate', ascending=True)
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
