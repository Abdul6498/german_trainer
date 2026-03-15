"""Study-first popup window for previewing word details before quizzing."""

from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from engine.quiz_engine import QuizItem
from ui.window_utils import pin_window_temporarily


@dataclass
class StudySubmission:
    understood: bool


class StudyWindow:
    """Display German word details and collect understanding confirmation."""

    def __init__(self, root: tk.Tk, on_play_pronunciation, view_mode: str = "basic") -> None:
        self.root = root
        self.on_play_pronunciation = on_play_pronunciation
        self.view_mode = view_mode if view_mode in {"basic", "detail"} else "basic"

    def show(self, quiz: QuizItem) -> StudySubmission:
        window = tk.Toplevel(self.root)
        window.title("German Trainer")
        if self.view_mode == "basic":
            window.geometry("500x300")
            window.minsize(460, 260)
            window.resizable(False, False)
        else:
            window.geometry("1080x780")
            window.minsize(860, 620)
            window.resizable(True, True)
        pin_window_temporarily(window)

        if self.view_mode == "basic":
            submission = self._show_basic(window, quiz)
        else:
            submission = self._show_detail(window, quiz)

        return submission

    def _show_detail(self, window: tk.Toplevel, quiz: QuizItem) -> StudySubmission:
        shell = ttk.Frame(window, padding=14)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="German Trainer - Study", font=("TkDefaultFont", 14, "bold")).pack(pady=(2, 6))
        ttk.Label(shell, text=f"German: {quiz.german_word}", font=("TkDefaultFont", 14, "bold")).pack(pady=2)
        ttk.Label(shell, text=f"English: {quiz.english_word}", font=("TkDefaultFont", 11)).pack(pady=2)
        ttk.Label(shell, text=f"Word type: {quiz.word_type}", font=("TkDefaultFont", 11)).pack(pady=1)
        if quiz.cefr_level:
            ttk.Label(shell, text=f"Detected CEFR: {quiz.cefr_level}").pack(pady=1)

        body_host = ttk.Frame(shell)
        body_host.pack(fill="both", expand=True, pady=8)
        body_canvas = tk.Canvas(body_host, highlightthickness=0)
        body_scrollbar = ttk.Scrollbar(body_host, orient="vertical", command=body_canvas.yview)
        body_canvas.configure(yscrollcommand=body_scrollbar.set)
        body_scrollbar.pack(side="right", fill="y")
        body_canvas.pack(side="left", fill="both", expand=True)
        body = ttk.Frame(body_canvas)
        body_window_id = body_canvas.create_window((0, 0), window=body, anchor="nw")

        def _resize_body(_event: tk.Event) -> None:
            body_canvas.configure(scrollregion=body_canvas.bbox("all"))
            body_canvas.itemconfigure(body_window_id, width=body_canvas.winfo_width())

        body.bind("<Configure>", _resize_body)
        body_canvas.bind("<Configure>", _resize_body)
        body_canvas.bind("<MouseWheel>", lambda event: body_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units"))
        body_canvas.bind("<Button-4>", lambda _event: body_canvas.yview_scroll(-1, "units"))
        body_canvas.bind("<Button-5>", lambda _event: body_canvas.yview_scroll(1, "units"))
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        summary_rows = [
            ("Article", quiz.noun_info.article or "-"),
            ("Plural", quiz.noun_info.plural or "-"),
            ("Gender", quiz.noun_info.gender or "-"),
            ("Word Type", quiz.word_type or "-"),
            ("CEFR", quiz.cefr_level or "-"),
        ]
        self._add_kv_table(body, "Core Details", summary_rows, row=0, col=0, col_span=2, height=5)

        sentence_rows = [(sentence,) for sentence in quiz.examples]
        self._add_single_col_table(body, "Example Sentences", "sentence", sentence_rows, row=1, col=0)

        if quiz.conjugations:
            conjugation_rows = [(k, v) for k, v in quiz.conjugations.items()]
            self._add_kv_table(body, "Verb Conjugation (Present)", conjugation_rows, row=1, col=1)

        dict_rows = self._analysis_rows(quiz.analysis_details)
        self._add_kv_table(body, "verbformen Details", dict_rows, row=2, col=0)

        noun_meta_rows: list[tuple[str, str]] = []
        if quiz.noun_details:
            noun_meta_rows.extend(
                [
                    ("lemma", str(quiz.noun_details.get("lemma", "-"))),
                    ("genus", str(quiz.noun_details.get("genus", "-"))),
                    ("pos", str(quiz.noun_details.get("pos", "-"))),
                ]
            )
        if quiz.compound_parts:
            noun_meta_rows.append(("compound parts", ", ".join(quiz.compound_parts)))
        if not noun_meta_rows:
            noun_meta_rows = [("noun details", "-")]
        self._add_kv_table(body, "Noun Meta", noun_meta_rows, row=2, col=1)

        flexion_rows: list[tuple[str, str]] = []
        flexion = quiz.noun_details.get("flexion", {}) if quiz.noun_details else {}
        if isinstance(flexion, dict):
            order = [
                "nominativ singular",
                "akkusativ singular",
                "dativ singular",
                "genitiv singular",
                "nominativ plural",
                "akkusativ plural",
                "dativ plural",
                "genitiv plural",
            ]
            for key in order:
                if key in flexion:
                    flexion_rows.append((key, str(flexion[key])))
        if flexion_rows:
            self._add_kv_table(body, "Noun Flexion", flexion_rows, row=3, col=0, col_span=2, height=8)

        if quiz.ai_word_notes:
            note_rows = [(line,) for line in quiz.ai_word_notes]
            self._add_single_col_table(body, "AI Level Explanation", "note", note_rows, row=4, col=0)

        understood_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            shell,
            text="Yes, I understand this word. Next time quiz me with English prompt.",
            variable=understood_var,
        ).pack(anchor="w", padx=14, pady=6)

        result = {"submission": None}

        def submit() -> None:
            result["submission"] = StudySubmission(understood=understood_var.get())
            window.destroy()

        actions = ttk.Frame(shell)
        actions.pack(fill="x", padx=14, pady=8)
        ttk.Button(actions, text="Play pronunciation", command=lambda: self.on_play_pronunciation(self._spoken_word(quiz))).pack(
            side="left"
        )
        ttk.Button(actions, text="Continue", command=submit).pack(side="right")

        window.protocol("WM_DELETE_WINDOW", submit)
        window.update_idletasks()
        window.deiconify()
        window.focus_force()

        while result["submission"] is None and window.winfo_exists():
            self.root.update()
            time.sleep(0.05)

        return result["submission"] or StudySubmission(understood=False)

    def _show_basic(self, window: tk.Toplevel, quiz: QuizItem) -> StudySubmission:
        shell = ttk.Frame(window, padding=12)
        shell.pack(fill="both", expand=True)

        top = ttk.Frame(shell)
        top.pack(fill="x", pady=(0, 10))
        ttk.Label(top, text=f"German: {quiz.german_word}", font=("TkDefaultFont", 12, "bold")).pack(side="left")
        ttk.Label(top, text=f"English: {quiz.english_word}", font=("TkDefaultFont", 11)).pack(side="right")

        details = ttk.LabelFrame(shell, text="Quick Details", padding=8)
        details.pack(fill="x")
        info_line = f"Type: {quiz.word_type}"
        if quiz.word_type == "noun":
            info_line += f" | Article: {quiz.noun_info.article or '-'} | Plural: {quiz.noun_info.plural or '-'}"
        if quiz.cefr_level:
            info_line += f" | CEFR: {quiz.cefr_level}"
        ttk.Label(details, text=info_line, wraplength=450).pack(anchor="w")
        if quiz.examples:
            ttk.Label(details, text=f"Example: {quiz.examples[0]}", wraplength=450).pack(anchor="w", pady=(6, 0))

        understood_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            shell,
            text="I understand this word. Next time quiz me with English prompt.",
            variable=understood_var,
        ).pack(anchor="w", pady=(10, 8))

        result = {"submission": None}

        def submit() -> None:
            result["submission"] = StudySubmission(understood=understood_var.get())
            window.destroy()

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 2))
        ttk.Button(actions, text="Play", command=lambda: self.on_play_pronunciation(self._spoken_word(quiz))).pack(side="left")
        ttk.Button(actions, text="Continue", command=submit).pack(side="right")

        window.protocol("WM_DELETE_WINDOW", submit)
        window.update_idletasks()
        window.deiconify()
        window.focus_force()

        while result["submission"] is None and window.winfo_exists():
            self.root.update()
            time.sleep(0.05)

        return result["submission"] or StudySubmission(understood=False)

    @staticmethod
    def _add_kv_table(
        parent: ttk.Frame,
        title: str,
        rows: list[tuple[str, str]],
        row: int,
        col: int,
        col_span: int = 1,
        height: int = 6,
    ) -> None:
        frame = ttk.LabelFrame(parent, text=title)
        frame.grid(row=row, column=col, columnspan=col_span, sticky="nsew", padx=4, pady=4)
        tree = ttk.Treeview(frame, columns=("field", "value"), show="headings", height=height)
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        tree.heading("field", text="Field")
        tree.heading("value", text="Value")
        tree.column("field", width=220, anchor="w", stretch=True)
        tree.column("value", width=620 if col_span == 2 else 420, anchor="w", stretch=True)
        for field, value in rows:
            tree.insert("", "end", values=(field, value))
        y_scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, padx=4, pady=(4, 0))
        x_scroll.pack(fill="x", padx=4, pady=(0, 2))

    @staticmethod
    def _add_single_col_table(
        parent: ttk.Frame,
        title: str,
        col_name: str,
        rows: list[tuple[str]],
        row: int,
        col: int,
    ) -> None:
        frame = ttk.LabelFrame(parent, text=title)
        frame.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
        tree = ttk.Treeview(frame, columns=(col_name,), show="headings", height=6)
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        tree.heading(col_name, text="Sentence")
        tree.column(col_name, width=500, anchor="w", stretch=True)
        for data in rows:
            tree.insert("", "end", values=data)
        y_scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, padx=4, pady=(4, 0))
        x_scroll.pack(fill="x", padx=4, pady=(0, 2))

    @staticmethod
    def _analysis_rows(details: dict[str, object]) -> list[tuple[str, str]]:
        if not details:
            return [("details", "no online verbformen details available")]

        rows: list[tuple[str, str]] = []
        for key, value in details.items():
            if key == "flexion":
                continue
            text = str(value).replace("\n", " ").strip()
            if len(text) > 120:
                text = f"{text[:117]}..."
            rows.append((key, text))
        if not rows:
            rows = [("details", "available")]
        return rows

    @staticmethod
    def _spoken_word(quiz: QuizItem) -> str:
        if quiz.word_type == "noun" and quiz.noun_info.article:
            return f"{quiz.noun_info.article} {quiz.german_word}"
        return quiz.german_word
