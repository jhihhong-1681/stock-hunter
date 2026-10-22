"""選股評分的完整歷史（每天一個 gz 檔，data/score_history/YYYY-MM-DD.json.gz）。純函式，不依賴網路。

目的：驗證分數有沒有預測力。每天存「所有進入進場區的候選」（不只前 30 名），含各分項分數、判定、類型把握度，
之後 scripts/score_returns.py 補算後續 5／20／60／120 個交易日報酬，做消融比較。
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

HIST_DIR = Path(__file__).resolve().parent.parent / "data" / "score_history"


def _r(x, n=4):
    return None if x is None else round(float(x), n)


def compact(c: dict) -> dict:
    p, m = c.get("pillars") or {}, c.get("metrics") or {}
    return {"s": c["symbol"], "k": c.get("kind"), "kc": c.get("kind_conf"), "p": _r(c.get("price"), 2), "dd": _r(c.get("dd")), "vol": _r(c.get("vol")),
            "f": _r(p.get("基本面"), 1), "pr": _r(p.get("價格"), 1), "fl": _r(p.get("預期資金"), 1), "q": _r(c.get("quant_score"), 1),
            "v": c.get("verdict"), "vt": bool(c.get("veto")), "sec": c.get("sector"), "mc": _r(c.get("mcap"), 0), "yoy": _r(m.get("營收年增率")),
            "ed": c.get("earnings_days")}


def save_day(day: str, cands: list, meta: dict | None = None, hist_dir: Path = HIST_DIR):
    hist_dir.mkdir(parents=True, exist_ok=True)
    doc = {"date": day, "meta": meta or {}, "cands": [compact(c) for c in cands], "news": {}}
    with gzip.open(hist_dir / f"{day}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


def load_day(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def attach_news(day: str, scores: dict, hist_dir: Path = HIST_DIR) -> bool:
    """把當天的新聞評分補進歷史檔（新聞評分在選股掃描之後才產生）。回傳是否有更新。"""
    path = hist_dir / f"{day}.json.gz"
    if not path.exists():
        return False
    doc = load_day(path)
    doc["news"] = {s: {"score": v.get("score"), "veto": bool(v.get("veto"))} for s, v in scores.items() if v.get("asof") and v.get("score") is not None}
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    return True


def load_all(hist_dir: Path = HIST_DIR) -> list:
    return [load_day(p) for p in sorted(hist_dir.glob("*.json.gz"))] if hist_dir.exists() else []
