"""
TAIFEX 台指期三大法人未平倉 抓取腳本
每日由 GitHub Actions 執行，結果存到 data/futures_institutional_latest.json
"""
import requests
import pandas as pd
import json
import io
import sys
from datetime import date, timedelta
from pathlib import Path

OUTPUT = Path(__file__).parent.parent / "data" / "futures_institutional_latest.json"

CONTRACTS = {
    "TXF": "臺股期貨(台指期)",
    "MXF": "小型臺指期貨(小台)",
}

INST_KEYWORDS = {
    "自營商": "自營商",
    "投信": "投信",
    "外資及陸資": "外資",
    "外資": "外資",
}

def get_last_trading_day():
    d = date.today()
    for _ in range(7):
        if d.weekday() < 5:
            return d
        d -= timedelta(days=1)
    return date.today()

def fetch_one(query_date: date, commodity: str) -> dict | None:
    date_str = query_date.strftime("%Y/%m/%d")
    date_enc = date_str.replace("/", "%2F")
    url = (
        f"https://www.taifex.com.tw/cht/3/futContractsDate"
        f"?queryStartDate={date_enc}&queryEndDate={date_enc}&commodityId={commodity}"
    )
    hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Referer": "https://www.taifex.com.tw/cht/3/futContractsDate",
    }
    try:
        r = requests.get(url, headers=hdrs, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  HTTP 失敗 {commodity}: {e}")
        return None

    try:
        tables = pd.read_html(io.StringIO(r.text), thousands=",")
    except Exception as e:
        print(f"  HTML parse 失敗 {commodity}: {e}")
        return None

    # Find the table that contains institutional data
    target = None
    for tbl in tables:
        flat = tbl.to_string()
        if "外資" in flat and "自營商" in flat:
            target = tbl
            break

    if target is None:
        print(f"  找不到法人表格 {commodity}")
        return None

    # Flatten multi-level columns if needed
    if isinstance(target.columns, pd.MultiIndex):
        target.columns = [" ".join(str(c) for c in col).strip() for col in target.columns]

    # Convert all to string for searching
    result = {}
    for _, row in target.iterrows():
        row_vals = [str(v) for v in row.values]
        row_str = " ".join(row_vals)

        matched_inst = None
        for keyword, inst_name in INST_KEYWORDS.items():
            if keyword in row_str:
                matched_inst = inst_name
                break

        if matched_inst is None:
            continue

        # Extract all integers from the row
        nums = []
        for v in row_vals:
            cleaned = str(v).replace(",", "").replace("+", "").strip()
            try:
                nums.append(int(cleaned))
            except ValueError:
                nums.append(None)

        # Remove leading None values (商品名稱, 身份別 columns)
        int_nums = [n for n in nums if n is not None]

        # Expected order: [成交多, 成交多金額, 成交空, 成交空金額, 成交淨, 成交淨金額,
        #                   OI多, OI多金額, OI空, OI空金額, OI淨, OI淨金額]
        if len(int_nums) >= 12:
            result[matched_inst] = {
                "trade_long":  int_nums[0],
                "trade_short": int_nums[2],
                "trade_net":   int_nums[4],
                "oi_long":     int_nums[6],
                "oi_short":    int_nums[8],
                "oi_net":      int_nums[10],
            }
        elif len(int_nums) >= 6:
            # Only OI data
            result[matched_inst] = {
                "trade_long":  None,
                "trade_short": None,
                "trade_net":   None,
                "oi_long":     int_nums[0],
                "oi_short":    int_nums[2],
                "oi_net":      int_nums[4],
            }

    return result if result else None


def main():
    trading_day = get_last_trading_day()
    print(f"抓取日期：{trading_day}")

    payload = {
        "date": trading_day.strftime("%Y/%m/%d"),
        "contracts": {},
    }

    for code, name in CONTRACTS.items():
        print(f"  fetching {code} ({name})...")
        data = fetch_one(trading_day, code)
        if data:
            payload["contracts"][code] = {"name": name, "institutions": data}
            print(f"  OK {code}: {list(data.keys())}")
        else:
            print(f"  NG {code}: 無資料")

    if not payload["contracts"]:
        print("所有合約均無資料，退出。")
        sys.exit(1)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已儲存：{OUTPUT}（{len(payload['contracts'])} 個合約）")


if __name__ == "__main__":
    main()