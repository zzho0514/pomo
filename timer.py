# timer.py
from __future__ import annotations
import time
from typing import Callable, Optional

class Timer:
    """
    a countdown timer
    supports start, pause, reset, and callback on finish
    """
    def __init__(self, 
                 on_tick: Callable[[int], None],
                 on_finish: Optional[Callable[[], None]] = None):
        self._on_tick = on_tick # callback every second with remaining time
        self._on_finish = on_finish # callback when timer finishes

        self._running = False # is the timer running
        self._after_id = None # for storing after job id
        self._remaining = 25*60 # remaining time in seconds, default 25 minutes
        self._end_time = None # target end timestamp
        self._tkroot = None # reference to Tk root for after method

    # ----- properties -----
    @property
    def running(self) -> bool:
        """return wether timer running"""
        return self._running

    @property
    def remaining(self) -> int:
        """return remaining seconds (>=0)"""
        return max(0, int(self._remaining))

    @staticmethod
    def format_mmss(seconds: int) -> str:
        """format seconds as MM:SS"""
        mm = seconds // 60
        ss = seconds % 60
        return f"{mm:02d}:{ss:02d}"

    # ----- outer controls -----
    def set_seconds(self, seconds: int) -> None:
        """set remaining seconds"""
        if self._running:
            return
        self._remaining = max(0, int(seconds))

    def start(self, tkroot) -> None:
        """start the countdown"""
        if self._running:
            return
        self._tkroot = tkroot
        self._running = True
        # end_ts = current time + remaining
        self._end_ts = time.time() + self._remaining
        self._schedule_next_tick()

    def pause(self) -> None:
        """pause the countdown"""
        if not self._running:
            return
        self._running = False
        self._cancel_after()
        # upsate remaining based on end_ts
        if self._end_ts is not None:
            self._remaining = max(0, int(round(self._end_ts - time.time())))
            self._end_ts = None

    def reset(self, seconds: Optional[int] = None) -> None:
        """
        reset the countdown; if seconds is given, set to that value
        will pause if running
        """
        self.pause()
        if seconds is not None:
            self._remaining = max(0, int(seconds))
        # update UI
        self._on_tick(self.remaining)

    # ----- internal methods -----
    def _schedule_next_tick(self) -> None:
        """schedule the next tick after 1000ms"""
        if self._tkroot is None:
            return
        # call tick immediately to update UI
        self._tick()
        # if running, schedule next tick after 1000ms
        if self._running:
            self._after_id = self._tkroot.after(1000, self._schedule_next_tick)

    def _tick(self) -> None:
        """
        update remaining time
        call on_tick callback with remaining time
        """
        if not self._running:
            return
        now = time.time()
        if self._end_ts is None:
            # defensive: should not happen
            self._end_ts = now + self._remaining

        self._remaining = max(0, int(round(self._end_ts - now)))
        self._on_tick(self.remaining)

        if self._remaining <= 0:
            # tiemer finished, stop it, call on_finish
            self._running = False
            self._cancel_after()
            if self._on_finish:
                self._on_finish()

    def _cancel_after(self) -> None:
        """cancel any pending TK after"""
        if self._tkroot is not None and self._after_id is not None:
            try:
                self._tkroot.after_cancel(self._after_id)
            except Exception:
                pass
            finally:
                self._after_id = None