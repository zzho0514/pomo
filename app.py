# app.py
import tkinter as tk

APP_TITLE = "Pomotask (MVP - Phase 0)"
from tkinter import ttk, messagebox
from timer import Timer

APP_TITLE = "Pomotask (MVP - Phase 1.1)"

DEFAULT_MIN = 25 # default minutes for Pomodoro
DEFAULT_SEC = 0 # default seconds for Pomodoro


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("520x360")

        # title
        title = tk.Label(root, text="Pomotask", font=("Segoe UI", 22, "bold"))
        title.pack(pady=(16, 8))

        # time display
        self.time_var = tk.StringVar(value=f"{DEFAULT_MIN:02d}:{DEFAULT_SEC:02d}")
        self.time_label = tk.Label(root, textvariable=self.time_var,
                                   font=("Consolas", 52, "bold"))
        self.time_label.pack(pady=6)

        # spinbox for minutes and seconds
        mfrm = tk.Frame(root)
        mfrm.pack(pady=6)

        tk.Label(mfrm, text="Minutes:").pack(side="left", padx=(0, 6))
        self.min_var = tk.IntVar(value=DEFAULT_MIN)
        self.min_spin = tk.Spinbox(
            mfrm, from_=0, to=180, width=4, textvariable=self.min_var, font=("Segoe UI", 12)
        )
        self.min_spin.pack(side="left", padx=(0, 12))

        tk.Label(mfrm, text="Seconds:").pack(side="left", padx=(0, 6))
        self.sec_var = tk.IntVar(value=DEFAULT_SEC)
        self.sec_spin = tk.Spinbox(
            mfrm, from_=0, to=59, width=4, textvariable=self.sec_var, font=("Segoe UI", 12)
        )
        self.sec_spin.pack(side="left")

        # buttons
        bfrm = tk.Frame(root)
        bfrm.pack(pady=16)
        self.btn_start = ttk.Button(bfrm, text="Start", command=self.on_start)
        self.btn_pause = ttk.Button(bfrm, text="Pause", command=self.on_pause, state="disabled")
        self.btn_reset = ttk.Button(bfrm, text="Reset", command=self.on_reset)

        self.btn_start.grid(row=0, column=0, padx=6)
        self.btn_pause.grid(row=0, column=1, padx=6)
        self.btn_reset.grid(row=0, column=2, padx=6)

        # key bindings
        self.root.bind("<space>", self._toggle_start_pause)  # space start/pause
        self.root.bind("<Escape>", lambda e: self.on_reset())  # ESC reset

        # timer
        self.timer = Timer(on_tick=self._on_tick, on_finish=self._on_finish)

        # initialize timer with default minutes
        self.timer.set_seconds(self.get_preset_seconds())
        self._on_tick(self.timer.remaining)

        # change minute, update timer
        self.min_var.trace_add("write", self._on_preset_changed)
        self.sec_var.trace_add("write", self._on_preset_changed)

        # tip label
        tip = tk.Label(root, text="Space: Start/Pause,  Esc: Reset",
                       font=("Segoe UI", 9), fg="#666")
        tip.pack(side="bottom", pady=8)

    # tools
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

        # range limit
        m = max(0, min(180, m))
        s = max(0, min(59, s))

        total = m * 60 + s
        return max(1, total)
    

    # callbacks for Timer
    def _on_tick(self, remaining: int) -> None:
        mm = remaining // 60
        ss = remaining % 60
        self.time_var.set(f"{mm:02d}:{ss:02d}")

    def _on_finish(self) -> None:
        self._set_buttons_state(running=False)
        try:
            messagebox.showinfo("Time's up", "Pomodoro finished!")
        except Exception:
            pass
        # reset timer to preset
        self.timer.reset(seconds=self.get_preset_seconds())
        self._on_tick(self.timer.remaining)

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
        self.timer.start(self.root)
        self._set_buttons_state(running=True)

    def on_pause(self):
        self.timer.pause()
        self._set_buttons_state(running=False)

    def on_reset(self):
        self.timer.reset(seconds=self.get_preset_seconds())
        self._set_buttons_state(running=False)

    def _set_buttons_state(self, running: bool):
        # start disable when running
        self.btn_start.config(state="disabled" if running else "normal")
        # Pause enable when running
        self.btn_pause.config(state="normal" if running else "disabled")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
