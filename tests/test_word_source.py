from pathlib import Path

from services.progress_tracker import ProgressTracker
from services.word_source import WordSource


class StubWordGenerator:
    def __init__(self) -> None:
        self.words = ["house", "apple", "friend", "garden", "river"]
        self.index = 0

    def word(self, word_min_length: int = 1, word_max_length: int = 20) -> str:
        _ = (word_min_length, word_max_length)
        value = self.words[self.index % len(self.words)]
        self.index += 1
        return value


def test_generates_and_saves_words(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    storage_dir = tmp_path / "storage"
    tracker = ProgressTracker(storage_dir)

    source = WordSource(
        data_dir=data_dir,
        progress_tracker=tracker,
        level="A1",
        random_word_generator=StubWordGenerator(),
    )

    assert source.next_word()
    cache_path = data_dir / "generated_words_a1.txt"
    assert cache_path.exists()
    contents = cache_path.read_text(encoding="utf-8")
    assert "house" in contents
