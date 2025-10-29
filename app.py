# app.py
import tkinter as tk
from tkinter import ttk, messagebox
import time
from datetime import datetime, date
from timer import Timer

APP_TITLE = "Pomotask (MVP - Phase 2)"

DEFAULT_MIN = 25 # default minutes for Pomodoro
DEFAULT_SEC = 0 # default seconds for Pomodoro

DEFAULT_TAGS = ["Read", "Study", "Work", "Health", "Other"] # default tags for tasks

class App:
    def __init__(self, root: tk.Tk):
        #----- class init -----
        # main window
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("620x520")

        # State variables
        self.sessions = [] # list[dict]  # stored sessions
        self._current_start_ts = None    # current session start timestamp
        self._current_tag = None         # current session tag
        self._current_note = ""          # current session note

        #----- UI components -----
        # title
        title = tk.Label(root, text="Pomotask", font=("Segoe UI", 22, "bold"))
        title.pack(pady=(16, 8))

        # time display
        self.time_var = tk.StringVar(value=f"{DEFAULT_MIN:02d}:{DEFAULT_SEC:02d}")
        self.time_label = tk.Label(root, textvariable=self.time_var,
                                   font=("Consolas", 52, "bold"))
        self.time_label.pack(pady=6)

        # Time Preset Controls
        pfrm = tk.Frame(root)
        pfrm.pack(pady=8)

        tk.Label(pfrm, text="Minutes:").grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.min_var = tk.IntVar(value=DEFAULT_MIN)
        self.min_spin = tk.Spinbox(pfrm, from_=0, to=180, width=4,
                                   textvariable=self.min_var, font=("Segoe UI", 12))
        self.min_spin.grid(row=0, column=1, padx=(0, 12))

        tk.Label(pfrm, text="Seconds:").grid(row=0, column=2, sticky="e", padx=(0, 6))
        self.sec_var = tk.IntVar(value=DEFAULT_SEC)
        self.sec_spin = tk.Spinbox(pfrm, from_=0, to=59, width=4,
                                   textvariable=self.sec_var, font=("Segoe UI", 12))
        self.sec_spin.grid(row=0, column=3)

        # tag and notes
        cfrm = tk.LabelFrame(root, text="Session Meta", padx=10, pady=8)
        cfrm.pack(padx=10, pady=10, fill="x")

        tk.Label(cfrm, text="Tag:").grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.tag_var = tk.StringVar(value=DEFAULT_TAGS[0])
        self.tag_combo = ttk.Combobox(cfrm, textvariable=self.tag_var,
                                      values=DEFAULT_TAGS, state="readonly", width=16)
        self.tag_combo.grid(row=0, column=1, sticky="w")

        tk.Label(cfrm, text="Note:").grid(row=1, column=0, sticky="ne", padx=(0, 6), pady=(8,0))
        self.note_text = tk.Text(cfrm, width=40, height=3)
        self.note_text.grid(row=1, column=1, sticky="w", pady=(8,0))

        # buttons
        bfrm = tk.Frame(root)
        bfrm.pack(pady=12)
        self.btn_start = ttk.Button(bfrm, text="Start", command=self.on_start)
        self.btn_pause = ttk.Button(bfrm, text="Pause", command=self.on_pause, state="disabled")
        self.btn_finish = ttk.Button(bfrm, text="Finish", command=self.on_finish, state="disabled")
        self.btn_reset = ttk.Button(bfrm, text="Reset", command=self.on_reset)

        self.btn_start.grid(row=0, column=0, padx=6)
        self.btn_pause.grid(row=0, column=1, padx=6)
        self.btn_finish.grid(row=0, column=2, padx=6)
        self.btn_reset.grid(row=0, column=3, padx=6)

        # Keyboard Shortcuts
        self.root.bind("<space>", self._toggle_start_pause)  # space start/pause
        self.root.bind("<Escape>", lambda e: self.on_reset())  # ESC reset
        self.root.bind("<Return>", lambda e: self.on_finish() if self.timer.running else None)  # Enter finish

        prev_box = tk.LabelFrame(root, text="Last Session", padx=10, pady=8)
        prev_box.pack(padx=10, pady=8, fill="both", expand=False)

        # Last Session Preview
        self.last_session_var = tk.StringVar(value="(no session yet)")
        tk.Label(prev_box, textvariable=self.last_session_var, justify="left").pack(anchor="w")

        # timer
        self.timer = Timer(on_tick=self._on_tick, on_finish=self._on_timer_finished)

        # initialize timer with default minutes
        self.timer.set_seconds(self.get_preset_seconds())
        self._on_tick(self.timer.remaining)

        # change minute, update timer
        self.min_var.trace_add("write", self._on_preset_changed)
        self.sec_var.trace_add("write", self._on_preset_changed)

        # tip label
        tip = tk.Label(root, text="Space: Start/Pause   Enter: Finish   Esc: Reset",
                       font=("Segoe UI", 9), fg="#666")
        tip.pack(side="bottom", pady=8)

    #----- Utility Methods -----
    def get_preset_seconds(self) -> int:
        """grt total seconds, at least 1 second"""
        try:
            m = int(self.min_var.get())
        except Exception:
            m = DEFAULT_MIN
        try:
            s = int(self.sec_var.get())
        except Exception:
            s = DEFAULT_SEC
        m = max(0, min(180, m))
        s = max(0, min(59, s))
        total = m * 60 + s
        return max(1, total)
    
    def _now_ts(self) -> float:
        return time.time()

    def _date_str(self, ts: float) -> str:
        # Converts Unix timestamp to "YYYY-MM-DD" format
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")

    #----- Timer Callbacks -----
    def _on_tick(self, remaining: int) -> None:
        mm = remaining // 60
        ss = remaining % 60
        self.time_var.set(f"{mm:02d}:{ss:02d}")

    def _on_timer_finished(self) -> None:
        self._finalize_session(auto=True)
        self._set_buttons_state(running=False)
        try:
            messagebox.showinfo("Time's up", "Pomodoro finished!")
        except Exception:
            pass
        self.timer.reset(seconds=self.get_preset_seconds())
        self._on_tick(self.timer.remaining)

    #----- Event Handlers -----
    def _on_preset_changed(self, *args) -> None:
        # only update timer if not running
        if not self.timer.running:
            self.timer.set_seconds(self.get_preset_seconds())
            self._on_tick(self.timer.remaining)

    def _toggle_start_pause(self, event=None):
        if self.timer.running:
            self.on_pause()
        else:
            self.on_start()

    def on_start(self):
        if self.timer.running:
            return
        # Captures current tag and note when Start is pressed
        self._current_tag = self.tag_var.get().strip() or "Other"
        self._current_note = self.note_text.get("1.0", "end").strip()
        self._current_start_ts = self._now_ts()

        self.timer.start(self.root)
        self._set_buttons_state(running=True)


    def on_pause(self):
        self.timer.pause()
        self._set_buttons_state(running=False)

    def on_finish(self):
        # Manual session completion
        if not self._current_start_ts:
            return
        self._finalize_session(auto=False)
        self.timer.reset(seconds=self.get_preset_seconds())
        self._on_tick(self.timer.remaining)
        self._set_buttons_state(running=False)

    def on_reset(self):
        self.timer.reset(seconds=self.get_preset_seconds())
        self._on_tick(self.timer.remaining)
        self._set_buttons_state(running=False)
        self._current_start_ts = None
        self._current_tag = None
        self._current_note = ""

    def _set_buttons_state(self, running: bool):
        # start disable when running
        self.btn_start.config(state="disabled" if running else "normal")
        # Pause enable when running
        self.btn_pause.config(state="normal" if running else "disabled")
        # Finish enable when running
        self.btn_finish.config(state="normal" if running else "disabled")


    #----- Session Recording -----
    def _finalize_session(self, auto: bool):
        """
        Creates a session record with:
            start_ts, end_ts, duration_s, tag, note, date
        appends to self.sessions
        Updates the "Last Session" preview display
        Clears the session snapshot
        """
        end_ts = self._now_ts()
        start_ts = self._current_start_ts or end_ts
        duration_s = max(0, int(round(end_ts - start_ts)))
        session = {
            "start_ts": int(start_ts),
            "end_ts": int(end_ts),
            "duration_s": duration_s,
            "tag": self._current_tag or (self.tag_var.get().strip() or "Other"),
            "note": self._current_note,
            "date": self._date_str(end_ts),
            "ended_by": "auto" if auto else "manual"
        }
        self.sessions.append(session)
        # Update last session preview
        mm, ss = divmod(duration_s, 60)
        preview = (f"- Tag: {session['tag']}\n"
                   f"- Duration: {mm}m {ss}s\n"
                   f"- Date: {session['date']}  ({session['ended_by']})")
        self.last_session_var.set(preview)
        # Clear current session snapshot
        self._current_start_ts = None
        self._current_tag = None
        self._current_note = ""


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
