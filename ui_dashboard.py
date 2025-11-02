# ui_dashboard.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, timedelta
from typing import Dict, Tuple, List

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import cm, ticker

from stats import weekly_totals_by_tag, monthly_totals_by_tag

GOALS_HEIGHT = 220 

class DashboardTab:
    """
    Dashboard tab:
      - Period controls (Week/Month + Prev/Next)
      - Goals panel (scrollable; only shows tags that have goals)
      - Matplotlib bar chart with a right secondary axis (hours)
    HD-safe and resize-stable:
      * No tight_layout/constrained_layout; use fixed subplots_adjust margins
      * Figure inch-size is matched to container pixel-size (ppi-aware)
      * Debounced resize; skip drawing at tiny sizes during fullscreen storms
    """

    def __init__(self, parent, state, ppi: float = 96.0):
        self.state = state
        self.ppi = float(ppi)

        # Root frame for this tab (use GRID for all direct children)
        self.frame = ttk.Frame(parent)
        self.frame.grid_rowconfigure(4, weight=1)  # row 4 = chart area expands
        self.frame.grid_columnconfigure(0, weight=1)

        # Build UI parts
        self._build_controls()
        self._build_chart()

        # Period context
        self._ref_date = date.today()
        self._year = self._ref_date.year
        self._month = self._ref_date.month

        # First render after Tk finishes first layout pass
        self.frame.after_idle(self.refresh)

        # Re-render when AppState changes (sessions/goals updated)
        self.state.subscribe(self.refresh)

        # Redraw when switching to this tab
        parent.bind("<<NotebookTabChanged>>", self._on_tab_changed)

    # ---------- UI builders ----------

    def _build_controls(self) -> None:
        """Build period control bar, goals header + scroller, and range label."""
        # Row 0: period radio + prev/next
        ctrl = ttk.Frame(self.frame)
        ctrl.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        ctrl.grid_columnconfigure(2, weight=1)

        ttk.Label(ctrl, text="Period:").grid(row=0, column=0, sticky="w")
        self.period_var = tk.StringVar(value="Week")
        ttk.Radiobutton(ctrl, text="Week", variable=self.period_var, value="Week",
                        command=self.refresh).grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Radiobutton(ctrl, text="Month", variable=self.period_var, value="Month",
                        command=self.refresh).grid(row=0, column=2, sticky="w", padx=(6, 0))
        ttk.Button(ctrl, text="◀ Prev", command=self._prev_period).grid(row=0, column=3, sticky="e", padx=4)
        ttk.Button(ctrl, text="Next ▶", command=self._next_period).grid(row=0, column=4, sticky="e", padx=4)

        # Row 1: goals header
        gbar = ttk.Frame(self.frame)
        gbar.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 4))
        ttk.Label(gbar, text="Goals", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(gbar, text="Manage Goals", command=self._open_goals_dialog).pack(side="right")

        # Row 2: goals scroller (fixed visual height; inner uses pack)
        gwrap = ttk.Frame(self.frame)
        gwrap.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 4))
        gwrap.grid_propagate(False)
        gwrap.configure(height=GOALS_HEIGHT)

        self.goals_canvas = tk.Canvas(gwrap, height=GOALS_HEIGHT, highlightthickness=0, bd=0)
        self.goals_scrollbar = ttk.Scrollbar(gwrap, orient="vertical", command=self.goals_canvas.yview)
        self.goals_container = ttk.Frame(self.goals_canvas)
        self.goals_container.bind(
            "<Configure>",
            lambda e: self.goals_canvas.configure(scrollregion=self.goals_canvas.bbox("all"))
        )
        self.goals_canvas.create_window((0, 0), window=self.goals_container, anchor="nw")
        self.goals_canvas.configure(yscrollcommand=self.goals_scrollbar.set)
        self.goals_canvas.pack(side="left", fill="x", expand=True)
        self.goals_scrollbar.pack(side="right", fill="y")

        # Row 3: period range label
        self.range_label_var = tk.StringVar(value="")
        ttk.Label(self.frame, textvariable=self.range_label_var,
                  font=("Segoe UI", 12, "bold")).grid(row=3, column=0, sticky="w", padx=10, pady=(0, 4))

    def _build_chart(self) -> None:
        """Create a ppi-aware figure and embed it in a container that uses GRID."""
        # High-DPI figure; inch-size will later be matched to container pixels
        self.fig = Figure(figsize=(6.4, 3.8), dpi=self.ppi)
        self.ax = self.fig.add_subplot(111)

        # Row 4: chart container (gridded into self.frame; can expand)
        self.chart_wrap = ttk.Frame(self.frame)
        self.chart_wrap.grid(row=4, column=0, sticky="nsew", padx=10, pady=4)

        # Canvas lives inside chart_wrap; pack is allowed inside this child container
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_wrap)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Debounce handle so bursty resizes schedule only one redraw
        self._resize_job = None

        def _do_resize(force_draw: bool = False) -> None:
            """Resize figure to match container pixel size; skip tiny sizes during storms."""
            self._resize_job = None  # this call is the committed execution
            w = max(self.chart_wrap.winfo_width(), 1)
            h = max(self.chart_wrap.winfo_height(), 1)

            # During fullscreen/maximize Configure storms, width/height can be tiny (1~100).
            if w < 160 or h < 160:
                # Retry shortly; avoid drawing a nearly-zero figure
                self._resize_job = self.chart_wrap.after(60, lambda: _do_resize(force_draw))
                return

            dpi = self.fig.get_dpi()
            self.fig.set_size_inches(w / dpi, h / dpi)

            # Reserve a safe right margin for the secondary y-axis; avoid tight/constrained layout
            self.fig.subplots_adjust(left=0.12, right=0.85, top=0.90, bottom=0.22)

            # Fullscreen/Map: prefer immediate paint; otherwise idle is fine
            (self.canvas.draw if force_draw else self.canvas.draw_idle)()

        def _request_resize(force_draw: bool = False) -> None:
            """Schedule a single resize at the tail of multiple Configure events."""
            if self._resize_job is not None:
                self.chart_wrap.after_cancel(self._resize_job)
            self._resize_job = self.chart_wrap.after(80, lambda: _do_resize(force_draw))

        # First map: force a valid-sized draw immediately
        self.chart_wrap.bind("<Map>", lambda e: _request_resize(force_draw=True))
        # Later resizes: debounce + idle draw
        self.chart_wrap.bind("<Configure>", lambda e: _request_resize(False))

        # Also listen to top-level Configure (maximize/restore on the window)
        toplevel = self.frame.winfo_toplevel()
        toplevel.bind("<Configure>", lambda e: _request_resize(False))

    # ---------- data helpers ----------

    def _current_period_totals(self) -> Tuple[Dict[str, float], str]:
        """Return (totals_by_tag_in_minutes, label) for current Week/Month window."""
        if self.period_var.get() == "Week":
            return weekly_totals_by_tag(self.state.sessions, self._ref_date)
        return monthly_totals_by_tag(self.state.sessions, self._year, self._month)

    # ---------- refresh pipeline ----------

    def refresh(self) -> None:
        """Refresh goals panel, range label, and redraw the chart."""
        self._refresh_goals_panel()
        totals, label = self._current_period_totals()
        self.range_label_var.set(f"{self.period_var.get()}: {label}")
        self._draw_chart(totals)

    def _draw_chart(self, totals: Dict[str, float]) -> None:
        """Render the bar chart with fixed margins and a right secondary axis in hours."""
        self.ax.cla()

        if not totals:
            self.ax.text(0.5, 0.5, "No data", ha="center", va="center", fontsize=12)
            self.ax.set_xticks([]); self.ax.set_yticks([])
            self.canvas.draw_idle()
            return

        tags = list(totals.keys())
        mins = [float(totals[t]) for t in tags]
        xs = range(len(tags))

        # Colors (tab20)
        cmap = cm.get_cmap("tab20")
        colors = [cmap(i % cmap.N) for i in range(len(tags))]

        # Bars
        bars = self.ax.bar(xs, mins, color=colors, linewidth=0)

        # X/Y labels
        self.ax.set_xticks(list(xs))
        self.ax.set_xticklabels(tags, rotation=20, ha="right")
        self.ax.set_ylabel("Minutes")
        self.ax.set_title("Data statistics", fontweight="bold")

        # Grid + headroom on primary axis
        self.ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=6, integer=False))
        self.ax.grid(axis="y", linestyle=(0, (4, 4)), linewidth=0.8, alpha=0.6)
        y_max = max(mins) if mins else 1.0
        self.ax.set_ylim(0, y_max * 1.15)

        # Create the secondary y-axis (hours) AFTER limits are set
        sec = self.ax.secondary_yaxis(
            'right',
            functions=(lambda m: m / 60.0, lambda h: h * 60.0)  # type: ignore
        )
        sec.set_ylabel("Hours (h)")
        sec.tick_params(axis="y")
        # Keep the axis label within the right margin (safe anchor)
        # sec.yaxis.set_label_coords(1.02, 0.5)
        # Optional: display unit on every tick (uncomment if desired)
        # sec.yaxis.set_major_formatter(lambda val, _: f"{val:.1f} h")

        # Value labels for small N
        if len(tags) <= 10:
            for rect, v in zip(bars, mins):
                self.ax.text(rect.get_x() + rect.get_width() / 2,
                             rect.get_height(), f"{v:.0f}",
                             ha="center", va="bottom", fontsize=9)

        self.canvas.draw_idle()

    # ---------- goals panel ----------

    def _refresh_goals_panel(self) -> None:
        """Rebuild the goals list only for tags that have goals in this period."""
        # Clear previous rows
        for w in self.goals_container.winfo_children():
            w.destroy()

        totals, _ = self._current_period_totals()
        period = self.period_var.get()
        goal_map = self.state.goals["weekly" if period == "Week" else "monthly"]

        if not goal_map:
            ttk.Label(
                self.goals_container,
                text="No goals set for this period. Click 'Manage Goals' to add goals."
            ).pack(anchor="w", pady=(4, 4))
            self.goals_canvas.configure(scrollregion=self.goals_canvas.bbox("all"))
            return

        header = ttk.Frame(self.goals_container); header.pack(fill="x", pady=(2, 2))
        ttk.Label(header, text="Tag", width=16, anchor="w").pack(side="left")
        ttk.Label(header, text="Progress", anchor="w").pack(side="left", padx=(6, 0))

        for tag, goal_min in sorted(goal_map.items()):
            try:
                g = float(goal_min)
            except Exception:
                continue
            if g <= 0:
                continue

            row = ttk.Frame(self.goals_container); row.pack(fill="x", pady=2)
            ttk.Label(row, text=tag, width=16, anchor="w").pack(side="left")

            done_min = float(totals.get(tag, 0.0))
            inner = ttk.Frame(row); inner.pack(side="left", fill="x", expand=True)

            bar = ttk.Progressbar(
                inner, orient="horizontal", length=300, mode="determinate",
                maximum=g, value=min(done_min, g)
            )
            bar.pack(side="left", padx=(0, 6))
            pct = (100.0 * done_min / g) if g > 0 else 0.0
            ttk.Label(inner, text=f"{done_min:.1f} / {g:.0f} min  ({pct:.0f}%)",
                      width=24, anchor="w").pack(side="left")

        self.goals_canvas.configure(scrollregion=self.goals_canvas.bbox("all"))

    # ---------- period paging ----------

    def _prev_period(self) -> None:
        if self.period_var.get() == "Week":
            self._ref_date -= timedelta(days=7)
        else:
            y, m = self._year, self._month
            if m == 1:
                y, m = y - 1, 12
            else:
                m -= 1
            self._year, self._month = y, m
        self.refresh()

    def _next_period(self) -> None:
        if self.period_var.get() == "Week":
            self._ref_date += timedelta(days=7)
        else:
            y, m = self._year, self._month
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
            self._year, self._month = y, m
        self.refresh()

    # ---------- goals dialog ----------

    def _open_goals_dialog(self) -> None:
        """Open a small dialog to edit weekly/monthly goals."""
        dlg = tk.Toplevel(self.frame)
        dlg.title("Manage Goals")
        
        dlg.resizable(True, True)
        dlg.minsize(520, 420)    
        dlg.geometry("620x520")  

        dlg.transient(self.frame.winfo_toplevel())
        dlg.grab_set()

        nb = ttk.Notebook(dlg)
        frm_week = ttk.Frame(nb); frm_month = ttk.Frame(nb)
        nb.add(frm_week, text="Weekly"); nb.add(frm_month, text="Monthly")
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        def build_table(frame, key: str):
            head = ttk.Frame(frame); head.pack(fill="x", pady=(2, 4))
            ttk.Label(head, text="Tag", width=18, anchor="w").pack(side="left")
            ttk.Label(head, text="Target (min)", anchor="w").pack(side="left")

            rows: List[tuple[str, tk.StringVar]] = []
            period_map = dict(self.state.goals.get(key, {}))
            tags = sorted(set(self.state.config.get("tags", [])) | set(period_map.keys()))

            body = ttk.Frame(frame); body.pack(fill="both", expand=True)
            for tag in tags:
                r = ttk.Frame(body); r.pack(fill="x", pady=2)
                ttk.Label(r, text=tag, width=18, anchor="w").pack(side="left")
                v = tk.StringVar(value=str(period_map.get(tag, "")))
                ttk.Entry(r, textvariable=v, width=12).pack(side="left")
                rows.append((tag, v))

            def on_save():
                new_map: Dict[str, int] = {}
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

            ttk.Button(frame, text="Save", command=on_save).pack(side="right", pady=6)

        build_table(frm_week, "weekly")
        build_table(frm_month, "monthly")
        
        # center dialog over parent
        def _center_to_parent(win, parent):
            win.update_idletasks()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            x = px + max((pw - w) // 2, 0)
            y = py + max((ph - h) // 2, 0)
            win.geometry(f"{w}x{h}+{x}+{y}")

        _center_to_parent(dlg, self.frame.winfo_toplevel())

    # ---------- notebook events ----------

    def _on_tab_changed(self, event) -> None:
        """Force a clean redraw when this tab becomes visible."""
        nb = event.widget
        if nb.tab(nb.select(), "text") == "Dashboard":
            # Draw immediately after geometry settles a little
            self.frame.after(80, self._force_redraw)

    def _force_redraw(self) -> None:
        """Resync figure to container pixels and redraw immediately (idempotent)."""
        try:
            # Cancel any pending debounced jobs, then draw now
            if hasattr(self, "_resize_job") and self._resize_job is not None:
                self.chart_wrap.after_cancel(self._resize_job)
                self._resize_job = None

            w = max(self.chart_wrap.winfo_width(), 1)
            h = max(self.chart_wrap.winfo_height(), 1)
            if w < 160 or h < 160:
                # Retry if geometry is not stable yet
                self._resize_job = self.chart_wrap.after(60, self._force_redraw)
                return

            dpi = self.fig.get_dpi()
            self.fig.set_size_inches(w / dpi, h / dpi)
            self.fig.subplots_adjust(left=0.12, right=0.85, top=0.90, bottom=0.22)
            self.canvas.draw()
        except Exception:
            pass
