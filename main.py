# main.py
import tkinter as tk
from tkinter import ttk
from app_state import AppState
from ui_timer import TimerTab
from ui_dashboard import DashboardTab
from ui_milestones import MilestonesTab

import ctypes
from tkinter import font as tkfont

def enable_dpi_awareness():
    """Enable DPI awareness on Windows so Tk windows render sharply on high-DPI displays."""
    try:
        # Try Per-Monitor v2 / v1, fall back to legacy SetProcessDPIAware
        shcore = ctypes.windll.shcore
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
        except Exception:
            pass


def center_window(window, width=1080, height=860):
    """Center window on screen with given size"""
    # Get screen dimensions
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Calculate position coordinates
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    # Set window size and position
    window.geometry(f"{width}x{height}+{x}+{y}")

actual_ppi = 96.0
def adjust_tk_scaling(root: tk.Tk):
    """
    Adjust Tk scaling based on actual pixels-per-inch so fonts/widgets are crisp.
    Should be called *after* creating the root window.
    """
    try:
        # Query pixels per inch
        ppi = root.winfo_fpixels('1i')
        '''
        scale = ppi / 72.0  # 72 dpi = Tk default
        root.tk.call('tk', 'scaling', scale)
        '''
        actual_ppi = float(ppi)
    except Exception:
        pass

def main():
    try:
        enable_dpi_awareness()
    except Exception:
        pass
    # main window
    root = tk.Tk()
    root.title("Pomotask")

    # Adjust Tk scaling based on actual pixels-per-inch so fonts/widgets are crisp
    adjust_tk_scaling(root)

    # Tweak default fonts to a crisp system font (Segoe UI) and sensible sizes
    try:
        default_font = tkfont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=9)
        for name, size in (("TkTextFont", 10), ("TkMenuFont", 9), ("TkHeadingFont", 11)):
            try:
                f = tkfont.nametofont(name)
                f.configure(family="Segoe UI", size=size)
            except Exception:
                pass
    except Exception:
        pass

    # Center window on screen
    center_window(root)

    # Optional: light styling
    style = ttk.Style()
    try:
        style.theme_use("light")
    except Exception:
        pass
    style.configure("TButton", padding=6)
    style.configure("TLabel", padding=2)

    state = AppState()  # shared app state (config/goals/sessions)

    # tabs
    nb = ttk.Notebook(root)
    tab_timer = TimerTab(nb, state)
    tab_dash  = DashboardTab(nb, state)
    tab_miles = MilestonesTab(nb, state)
    nb.add(tab_timer.frame, text="Timer")
    nb.add(tab_dash.frame,  text="Dashboard")
    nb.add(tab_miles.frame, text="Milestones")
    nb.pack(fill="both", expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
