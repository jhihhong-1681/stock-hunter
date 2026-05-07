"""
股票分批買入監控器 — Discord 通知版
每 CHECK_INTERVAL 分鐘抓一次 Yahoo Finance 股價
當股價觸及 T2~T5 進場點位時，透過 Discord Webhook 發送提醒
"""

import os, json, time, requests
import pandas as pd
from datetime import datetime, timedelta

# ── 設定檔路徑 ──────────────────────────────────────────────────────────
BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(BASE_DIR, "watchlist_alerts.csv")
CONFIG_FILE    = os.path.join(BASE_DIR, "discord_config.json")
ALERT_LOG_FILE = os.path.join(BASE_DIR, "alert_history.json")

# ── 分批模板參數（與 app.py 一致）────────────────────────────────────────
TRANCHES = [
    {"name": "T1", "price_ratio": 1.00, "weight": 0.35, "label": "第1批 P₀"},
    {"name": "T2", "price_ratio": 0.90, "weight": 0.25, "label": "第2批 -10%"},
    {"name": "T3", "price_ratio": 0.80, "weight": 0.20, "label": "第3批 -20%"},
    {"name": "T4", "price_ratio": 0.70, "weight": 0.12, "label": "第4批 -30%"},
    {"name": "T5", "price_ratio": 0.62, "weight": 0.08, "label": "第5批 -38%"},
]
STOP_RATIO   = 0.78
TARGET_RATIO = 2.00

# ── 讀取設定 ─────────────────────────────────────────────────────────────
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "webhook_url": "",
        "check_interval_minutes": 5,
        "cooldown_hours": 4,
        "alert_t1": False,   # T1 通常是主動進場，預設不通知
        "alert_stop": True,  # 停損跌破一定通知
    }

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

