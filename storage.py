# storage.py
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import List, Dict, Any

# path setup
ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"
SESSIONS_CSV = DATA_DIR / "sessions.csv"

# CSV fields
CSV_FIELDS = [
    "start_ts", "end_ts", "duration_s", "tag", "note", "date", "ended_by"
]

def ensure_data_files(default_config: Dict[str, Any]) -> None:
    """
    check and create data directory and files if they do not exist.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # config.json
    if not CONFIG_PATH.exists():
        save_config(default_config)

    # sessions.csv： create with header if not existing or empty
    if not SESSIONS_CSV.exists() or SESSIONS_CSV.stat().st_size == 0:
        with SESSIONS_CSV.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg: Dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def append_session(session: Dict[str, Any]) -> None:
    """
    append a session record to sessions.csv.
    if some fields are missing, use empty string as default.
    """
    row = {k: session.get(k, "") for k in CSV_FIELDS}
    with SESSIONS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writerow(row)

def load_sessions() -> List[Dict[str, Any]]:
    """
    read all session records from sessions.csv.
    """
    if not SESSIONS_CSV.exists():
        return []
    with SESSIONS_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        out = []
        for r in reader:
            # 做基本类型转换
            r["start_ts"]  = int(r.get("start_ts", 0) or 0)
            r["end_ts"]    = int(r.get("end_ts", 0)   or 0)
            r["duration_s"]= int(r.get("duration_s",0) or 0)
            out.append(r)
        return out
