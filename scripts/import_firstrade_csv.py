"""把 Firstrade 匯出的歷史交易 CSV 併進 portfolio-calendar/trades.js。

用法：python scripts/import_firstrade_csv.py <Firstrade 匯出的 CSV>

只取 RecordType=Trade 的買賣（BUY / SELL）；到期、轉帳、利息、入金等不是成交，略過。
欄位格式跟桌機排程（FIRSTRADE_TASK.md 第 4b 步）寫的一致，重複的成交（同日期、代號、買賣方向、合約、數量、價格）不會再加。
CSV 含個人交易資料，不要放進 repo，只把產生的 trades.js 提交（提交前先確認要公開）。
"""
import csv
import json
from collections import Counter
import re
import sys
from pathlib import Path

TRADES_JS = Path(__file__).resolve().parent.parent / "portfolio-calendar" / "trades.js"
OPT = re.compile(r"^(CALL|PUT)\s+(\S+)\s+(\d{2})/(\d{2})/(\d{2})\s+([\d.]+)\s", re.I)
EXEC = re.compile(r"EXEC TIME:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})")


def convert(row: dict) -> dict | None:
    if row["RecordType"] != "Trade" or row["Action"] not in ("BUY", "SELL"):
        return None
    desc = row["Description"]
    buy = row["Action"] == "BUY"
    m = OPT.match(desc.strip())
    qty = abs(float(row["Quantity"]))
    qty = int(qty) if qty == int(qty) else qty
    price = float(row["Price"])
    t = EXEC.search(desc)
    if m:
        cp, sym, mo, d, y, strike = m.groups()
        return {
            "date": row["TradeDate"], "time": t.group(2) if t else None,
            "side": "Buy Open" if buy else "Sell Close", "symbol": sym, "type": "option",
            "description": f"{sym} {mo}/{d}/20{y} {float(strike):.2f} {cp.capitalize()}",
            "qty": qty, "price": price,
        }
    return {
        "date": row["TradeDate"], "time": t.group(2) if t else None,
        "side": "買進" if buy else "賣出", "symbol": row["Symbol"].strip(), "type": "stock",
        "description": None, "qty": qty, "price": price,
    }


def key(t: dict) -> tuple:
    # 時間不納入：桌機排程抄的是訂單更新時間，CSV 是成交時間，同一筆可能差幾秒。
    return (t["date"], t["symbol"], t["side"].lower().startswith("buy") or t["side"] == "買進", t["description"], t["qty"], t["price"])


def fmt(t: dict) -> str:
    return "  { " + ", ".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in t.items()) + " }"


def main(csv_path: str) -> None:
    text = TRADES_JS.read_text(encoding="utf-8")
    head, body = text.split("window.TRADES = [", 1)
    existing = [json.loads(re.sub(r"([{,]\s*)([A-Za-z_]\w*):", r'\1"\2":', line.strip().rstrip(","))) for line in body.splitlines() if line.strip().startswith("{")]
    # 只跟「已經在檔案裡的」比對：同一天同價同量的兩筆成交是兩筆，不能互相當成重複。
    have = Counter(key(t) for t in existing)
    added = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            t = convert(row)
            if not t:
                continue
            if have[key(t)] > 0:
                have[key(t)] -= 1
            else:
                added.append(t)
    allt = sorted(existing + added, key=lambda t: (t["date"], t["time"] or ""))
    TRADES_JS.write_text(head + "window.TRADES = [\n" + ",\n".join(fmt(t) for t in allt) + "\n];\n", encoding="utf-8")
    print(f"原有 {len(existing)} 筆，新增 {len(added)} 筆，共 {len(allt)} 筆（{allt[0]['date']} ～ {allt[-1]['date']}）")


if __name__ == "__main__":
    main(sys.argv[1])
