"""Result popup window."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from engine.quiz_engine import QuizItem, QuizResult
from ui.window_utils import pin_window_temporarily


class ResultWindow:
    """Display answer feedback after each quiz."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root

    def show(self, quiz: QuizItem, result: QuizResult) -> None:
        window = tk.Toplevel(self.root)
        window.title("German Trainer - Result")
        window.geometry("760x640")
        window.minsize(680, 520)
        window.resizable(True, True)
        pin_window_temporarily(window)

        outcome = "Correct!" if result.is_correct else "Not quite"
        shell = ttk.Frame(window, padding=14)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text=outcome, font=("TkDefaultFont", 15, "bold")).pack(pady=(0, 8))

        summary_lines = [
            f"Expected translation: {result.expected_translation}",
            f"Article: {result.expected_article}",
            f"Plural: {result.expected_plural}",
            f"Word type: {result.expected_type}",
            f"CEFR: {quiz.cefr_level or '-'}",
            f"Focus mode: {quiz.focus_mode}",
            "",
            f"Translation correct: {result.translation_correct}",
            f"Article correct: {result.article_correct}",
            f"Type correct: {result.type_correct}",
            f"Required word in sentence: {result.sentence_has_required_word}",
            f"Sentence correct: {result.sentence_correct}",
        ]

        if result.sentence_corrected:
            summary_lines.append(f"Corrected sentence: {result.sentence_corrected}")

        if result.sentence_issues:
            summary_lines.append("Sentence issues:")
            for issue in result.sentence_issues:
                summary_lines.append(f"- {issue}")

        if result.sentence_translation_en:
            summary_lines.append("")
            summary_lines.append(f"AI English translation: {result.sentence_translation_en}")

        if result.sentence_structure:
            summary_lines.append(f"AI sentence structure: {result.sentence_structure}")

        if result.sentence_structure_points:
            summary_lines.append("AI structure notes:")
            for point in result.sentence_structure_points:
                summary_lines.append(f"- {point}")

        summary_lines.extend(["", "Example sentences:"])

        for sentence in result.examples:
            summary_lines.append(f"- {sentence}")

        if result.conjugations:
            summary_lines.append("")
            summary_lines.append("Verb conjugation:")
            for pronoun, form in result.conjugations.items():
                summary_lines.append(f"{pronoun}: {form}")

        if quiz.analysis_details:
            summary_lines.append("")
            summary_lines.append("verbformen details:")
            for key, value in quiz.analysis_details.items():
                summary_lines.append(f"{key}: {value}")

        text = ScrolledText(shell, wrap="word", height=24)
        text.insert("1.0", "\n".join(summary_lines))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True, pady=8)

        ttk.Button(shell, text="Close", command=window.destroy).pack(pady=(4, 2))
        window.protocol("WM_DELETE_WINDOW", window.destroy)
        window.update_idletasks()
        window.deiconify()
        window.focus_force()

        while window.winfo_exists():
            self.root.update()
            time.sleep(0.05)
