"""Spaced repetition helpers for word review scheduling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ProgressRecord:
    """Persisted state for one vocabulary word."""

    correct_count: int = 0
    wrong_count: int = 0
    last_seen: str = ""
    next_review: str = ""


class SpacedRepetitionEngine:
    """Compute review intervals based on answer quality and difficulty."""

    _BASE_INTERVALS_DAYS = {
        "easy": [1, 3, 7, 14, 30],
        "medium": [1, 2, 5, 10, 21],
        "hard": [0, 1, 2, 4, 7],
    }

    def __init__(self, difficulty: str = "medium") -> None:
        self.difficulty = difficulty if difficulty in self._BASE_INTERVALS_DAYS else "medium"

    def update(self, raw_record: dict[str, object], is_correct: bool) -> dict[str, object]:
        """Update record fields and return a JSON-serializable dictionary."""
        record = ProgressRecord(
            correct_count=int(raw_record.get("correct_count", 0)),
            wrong_count=int(raw_record.get("wrong_count", 0)),
            last_seen=str(raw_record.get("last_seen", "")),
            next_review=str(raw_record.get("next_review", "")),
        )
        now = datetime.now()

        if is_correct:
            record.correct_count += 1
        else:
            record.wrong_count += 1
            record.correct_count = max(0, record.correct_count - 1)

        interval_days = self._next_interval_days(record.correct_count, is_correct)
        record.last_seen = now.isoformat()
        record.next_review = (now + timedelta(days=interval_days)).isoformat()

        return {
            "correct_count": record.correct_count,
            "wrong_count": record.wrong_count,
            "last_seen": record.last_seen,
            "next_review": record.next_review,
        }

    def is_due(self, raw_record: dict[str, object]) -> bool:
        """Return True when a word is due for review."""
        next_review = str(raw_record.get("next_review", "")).strip()
        if not next_review:
            return True
        try:
            return datetime.now() >= datetime.fromisoformat(next_review)
        except ValueError:
            return True

    def _next_interval_days(self, correct_count: int, is_correct: bool) -> int:
        if not is_correct:
            return 0
        sequence = self._BASE_INTERVALS_DAYS[self.difficulty]
        return sequence[min(correct_count - 1, len(sequence) - 1)]
