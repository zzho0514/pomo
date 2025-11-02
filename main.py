# main.py
import tkinter as tk
from tkinter import ttk
from app_state import AppState
from ui_timer import TimerTab
from ui_dashboard import DashboardTab

def main():
    # main window
    root = tk.Tk()
    root.title("Pomotask")
    root.geometry("900x740") # width x height

    # Optional: light styling
    style = ttk.Style()
    try:
        style.theme_use("light")
    except Exception:
        pass
    style.configure("TButton", padding=6)
    style.configure("TLabel", padding=2)

    state = AppState()  # shared app state (config/goals/sessions)

    nb = ttk.Notebook(root)
    tab_timer = TimerTab(nb, state)
    tab_dash  = DashboardTab(nb, state)
    nb.add(tab_timer.frame, text="Timer")
    nb.add(tab_dash.frame,  text="Dashboard")
    nb.pack(fill="both", expand=True)

    root.mainloop()

if __name__ == "__main__":
    main()
