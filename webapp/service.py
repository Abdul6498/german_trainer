"""Service layer for the browser-based German Trainer app."""

from __future__ import annotations

from argparse import Namespace
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
import threading

from engine.grammar_checker import GrammarChecker
from engine.quiz_engine import QuizEngine, QuizItem, QuizResult
from engine.sentence_generator import SentenceGenerator
from engine.spaced_repetition import SpacedRepetitionEngine
from services.ai_sentence_service import AISentenceService
from services.ai_translator import AITranslatorService
from services.ai_word_service import AIWordService
from services.progress_tracker import ProgressTracker
from services.sentence_checker import SentenceChecker
from services.translator import TranslatorService
from services.word_source import WordSource
from webapp.schemas import NounInfoPayload, QuizPayload, SessionPayload, StatsPayload


def _model_to_dict(model: object) -> dict[str, object]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    return dict(model)  # type: ignore[arg-type]


class TrainerWebService:
    """Owns trainer state and exposes browser-friendly session operations."""

    def __init__(self, root_dir: Path, args: Namespace) -> None:
        self.root_dir = root_dir
        self.args = args
        self._state_lock = threading.RLock()
        self._current_quiz: QuizItem | None = None
        self._prefetched_quiz: QuizItem | None = None
        self._current_stage: str = "idle"
        self._latest_result: dict[str, object] | None = None
        self._next_due_at = datetime.now()
        self._prefetch_lock = threading.Lock()
        self._prefetch_thread: threading.Thread | None = None
        self._build_runtime()
        self._schedule_prefetch_if_needed()

    def _build_runtime(self) -> None:
        self.progress_tracker = ProgressTracker(self.root_dir / "storage")
        note_limit = {"off": 0, "short": 2, "full": -1}.get(self.args.ai_notes, 0)
        self.progress_tracker.set_meta_note_limit(note_limit)
        self.progress_tracker.compact_word_meta_store(note_limit=note_limit)

        default_translator = TranslatorService()
        ai_translator = AITranslatorService(
            model=self.args.openai_model,
            enabled=self.args.translation_source == "ai",
        )
        if self.args.translation_source == "ai":
            if not ai_translator.available:
                raise RuntimeError(
                    "AI translation requested but unavailable. "
                    f"{ai_translator.init_error or 'Check OPENAI_API_KEY and OpenAI package installation.'}"
                )
            self.translator = ai_translator
        else:
            self.translator = default_translator

        grammar_checker = GrammarChecker()
        sentence_generator = SentenceGenerator()
        ai_word_service = AIWordService(
            model=self.args.openai_model,
            enabled=self.args.word_source == "ai",
            level=self.args.level,
        )
        if self.args.word_source == "ai" and not ai_word_service.available:
            raise RuntimeError(
                "AI word source requested but unavailable. "
                f"{ai_word_service.init_error or 'Check OPENAI_API_KEY and OpenAI package installation.'}"
            )
        self.ai_sentence_service = AISentenceService(
            model=self.args.openai_model,
            enabled=self.args.sentence_source == "ai",
            style_level=self.args.level,
            notes_mode=self.args.ai_notes,
        )
        if self.args.sentence_source == "ai" and not self.ai_sentence_service.available:
            raise RuntimeError(
                "AI sentence service requested but unavailable. "
                f"{self.ai_sentence_service.init_error or 'Check OPENAI_API_KEY and OpenAI package installation.'}"
            )
        sentence_checker = SentenceChecker(language="de-DE") if self.args.sentence_source != "ai" else None
        word_source = WordSource(
            self.root_dir / "data",
            self.progress_tracker,
            level=self.args.level,
            source=self.args.word_source,
            ai_word_service=ai_word_service,
        )

        self.engine = QuizEngine(
            translator=self.translator,
            grammar_checker=grammar_checker,
            sentence_generator=sentence_generator,
            ai_sentence_service=self.ai_sentence_service,
            sentence_checker=sentence_checker,
            word_source=word_source,
            progress_tracker=self.progress_tracker,
            spaced_repetition=SpacedRepetitionEngine(difficulty=self.args.srs_intensity),
            sentence_source=self.args.sentence_source,
            daily_goal_words=self.args.daily_goal_words,
        )

    def get_session(self) -> SessionPayload:
        with self._state_lock:
            self._activate_due_card()
            return SessionPayload(
                stage=self._current_stage if self._current_quiz is not None or self._current_stage == "result" else "idle",
                interval_minutes=self.args.interval_minutes,
                next_due_in_seconds=max(0, int((self._next_due_at - datetime.now()).total_seconds())),
                daily_goal_words=self.args.daily_goal_words,
                srs_intensity=self.args.srs_intensity,
                level=self.args.level,
                new_words_today=self.progress_tracker.new_words_today(),
                mode=self.args.mode,
                view=self.args.view,
                quiz=self._serialize_quiz(self._current_quiz) if self._current_quiz is not None else None,
                result=self._latest_result,
                stats=StatsPayload(**self.progress_tracker.stats()),
            )

    def update_settings(
        self,
        level: str,
        srs_intensity: str,
        mode: str,
        view: str,
        daily_goal_words: int,
    ) -> SessionPayload:
        with self._state_lock:
            self.args.level = level
            self.args.srs_intensity = srs_intensity
            self.args.mode = mode
            self.args.view = view
            self.args.daily_goal_words = daily_goal_words
            self._current_quiz = None
            self._prefetched_quiz = None
            self._latest_result = None
            self._current_stage = "idle"
            self._next_due_at = datetime.now()
            self._build_runtime()
            self._schedule_prefetch_if_needed()
            return self.get_session()

    def submit_study(self, understood: bool) -> SessionPayload:
        with self._state_lock:
            if self._current_quiz is None:
                return self.get_session()
            if understood:
                self.engine.mark_understood(self._current_quiz.english_word)
            self._clear_current()
            return self.get_session()

    def submit_quiz(self, submission: dict[str, object]) -> SessionPayload:
        with self._state_lock:
            if self._current_quiz is None:
                return self.get_session()

            if bool(submission.get("learned", False)):
                quiz = self._current_quiz
                self.engine.mark_learned(quiz.english_word)
                self._latest_result = self._serialize_learned_result(quiz)
                self._current_stage = "result"
                self._clear_current(schedule_next=False)
                return self.get_session()

            result = self.engine.evaluate(
                quiz=self._current_quiz,
                user_translation=str(submission.get("translation", "")),
                user_article=str(submission.get("article", "")),
                user_word_type=str(submission.get("word_type", "")),
                user_sentence=str(submission.get("sentence", "")),
                skipped=bool(submission.get("skipped", False)),
            )
            self._latest_result = self._serialize_result(self._current_quiz, result)
            self._current_stage = "result"
            self._clear_current(schedule_next=False)
            return self.get_session()

    def next_after_result(self) -> SessionPayload:
        with self._state_lock:
            self._latest_result = None
            self._current_stage = "idle"
            self._next_due_at = datetime.now() + timedelta(minutes=self.args.interval_minutes)
            self._schedule_prefetch_if_needed()
            return self.get_session()

    def trigger_now(self) -> SessionPayload:
        with self._state_lock:
            self._latest_result = None
            self._next_due_at = datetime.now()
            return self.get_session()

    def _should_prefetch(self) -> bool:
        return self.args.mode != "quiz-only"

    def _schedule_prefetch_if_needed(self) -> None:
        if not self._should_prefetch():
            return
        if self._current_quiz is not None or self._latest_result is not None or self._prefetched_quiz is not None:
            return
        if self._prefetch_thread is not None and self._prefetch_thread.is_alive():
            return

        self._prefetch_thread = threading.Thread(target=self._prefetch_next_quiz, daemon=True)
        self._prefetch_thread.start()

    def _prefetch_next_quiz(self) -> None:
        try:
            quiz = self.engine.create_quiz(mark_presented=False)
        except Exception:
            return

        with self._state_lock, self._prefetch_lock:
            if self._current_quiz is None and self._latest_result is None and self._prefetched_quiz is None and self._should_prefetch():
                self._prefetched_quiz = quiz

    def _activate_due_card(self) -> None:
        if self._latest_result is not None:
            self._current_stage = "result"
            return
        if self._current_quiz is not None:
            return
        if datetime.now() < self._next_due_at:
            return

        quiz: QuizItem | None = None
        with self._prefetch_lock:
            if self._prefetched_quiz is not None:
                quiz = self._prefetched_quiz
                self._prefetched_quiz = None

        if quiz is None:
            quiz = self.engine.create_quiz()
        else:
            self.progress_tracker.mark_word_presented(quiz.english_word)

        stage = self.progress_tracker.get_learning_stage(quiz.english_word)
        if self.args.mode == "quiz-only" and stage == "study":
            self.engine.mark_understood(quiz.english_word)
            stage = "quiz"

        self._current_quiz = quiz
        self._current_stage = "study" if self.args.mode == "study-only" or (self.args.mode == "mixed" and stage == "study") else "quiz"

    def _clear_current(self, schedule_next: bool = True) -> None:
        self._current_quiz = None
        if schedule_next:
            self._current_stage = "idle"
            self._next_due_at = datetime.now() + timedelta(minutes=self.args.interval_minutes)
            self._schedule_prefetch_if_needed()

    @staticmethod
    def _serialize_quiz(quiz: QuizItem | None) -> QuizPayload | None:
        if quiz is None:
            return None
        return QuizPayload(
            english_word=quiz.english_word,
            german_word=quiz.german_word,
            word_type=quiz.word_type,
            cefr_level=quiz.cefr_level,
            noun_info=NounInfoPayload(
                article=quiz.noun_info.article,
                plural=quiz.noun_info.plural,
                gender=quiz.noun_info.gender,
            ),
            examples=quiz.examples,
            ai_word_notes=quiz.ai_word_notes,
            conjugations=quiz.conjugations,
            analysis_details=quiz.analysis_details,
            focus_mode=quiz.focus_mode,
        )

    @staticmethod
    def _serialize_result(quiz: QuizItem, result: QuizResult) -> dict[str, object]:
        payload = asdict(result)
        payload["quiz"] = _model_to_dict(TrainerWebService._serialize_quiz(quiz))
        payload["result_label"] = "Correct!" if result.is_correct else "Not quite"
        return payload

    @staticmethod
    def _serialize_learned_result(quiz: QuizItem) -> dict[str, object]:
        quiz_payload = _model_to_dict(TrainerWebService._serialize_quiz(quiz))
        article = quiz.noun_info.article if quiz.word_type == "noun" else "-"
        return {
            "quiz": quiz_payload,
            "result_label": "Marked Learned",
            "is_correct": True,
            "expected_translation": quiz.german_word,
            "expected_type": quiz.word_type,
            "expected_article": article,
            "translation_correct": True,
            "article_correct": True,
            "type_correct": True,
            "sentence_corrected": "",
            "sentence_translation_en": "",
            "sentence_structure": "",
            "sentence_structure_points": [
                f"{quiz.english_word} is now marked as learned and will move into review-based repetition.",
            ],
            "sentence_issues": [],
            "examples": quiz.examples,
        }
