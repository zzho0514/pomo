# main.py
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
import ctypes

from app_state import AppState
from ui_timer import TimerTab
from ui_dashboard import DashboardTab
from ui_milestones import MilestonesTab

def enable_dpi_awareness():
    """
    Windows-only: enable per-monitor DPI awareness before creating Tk root.
    Safe to no-op on other platforms.
    """
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-monitor v2
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()    # Legacy fallback
        except Exception:
            pass

def get_screen_ppi(root: tk.Tk) -> float:
    """
    Return physical pixels per inch for the current display.
    This works cross-platform; Tk returns pixels in '1i' (1 inch).
    """
    try:
        return float(root.winfo_fpixels('1i'))
    except Exception:
        return 96.0  # safe default

def apply_tk_scaling_and_fonts(root: tk.Tk, ppi: float):
    """
    Make all Tk/ttk text crisp by aligning Tk's internal scaling to the real PPI,
    and setting consistent fonts across widgets.
    """
    # 1) Align Tk scaling (72 logical dpi is Tk's default)
    try:
        scale = max(0.5, min(ppi / 72.0, 4.0))  # clamp for safety
        root.tk.call('tk', 'scaling', scale)
    except Exception:
        pass

    # 2) Set global fonts (Segoe UI is crisp on Windows; fallback is fine elsewhere)
    try:
        base = tkfont.nametofont("TkDefaultFont")
        base.configure(family="Segoe UI", size=10)
        for name, size in (("TkTextFont", 10), ("TkMenuFont", 10), ("TkHeadingFont", 11)):
            try:
                tkfont.nametofont(name).configure(family="Segoe UI", size=size)
            except Exception:
                pass
    except Exception:
        pass


def center_window_relative(window: tk.Tk, rel_width: float = 0.6, rel_height: float = 0.7) -> None:
    """
    Center the window as a *percentage* of screen size.
    Called after the first layout pass so Tk knows actual metrics (HD-safe).
    """
    window.update_idletasks()  # ensure Tk has computed widget sizes
    sw, sh = window.winfo_screenwidth(), window.winfo_screenheight()
    w = int(sw * rel_width)
    h = int(sh * rel_height)
    x = (sw - w) // 2
    y = (sh - h) // 2
    window.geometry(f"{w}x{h}+{x}+{y}")


def main():
    # Enable HD before Tk root
    enable_dpi_awareness()
    # main window
    root = tk.Tk()
    root.title("Pomotask")

    # Detect PPI and apply crisp scaling + fonts globally
    ppi = get_screen_ppi(root)
    apply_tk_scaling_and_fonts(root, ppi)

    # Optional: light styling
    style = ttk.Style()
    try:
        style.theme_use("light")
    except Exception:
        pass
    style.configure(".", font=("Segoe UI", 10))
    style.configure("TButton", padding=6)
    style.configure("TLabel", padding=2)

    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)
    
    # Center window on screen
    # center_window(root)

    state = AppState()  # shared app state (config/goals/sessions)

    # tabs
    nb = ttk.Notebook(root)
    tab_timer = TimerTab(nb, state)
    tab_dash  = DashboardTab(nb, state, ppi=ppi)    # pass PPI to the chart tab
    tab_miles = MilestonesTab(nb, state)

    nb.add(tab_timer.frame, text="Timer")
    nb.add(tab_dash.frame,  text="Dashboard")
    nb.add(tab_miles.frame, text="Milestones")
    # nb.pack(fill="both", expand=True)
    nb.grid(row=0, column=0, sticky="nsew")
    root.after_idle(lambda: center_window_relative(root, 0.6, 0.7))

    root.mainloop()

if __name__ == "__main__":
    main()
