from pathlib import Path

from engine.grammar_checker import GrammarChecker
from engine.quiz_engine import QuizEngine
from engine.sentence_generator import SentenceGenerator
from engine.spaced_repetition import SpacedRepetitionEngine
from services.progress_tracker import ProgressTracker
from services.word_source import WordSource


class StubTranslator:
    def to_german(self, english_word: str) -> str:
        return "Haus" if english_word == "house" else "laufen"


class StubWordGenerator:
    def word(self, word_min_length: int = 1, word_max_length: int = 20) -> str:
        _ = (word_min_length, word_max_length)
        return "house"


def test_quiz_creation(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    storage_dir = tmp_path / "storage"
    tracker = ProgressTracker(storage_dir)

    engine = QuizEngine(
        translator=StubTranslator(),
        grammar_checker=GrammarChecker(),
        sentence_generator=SentenceGenerator(),
        word_source=WordSource(
            data_dir,
            tracker,
            level="A1",
            random_word_generator=StubWordGenerator(),
        ),
        progress_tracker=tracker,
        spaced_repetition=SpacedRepetitionEngine(),
    )

    quiz = engine.create_quiz()
    assert quiz.english_word == "house"
    assert quiz.german_word == "Haus"
