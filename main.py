# main.py
import tkinter as tk
from tkinter import ttk
from app_state import AppState
from ui_timer import TimerTab
from ui_dashboard import DashboardTab
from ui_milestones import MilestonesTab

def center_window(window, width=960, height=740):
    """Center window on screen with given size"""
    # Get screen dimensions
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Calculate position coordinates
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    # Set window size and position
    window.geometry(f"{width}x{height}+{x}+{y}")

def main():
    # main window
    root = tk.Tk()
    root.title("Pomotask")
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
