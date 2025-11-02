# ui_timer.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
import time
from datetime import datetime
from typing import Optional

from timer import Timer  # reuse your existing timer.py

DEFAULT_MIN, DEFAULT_SEC = 25, 0

class TimerTab:
    """
    Timer page:
    - Big clock with minutes/seconds presets
    - Editable Tag combobox (+ persist to config tags)
    - Note input
    - Start / Pause / Finish / Reset
    - Accumulates active time across pauses
    - On finish, writes a session via AppState.add_session(...)
    """
    def __init__(self, parent, state):
        self.state = state
        self.frame = ttk.Frame(parent)

        # ------- title -------
        tk.Label(self.frame, text="Pomotask", font=("Segoe UI", 22, "bold")).pack(pady=(16, 8))

        # ------- big time display -------
        self.time_var = tk.StringVar(value=f"{DEFAULT_MIN:02d}:{DEFAULT_SEC:02d}")
        tk.Label(self.frame, textvariable=self.time_var, font=("Consolas", 52, "bold")).pack(pady=6)

         # ------- Pomodoro Auto Mode toggle -------
        self.auto_mode = tk.BooleanVar(value=False)
        self.chk_auto = ttk.Checkbutton(
            self.frame, text="Enable Pomodoro Auto Mode", variable=self.auto_mode,
            command=self._on_auto_mode_toggled)
        self.chk_auto.pack(pady=(0, 8))

        # ------- presets (minutes + seconds) -------
        pfrm = tk.Frame(self.frame); pfrm.pack(pady=8)
        tk.Label(pfrm, text="Minutes:").grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.min_var = tk.IntVar(value=DEFAULT_MIN)
        tk.Spinbox(pfrm, from_=0, to=180, width=4,
                   textvariable=self.min_var, font=("Segoe UI", 12)).grid(row=0, column=1, padx=(0, 12))
        tk.Label(pfrm, text="Seconds:").grid(row=0, column=2, sticky="e", padx=(0, 6))
        self.sec_var = tk.IntVar(value=DEFAULT_SEC)
        tk.Spinbox(pfrm, from_=0, to=59, width=4,
                   textvariable=self.sec_var, font=("Segoe UI", 12)).grid(row=0, column=3)

        # ------- meta (tag + note) -------
        cfrm = ttk.LabelFrame(self.frame, text="Session Meta", padding=8)
        cfrm.pack(padx=10, pady=10, fill="x")

        tk.Label(cfrm, text="Tag:").grid(row=0, column=0, sticky="e", padx=(0, 6))
        tags = list(self.state.config.get("tags", ["Reading", "Other"])) or ["Other"]
        self.tag_var = tk.StringVar(value=tags[0])
        self.tag_combo = ttk.Combobox(cfrm, textvariable=self.tag_var, values=tags,
                                      state="normal", width=22)  # editable
        self.tag_combo.grid(row=0, column=1, sticky="w")

        ttk.Button(cfrm, text="Add Tag", command=self._add_tag).grid(row=0, column=2, padx=6)
        ttk.Button(cfrm, text="Delete",  command=self._delete_tag).grid(row=0, column=3)

        tk.Label(cfrm, text="Note:").grid(row=1, column=0, sticky="ne", padx=(0, 6), pady=(8,0))
        self.note_text = tk.Text(cfrm, width=60, height=3)
        self.note_text.grid(row=1, column=1, columnspan=3, sticky="w", pady=(8,0))

        # ------- controls -------
        bfrm = tk.Frame(self.frame); bfrm.pack(pady=12)
        self.btn_start  = ttk.Button(bfrm, text="Start",  command=self.on_start)
        self.btn_pause  = ttk.Button(bfrm, text="Pause",  command=self.on_pause,  state="disabled")
        self.btn_finish = ttk.Button(bfrm, text="Finish", command=self.on_finish, state="disabled")
        self.btn_reset  = ttk.Button(bfrm, text="Reset",  command=self.on_reset)
        self.btn_start.grid(row=0, column=0, padx=6)
        self.btn_pause.grid(row=0, column=1, padx=6)
        self.btn_finish.grid(row=0, column=2, padx=6)
        self.btn_reset.grid(row=0, column=3, padx=6)

        # hotkeys
        self.frame.bind_all("<space>", self._toggle_start_pause)
        self.frame.bind_all("<Escape>", lambda e: self.on_reset())
        self.frame.bind_all("<Return>", lambda e: self.on_finish() if self._session_active else None)

        # last session preview
        prev_box = ttk.LabelFrame(self.frame, text="Last Session", padding=8)
        prev_box.pack(padx=10, pady=8, fill="x")
        self.last_session_var = tk.StringVar(value="(no session yet)")
        tk.Label(prev_box, textvariable=self.last_session_var,
                 justify="left", anchor="w", wraplength=820).pack(fill="x", anchor="w")

        # timer engine
        self.timer = Timer(on_tick=self._on_tick, on_finish=self._on_timer_finished)
        self.timer.set_seconds(self._preset_seconds())
        self._on_tick(self.timer.remaining)

        # react to preset changes when not running
        self.min_var.trace_add("write", self._on_preset_changed)
        self.sec_var.trace_add("write", self._on_preset_changed)

        tk.Label(self.frame, text="Space: Start/Pause   Enter: Finish   Esc: Reset",
                 font=("Segoe UI", 9), fg="#666").pack(side="bottom", pady=6)

        # session runtime state
        self._session_active: bool = False
        self._current_tag: Optional[str] = None
        self._current_note: str = ""
        self._current_start_ts: Optional[float] = None
        self._last_run_start_ts: Optional[float] = None
        self._accum_active_s: int = 0

        # --- Pomodoro Auto Mode state ---
        self._pomo_phase = "work"  # "work" | "short" | "long"
        self._pomo_cycle_count = 0

    # ---------- Pomodoro Auto Mode ----------
    def _on_auto_mode_toggled(self):
        """Enable/disable auto mode UI behavior."""
        if self.auto_mode.get():
            self.min_var.set(self.state.config.get("work_min", 25))
            self.sec_var.set(0)
            # tokens for enabling/disabling Variable traces
            self._trace_min_id = self.min_var.trace_add("write", lambda *args: self._on_preset_changed())
            self._trace_sec_id = self.sec_var.trace_add("write", lambda *args: self._on_preset_changed())

        else:
            # Allow manual preset editing again
            self.min_var.trace_add("write", self._on_preset_changed)
            self.sec_var.trace_add("write", self._on_preset_changed)
        self._set_phase("work")

    def _set_phase(self, phase: str):
        """Switch to a Pomodoro phase (work/short/long) and reset timer length."""
        self._pomo_phase = phase
        conf = self.state.config
        mins = {
            "work": conf.get("work_min", 25),
            "short": conf.get("short_break_min", 5),
            "long": conf.get("long_break_min", 15)
        }.get(phase, 25)
        if self.auto_mode.get():
            self.timer.reset(seconds=int(mins * 60))
            self._on_tick(self.timer.remaining)
            title = {"work":"Work", "short":"Short Break", "long":"Long Break"}[phase]
            self.time_var.set(f"{mins:02d}:00")
            self._update_title(title)

    def _update_title(self, phase_name: str):
        """Change window title text according to phase."""
        root = self.frame.winfo_toplevel()
        root.title(f"Pomotask — {phase_name}")

    # ---------- helpers ----------
    def _now(self) -> float: return time.time()

    def _preset_seconds(self) -> int:
        try: m = int(self.min_var.get())
        except Exception: m = DEFAULT_MIN
        try: s = int(self.sec_var.get())
        except Exception: s = DEFAULT_SEC
        m = max(0, min(180, m)); s = max(0, min(59, s))
        return max(1, m*60 + s)

    def _normalize_tag(self, t: str) -> str:
        return (t or "").strip()[:30] or "Other"

    def _save_tags(self):
        tags = list(self.tag_combo["values"])
        self.state.config["tags"] = tags
        self.state.save_config()

    def _add_tag(self):
        t = self._normalize_tag(self.tag_var.get())
        values = list(self.tag_combo["values"])
        if t not in values:
            values.append(t)
            self.tag_combo["values"] = values
            self._save_tags()
        self.tag_var.set(t)

    def _delete_tag(self):
        t = self._normalize_tag(self.tag_var.get())
        if self._session_active and t == (self._current_tag or ""):
            messagebox.showwarning("Cannot delete", "Tag is used by the active session.")
            return
        values = [x for x in self.tag_combo["values"] if x != t]
        if not values:
            values = ["Other"]
        self.tag_combo["values"] = values
        self.tag_var.set(values[0])
        self._save_tags()

    # ---------- timer callbacks ----------
    def _on_tick(self, remaining: int) -> None:
        mm, ss = divmod(remaining, 60)
        self.time_var.set(f"{mm:02d}:{ss:02d}")

    def _on_timer_finished(self) -> None:
        # Add the last running segment
        if self._session_active and self._last_run_start_ts is not None:
            self._accum_active_s += int(round(self._now() - self._last_run_start_ts))
            self._last_run_start_ts = None
        self._finalize_session(auto=True)
        self._set_buttons(False)
        try:
            messagebox.showinfo("Time's up", "Pomodoro finished!")
        except Exception:
            pass
        self.timer.reset(seconds=self._preset_seconds())
        self._on_tick(self.timer.remaining)

    # --- Auto Mode transition ---
    def _advance_pomodoro_cycle(self):
        """Advance to next Pomodoro phase automatically."""
        conf = self.state.config
        long_every = int(conf.get("long_every", 4))

        if self._pomo_phase == "work":
            self._pomo_cycle_count += 1
            if self._pomo_cycle_count % long_every == 0:
                self._set_phase("long")
            else:
                self._set_phase("short")
        else:
            self._set_phase("work")

        # auto start next phase
        self.on_start()

    # ---------- events ----------
    def _on_preset_changed(self, *args):
        if not self.timer.running:
            self.timer.set_seconds(self._preset_seconds())
            self._on_tick(self.timer.remaining)

    def _toggle_start_pause(self, _=None):
        if self.timer.running: self.on_pause()
        else: self.on_start()

    def on_start(self):
        if self.timer.running: return
        now = self._now()
        if not self._session_active:
            # first start
            t = self._normalize_tag(self.tag_var.get())
            self._add_tag()  # ensure persist
            self._current_tag = t
            self._current_note = self.note_text.get("1.0", "end").strip()
            self._current_start_ts = now
            self._accum_active_s = 0
            self._last_run_start_ts = now
            self._session_active = True
        else:
            # resume from pause
            if self._last_run_start_ts is None:
                self._last_run_start_ts = now
        self.timer.start(self.frame.winfo_toplevel())
        self._set_buttons(True)

    def on_pause(self):
        if self.timer.running:
            self.timer.pause()
            now = self._now()
            if self._last_run_start_ts is not None:
                self._accum_active_s += int(round(now - self._last_run_start_ts))
                self._last_run_start_ts = None
        self._set_buttons(False)

    def on_finish(self):
        if not self._session_active: return
        if self.timer.running:
            self.timer.pause()
            now = self._now()
            if self._last_run_start_ts is not None:
                self._accum_active_s += int(round(now - self._last_run_start_ts))
                self._last_run_start_ts = None
        self._finalize_session(auto=False)
        self.timer.reset(seconds=self._preset_seconds())
        self._on_tick(self.timer.remaining)
        self._set_buttons(False)

    def on_reset(self):
        self.timer.reset(seconds=self._preset_seconds())
        self._on_tick(self.timer.remaining)
        self._set_buttons(False)
        # clear session state (no record)
        self._session_active = False
        self._current_tag = None
        self._current_note = ""
        self._current_start_ts = None
        self._last_run_start_ts = None
        self._accum_active_s = 0

    def _set_buttons(self, running: bool):
        self.btn_start.config(state="disabled" if running else "normal")
        self.btn_pause.config(state="normal" if running else "disabled")
        self.btn_finish.config(state="normal" if running else "disabled")

    # ---------- finalize ----------
    def _finalize_session(self, auto: bool):
        if not self._session_active:
            return
        end_ts = self._now()
        duration_s = max(0, int(self._accum_active_s))
        start_ts = self._current_start_ts or end_ts
        session = {
            "start_ts": int(start_ts),
            "end_ts": int(end_ts),
            "duration_s": int(duration_s),
            "tag": self._current_tag or "Other",
            "note": self._current_note,
            "date": datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d"),
            "ended_by": "auto" if auto else "manual",
        }
        # preview
        mm, ss = divmod(duration_s, 60)
        note_line = " ".join((self._current_note or "").split())
        if len(note_line) > 140:
            note_line = note_line[:139] + "…"
        self.last_session_var.set(
            f"- Tag: {session['tag']}\n"
            f"- Duration: {mm}m {ss}s\n"
            f"- Date: {session['date']}  ({session['ended_by']})\n"
            f"- Note: {note_line or '(empty)'}"
        )
        # persist via AppState (will notify dashboard)
        self.state.add_session(session)

        # clear session runtime state
        self._session_active = False
        self._current_tag = None
        self._current_note = ""
        self._current_start_ts = None
        self._last_run_start_ts = None
        self._accum_active_s = 0
