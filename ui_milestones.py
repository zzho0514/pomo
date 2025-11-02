# ui_milestones.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime
from typing import Dict, Any, List, Tuple

from storage import load_milestones, save_milestones


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()

def _today() -> date:
    return date.today()

class MilestonesTab:
    """
    A dedicated tab for managing Milestones:
      - Two tables: Countdown (future dates) and Since (past dates)
      - Add / Edit / Delete / Save
      - Days column is computed relative to today
    Data is persisted in data/milestones.json via storage helpers.
    """
    def __init__(self, parent, state=None):
        # state is optional; kept for consistency with other tabs
        self.state = state
        self.frame = ttk.Frame(parent, padding=(8, 8))

        # Global style for Treeview: unify row height and font
        style = ttk.Style()
        style.configure("Milestone.Treeview",
                        rowheight=28,
                        font=("Segoe UI", 10))
        style.configure("Milestone.Treeview.Heading",
                        font=("Segoe UI", 10, "bold"))

        self.data: Dict[str, Any] = {"countdown": [], "since": []}
        self._build_ui()
        self._load()

    # ---------- UI ----------
    def _build_ui(self):
        title = tk.Label(self.frame, text="Milestones", font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", pady=(4, 8))

        note = tk.Label(
            self.frame,
            text="Add countdowns (future events) and anniversaries (past events).",
            fg="#666"
        )
        note.pack(anchor="w", pady=(0, 8))

        # Two side-by-side panels
        wrap = tk.Frame(self.frame)
        wrap.pack(fill="both", expand=True)

        # Countdown 
        self.cd_panel = self._build_panel(
            wrap, "Countdown", columns=("Title", "Date", "Days Left"),
            help_text="Events with a future date. Example: Final Exam, 2025-11-20"
        )
        self.cd_panel["frame"].pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Since
        self.sc_panel = self._build_panel(
            wrap, "Since", columns=("Title", "Date", "Days Since"),
            help_text="Events that already happened. Example: Started Uni, 2024-03-01"
        )
        self.sc_panel["frame"].pack(side="left", fill="both", expand=True, padx=(6, 0))

        # Bottom Save button (saves both tables)
        btnbar = tk.Frame(self.frame)
        btnbar.pack(fill="x", pady=(8, 0))
        ttk.Button(btnbar, text="Save All", command=self._save_all).pack(side="right")

    def _build_panel(self, parent, title: str, columns: Tuple[str, str, str], help_text: str):
        """Create a labeled table panel with Add/Edit/Delete buttons."""
        lf = ttk.LabelFrame(parent, text=title, padding=8)

        # Treeview with unified style
        tv = ttk.Treeview(
            lf, columns=columns, show="headings", height=20, style="Milestone.Treeview"
        )
        for c, w in zip(columns, (220, 120, 110)):
            tv.heading(c, text=c)
            tv.column(c, width=w, anchor="w")
        tv.pack(fill="both", expand=True)

        # Hint label
        tk.Label(lf, text=help_text, fg="#777").pack(anchor="w", pady=(4, 0))

        # Button bar
        bar = tk.Frame(lf)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Button(bar, text="Add", command=lambda: self._add_row(tv)).pack(side="left")
        ttk.Button(bar, text="Edit", command=lambda: self._edit_row(tv)).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Delete", command=lambda: self._delete_row(tv)).pack(side="left", padx=(6, 0))

        # Double-click to edit
        tv.bind("<Double-1>", lambda e, t=tv: self._edit_row(t))

        return {"frame": lf, "tree": tv, "columns": columns}

    # ---------- Data I/O ----------
    def _load(self):
        """Load milestones from storage and refresh both views."""
        self.data = load_milestones()
        self._refresh_views()

    def _refresh_views(self):
        """Refresh both Countdown and Since Treeviews."""
        self._fill_tree(self.cd_panel["tree"], self.data.get("countdown", []), mode="countdown")
        self._fill_tree(self.sc_panel["tree"], self.data.get("since", []), mode="since")

    def _fill_tree(self, tv: ttk.Treeview, items: List[Dict[str, str]], mode: str):
        """Populate the given Treeview with sorted milestone data."""
        tv.delete(*tv.get_children())
        today = _today()
        items_sorted = sorted(items, key=lambda x: x.get("date", ""), reverse=(mode == "since"))

        for it in items_sorted:
            title = it.get("title", "").strip()
            ds = it.get("date", "").strip()
            if not title or not ds:
                continue
            try:
                d = _parse_date(ds)
                if mode == "countdown":
                    delta = (d - today).days
                    disp = f"{delta} days left"
                else:
                    delta = (today - d).days
                    disp = f"{delta} days"
            except Exception:
                disp = "?"
            tv.insert("", "end", values=(title, ds, disp))

    def _tree_to_list(self, tv: ttk.Treeview, mode: str) -> List[Dict[str, str]]:
        """Convert all Treeview rows into a serializable list."""
        items = []
        for iid in tv.get_children():
            title, ds, _ = tv.item(iid, "values")
            title = str(title).strip()
            ds = str(ds).strip()
            if title and ds:
                items.append({"title": title, "date": ds})
        items.sort(key=lambda x: x["date"])
        return items

    # ---------- CRUD ----------
    def _add_row(self, tv: ttk.Treeview):
        self._open_editor_dialog(tv)

    def _edit_row(self, tv: ttk.Treeview):
        sel = tv.selection()
        if not sel:
            messagebox.showinfo("Edit", "Please select a row to edit.")
            return
        iid = sel[0]
        vals = tv.item(iid, "values")
        self._open_editor_dialog(tv, iid, existing=vals)

    def _delete_row(self, tv: ttk.Treeview):
        sel = tv.selection()
        if not sel:
            return
        for iid in sel:
            tv.delete(iid)

    def _open_editor_dialog(self, tv: ttk.Treeview, iid: str | None = None, existing=None):
        """Open a popup dialog for adding or editing a milestone."""
        dlg = tk.Toplevel(self.frame)
        dlg.title("Edit Milestone" if existing else "Add Milestone")
        dlg.resizable(True, True)
        dlg.minsize(460, 180)
        dlg.geometry("600x200")

        dlg.transient(self.frame.winfo_toplevel())
        dlg.grab_set()

        def on_cancel():
            dlg.destroy()

        f = ttk.Frame(dlg, padding="12")
        f.pack(fill="both", expand=True)

        ttk.Label(f, text="Title:").grid(row=0, column=0, sticky="e", padx=(0, 6), pady=(0, 6))
        ttk.Label(f, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="e", padx=(0, 6))

        v_title = tk.StringVar(value=existing[0] if existing else "")
        v_date = tk.StringVar(value=existing[1] if existing else "")

        ttk.Entry(f, textvariable=v_title, width=32).grid(row=0, column=1, columnspan=2, sticky="ew")
        ttk.Entry(f, textvariable=v_date, width=32).grid(row=1, column=1, columnspan=2, sticky="ew")

        btn_frame = ttk.Frame(f)
        btn_frame.grid(row=2, column=0, columnspan=3, sticky="e", pady=(12, 0))

        def on_ok():
            t = v_title.get().strip()
            ds = v_date.get().strip()
            if not t or not ds:
                messagebox.showwarning("Invalid", "Title and Date are required.", parent=dlg)
                return
            try:
                _parse_date(ds)
            except ValueError:
                messagebox.showwarning(
                    "Invalid date", "Use YYYY-MM-DD format (e.g., 2025-11-20).", parent=dlg
                )
                return
            if iid is None:
                tv.insert("", "end", values=(t, ds, ""))
            else:
                tv.item(iid, values=(t, ds, ""))
            dlg.destroy()
            self._recompute_days_in_tree(tv)

        ttk.Button(btn_frame, text="OK", command=on_ok).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel).pack(side="left", padx=3)

        dlg.bind("<Return>", lambda e: on_ok())
        dlg.bind("<Escape>", lambda e: on_cancel())
        dlg.focus_set()

        def _center_to_parent(win, parent):
            win.update_idletasks()
            pw, ph = parent.winfo_width(), parent.winfo_height()
            px, py = parent.winfo_rootx(), parent.winfo_rooty()
            w, h = win.winfo_width(), win.winfo_height()
            x = px + max((pw - w) // 2, 0)
            y = py + max((ph - h) // 2, 0)
            win.geometry(f"{w}x{h}+{x}+{y}")

        _center_to_parent(dlg, self.frame.winfo_toplevel())

    def _save_all(self):
        """Save both tables to JSON."""
        self.data["countdown"] = self._tree_to_list(self.cd_panel["tree"], "countdown")
        self.data["since"] = self._tree_to_list(self.sc_panel["tree"], "since")
        try:
            save_milestones(self.data)
            messagebox.showinfo("Saved", "Milestones saved.")
        except Exception as e:
            messagebox.showwarning("Save failed", str(e))
        self._refresh_views()

    def _recompute_days_in_tree(self, tv: ttk.Treeview):
        """Recalculate the 'days left/since' column for all rows."""
        today = _today()
        mode = "countdown" if tv is self.cd_panel["tree"] else "since"
        for iid in tv.get_children():
            title, ds, _ = tv.item(iid, "values")
            try:
                d = _parse_date(str(ds).strip())
                if mode == "countdown":
                    delta = (d - today).days
                    disp = f"{delta} days left"
                else:
                    delta = (today - d).days
                    disp = f"{delta} days"
            except Exception:
                disp = "?"
            tv.item(iid, values=(title, ds, disp))