# ui_dashboard.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from typing import Dict, Tuple, List
from matplotlib import cm, ticker
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
    def __init__(self, parent, state, ppi=96.0):
        self.state = state
        self.frame = ttk.Frame(parent)
        self.ppi = ppi
        # make the main frame grid-aware
        self.frame.grid_rowconfigure(4, weight=1)   # row 4 = chart area grows
        self.frame.grid_columnconfigure(0, weight=1)

        self._build_controls()
        self._build_chart()

        self._ref_date = date.today()
        self._year = self._ref_date.year
        self._month = self._ref_date.month

        # delay first render until widgets are realized (prevents first-frame clipping)
        self.frame.after_idle(self.refresh)

        # subscribe to state changes (new sessions etc.)
        self.state.subscribe(self.refresh)
        # When the notebook switches to this tab, ensure the chart resizes once properly
        parent.bind("<<NotebookTabChanged>>", lambda e: self._on_tab_changed(e))

    # ---------- UI builders ----------
    def _build_controls(self):
        # row 0: period + prev/next
        ctrl = tk.Frame(self.frame)
        ctrl.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ctrl.grid_columnconfigure(2, weight=1)  # push right-side buttons

        tk.Label(ctrl, text="Period:").grid(row=0, column=0, sticky="w")
        self.period_var = tk.StringVar(value="Week")
        ttk.Radiobutton(ctrl, text="Week",  variable=self.period_var, value="Week",
                        command=self.refresh).grid(row=0, column=1, sticky="w", padx=(6,0))
        ttk.Radiobutton(ctrl, text="Month", variable=self.period_var, value="Month",
                        command=self.refresh).grid(row=0, column=2, sticky="w", padx=(6,0))
        
        ttk.Button(ctrl, text="Next ▶", command=self._next_period).grid(row=0, column=4, sticky="e", padx=4)
        ttk.Button(ctrl, text="◀ Prev", command=self._prev_period).grid(row=0, column=3, sticky="e", padx=4)

        # row 1: goals header
        gbar = tk.Frame(self.frame)
        gbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0,4))
        tk.Label(gbar, text="Goals", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(gbar, text="Manage Goals", command=self._open_goals_dialog).pack(side="right")

        # row 2: scrollable goals （fixed height）
        gwrap = tk.Frame(self.frame)
        gwrap.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,4))
        gwrap.grid_propagate(False)
        gwrap.configure(height=140)

        self.goals_canvas = tk.Canvas(gwrap, height=140, highlightthickness=0)
        self.goals_scrollbar = ttk.Scrollbar(gwrap, orient="vertical", command=self.goals_canvas.yview)
        self.goals_container = tk.Frame(self.goals_canvas)
        self.goals_container.bind("<Configure>",
            lambda e: self.goals_canvas.configure(scrollregion=self.goals_canvas.bbox("all")))
        self.goals_canvas.create_window((0, 0), window=self.goals_container, anchor="nw")
        self.goals_canvas.configure(yscrollcommand=self.goals_scrollbar.set)
        self.goals_canvas.pack(side="left", fill="x", expand=True)
        self.goals_scrollbar.pack(side="right", fill="y")

        # row 3: range label
        self.range_label_var = tk.StringVar(value="")
        tk.Label(self.frame, textvariable=self.range_label_var,
                font=("Segoe UI", 12, "bold")).grid(row=3, column=0, sticky="w", padx=10, pady=(0,4))
        
        # ensure frame expands inside notebook
        self.frame.pack(fill="both", expand=True)

    def _build_chart(self):
        # Higher DPI for crisper text and lines
        self.fig = Figure(figsize=(7.6, 4.4), dpi=self.ppi)

        # Respect theme background (optional but nice)
        theme = (self.state.config or {}).get("theme", "light")
        face = "#FFFFFF" if theme == "light" else "#111418"
        self.fig.set_facecolor(face)

        self.ax = self.fig.add_subplot(111)

        self.chart_wrap = tk.Frame(self.frame)
        self.chart_wrap.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_wrap)
        widget = self.canvas.get_tk_widget()
        widget.pack(fill="both", expand=True)

        # --- New: unified resize handler (supports first-map & later resizes) ---
        def _resize_to_wrap():
            w, h = self.chart_wrap.winfo_width(), self.chart_wrap.winfo_height()
            # If size is still invalid, retry a bit later
            if w < 50 or h < 50:
                self.chart_wrap.after(50, _resize_to_wrap)
                return
            dpi = self.fig.get_dpi()
            self.fig.set_size_inches(max(w, 50)/dpi, max(h, 50)/dpi)
            # avoid tight_layout here; just reserve margins for labels/secondary axis
            self.fig.subplots_adjust(left=0.10, right=0.95, top=0.88, bottom=0.22)
            self.canvas.draw_idle()

        self.chart_wrap.bind("<Map>", lambda e: _resize_to_wrap())
        self.chart_wrap.bind("<Configure>", lambda e: _resize_to_wrap())


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
        """
        Draw a clean, modern bar chart:
        - Theme-aware palette
        - Y-grid only, removed top/right spines
        - Minute labels + secondary axis in hours
        - Smart value annotations for small N
        """
        self.ax.cla()

        # Theme-aware colors
        theme = (self.state.config or {}).get("theme", "light")
        bg = "#FFFFFF" if theme == "light" else "#111418"
        fg = "#111111" if theme == "light" else "#E6E6E6"
        gridc = "#D9D9D9" if theme == "light" else "#2A2F36"

        self.ax.set_facecolor(bg)
        for spine in ("top", "right"):
            self.ax.spines[spine].set_visible(False)
        self.ax.spines["left"].set_color(gridc)
        self.ax.spines["bottom"].set_color(gridc)
        self.ax.tick_params(colors=fg)
        self.ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=False))

        if not totals:
            self.ax.text(0.5, 0.5, "No data",
                        ha="center", va="center",
                        fontsize=12, color=fg)
            self.ax.set_xticks([]); self.ax.set_yticks([])
            # self.fig.tight_layout()
            self.canvas.draw()
            return

        tags = list(totals.keys())
        mins = [float(totals[t]) for t in tags]
        x = range(len(tags))

        # Deterministic palette per tag (tab20 works well)
        cmap = cm.get_cmap("tab20")
        colors = [cmap(i % cmap.N) for i in range(len(tags))]

        bars = self.ax.bar(x, mins, color=colors, linewidth=0)

        # X ticks
        self.ax.set_xticks(list(x))
        # Rotate & right-align to reduce overlap
        self.ax.set_xticklabels(tags, rotation=20, ha="right", color=fg)

        # Y label
        self.ax.set_ylabel("Minutes", color=fg)

        # Secondary axis in hours (right side)
        sec = self.ax.secondary_yaxis(
            'right',
            functions=(lambda m: m/60.0, lambda h: h*60.0)  # type: ignore
        )
        sec.set_ylabel("Hours", color=fg)
        sec.tick_params(colors=fg)

        # Title + total summary
        total_min = round(sum(mins), 1)
        total_hr = total_min / 60.0
        self.ax.set_title("Time Spent by Tag", color=fg, pad=8, fontweight="bold")
        self.ax.text(0.98, 0.94,
                    f"Total: {total_min:.1f} min ({total_hr:.2f} h)",
                    transform=self.ax.transAxes, ha="right", va="top", color=fg)

        # Light Y grid only
        self.ax.grid(axis="y", linestyle=(0, (4, 4)), linewidth=0.8, alpha=0.6, color=gridc)

        # Top padding (avoid label clipping)
        y_max = max(mins) if mins else 1.0
        self.ax.set_ylim(0, y_max * 1.15)

        # Value labels (only if not too many bars)
        if len(tags) <= 10:
            for rect, v in zip(bars, mins):
                self.ax.text(rect.get_x() + rect.get_width() / 2,
                            rect.get_height(),
                            f"{v:.0f}",
                            ha="center", va="bottom",
                            fontsize=9, color=fg)

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

    def _on_tab_changed(self, event):
        nb = event.widget
        tab_text = nb.tab(nb.select(), "text")
        if tab_text == "Dashboard":
            # Ensure the figure matches container size when this tab becomes visible
            self.frame.after(100, self._force_redraw)

    def _force_redraw(self):
        try:
            w, h = self.chart_wrap.winfo_width(), self.chart_wrap.winfo_height()
            dpi = self.fig.get_dpi()
            if w > 50 and h > 50:
                self.fig.set_size_inches(w / dpi, h / dpi)
                self.fig.subplots_adjust(left=0.10, right=0.95, top=0.88, bottom=0.22)
                self.canvas.draw_idle()
        except Exception:
            pass

    
