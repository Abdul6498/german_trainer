"""Entry point for the German Trainer desktop app."""

from __future__ import annotations

import argparse
import os
import signal
import time
import tkinter as tk
from pathlib import Path

import schedule
from rich.console import Console
from rich.table import Table

from engine.grammar_checker import GrammarChecker
from engine.quiz_engine import QuizEngine
from engine.sentence_generator import SentenceGenerator
from engine.spaced_repetition import SpacedRepetitionEngine
from services.ai_sentence_service import AISentenceService
from services.ai_translator import AITranslatorService
from services.ai_word_service import AIWordService
from services.progress_tracker import ProgressTracker
from services.pronunciation import PronunciationService
from services.sentence_checker import SentenceChecker
from services.translator import TranslatorService
from services.word_source import WordSource
from ui.quiz_window import QuizWindow
from ui.result_window import ResultWindow
from ui.study_window import StudyWindow
from ui.theme import apply_theme


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="German Trainer")
    parser.add_argument("--interval-minutes", type=int, default=5, help="Minutes between popup quizzes.")
    parser.add_argument(
        "--level",
        default="A1.1",
        help="CEFR level/sub-level (A1.1, A1.2, A2.1, A2.2, B1.1, B1.2).",
    )
    parser.add_argument(
        "--srs-intensity",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="How aggressively the spaced repetition repeats mistakes.",
    )
    parser.add_argument(
        "--mode",
        choices=["mixed", "study-only", "quiz-only"],
        default="mixed",
        help="Learning flow mode: study-only, quiz-only, or mixed stage progression.",
    )
    parser.add_argument(
        "--view",
        choices=["basic", "detail"],
        default="basic",
        help="Study card detail level: basic essentials or full dictionary detail.",
    )
    parser.add_argument(
        "--sentence-source",
        choices=["ai"],
        default="ai",
        help="Sentence generation/correction backend (AI only).",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-4.1-mini",
        help="OpenAI model for AI sentence mode.",
    )
    parser.add_argument(
        "--word-source",
        choices=["ai", "local"],
        default="ai",
        help="Vocabulary source backend.",
    )
    parser.add_argument(
        "--translation-source",
        choices=["ai", "deep-translator"],
        default="ai",
        help="Translation backend.",
    )
    parser.add_argument(
        "--daily-goal-words",
        type=int,
        default=60,
        help="Daily target for new words. Before goal: prefer new words. After goal: prefer repeats.",
    )
    parser.add_argument(
        "--ai-notes",
        choices=["off", "short", "full"],
        default="off",
        help="AI word explanation note density: off (least tokens), short, or full.",
    )
    return parser.parse_args()


def render_stats(console: Console, stats: dict[str, object]) -> None:
    table = Table(title="German Trainer Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Total Questions", str(stats.get("total_questions", 0)))
    table.add_row("Correct", str(stats.get("correct_answers", 0)))
    table.add_row("Wrong", str(stats.get("wrong_answers", 0)))
    table.add_row("Accuracy", f"{stats.get('accuracy', 0.0)}%")
    table.add_row("Last Updated", str(stats.get("last_updated", "")))
    console.print(table)


