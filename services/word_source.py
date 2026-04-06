"""CEFR sublevel-aware vocabulary generation/caching and weighted sampling."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path
from typing import Any

from services.progress_tracker import ProgressTracker
from services.ai_word_service import AIWordService


class WordSource:
    """Build practice words from CEFR sublevel curriculum + wonderwords cache."""

    LEVELS = ("A1.1", "A1.2", "A2.1", "A2.2", "B1.1", "B1.2")

    _LEVEL_ALIASES = {
        "A1": "A1.2",
        "A2": "A2.2",
        "B1": "B1.2",
        "BB1": "B1.2",
    }

    _CURRICULUM: dict[str, list[str]] = {
        "A1.1": [
            "house",
            "book",
            "car",
            "friend",
            "school",
            "city",
            "water",
            "food",
            "work",
            "sleep",
            "eat",
            "drink",
            "write",
            "read",
            "learn",
            "speak",
            "walk",
            "small",
            "big",
            "new",
            "old",
            "with",
            "without",
            "to",
            "in",
            "on",
        ],
        "A1.2": [
            "fast",
            "slow",
            "today",
            "tomorrow",
            "before",
            "after",
            "from",
            "for",
            "under",
            "nominative",
            "accusative",
            "dative",
            "genitive",
            "family",
            "apartment",
            "doctor",
            "market",
        ],
        "A2.1": [
            "journey",
            "language",
            "meeting",
            "holiday",
            "important",
            "possible",
            "difficult",
            "easy",
            "healthy",
            "often",
            "already",
            "never",
            "because",
            "during",
            "between",
        ],
        "A2.2": [
            "against",
            "around",
            "through",
            "since",
            "until",
            "case",
            "article",
            "plural",
            "careful",
            "support",
            "understand",
            "believe",
            "organize",
        ],
        "B1.1": [
            "challenge",
            "environment",
            "relationship",
            "experience",
            "knowledge",
            "responsibility",
            "improve",
            "decide",
            "successful",
            "available",
            "necessary",
            "grammar",
            "adjective",
            "preposition",
        ],
        "B1.2": [
            "carefully",
            "meanwhile",
            "despite",
            "according",
            "discussion",
            "analysis",
            "strategy",
            "efficient",
            "precise",
            "therefore",
        ],
    }

    _LEVEL_WORD_LENGTH = {
        "A1.1": (3, 5),
        "A1.2": (3, 6),
        "A2.1": (4, 7),
        "A2.2": (4, 8),
        "B1.1": (5, 9),
        "B1.2": (5, 10),
    }

    _SEED_COUNT = {
        "A1.1": 40,
        "A1.2": 55,
        "A2.1": 70,
        "A2.2": 80,
        "B1.1": 90,
        "B1.2": 100,
    }

    def __init__(
        self,
        data_dir: Path,
        progress_tracker: ProgressTracker,
        level: str = "A1.1",
        random_word_generator: Any | None = None,
        source: str = "local",
        ai_word_service: AIWordService | None = None,
    ) -> None:
        self.data_dir = data_dir
        self.progress_tracker = progress_tracker
        self.level = self._normalize_level(level)
        self.source = source
        self.ai_word_service = ai_word_service

        cache_suffix = self.level.lower().replace(".", "_")
        if self.source == "ai":
            self.cache_file = self.data_dir / f"generated_german_words_{cache_suffix}.txt"
        else:
            self.cache_file = self.data_dir / f"generated_words_{cache_suffix}.txt"
        self.generator = random_word_generator or self._default_generator()
        self.words = self._load_cached_words()
        self._ensure_seed_words()
        if not self.words:
            raise ValueError("Unable to load or generate vocabulary words.")

    def next_word(self) -> str:
        if random.random() < 0.15:
            self._generate_and_store_word()

        progress = self.progress_tracker.all_progress()
        available_words = [word for word in self.words if not bool(progress.get(word, {}).get("learned", False))]
        if not available_words:
            available_words = list(self.words)

        weighted_words: list[tuple[str, float]] = []
        for word in available_words:
            record = progress.get(word, {})
            wrong = int(record.get("wrong_count", 0))
            correct = int(record.get("correct_count", 0))
            next_review = str(record.get("next_review", ""))
            stage = str(record.get("learning_stage", "study")).strip().lower()
            due_bonus = 2.0 if self._is_due(next_review) else 0.2
            stage_bonus = 2.2 if stage != "quiz" else 0.0
            weight = max(0.1, 1.0 + wrong * 1.5 - correct * 0.3 + due_bonus + stage_bonus)
            weighted_words.append((word, weight))

        words, weights = zip(*weighted_words)
        return random.choices(words, weights=weights, k=1)[0]

    def _load_cached_words(self) -> list[str]:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.cache_file.exists():
            self.cache_file.write_text("", encoding="utf-8")
        words: list[str] = []
        for line in self.cache_file.read_text(encoding="utf-8").splitlines():
            token = self._normalize_word(line.strip())
            if token:
                words.append(token)
        return list(dict.fromkeys(words))

    def _ensure_seed_words(self) -> None:
        if self.source != "ai":
            self._seed_from_curriculum()
        target = 15 if self.source == "ai" else self._SEED_COUNT.get(self.level, self._SEED_COUNT["A1.1"])
        attempts = 0
        while len(self.words) < target and attempts < target * 5:
            attempts += 1
            self._generate_and_store_word()

    def _seed_from_curriculum(self) -> None:
        for word in self._active_curriculum_words():
            if word not in self.words:
                self.words.append(word)
                with self.cache_file.open("a", encoding="utf-8") as handle:
                    handle.write(f"{word}\n")

    def _active_curriculum_words(self) -> list[str]:
        max_index = self.LEVELS.index(self.level)
        words: list[str] = []
        for idx, lvl in enumerate(self.LEVELS):
            if idx > max_index:
                break
            words.extend(self._CURRICULUM.get(lvl, []))
        return list(dict.fromkeys(words))


    def _generate_and_store_word(self) -> None:
        candidate = self._generate_word()
        if not candidate or candidate in self.words:
            return
        self.words.append(candidate)
        with self.cache_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{candidate}\n")

    def _generate_word(self) -> str:
        if self.source == "ai" and self.ai_word_service is not None:
            ai_word = self.ai_word_service.next_word()
            if ai_word:
                return self._normalize_word(ai_word)

        min_len, max_len = self._LEVEL_WORD_LENGTH.get(self.level, self._LEVEL_WORD_LENGTH["A1.1"])

        try:
            if hasattr(self.generator, "word"):
                try:
                    raw = self.generator.word(word_min_length=min_len, word_max_length=max_len)
                except TypeError:
                    raw = self.generator.word()
                return self._normalize_word(str(raw))
            if hasattr(self.generator, "random_words"):
                raw_words = self.generator.random_words(1)
                if raw_words:
                    return self._normalize_word(str(raw_words[0]))
        except Exception:
            return ""
        return ""

    @classmethod
    def _normalize_level(cls, level: str) -> str:
        token = level.strip().upper()
        token = cls._LEVEL_ALIASES.get(token, token)
        if token in cls.LEVELS:
            return token
        return "A1.1"

    @staticmethod
    def _default_generator() -> Any:
        from wonderwords import RandomWord

        return RandomWord()

    @staticmethod
    def _normalize_word(value: str) -> str:
        cleaned = value.strip()
        if not cleaned.isalpha():
            return ""
        return cleaned

    @staticmethod
    def _is_due(next_review: str) -> bool:
        if not next_review:
            return True
        try:
            return datetime.now() >= datetime.fromisoformat(next_review)
        except ValueError:
            return True
