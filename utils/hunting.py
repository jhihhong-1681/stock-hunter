"""Hunting 清單：研究監控日誌裡阿紘想跟的推薦，按一個鈕加進「準備下單清單」。

存放：跟「未成交訂單不再追蹤」共用同一支 Apps Script 中繼（scripts/journal_relay.gs）、同一個 Google Sheet 的
「PendingRemoved」分頁，但 key 用 "hunt|" 開頭、後面接 JSON（一筆推薦的快照）。這樣不用重新部署 Apps Script；
未成交訂單的遮罩只拿 key 去比對，多出來的 hunt| 列不會影響它。移除 = 呼叫既有的 restorePending 刪掉那一列。
repo 是公開的：這裡只放程式，網址和金鑰一律在 Streamlit secrets。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

PREFIX = "hunt|"


def make_item(a: dict) -> dict:
    """從一篇文章（監控日誌的 article）取出下單要用的欄位。"""
    e = a.get("entryExit") or {}
    ident = a.get("url") or f'{a.get("title")}|{a.get("publishedAtUtc")}'
    return {
        "id": ident,
        "ticker": e.get("ticker"),
        "action": e.get("action"),
        "instrument": e.get("instrument"),
        "contract": e.get("contract"),
        "entry": e.get("entry"),
        "target": e.get("target"),
        "stop": e.get("stop"),
        "title": a.get("title"),
        "url": a.get("url"),
        "site": a.get("site"),
        "published": a.get("publishedAtUtc"),
        "added": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def can_hunt(a: dict) -> bool:
    e = a.get("entryExit") or {}
    return bool(e.get("ticker")) and "買進" in (e.get("action") or "")


def _key(item: dict) -> str:
    return PREFIX + json.dumps(item, ensure_ascii=False, separators=(",", ":"))


def load(api_url: str, api_key: str) -> list[dict]:
    """目前 Hunting 清單（同一篇文章只留一筆），新加的在前。"""
    import requests
    r = requests.get(api_url, params={"what": "removed", "key": api_key}, timeout=20)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "讀取失敗"))
    items, seen = [], set()
    for k in data["keys"]:
        if not k.startswith(PREFIX):
            continue
        try:
            it = json.loads(k[len(PREFIX):])
        except ValueError:
            continue
        if it.get("id") not in seen:
            seen.add(it.get("id"))
            it["_key"] = k
            items.append(it)
    return sorted(items, key=lambda x: x.get("added") or "", reverse=True)


def _post(api_url: str, api_key: str, action: str, pkey: str) -> None:
    import requests
    r = requests.post(api_url, data=json.dumps({"key": api_key, "action": action, "pkey": pkey}),
                      headers={"Content-Type": "text/plain"}, timeout=20)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("error", "寫入失敗"))


def add(api_url: str, api_key: str, item: dict) -> None:
    _post(api_url, api_key, "removePending", _key(item))


def remove(api_url: str, api_key: str, item: dict) -> None:
    _post(api_url, api_key, "restorePending", item["_key"])


def first_price(text: str | None) -> float | None:
    """進場價文字（例如「限價不超過8.25美元/口」「50%現價約$348進場…」）裡的第一個數字。"""
    m = re.search(r"\d+(?:\.\d+)?", (text or "").replace(",", ""))
    return float(m.group(0)) if m else None
