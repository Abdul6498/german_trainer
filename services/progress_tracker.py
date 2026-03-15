"""Persistence for spaced repetition and aggregate stats."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class ProgressTracker:
    """Read and write progress/history JSON files."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.progress_path = storage_dir / "progress.json"
        self.history_path = storage_dir / "history.json"
        self.word_meta_path = storage_dir / "word_meta.json"
        self.meta_note_limit = 2
        self._ensure_files()

    def get_word_progress(self, english_word: str) -> dict[str, object]:
        data = self._load_json(self.progress_path, fallback={})
        return dict(data.get(english_word, {}))

    def update_word_progress(self, english_word: str, record: dict[str, object]) -> None:
        data = self._load_json(self.progress_path, fallback={})
        data[english_word] = record
        self._dump_json(self.progress_path, data)

    def get_learning_stage(self, english_word: str) -> str:
        record = self.get_word_progress(english_word)
        if bool(record.get("learned", False)):
            return "quiz"
        stage = str(record.get("learning_stage", "study")).strip().lower()
        return stage if stage in {"study", "quiz"} else "study"

    def set_learning_stage(self, english_word: str, stage: str) -> None:
        normalized = stage.strip().lower()
        if normalized not in {"study", "quiz"}:
            normalized = "study"
        record = self.get_word_progress(english_word)
        record["learning_stage"] = normalized
        self.update_word_progress(english_word, record)

    def all_progress(self) -> dict[str, dict[str, object]]:
        raw = self._load_json(self.progress_path, fallback={})
        return {str(k): dict(v) for k, v in raw.items()}

    def record_attempt(self, is_correct: bool) -> None:
        history = self._load_json(
            self.history_path,
            fallback={
                "total_questions": 0,
                "correct_answers": 0,
                "wrong_answers": 0,
                "accuracy": 0.0,
                "last_updated": "",
            },
        )

        history["total_questions"] = int(history.get("total_questions", 0)) + 1
        if is_correct:
            history["correct_answers"] = int(history.get("correct_answers", 0)) + 1
        else:
            history["wrong_answers"] = int(history.get("wrong_answers", 0)) + 1

        total = max(1, int(history["total_questions"]))
        history["accuracy"] = round((int(history.get("correct_answers", 0)) / total) * 100.0, 2)
        history["last_updated"] = datetime.now().isoformat()

        self._dump_json(self.history_path, history)

    def stats(self) -> dict[str, object]:
        return self._load_json(self.history_path, fallback={})

    def is_new_word(self, english_word: str) -> bool:
        record = self.get_word_progress(english_word)
        return not bool(str(record.get("first_seen", "")).strip())

    def new_words_today(self) -> int:
        today = datetime.now().date()
        count = 0
        for _word, record in self.all_progress().items():
            first_seen = str(record.get("first_seen", "")).strip()
            if not first_seen:
                continue
            dt = self._parse_datetime(first_seen)
            if dt and dt.date() == today:
                count += 1
        return count

    def mark_word_presented(self, english_word: str) -> None:
        record = self.get_word_progress(english_word)
        now = datetime.now().isoformat()
        if not str(record.get("first_seen", "")).strip():
            record["first_seen"] = now
        record["last_presented"] = now
        record["presented_count"] = int(record.get("presented_count", 0)) + 1
        self.update_word_progress(english_word, record)

    def get_word_meta(self, english_word: str) -> dict[str, object]:
        data = self._load_json(self.word_meta_path, fallback={})
        return dict(data.get(english_word, {}))

    def update_word_meta(self, english_word: str, record: dict[str, object]) -> None:
        data = self._load_json(self.word_meta_path, fallback={})
        existing = dict(data.get(english_word, {}))
        merged = {**existing, **record}
        merged["english_word"] = english_word
        merged["last_updated"] = datetime.now().isoformat()
        merged["seen_count"] = int(existing.get("seen_count", 0)) + 1
        data[english_word] = self._compact_meta_record(merged, note_limit=self.meta_note_limit)
        self._dump_json(self.word_meta_path, data)

    def set_meta_note_limit(self, note_limit: int) -> None:
        self.meta_note_limit = note_limit

    def compact_word_meta_store(self, note_limit: int = 2) -> None:
        data = self._load_json(self.word_meta_path, fallback={})
        compacted = {str(k): self._compact_meta_record(dict(v), note_limit=note_limit) for k, v in data.items()}
        self._dump_json(self.word_meta_path, compacted)

    def _ensure_files(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        if not self.progress_path.exists():
            self._dump_json(self.progress_path, {})
        if not self.history_path.exists():
            self._dump_json(
                self.history_path,
                {
                    "total_questions": 0,
                    "correct_answers": 0,
                    "wrong_answers": 0,
                    "accuracy": 0.0,
                    "last_updated": "",
                },
            )
        if not self.word_meta_path.exists():
            self._dump_json(self.word_meta_path, {})

    @staticmethod
    def _load_json(path: Path, fallback: dict[str, object]) -> dict[str, object]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(fallback)

    @staticmethod
    def _dump_json(path: Path, payload: dict[str, object]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    @staticmethod
    def _compact_meta_record(record: dict[str, object], note_limit: int = 2) -> dict[str, object]:
        compacted = dict(record)

        examples = compacted.get("examples", [])
        if isinstance(examples, list):
            compacted["examples"] = [str(x).strip() for x in examples if str(x).strip()][:2]

        notes = compacted.get("ai_word_notes", [])
        if isinstance(notes, list):
            cleaned = [str(x).strip() for x in notes if str(x).strip()]
            compacted["ai_word_notes"] = cleaned if note_limit < 0 else cleaned[:note_limit]

        noun_details = compacted.get("noun_details", {})
        if isinstance(noun_details, dict):
            flexion = noun_details.get("flexion", {})
            if isinstance(flexion, dict):
                keep_keys = {
                    "nominativ singular",
                    "nominativ plural",
                    "akkusativ singular",
                    "akkusativ plural",
                }
                noun_details["flexion"] = {k: str(v) for k, v in flexion.items() if str(k).lower() in keep_keys}
            compacted["noun_details"] = noun_details

        analysis_details = compacted.get("analysis_details", {})
        if isinstance(analysis_details, dict):
            trimmed: dict[str, object] = {}
            for idx, (k, v) in enumerate(analysis_details.items()):
                if idx >= 8:
                    break
                text = str(v)
                trimmed[str(k)] = text[:160] + ("..." if len(text) > 160 else "")
            compacted["analysis_details"] = trimmed

        return compacted
