"""從報牌文字解析期權合約（標的、Call/Put、行使價、到期日、限價、口數）。

支援：OCC 代碼（RIG270617C00004000）、英文與中文敘述（"$4 strike"、"expiring on June 17, 2027"、"limit of $2.50"、
"4 美元的行使價"、"2.50 美元的限額"、"購買兩份合約" 等）。解析不到的欄位回 None，由頁面請使用者補。
"""
from __future__ import annotations

import re
from datetime import date, datetime

_OCC = re.compile(r"\b([A-Z]{1,6})(\d{2})(\d{2})(\d{2})([CP])(\d{8})\b")
_CN_NUM = {"一": 1, "兩": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_option_text(text: str) -> dict:
    out = {"symbol": None, "kind": None, "strike": None, "expiry": None, "premium": None, "qty": None}
    if not text or not text.strip():
        return out
    m = _OCC.search(text)
    if m:
        out["symbol"] = m.group(1)
        out["expiry"] = date(2000 + int(m.group(2)), int(m.group(3)), int(m.group(4)))
        out["kind"] = "Call" if m.group(5) == "C" else "Put"
        out["strike"] = int(m.group(6)) / 1000
    if out["symbol"] is None:
        m = re.search(r"(?:ticker|symbol|股票代號|代號)\s*(?:is|為|:|：)?\s*[:：]?\s*\$?([A-Z]{1,6})\b", text)
        if m:
            out["symbol"] = m.group(1)
    if out["strike"] is None:
        for pat in (r"\$\s*(\d+(?:\.\d+)?)\s*strike", r"strike(?:\s*price)?\s*(?:of|is|:)?\s*\$\s*(\d+(?:\.\d+)?)",
                    r"(\d+(?:\.\d+)?)\s*(?:美元|元|USD)的?\s*行使價", r"行使價\s*(?:為|是|:|：)?\s*\$?\s*(\d+(?:\.\d+)?)"):
            m = re.search(pat, text, re.I)
            if m:
                out["strike"] = _num(m.group(1))
                break
    if out["kind"] is None:
        low = text.lower()
        if re.search(r"\bcalls?\b|呼叫|買權|看漲", low):
            out["kind"] = "Call"
        elif re.search(r"\bputs?\b|賣權|看跌", low):
            out["kind"] = "Put"
    if out["expiry"] is None:
        m = re.search(r"(?:expir\w*|到期)[^A-Za-z0-9]{0,20}(?:on\s+)?([A-Z][a-z]+\.?\s+\d{1,2},?\s+\d{4})", text)
        if m:
            raw = re.sub(r"[.,]", "", m.group(1))
            for fmt in ("%B %d %Y", "%b %d %Y"):
                try:
                    out["expiry"] = datetime.strptime(raw, fmt).date()
                    break
                except ValueError:
                    pass
        if out["expiry"] is None:
            m = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})", text)
            if m:
                out["expiry"] = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    for pat in (r"limit(?:\s*(?:price|order))?\s*(?:of|at|:)?\s*\$\s*(\d+(?:\.\d+)?)", r"(\d+(?:\.\d+)?)\s*(?:美元|元|USD)的?\s*限額",
                r"限(?:價|額)\s*(?:為|是|:|：)?\s*\$?\s*(\d+(?:\.\d+)?)", r"限額[^0-9]{0,10}(\d+(?:\.\d+)?)\s*美元"):
        m = re.search(pat, text, re.I)
        if m:
            out["premium"] = _num(m.group(1))
            break
    m = re.search(r"(\d+)\s*(?:contracts?|份合約|口)", text, re.I)
    if m:
        out["qty"] = int(m.group(1))
    else:
        m = re.search(r"([一兩二三四五六七八九十])\s*(?:份|口)", text)
        if m:
            out["qty"] = _CN_NUM[m.group(1)]
        elif re.search(r"pairs? of contracts", text, re.I):
            out["qty"] = 2
    return out