# ── 通知歷史（防重複）────────────────────────────────────────────────────
def load_alert_log() -> dict:
    if os.path.exists(ALERT_LOG_FILE):
        with open(ALERT_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_alert_log(log: dict):
    with open(ALERT_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

def already_alerted(log: dict, key: str, cooldown_hours: int) -> bool:
    """檢查是否在冷卻時間內已發過通知"""
    if key not in log:
        return False
    last_time = datetime.fromisoformat(log[key])
    return datetime.now() - last_time < timedelta(hours=cooldown_hours)

def mark_alerted(log: dict, key: str):
    log[key] = datetime.now().isoformat()

# ── Yahoo Finance 抓現價 ──────────────────────────────────────────────────
def fetch_price(ticker: str) -> float | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=8)
        data = r.json()
        closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        return round(closes[-1], 2) if closes else None
    except Exception as e:
        print(f"  [警告] 無法抓取 {ticker} 股價：{e}")
        return None

# ── Discord Webhook 發送 ──────────────────────────────────────────────────
def send_discord(webhook_url: str, embeds: list):
    """發送 Discord embed 訊息"""
    payload = {"embeds": embeds}
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code not in [200, 204]:
            print(f"  [Discord 錯誤] Status {r.status_code}: {r.text[:200]}")
            return False
        return True
    except Exception as e:
        print(f"  [Discord 錯誤] {e}")
        return False

def build_tranche_embed(ticker: str, name: str, tranche_idx: int,
                        current_price: float, tranche_price: float,
                        budget_usd: float, p0: float,
                        avg_cost: float | None, stop_loss: float | None,
                        target: float | None) -> dict:
    """建立進場點通知的 Discord embed"""
    t = TRANCHES[tranche_idx]
    alloc = round(budget_usd * t["weight"], 0)
    shares = round(alloc / tranche_price, 2)

    # 顏色：T2=綠、T3=黃、T4=橙、T5=紅
    colors = {0: 0x808080, 1: 0x00AA44, 2: 0xFFCC00, 3: 0xFF8800, 4: 0xFF3131}
    color = colors.get(tranche_idx, 0x3498DB)

    fields = [
        {"name": "📍 現價",        "value": f"**${current_price:.2f}**",          "inline": True},
        {"name": "🎯 進場目標價",  "value": f"**${tranche_price:.2f}**",          "inline": True},
        {"name": "💰 建議買入",    "value": f"${alloc:,.0f} ≈ {shares:.1f} 股",   "inline": True},
        {"name": "📊 P₀ 基準價",   "value": f"${p0:.2f}",                          "inline": True},
        {"name": "📐 佔比",        "value": f"{t['weight']*100:.0f}% 總資金",      "inline": True},
        {"name": "總資金分配",     "value": f"${budget_usd:,.0f} USD",             "inline": True},
    ]

    if avg_cost:
        fields += [
            {"name": "📈 已填批次均成本", "value": f"${avg_cost:.2f}",  "inline": True},
            {"name": "🛑 停損位 (-22%)",  "value": f"${stop_loss:.2f}", "inline": True},
            {"name": "🎯 目標價 (×2)",    "value": f"${target:.2f}",    "inline": True},
        ]

    return {
        "title": f"🚨 {ticker} {t['name']} 進場點已到！",
        "description": f"**{name or ticker}** 股價已觸及 **{t['label']}** 買入區間",
        "color": color,
        "fields": fields,
        "footer": {"text": f"股票監控系統 | {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
        "thumbnail": {"url": f"https://logo.clearbit.com/finance.yahoo.com"},
    }

def build_stop_embed(ticker: str, name: str, current_price: float,
                     stop_loss: float, avg_cost: float, p0: float) -> dict:
    """建立停損警告的 Discord embed"""
    drawdown = (current_price - stop_loss) / stop_loss * 100
    return {
        "title": f"⚠️ {ticker} 已跌破停損位！",
        "description": f"**{name or ticker}** 現價已跌破停損點，請確認是否執行停損！",
        "color": 0xFF0000,
        "fields": [
            {"name": "📍 現價",      "value": f"**${current_price:.2f}**", "inline": True},
            {"name": "🛑 停損位",    "value": f"${stop_loss:.2f}",         "inline": True},
            {"name": "📉 幅度",      "value": f"{drawdown:+.1f}%",         "inline": True},
            {"name": "📊 均成本",    "value": f"${avg_cost:.2f}",          "inline": True},
            {"name": "📊 P₀ 基準",   "value": f"${p0:.2f}",               "inline": True},
        ],
        "footer": {"text": f"股票監控系統 | {datetime.now().strftime('%Y-%m-%d %H:%M')}"},
    }

# ── 均成本計算（與 app.py 一致）──────────────────────────────────────────
def calc_avg_cost(p0: float, budget: float, filled: list[bool]):
    total_cost, total_shares = 0.0, 0.0
    for i, t in enumerate(TRANCHES):
        if i < len(filled) and filled[i]:
            price = p0 * t["price_ratio"]
            alloc = budget * t["weight"]
            shares = alloc / price if price > 0 else 0
            total_cost   += price * shares
            total_shares += shares
    if total_shares > 0:
        avg = round(total_cost / total_shares, 2)
        return avg, round(avg * STOP_RATIO, 2), round(avg * TARGET_RATIO, 2)
    return None, None, None

# ── 主監控迴圈 ────────────────────────────────────────────────────────────
def run_monitor():
    print("=" * 55)
    print("  📡 股票分批買入監控器已啟動")
    print("=" * 55)

    while True:
        cfg = load_config()
        webhook = cfg.get("webhook_url", "").strip()
        interval_min = int(cfg.get("check_interval_minutes", 5))
        cooldown_h   = int(cfg.get("cooldown_hours", 4))
        alert_t1     = cfg.get("alert_t1", False)
        alert_stop   = cfg.get("alert_stop", True)

        if not webhook:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  尚未設定 Discord Webhook URL，請在 app.py 介面中設定後重啟。")
            time.sleep(60)
            continue

        # 讀取自選股清單
        if not os.path.exists(WATCHLIST_FILE):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️  找不到 watchlist_alerts.csv")
            time.sleep(interval_min * 60)
            continue

        wl = pd.read_csv(WATCHLIST_FILE, dtype=str).fillna("")
        if wl.empty:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 自選股清單為空，等待 {interval_min} 分鐘...")
            time.sleep(interval_min * 60)
            continue

        log = load_alert_log()
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 開始掃描 {len(wl)} 支股票...")

        for _, row in wl.iterrows():
            ticker = str(row.get("股票代號", "")).strip()
            name   = str(row.get("股票名稱", "")).strip()
            try:
                p0     = float(str(row.get("P₀ (第一批進場價)", "0")).replace("$","").replace(",",""))
                budget = float(str(row.get("總資金 (USD)", "0")).replace("$","").replace(",",""))
            except:
                continue

            if not ticker or p0 <= 0:
                continue

            filled = [
                str(row.get("T1已填","False")).strip().lower() in ["true","1","yes"],
                str(row.get("T2已填","False")).strip().lower() in ["true","1","yes"],
                str(row.get("T3已填","False")).strip().lower() in ["true","1","yes"],
                str(row.get("T4已填","False")).strip().lower() in ["true","1","yes"],
                str(row.get("T5已填","False")).strip().lower() in ["true","1","yes"],
            ]

            current = fetch_price(ticker)
            if current is None:
                continue

            print(f"  {ticker:<8} 現價 ${current:.2f}")

            avg_cost, stop_loss, target = calc_avg_cost(p0, budget, filled)

            embeds_to_send = []

            # ── 檢查每個批次 ──
            for i, t in enumerate(TRANCHES):
                if i == 0 and not alert_t1:
                    continue   # T1 預設不通知

                tranche_price = round(p0 * t["price_ratio"], 2)

                # 已填就不再提醒
                if i < len(filled) and filled[i]:
                    continue

                # 價格觸及（允許 0.5% 誤差）
                if current <= tranche_price * 1.005:
                    key = f"{ticker}_{t['name']}"
                    if not already_alerted(log, key, cooldown_h):
                        print(f"    🚨 {t['name']} 進場點觸發！${current:.2f} ≤ ${tranche_price:.2f}")
                        embed = build_tranche_embed(
                            ticker, name, i, current, tranche_price,
                            budget, p0, avg_cost, stop_loss, target
                        )
                        embeds_to_send.append(embed)
                        mark_alerted(log, key)

            # ── 停損警告 ──
            if alert_stop and stop_loss and current <= stop_loss:
                key = f"{ticker}_STOP"
                if not already_alerted(log, key, max(1, cooldown_h // 2)):
                    print(f"    ⚠️  停損觸發！${current:.2f} ≤ ${stop_loss:.2f}")
                    embeds_to_send.append(
                        build_stop_embed(ticker, name, current, stop_loss, avg_cost, p0)
                    )
                    mark_alerted(log, key)

            # ── 發送（Discord 最多一次 10 個 embed）──
            if embeds_to_send:
                for chunk in [embeds_to_send[j:j+10] for j in range(0, len(embeds_to_send), 10)]:
                    ok = send_discord(webhook, chunk)
                    print(f"    Discord 通知：{'✅ 已發送' if ok else '❌ 失敗'}")

        save_alert_log(log)
        print(f"  ✅ 掃描完成，下次檢查：{interval_min} 分鐘後")
        time.sleep(interval_min * 60)


if __name__ == "__main__":
    run_monitor()
