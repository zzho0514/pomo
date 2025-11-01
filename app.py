# app.py
import tkinter as tk
from tkinter import ttk, messagebox
import time
from datetime import datetime, date, timedelta
from timer import Timer
from storage import (
    ensure_data_files, load_config, save_config,
    append_session, load_sessions,
    load_goals, save_goals
)
from stats import weekly_totals_by_tag, monthly_totals_by_tag, week_bounds

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


APP_TITLE = "Pomotask (MVP - Phase 4)"

# Default Settings
DEFAULT_CONFIG = {
    "work_min": 25,
    "short_break_min": 5,
    "long_break_min": 15,
    "long_every": 4,
    "theme": "light",
    "default_tag": "Reading",
    "tags": ["Reading", "Work", "Health", "Other"]
}
DEFAULT_MIN = 25
DEFAULT_SEC = 0

class App:
    def __init__(self, root: tk.Tk):
        #----- class init -----
        # main window
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("960x880")

        #----- Data/Configuration Initialization -----
        ensure_data_files(DEFAULT_CONFIG)
        self.config = load_config()
        self.goals = load_goals()  # {"weekly": {...}, "monthly": {...}}
        # tags from config or default
        self.tags = list(self.config.get("tags", DEFAULT_CONFIG["tags"])) or list(DEFAULT_CONFIG["tags"])
        self.sessions = load_sessions()
      

        #----- State variables ----- 
        self._current_start_ts = None    # current session start timestamp
        self._current_tag = None         # current session tag
        self._current_note = ""          # current session note

        self._last_run_start_ts = None     # timestamp of last run start
        self._accum_active_s = 0           # accumulated active seconds
        self._session_active = False       # is session currently active (including pauses)

        #----- notebook (timer / dashboard) -----
        self.nb = ttk.Notebook(root)
        self.tab_timer = ttk.Frame(self.nb)
        self.tab_dash  = ttk.Frame(self.nb)
        self.nb.add(self.tab_timer, text="Timer")
        self.nb.add(self.tab_dash,  text="Dashboard")
        self.nb.pack(fill="both", expand=True)

        #----- Timer Tab -----
        self._build_timer_tab()
        #----- Dashboard Tab -----
        self._build_dashboard_tab()

        #----- initialize timer -----
        self.timer = Timer(on_tick=self._on_tick, on_finish=self._on_timer_finished)
        self.timer.set_seconds(self.get_preset_seconds())
        self._on_tick(self.timer.remaining)

        # Preset changes
        self.min_var.trace_add("write", self._on_preset_changed)
        self.sec_var.trace_add("write", self._on_preset_changed)

        # tip label
        tip = tk.Label(root, text="Space: Start/Pause   Enter: Finish   Esc: Reset",
                       font=("Segoe UI", 9), fg="#666")
        tip.pack(side="bottom", pady=6)

        self._refresh_dashboard()
        self._refresh_goals_panel()

    #----- timer UI -----
    def _build_timer_tab(self):
        # title
        title = tk.Label(self.tab_timer, text="Pomotask", font=("Segoe UI", 22, "bold"))
        title.pack(pady=(16, 8))

        # time display
        self.time_var = tk.StringVar(value=f"{DEFAULT_MIN:02d}:{DEFAULT_SEC:02d}")
        self.time_label = tk.Label(self.tab_timer, textvariable=self.time_var,
                                font=("Consolas", 52, "bold"))
        self.time_label.pack(pady=6)

        # Time Preset Controls
        pfrm = tk.Frame(self.tab_timer)
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
        cfrm = tk.LabelFrame(self.tab_timer, text="Session Meta", padx=10, pady=8)
        cfrm.pack(padx=10, pady=10, fill="x")

        tk.Label(cfrm, text="Tag:").grid(row=0, column=0, sticky="e", padx=(0, 6))
        self.tag_var = tk.StringVar(value=self.tags[0])
        self.tag_combo = ttk.Combobox(
            cfrm, textvariable=self.tag_var, values=self.tags,
            state="normal", width=22   # allow typing new tags
        )
        self.tag_combo.grid(row=0, column=1, sticky="w")

        self.btn_add_tag = ttk.Button(cfrm, text="Add Tag", command=self.add_tag)
        self.btn_add_tag.grid(row=0, column=2, padx=6)
        self.btn_del_tag = ttk.Button(cfrm, text="Delete", command=self.delete_tag)
        self.btn_del_tag.grid(row=0, column=3)

        tk.Label(cfrm, text="Note:").grid(row=1, column=0, sticky="ne", padx=(0, 6), pady=(8,0))
        self.note_text = tk.Text(cfrm, width=44, height=3)
        self.note_text.grid(row=1, column=1, columnspan=3, sticky="w", pady=(8,0))

        # buttons
        bfrm = tk.Frame(self.tab_timer)
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
        
        # Last Session Preview
        prev_box = tk.LabelFrame(self.tab_timer, text="Last Session", padx=10, pady=8)
        prev_box.pack(padx=10, pady=8, fill="both", expand=False)
        
        self.last_session_var = tk.StringVar(value="(no session yet)")
        tk.Label(
            prev_box,
            textvariable=self.last_session_var,
            justify="left",
            anchor="w",
            wraplength=800 # approx 80% of window width
        ).pack(fill="x", anchor="w")

    #----- dashboard UI -----
    def _build_dashboard_tab(self):
        ctrl = tk.Frame(self.tab_dash)
        ctrl.pack(fill="x", padx=10, pady=8)
        # week/month switch
        tk.Label(ctrl, text="Period:").pack(side="left")
        self.period_var = tk.StringVar(value="Week")
        ttk.Radiobutton(ctrl, text="Week", variable=self.period_var, value="Week",
                        command=self._refresh_dashboard).pack(side="left", padx=6)
        ttk.Radiobutton(ctrl, text="Month", variable=self.period_var, value="Month",
                        command=self._refresh_dashboard).pack(side="left", padx=6)
        
        # next/prev period
        self.btn_prev = ttk.Button(ctrl, text="◀ Prev", command=self._prev_period)
        self.btn_next = ttk.Button(ctrl, text="Next ▶", command=self._next_period)
        self.btn_next.pack(side="right", padx=4)
        self.btn_prev.pack(side="right", padx=4)

        # goal management
        gbar = tk.Frame(self.tab_dash)
        gbar.pack(fill="x", padx=10, pady=(0,4))
        tk.Label(gbar, text="Goals", font=("Segoe UI", 11, "bold")).pack(side="left")

        self.btn_manage_goals = ttk.Button(gbar, text="Manage Goals", command=self._open_goals_dialog)
        self.btn_manage_goals.pack(side="right")
            # goals container
        self.goals_container = tk.Frame(self.tab_dash)
        self.goals_container.pack(fill="x", padx=10, pady=(0,4))
        
        # label
        self.range_label_var = tk.StringVar(value="")
        tk.Label(self.tab_dash, textvariable=self.range_label_var,
                 font=("Segoe UI", 12, "bold")).pack(pady=(0,4))
        # matplotlib figure
        self.fig = Figure(figsize=(7.8, 4.8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.tab_dash)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=4)
        # initial date reference
        self._dash_ref_date = date.today()
        self._dash_year = self._dash_ref_date.year
        self._dash_month = self._dash_ref_date.month

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
    
    #----- Tag Management -----
    def _normalize_tag(self, t: str) -> str:
        t = (t or "").strip()
        return t[:30] if t else ""

    def _save_tags(self):
        self.config["tags"] = self.tags
        try:
            save_config(self.config)
        except Exception as e:
            messagebox.showwarning("Save tags failed", str(e))

    def _ensure_tag_registered(self, t: str) -> str:
        t = self._normalize_tag(t) or "Other"
        if t not in self.tags:
            self.tags.append(t)
            self.tag_combo["values"] = self.tags
            self._save_tags()  # save updated tags
        return t
    
    def add_tag(self):
        t = self._normalize_tag(self.tag_var.get())
        if not t:
            messagebox.showwarning("Invalid tag", "Tag cannot be empty.")
            return
        if t not in self.tags:
            self.tags.append(t)
            self.tag_combo["values"] = self.tags
            self._save_tags()
        self.tag_var.set(t)
        self._refresh_dashboard()

    def delete_tag(self):
        t = self._normalize_tag(self.tag_var.get())
        if not t:
            return
        # prevent deleting tag in active session
        if self._session_active and t == (self._current_tag or ""):
            messagebox.showwarning("Cannot delete", "This tag is used by the active session.")
            return
        if t in self.tags and len(self.tags) > 1:
            self.tags.remove(t)
            self.tag_combo["values"] = self.tags
            self.tag_var.set(self.tags[0])
            self._save_tags()
            self._refresh_dashboard()

    #----- Timer Callbacks -----
    def _on_tick(self, remaining: int) -> None:
        mm = remaining // 60
        ss = remaining % 60
        self.time_var.set(f"{mm:02d}:{ss:02d}")

    def _on_timer_finished(self) -> None:
        '''
        The countdown ended naturally
        calculate active seconds
        record a session
        show messagebox
        reset timer
        '''
        if self._session_active and self._last_run_start_ts is not None:
            now = self._now_ts()
            self._accum_active_s += int(round(now - self._last_run_start_ts))
            self._last_run_start_ts = None

        self._finalize_session(auto=True)
        self._set_buttons_state(running=False)
        try:
            messagebox.showinfo("Time's up", "Pomodoro finished!")
        except Exception:
            pass
        self.timer.reset(seconds=self.get_preset_seconds())
        self._on_tick(self.timer.remaining)

    #----- Event Handlers for Timer-----
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
    
        now = self._now_ts()
        if not self._session_active:
            t = self._normalize_tag(self.tag_var.get()) or "Other"
            if t not in self.tags:
                self.tags.append(t)
                self.tag_combo["values"] = self.tags
                self._save_tags()
            self.tag_var.set(t)

            self._current_tag = t
            self._current_note = self.note_text.get("1.0", "end").strip()
            self._current_start_ts = now

            self._accum_active_s = 0
            self._last_run_start_ts = now
            self._session_active = True
        else:
            # Resuming from pause
            if self._last_run_start_ts is None:
                self._last_run_start_ts = now

        self.timer.start(self.root)
        self._set_buttons_state(running=True)

    def on_pause(self):
        if self.timer.running:
            self.timer.pause()
            now = self._now_ts()
            if self._last_run_start_ts is not None:
                self._accum_active_s += int(round(now - self._last_run_start_ts))
                self._last_run_start_ts = None
        self._set_buttons_state(running=False)

    def on_finish(self):
        # Manual session completion
        if not self._current_start_ts:
            return
        
        if self.timer.running:
            self.timer.pause()
            now = self._now_ts()
            if self._last_run_start_ts is not None:
                self._accum_active_s += int(round(now - self._last_run_start_ts))
                self._last_run_start_ts = None

        self._finalize_session(auto=False)
        self.timer.reset(seconds=self.get_preset_seconds())
        self._on_tick(self.timer.remaining)
        self._set_buttons_state(running=False)

    def on_reset(self):
        self.timer.reset(seconds=self.get_preset_seconds())
        self._on_tick(self.timer.remaining)
        self._set_buttons_state(running=False)
        # Clear current session snapshot
        self._session_active = False
        self._current_start_ts = None
        self._current_tag = None
        self._current_note = ""
        self._accum_active_s = 0
        self._last_run_start_ts = None
        self.note_text.delete("1.0", "end")

    def _set_buttons_state(self, running: bool):
        # start disable when running
        self.btn_start.config(state="disabled" if running else "normal")
        # Pause enable when running
        self.btn_pause.config(state="normal" if running else "disabled")
        # Finish enable when running
        self.btn_finish.config(state="normal" if running else "disabled")


    #----- Session Recording + refresh dashboard -----
    def _finalize_session(self, auto: bool):
        """
        Creates a session record with:
            start_ts, end_ts, duration_s, tag, note, date
        appends to self.sessions
        Updates the "Last Session" preview display
        Clears the session snapshot
        """
        if not self._session_active:
            return

        duration_s = max(0, int(self._accum_active_s))
        end_ts = self._now_ts()
        start_ts = self._current_start_ts or end_ts

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
        try:
            append_session(session)
        except Exception as e:
            messagebox.showwarning("Write session failed", str(e))
      
        # Update last session preview
        def _clean_one_line(text: str, max_len: int = 120) -> str:
            t = " ".join((text or "").split())
            return (t[: max_len - 1] + "…") if len(t) > max_len else t
        note_line = _clean_one_line(session["note"])
        mm, ss = divmod(duration_s, 60)
        preview = (
            f"- Tag: {session['tag']}\n"
            f"- Duration: {mm}m {ss}s\n"
            f"- Date: {session['date']}  ({session['ended_by']})\n"
            f"- Note: {note_line if note_line else '(empty)'}"
        )
        self.last_session_var.set(preview)

        # Clear current session snapshot
        self._session_active = False
        self._current_start_ts = None
        self._current_tag = None
        self._current_note = ""
        self._accum_active_s = 0
        self._last_run_start_ts = None

        self._refresh_dashboard()
        self._refresh_goals_panel()

    #----- Dashboard -----
    def _prev_period(self):
        if self.period_var.get() == "Week":
            self._dash_ref_date -= timedelta(days=7)
        else:
            y, m = self._dash_year, self._dash_month
            if m == 1:
                y, m = y - 1, 12
            else:
                m -= 1
            self._dash_year, self._dash_month = y, m
        self._refresh_dashboard()
        self._refresh_goals_panel()

    def _next_period(self):
        if self.period_var.get() == "Week":
            self._dash_ref_date += timedelta(days=7)
        else:
            y, m = self._dash_year, self._dash_month
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
            self._dash_year, self._dash_month = y, m
        self._refresh_dashboard()
        self._refresh_goals_panel()

    def _refresh_dashboard(self):
        # load sessions
        self.sessions = load_sessions()

        period = self.period_var.get()
        if period == "Week":
            totals, label = weekly_totals_by_tag(self.sessions, self._dash_ref_date)
        else:
            totals, label = monthly_totals_by_tag(self.sessions, self._dash_year, self._dash_month)

        self.range_label_var.set(f"{period}: {label}")

        # draw bar chart
        self.ax.cla()
        if not totals:
            self.ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12)
            self.ax.set_xticks([])
            self.ax.set_yticks([])
        else:
            tags = list(totals.keys())
            mins = [totals[t] for t in tags]
            x = range(len(tags))
            self.ax.bar(x, mins)                 
            self.ax.set_xticks(list(x))
            self.ax.set_xticklabels(tags, rotation=20, ha="right")
            self.ax.set_ylabel("Minutes")
            self.ax.set_title("Time Spent by Tag")
            # add value labels
            for i, v in enumerate(mins):
                self.ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
            # total
            total_min = round(sum(mins), 1)
            total_hr = total_min / 60.0
            self.ax.text(0.98, 0.94, f"Total: {total_min:.1f} min ({total_hr:.2f} h)",
                        transform=self.ax.transAxes, ha="right", va="top")
            # grid lines
            self.ax.grid(axis="y", linestyle="--", alpha=0.4)
        
        self.fig.tight_layout()
        self.canvas.draw()
        self._refresh_goals_panel()

    #----- Goals Management -----
    def _current_period_totals(self) -> tuple[dict[str, float], str]:
        """
        returns (totals: {tag: minutes(float)}, label: str) for current period
        """
        from stats import weekly_totals_by_tag, monthly_totals_by_tag
        if self.period_var.get() == "Week":
            totals, label = weekly_totals_by_tag(self.sessions, self._dash_ref_date)
        else:
            totals, label = monthly_totals_by_tag(self.sessions, self._dash_year, self._dash_month)
        return totals, label

    def _refresh_goals_panel(self):
        """refresh progress bars"""
        # clear existing
        for w in self.goals_container.winfo_children():
            w.destroy()

        totals, _ = self._current_period_totals()  # {tag: minutes(float)}
        period = self.period_var.get()  # "Week" or "Month"
        goal_map = self.goals["weekly" if period == "Week" else "monthly"]  # dict[tag] = minutes(int)

        # header
        header = tk.Frame(self.goals_container)
        header.pack(fill="x", pady=(2,2))
        tk.Label(header, text="Tag", width=16, anchor="w").pack(side="left")
        tk.Label(header, text="Progress", anchor="w").pack(side="left", padx=(6,0))

        tag_set = set(goal_map.keys()) | set(totals.keys()) | set(self.tags)
        if not tag_set:
            tk.Label(self.goals_container, text="No tags / goals yet. Click 'Manage Goals' to add.",
                    fg="#666").pack(anchor="w")
            return

        # rows for each tag
        for tag in sorted(tag_set):
            row = tk.Frame(self.goals_container)
            row.pack(fill="x", pady=2)

            tk.Label(row, text=tag, width=16, anchor="w").pack(side="left")

            # done vs goal
            done_min = float(totals.get(tag, 0.0))
            goal_min = int(goal_map.get(tag, 0))  # 0 means no goal

            # progress bar 
            inner = tk.Frame(row)
            inner.pack(side="left", fill="x", expand=True)

            if goal_min > 0:
                bar = ttk.Progressbar(inner, orient="horizontal", length=300, mode="determinate",
                                    maximum=goal_min, value=min(done_min, goal_min))
                bar.pack(side="left", padx=(0,6))
                pct = 100.0 * done_min / goal_min
                tk.Label(inner, text=f"{done_min:.1f} / {goal_min} min  ({pct:.0f}%)",
                        width=24, anchor="w").pack(side="left")
            else:
                # no goal set
                tk.Label(inner, text=f"{done_min:.1f} min (no goal)", anchor="w").pack(side="left")

    # goals dialog
    def _open_goals_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("Manage Goals")
        dlg.geometry("520x420")
        dlg.transient(self.root)
        dlg.grab_set()

        nb = ttk.Notebook(dlg)
        frm_week = ttk.Frame(nb)
        frm_month = ttk.Frame(nb)
        nb.add(frm_week, text="Weekly")
        nb.add(frm_month, text="Monthly")
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # build table function
        def build_table(frame, period_key: str):
            # table
            head = tk.Frame(frame); head.pack(fill="x", pady=(2,4))
            tk.Label(head, text="Tag", width=18, anchor="w").pack(side="left")
            tk.Label(head, text="Target (min)", anchor="w").pack(side="left")

            rows = []

            # rows
            period_map = dict(self.goals.get(period_key, {}))
            tag_set = set(self.tags) | set(period_map.keys())

            body = tk.Frame(frame); body.pack(fill="both", expand=True)
            for tag in sorted(tag_set):
                r = tk.Frame(body); r.pack(fill="x", pady=2)
                tk.Label(r, text=tag, width=18, anchor="w").pack(side="left")
                v = tk.StringVar(value=str(period_map.get(tag, "")))
                e = ttk.Entry(r, textvariable=v, width=12)
                e.pack(side="left")
                rows.append((tag, v))

            # save button
            def on_save():
                # collect and save
                new_map: dict[str, int] = {}
                for tag, var in rows:
                    s = var.get().strip()
                    if not s:
                        continue
                    try:
                        mins = int(float(s))
                    except ValueError:
                        mins = 0
                    if mins > 0:
                        new_map[tag] = mins
                self.goals[period_key] = new_map
                try:
                    save_goals(self.goals)
                    messagebox.showinfo("Saved", f"{period_key.capitalize()} goals saved.")
                except Exception as e:
                    messagebox.showwarning("Save failed", str(e))
                self._refresh_goals_panel()

            btnbar = tk.Frame(frame); btnbar.pack(fill="x", pady=(6,4))
            ttk.Button(btnbar, text="Save", command=on_save).pack(side="right")

        build_table(frm_week, "weekly")
        build_table(frm_month, "monthly")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    main()
