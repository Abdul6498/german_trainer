"""Application theme setup for a cleaner ttk look."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def apply_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg = "#f5f7fb"
    card = "#ffffff"
    text = "#1f2937"
    accent = "#0f766e"

    root.configure(bg=bg)
    style.configure(".", background=bg, foreground=text)
    style.configure("TFrame", background=bg)
    style.configure("TLabelframe", background=bg, borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", background=bg, foreground="#0f172a", font=("TkDefaultFont", 10, "bold"))
    style.configure("TLabel", background=bg, foreground=text)
    style.configure("TCheckbutton", background=bg, foreground=text)
    style.configure("TButton", padding=(10, 6), background=card, foreground=text)
    style.map("TButton", background=[("active", "#ecfeff"), ("pressed", "#ccfbf1")], foreground=[("active", "#0f172a")])

    style.configure(
        "Treeview",
        background=card,
        fieldbackground=card,
        foreground=text,
        rowheight=26,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "Treeview.Heading",
        background="#e2e8f0",
        foreground="#111827",
        font=("TkDefaultFont", 10, "bold"),
        relief="flat",
    )
    style.map("Treeview", background=[("selected", "#d1fae5")], foreground=[("selected", "#064e3b")])
    style.configure("Accent.TLabel", foreground=accent)
