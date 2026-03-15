"""Shared helpers for safe popup behavior."""

from __future__ import annotations

import tkinter as tk


def pin_window_temporarily(window: tk.Toplevel, milliseconds: int = 300) -> None:
    """Bring window to front briefly without crashing if it closes early."""
    window.lift()
    window.attributes("-topmost", True)

    def _unset_topmost() -> None:
        try:
            if window.winfo_exists():
                window.attributes("-topmost", False)
        except tk.TclError:
            return

    window.after(milliseconds, _unset_topmost)


def place_bottom_right(window: tk.Toplevel, *, margin_x: int = 18, margin_y: int = 56) -> None:
    """Place a toplevel at bottom-right of the current screen/work area."""
    try:
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = max(0, screen_w - width - margin_x)
        y = max(0, screen_h - height - margin_y)
        window.geometry(f"+{x}+{y}")
    except tk.TclError:
        return
