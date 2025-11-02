# app_state.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from storage import (
    load_config, save_config,
    load_goals,  save_goals,
    load_sessions, append_session,
    ensure_data_files,
)

# Ensure data/ exists & seed minimal files (uses your current storage.py behavior)
ensure_data_files({
    "work_min": 25,
    "short_break_min": 5,
    "long_break_min": 15,
    "long_every": 4,
    "theme": "light",
    "default_tag": "Reading",
    "tags": ["Reading", "Work", "Health", "Other"]
})

@dataclass
class AppState:
    """Holds shared app data and provides simple pub-sub for UI refresh."""
    config: Dict[str, Any] = field(default_factory=load_config)
    goals: Dict[str, Any] = field(default_factory=load_goals)
    sessions: List[Dict[str, Any]] = field(default_factory=load_sessions)

    _subscribers: List[Callable[[], None]] = field(default_factory=list, repr=False)

    # ---------- pub-sub ----------
    def subscribe(self, fn: Callable[[], None]) -> None:
        """Register a callback to be invoked whenever sessions/config/goals change."""
        self._subscribers.append(fn)

    def _notify(self) -> None:
        for fn in list(self._subscribers):
            try:
                fn()
            except Exception:
                pass

    # ---------- persistence helpers ----------
    def save_config(self) -> None:
        save_config(self.config)

    def save_goals(self) -> None:
        save_goals(self.goals)

    def reload_sessions(self) -> None:
        self.sessions = load_sessions()
        self._notify()

    def add_session(self, session: Dict[str, Any]) -> None:
        """Append a session to CSV and refresh in-memory list."""
        append_session(session)
        self.reload_sessions()
