"""
每日由 GitHub Actions 執行，抓取 TWSE 三大法人資料存成 JSON。
"""
import requests, json, urllib3, sys
from datetime import date, timedelta
from pathlib import Path

urllib3.disable_warnings()

OUTPUT = Path(__file__).parent.parent / "data" / "institutional_latest.json"

INVESTOR_MAP = {
    "外陸資買賣超股數(不含外資自營商)": "外資",
    "投信買賣超股數": "投信",
    "自營商買賣超股數(自行買賣)": "自營商(自行)",
    "自營商買賣超股數(避險)": "自營商(避險)",
    "三大法人買賣超股數": "三大法人合計",
}

def fetch(target_date: date):
    date_str = target_date.strftime("%Y%m%d")
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Accept": "application/json, */*",
        "Referer": "https://www.twse.com.tw/zh/trading/fund/T86.html",
        "X-Requested-With": "XMLHttpRequest",
    })
    try:
        s.get("https://www.twse.com.tw/zh/trading/fund/T86.html", verify=False, timeout=8)
    except Exception:
        pass

    urls = [
        f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json",
        f"https://www.twse.com.tw/fund/T86?response=json&date={date_str}&selectType=ALLBUT0999",
    ]
    for url in urls:
        try:
            r = s.get(url, verify=False, timeout=20)
            if r.status_code != 200 or not r.content:
                continue
            data = r.json()
            if data.get("stat") == "OK" and data.get("data"):
                return data["fields"], data["data"], target_date.isoformat()
        except Exception as e:
            print(f"  failed {url}: {e}")
    return None, None, None

def main():
    # 嘗試今天，若無資料往前找最近三個交易日
    for offset in range(4):
        d = date.today() - timedelta(days=offset)
        if d.weekday() >= 5:
            continue
        print(f"Trying {d}...")
        fields, rows, fetched_date = fetch(d)
        if fields and rows:
            print(f"  Got {len(rows)} rows for {fetched_date}")
            # 整理欄位
            rename = {"證券代號": "代號", "證券名稱": "名稱"}
            rename.update(INVESTOR_MAP)
            idx = {f: i for i, f in enumerate(fields)}
            records = []
            n_fields = len(fields)
            for row in rows:
                # 跳過欄數不符的合計行
                if len(row) != n_fields:
                    continue
                # 跳過代號不是數字的行（例如「合計」等）
                code = row[idx.get("證券代號", 0)] if "證券代號" in idx else ""
                if not str(code).strip().replace(" ", "").isdigit():
                    continue
                rec = {}
                for orig, new in rename.items():
                    if orig not in idx:
                        continue
                    val = row[idx[orig]]
                    if new in INVESTOR_MAP.values():
                        try:
                            val = int(str(val).replace(",", ""))
                        except Exception:
                            val = 0
                    rec[new] = val
                records.append(rec)

            OUTPUT.parent.mkdir(exist_ok=True)
            payload = {"date": fetched_date, "records": records}
            OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  Saved to {OUTPUT}")
            return
    print("No data found for the past 4 days.")
    sys.exit(1)

if __name__ == "__main__":
    main()
