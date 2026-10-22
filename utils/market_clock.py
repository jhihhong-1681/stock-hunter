"""美股盤中抓到的「今天」那根日線是未收盤的，不能當收盤價用。純函式。"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def drop_partial_bar(df, now: datetime | None = None):
    """DataFrame（index 為日期）：若最後一列是美東「今天」且還沒收盤（16:15 前），把它拿掉。"""
    if df is None or len(df) == 0:
        return df
    now_et = (now or datetime.now(ET)).astimezone(ET)
    last = df.index[-1]
    if last.date() == now_et.date() and (now_et.weekday() >= 5 or now_et.hour * 60 + now_et.minute < 16 * 60 + 15):
        return df.iloc[:-1]
    return df
