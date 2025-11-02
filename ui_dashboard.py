# ui_dashboard.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from typing import Dict, Tuple, List

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from stats import weekly_totals_by_tag, monthly_totals_by_tag

class DashboardTab:
    """
    Dashboard page:
    - Period controls (Week/Month, Prev/Next)
    - Goals panel (scrollable, ONLY shows tags with goals)
    - Bar chart using matplotlib
    - Manage Goals dialog (persist to data/goals.json via AppState)
    """
    def __init__(self, parent, state):
        self.state = state
        self.frame = ttk.Frame(parent)

        self._build_controls()
        self._build_chart()

        self._ref_date = date.today()
        self._year = self._ref_date.year
        self._month = self._ref_date.month

        # initial render
        self.refresh()

        # subscribe to state changes (new sessions etc.)
        self.state.subscribe(self.refresh)

    # ---------- UI builders ----------
    def _build_controls(self):
        ctrl = tk.Frame(self.frame); ctrl.pack(fill="x", padx=10, pady=8)

        tk.Label(ctrl, text="Period:").pack(side="left")
        self.period_var = tk.StringVar(value="Week")
        ttk.Radiobutton(ctrl, text="Week", variable=self.period_var, value="Week",
                        command=self.refresh).pack(side="left", padx=6)
        ttk.Radiobutton(ctrl, text="Month", variable=self.period_var, value="Month",
                        command=self.refresh).pack(side="left", padx=6)
        
        ttk.Button(ctrl, text="Next ▶", command=self._next_period).pack(side="right", padx=4)
        ttk.Button(ctrl, text="◀ Prev", command=self._prev_period).pack(side="right", padx=4)
        
        # goals header row
        gbar = tk.Frame(self.frame); gbar.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(gbar, text="Goals", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(gbar, text="Manage Goals", command=self._open_goals_dialog).pack(side="right")

        # scrollable goals container with fixed height
        gwrap = tk.Frame(self.frame); gwrap.pack(fill="x", padx=10, pady=(0, 4))
        self.goals_canvas = tk.Canvas(gwrap, height=140, highlightthickness=0)
        self.goals_scrollbar = ttk.Scrollbar(gwrap, orient="vertical", command=self.goals_canvas.yview)
        self.goals_container = tk.Frame(self.goals_canvas)
        self.goals_container.bind(
            "<Configure>",
            lambda e: self.goals_canvas.configure(scrollregion=self.goals_canvas.bbox("all"))
        )
        self.goals_canvas.create_window((0, 0), window=self.goals_container, anchor="nw")
        self.goals_canvas.configure(yscrollcommand=self.goals_scrollbar.set)
        self.goals_canvas.pack(side="left", fill="x", expand=True)
        self.goals_scrollbar.pack(side="right", fill="y")

        # range label (below goals)
        self.range_label_var = tk.StringVar(value="")
        tk.Label(self.frame, textvariable=self.range_label_var,
                 font=("Segoe UI", 12, "bold")).pack(pady=(0, 4))

    def _build_chart(self):
        self.fig = Figure(figsize=(7.8, 4.8), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=4)

    # ---------- helpers ----------
    def _current_period_totals(self) -> Tuple[Dict[str, float], str]:
        """Return (totals_by_tag_in_minutes, label) for current Week/Month window."""
        if self.period_var.get() == "Week":
            return weekly_totals_by_tag(self.state.sessions, self._ref_date)
        return monthly_totals_by_tag(self.state.sessions, self._year, self._month)

    # ---------- refresh ----------
    def refresh(self):
        # goals
        self._refresh_goals_panel()
        # chart
        totals, label = self._current_period_totals()
        self.range_label_var.set(f"{self.period_var.get()}: {label}")
        self._draw_chart(totals)

    def _draw_chart(self, totals: Dict[str, float]):
        self.ax.cla()
        if not totals:
            self.ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12)
            self.ax.set_xticks([]); self.ax.set_yticks([])
        else:
            tags = list(totals.keys())
            mins = [float(totals[t]) for t in tags]
            x = range(len(tags))
            self.ax.bar(x, mins)
            self.ax.set_xticks(list(x))
            self.ax.set_xticklabels(tags, rotation=20, ha="right")
            self.ax.set_ylabel("Minutes")
            self.ax.set_title("Time Spent by Tag")

            total_min = round(sum(mins), 1)
            total_hr = total_min / 60.0
            self.ax.text(0.98, 0.94, f"Total: {total_min:.1f} min ({total_hr:.2f} h)",
                         transform=self.ax.transAxes, ha="right", va="top")
            # optional value labels on top of bars
            for i, v in enumerate(mins):
                self.ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)

            self.ax.grid(axis="y", linestyle="--", alpha=0.4)
        self.fig.tight_layout()
        self.canvas.draw()

    def _refresh_goals_panel(self):
        # clear rows
        for w in self.goals_container.winfo_children():
            w.destroy()

        totals, _ = self._current_period_totals()
        period = self.period_var.get()
        goal_map = self.state.goals["weekly" if period == "Week" else "monthly"]

        if not goal_map:
            tk.Label(self.goals_container,
                     text="No goals set for this period. Click 'Manage Goals' to add goals.",
                     fg="#666").pack(anchor="w", pady=(4, 4))
            self.goals_canvas.configure(scrollregion=self.goals_canvas.bbox("all"))
            return

        header = tk.Frame(self.goals_container); header.pack(fill="x", pady=(2,2))
        tk.Label(header, text="Tag", width=16, anchor="w").pack(side="left")
        tk.Label(header, text="Progress", anchor="w").pack(side="left", padx=(6, 0))

        for tag, goal_min in sorted(goal_map.items()):
            try:
                g = float(goal_min)
            except Exception:
                continue
            if g <= 0:
                continue

            row = tk.Frame(self.goals_container); row.pack(fill="x", pady=2)
            tk.Label(row, text=tag, width=16, anchor="w").pack(side="left")

            done_min = float(totals.get(tag, 0.0))
            inner = tk.Frame(row); inner.pack(side="left", fill="x", expand=True)

            bar = ttk.Progressbar(inner, orient="horizontal", length=300, mode="determinate",
                                  maximum=g, value=min(done_min, g))
            bar.pack(side="left", padx=(0, 6))
            pct = (100.0 * done_min / g) if g > 0 else 0.0
            tk.Label(inner, text=f"{done_min:.1f} / {g:.0f} min  ({pct:.0f}%)",
                     width=24, anchor="w").pack(side="left")

        self.goals_canvas.configure(scrollregion=self.goals_canvas.bbox("all"))

    # ---------- paging ----------
    def _prev_period(self):
        if self.period_var.get() == "Week":
            self._ref_date -= timedelta(days=7)
        else:
            y, m = self._year, self._month
            if m == 1: y, m = y - 1, 12
            else:      m -= 1
            self._year, self._month = y, m
        self.refresh()

    def _next_period(self):
        if self.period_var.get() == "Week":
            self._ref_date += timedelta(days=7)
        else:
            y, m = self._year, self._month
            if m == 12: y, m = y + 1, 1
            else:       m += 1
            self._year, self._month = y, m
        self.refresh()

    # ---------- goals dialog ----------
    def _open_goals_dialog(self):
        dlg = tk.Toplevel(self.frame)
        dlg.title("Manage Goals")
        dlg.geometry("520x420")
        dlg.transient(self.frame.winfo_toplevel())
        dlg.grab_set()

        nb = ttk.Notebook(dlg)
        frm_week = ttk.Frame(nb); frm_month = ttk.Frame(nb)
        nb.add(frm_week, text="Weekly"); nb.add(frm_month, text="Monthly")
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        def build_table(frame, key: str):
            # header
            head = tk.Frame(frame); head.pack(fill="x", pady=(2,4))
            tk.Label(head, text="Tag", width=18, anchor="w").pack(side="left")
            tk.Label(head, text="Target (min)", anchor="w").pack(side="left")

            rows: List[tuple[str, tk.StringVar]] = []
            period_map = dict(self.state.goals.get(key, {}))
            tags = sorted(set(self.state.config.get("tags", [])) | set(period_map.keys()))

            body = tk.Frame(frame); body.pack(fill="both", expand=True)
            for tag in tags:
                r = tk.Frame(body); r.pack(fill="x", pady=2)
                tk.Label(r, text=tag, width=18, anchor="w").pack(side="left")
                v = tk.StringVar(value=str(period_map.get(tag, "")))
                ttk.Entry(r, textvariable=v, width=12).pack(side="left")
                rows.append((tag, v))

            def on_save():
                new_map = {}
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
                self.state.goals[key] = new_map
                try:
                    self.state.save_goals()
                    messagebox.showinfo("Saved", f"{key.capitalize()} goals saved.")
                except Exception as e:
                    messagebox.showwarning("Save failed", str(e))
                self.refresh()
                dlg.destroy()

            tk.Frame(frame)  # spacer
            ttk.Button(frame, text="Save", command=on_save).pack(side="right", pady=6)

        build_table(frm_week, "weekly")
        build_table(frm_month, "monthly")
