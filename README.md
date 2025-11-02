# Pomotask

## Main file to run

`main.py`

## Description

A simple Pomodoro-style productivity tool provides:

1. A timer
2. Session logging saved to a CSV file
3. Tag and note management for each session.
4. A data visualization dashboard (weekly/monthly statistics using NumPy + Matplotlib).
5. Goal tracking with progress bars for each tag

The project uses Tkinter for GUI and includes features such as file I/O and NumPy-based data aggregation.

## Quick Start

```py
# 1) Ensure Python 3.10+ is installed on your computer.
# 2) Install the required libraries by running in terminal
pip install matplotlib numpy
# 3) Open a terminal in the same folder as app.py and run:
python main.py
```

The Pomotask window will appear with these tabs:

- Timer – start a study timer, add notes, and end sessions.  
  - Enable Pomodoro auto mode: (Work (25min) - Short break (5min)) * 4 + Long break (15min)
  - Normal mode: Custom countdown duration
- Dashboard
  - view your weekly/monthly statistics
  - Set goals and view goal progress
- Milestones
  - add countdowns and anniversaries
  - shows “X days left / Y days since”
  - After editing (or add/delete), Click "Save All"

## Note for Tutor

This program uses tkinter and matplotlib, which do not run in Ed’s online environment.
Please run this project locally on your computer to see the GUI and charts.