def main() -> None:
    args = parse_args()
    root_dir = Path(__file__).resolve().parent
    console = Console()

    if os.name != "nt" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        console.print(
            "No GUI display detected. In WSL, enable WSLg or set DISPLAY before running tkinter popups."
        )
        return

    console.print(
        f"Starting German Trainer (interval={args.interval_minutes}m, level={args.level}, srs={args.srs_intensity}, mode={args.mode}, view={args.view}, sentence_source={args.sentence_source}, word_source={args.word_source}, translation_source={args.translation_source}, model={args.openai_model}, daily_goal_words={args.daily_goal_words}, ai_notes={args.ai_notes})"
    )
    if os.name != "nt":
        console.print(
            f"Display env: DISPLAY={os.environ.get('DISPLAY', '')!r}, WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')!r}"
        )

    progress_tracker = ProgressTracker(root_dir / "storage")
    note_limit = {"off": 0, "short": 2, "full": -1}.get(args.ai_notes, 0)
    progress_tracker.set_meta_note_limit(note_limit)
    progress_tracker.compact_word_meta_store(note_limit=note_limit)
    default_translator = TranslatorService()
    ai_translator = AITranslatorService(
        model=args.openai_model,
        enabled=args.translation_source == "ai",
    )
    translator = ai_translator if args.translation_source == "ai" else default_translator
    grammar_checker = GrammarChecker()
    sentence_generator = SentenceGenerator()
    ai_word_service = AIWordService(
        model=args.openai_model,
        enabled=args.word_source == "ai",
        level=args.level,
    )
    ai_sentence_service = AISentenceService(
        model=args.openai_model,
        enabled=args.sentence_source == "ai",
        style_level=args.level,
        notes_mode=args.ai_notes,
    )
    sentence_checker = SentenceChecker(language="de-DE") if args.sentence_source != "ai" else None
    word_source = WordSource(
        root_dir / "data",
        progress_tracker,
        level=args.level,
        source=args.word_source,
        ai_word_service=ai_word_service,
    )

    if args.word_source == "ai" and not ai_word_service.available:
        console.print(f"AI word source unavailable: {ai_word_service.init_error or 'OpenAI client not initialized'}")
        console.print("Set OPENAI_API_KEY and retry.")
        return

    if args.translation_source == "ai" and not ai_translator.available:
        console.print(
            f"AI translation unavailable: {ai_translator.init_error or 'OpenAI client not initialized'}"
        )
        console.print("Set OPENAI_API_KEY and retry.")
        return

    if args.sentence_source == "ai" and not ai_sentence_service.available:
        console.print("AI sentence source unavailable. Set OPENAI_API_KEY and retry.")
        return
    spaced_repetition = SpacedRepetitionEngine(difficulty=args.srs_intensity)
    pronunciation = PronunciationService()

    def play_pronunciation(word: str) -> None:
        ok, message = pronunciation.play(word)
        if not ok:
            console.print(f"Pronunciation failed for '{word}': {message}")

    engine = QuizEngine(
        translator=translator,
        grammar_checker=grammar_checker,
        sentence_generator=sentence_generator,
        ai_sentence_service=ai_sentence_service,
        sentence_checker=sentence_checker,
        word_source=word_source,
        progress_tracker=progress_tracker,
        spaced_repetition=spaced_repetition,
        sentence_source=args.sentence_source,
        daily_goal_words=args.daily_goal_words,
    )

    new_today = progress_tracker.new_words_today()
    console.print(f"Daily goal progress: {new_today}/{args.daily_goal_words} new words today.")

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        console.print(f"Unable to open tkinter window: {exc}")
        console.print("On WSL, make sure WSLg is enabled and GUI apps can open.")
        return
    root.withdraw()
    study_window = StudyWindow(root, play_pronunciation, view_mode=args.view)
    quiz_window = QuizWindow(root, play_pronunciation)
    result_window = ResultWindow(root)
    running = True
    stopping = False

    def handle_sigint(_signum, _frame) -> None:
        nonlocal running, stopping
        if stopping:
            return
        stopping = True
        running = False
        console.print("Stopping German Trainer (Ctrl+C)...")
        try:
            root.after(0, root.destroy)
        except tk.TclError:
            pass

    signal.signal(signal.SIGINT, handle_sigint)
    apply_theme(root)

    def run_quiz() -> None:
        quiz = engine.create_quiz()
        stage = progress_tracker.get_learning_stage(quiz.english_word)
        if args.mode == "quiz-only" and stage == "study":
            engine.mark_understood(quiz.english_word)
            stage = "quiz"

        if args.mode == "study-only" or (args.mode == "mixed" and stage == "study"):
            console.print(f"Study mode for word: {quiz.english_word}")
            study_submission = study_window.show(quiz)
            if study_submission.understood:
                engine.mark_understood(quiz.english_word)
                console.print(f"Marked understood: {quiz.english_word}. Next time this word will be a quiz.")
            else:
                console.print(f"Kept in study mode: {quiz.english_word}.")
            console.print("Session completed. Waiting for next schedule.")
            return

        console.print("Opening quiz popup...")
        while True:
            console.print(f"Quiz ready for word: {quiz.english_word}")
            submission = quiz_window.show(quiz)
            console.print("Quiz submission received.")

            if submission.learned:
                engine.mark_learned(quiz.english_word)
                console.print(f"Marked learned: {quiz.english_word}. Moving to next word.")
                break

            result = engine.evaluate(
                quiz=quiz,
                user_translation=submission.translation,
                user_article=submission.article,
                user_word_type=submission.word_type,
                user_sentence=submission.sentence,
                skipped=submission.skipped,
            )
            result_window.show(quiz, result)
            render_stats(console, progress_tracker.stats())

            if result.is_correct:
                console.print("Answer correct. Moving to next word.")
                break

            console.print("Answer not correct. Repeating the same word.")
            quiz = engine.create_quiz(english_word=quiz.english_word)

        console.print("Quiz completed. Waiting for next schedule.")

    schedule.every(args.interval_minutes).minutes.do(run_quiz)
    run_quiz()

    try:
        while running:
            root.update()
            schedule.run_pending()
            time.sleep(0.2)
    except tk.TclError:
        pass
    except KeyboardInterrupt:
        handle_sigint(signal.SIGINT, None)


if __name__ == "__main__":
    main()
