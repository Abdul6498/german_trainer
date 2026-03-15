"""Interactive quiz popup window."""

from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from engine.quiz_engine import QuizItem
from ui.window_utils import pin_window_temporarily


@dataclass
class QuizSubmission:
    translation: str
    article: str
    word_type: str
    sentence: str
    learned: bool
    skipped: bool


class QuizWindow:
    """Collect user answers for a quiz item."""

    def __init__(self, root: tk.Tk, on_play_pronunciation) -> None:
        self.root = root
        self.on_play_pronunciation = on_play_pronunciation

    def show(self, quiz: QuizItem) -> QuizSubmission:
        window = tk.Toplevel(self.root)
        window.title("German Trainer - Quiz")
        window.geometry("640x520")
        window.resizable(True, True)
        pin_window_temporarily(window)

        shell = ttk.Frame(window, padding=14)
        shell.pack(fill="both", expand=True)

        ttk.Label(shell, text="QUIZ MODE", font=("TkDefaultFont", 15, "bold")).pack(pady=(2, 10))
        ttk.Label(shell, text="Translate this word:").pack()
        ttk.Label(shell, text=f"ENGLISH WORD: {quiz.english_word}", font=("TkDefaultFont", 12, "bold")).pack(pady=4)
        ttk.Label(shell, text=f"Exercise focus: {quiz.focus_mode}").pack(pady=2)
        if quiz.cefr_level:
            ttk.Label(shell, text=f"Detected level: {quiz.cefr_level}").pack(pady=1)

        card = ttk.LabelFrame(shell, text="Your Answers", padding=10)
        card.pack(fill="both", expand=True, pady=(10, 8))
        content = ttk.Frame(card)
        content.pack(fill="x", padx=14, pady=8)
        content.columnconfigure(1, weight=1)

        ttk.Label(content, text="German translation:").grid(row=0, column=0, sticky="w", pady=4)
        translation_var = tk.StringVar()
        translation_entry = ttk.Entry(content, textvariable=translation_var)
        translation_entry.grid(row=0, column=1, sticky="ew")

        ttk.Label(content, text="Article:").grid(row=1, column=0, sticky="w", pady=4)
        article_var = tk.StringVar(value="der")
        article_combo = ttk.Combobox(content, textvariable=article_var, values=["der", "die", "das"], state="readonly", width=10)
        article_combo.grid(row=1, column=1, sticky="w")

        ttk.Label(content, text="Word type:").grid(row=2, column=0, sticky="w", pady=4)
        type_var = tk.StringVar(value="noun")
        type_combo = ttk.Combobox(
            content,
            textvariable=type_var,
            values=["noun", "verb", "adjective", "adverb", "preposition"],
            state="readonly",
            width=12,
        )
        type_combo.grid(row=2, column=1, sticky="w")

        ttk.Label(content, text="Example sentence:").grid(row=3, column=0, sticky="nw", pady=4)
        sentence_box = tk.Text(content, height=5, wrap="word")
        sentence_box.grid(row=3, column=1, sticky="ew")

        learned_var = tk.BooleanVar(value=False)
        learned_check = ttk.Checkbutton(
            content,
            text="I have learned this word (move to next word)",
            variable=learned_var,
        )
        learned_check.grid(row=4, column=1, sticky="w", pady=6)

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 6))

        result = {"submission": None}

        def submit(skipped: bool = False) -> None:
            result["submission"] = QuizSubmission(
                translation=translation_var.get().strip(),
                article=article_var.get().strip(),
                word_type=type_var.get().strip(),
                sentence=sentence_box.get("1.0", "end").strip(),
                learned=learned_var.get(),
                skipped=skipped,
            )
            window.destroy()

        ttk.Button(
            actions,
            text="Play pronunciation",
            command=lambda: self.on_play_pronunciation(self._spoken_word(quiz)),
        ).pack(side="left")
        ttk.Button(actions, text="Skip (Esc)", command=lambda: submit(skipped=True)).pack(side="left", padx=8)
        ttk.Button(actions, text="Submit", command=submit).pack(side="right")

        window.bind("<Escape>", lambda _event: submit(skipped=True))
        window.protocol("WM_DELETE_WINDOW", lambda: submit(skipped=True))
        window.update_idletasks()
        window.deiconify()
        window.focus_force()
        translation_entry.focus_set()

        # Avoid nested modal wait loops that can become invisible/unresponsive on WSL.
        while result["submission"] is None and window.winfo_exists():
            self.root.update()
            time.sleep(0.05)

        return result["submission"] or QuizSubmission("", "", "noun", "", False, True)

    @staticmethod
    def _spoken_word(quiz: QuizItem) -> str:
        if quiz.word_type == "noun" and quiz.noun_info.article:
            return f"{quiz.noun_info.article} {quiz.german_word}"
        return quiz.german_word
