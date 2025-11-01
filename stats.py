# stats.py
from __future__ import annotations
from typing import Dict, List, Tuple
from datetime import datetime, date, timedelta
import numpy as np

def _parse_ymd(d: str) -> date:
    # "YYYY-MM-DD" -> date
    return datetime.strptime(d, "%Y-%m-%d").date()

def _to_minutes_one_decimal(x: int | float) -> float:
    # seconds -> minutes (one decimal)
    return round(float(x) / 60.0, 1)

def _sessions_to_arrays(sessions: List[dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    returns:
      dates_arr: np.array[date]
      durations_s: np.array[int] (seconds)
      tags_arr: np.array[str]
    """
    if not sessions:
        return np.array([], dtype=object), np.array([], dtype=int), np.array([], dtype=object)

    dates_arr = np.array([_parse_ymd(s["date"]) for s in sessions], dtype=object)
    durations_s = np.array([int(s.get("duration_s", 0)) for s in sessions], dtype=int)
    tags_arr = np.array([str(s.get("tag", "Other")) for s in sessions], dtype=object)
    return dates_arr, durations_s, tags_arr

# ---------- weekly ----------
def week_bounds(ref: date) -> Tuple[date, date]:
    """
    for gien date, return (monday, sunday) of that week
    """
    wd = ref.isoweekday()  # 1..7 (Mon..Sun)
    monday = ref - timedelta(days=wd - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday

def weekly_totals_by_tag(sessions: List[dict], ref: date | None = None) -> Tuple[Dict[str,float], str]:
    """
    within the week of the given reference date
    Calculate the total minutes for each tag
    return: totals: {tag -> minutes}, label: 'YYYY-Wxx (Mon DD - Sun DD)'
    """
    if ref is None:
        ref = date.today()
    dates_arr, durations_s, tags_arr = _sessions_to_arrays(sessions)
    if dates_arr.size == 0:
        m, s = week_bounds(ref)
        label = f"{ref.isocalendar().year}-W{ref.isocalendar().week:02d}  ({m.strftime('%b %d')}-{s.strftime('%b %d')})"
        return {}, label

    mon, sun = week_bounds(ref)
    mask = (dates_arr >= mon) & (dates_arr <= sun)
    if not np.any(mask):
        label = f"{ref.isocalendar().year}-W{ref.isocalendar().week:02d}  ({mon.strftime('%b %d')}-{sun.strftime('%b %d')})"
        return {}, label

    sel_durations = durations_s[mask]
    sel_tags = tags_arr[mask]

    # Compute sums per tag
    tags_unique, inv = np.unique(sel_tags, return_inverse=True)
    sums_s = np.zeros(tags_unique.shape[0], dtype=float)
    np.add.at(sums_s, inv, sel_durations.astype(float))

    totals = {t: _to_minutes_one_decimal(s) for t, s in zip(tags_unique.tolist(), sums_s.tolist())}
    label = f"{ref.isocalendar().year}-W{ref.isocalendar().week:02d}  ({mon.strftime('%b %d')}–{sun.strftime('%b %d')})"
    return totals, label

# ---------- monthly ----------
def month_bounds(y: int, m: int) -> Tuple[date, date]:
    start = date(y, m, 1)
    if m == 12:
        end = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(y, m + 1, 1) - timedelta(days=1)
    return start, end

def monthly_totals_by_tag(sessions: List[dict], y: int, m: int) -> Tuple[Dict[str,float], str]:
    """
    within the given month and year
    Calculate the total minutes for each tag
    return: (totals: {tag -> minutes}, label: 'YYYY-MM')
    """
    dates_arr, durations_s, tags_arr = _sessions_to_arrays(sessions)
    if dates_arr.size == 0:
        return {}, f"{y}-{m:02d}"

    start, end = month_bounds(y, m)
    mask = (dates_arr >= start) & (dates_arr <= end)
    if not np.any(mask):
        return {}, f"{y}-{m:02d}"

    sel_durations = durations_s[mask]
    sel_tags = tags_arr[mask]

    tags_unique, inv = np.unique(sel_tags, return_inverse=True)
    sums_s = np.zeros(tags_unique.shape[0], dtype=float)
    np.add.at(sums_s, inv, sel_durations.astype(float))

    totals = {t: _to_minutes_one_decimal(s) for t, s in zip(tags_unique.tolist(), sums_s.tolist())}
    return totals, f"{y}-{m:02d}"
