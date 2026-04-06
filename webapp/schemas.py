"""Pydantic schemas for the web API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NounInfoPayload(BaseModel):
    article: str = ""
    plural: str = ""
    gender: str = ""


class QuizPayload(BaseModel):
    english_word: str
    german_word: str
    word_type: str
    cefr_level: str = ""
    noun_info: NounInfoPayload
    examples: list[str] = Field(default_factory=list)
    ai_word_notes: list[str] = Field(default_factory=list)
    conjugations: dict[str, str] = Field(default_factory=dict)
    analysis_details: dict[str, object] = Field(default_factory=dict)
    focus_mode: str


class StatsPayload(BaseModel):
    total_questions: int = 0
    correct_answers: int = 0
    wrong_answers: int = 0
    accuracy: float = 0.0
    last_updated: str = ""


class SessionPayload(BaseModel):
    stage: Literal["idle", "study", "quiz", "result"]
    interval_minutes: int
    next_due_in_seconds: int
    pace: Literal["timed", "continuous"]
    daily_goal_words: int
    srs_intensity: str
    level: str
    new_words_today: int
    mode: str
    view: str
    quiz: QuizPayload | None = None
    result: dict[str, object] | None = None
    stats: StatsPayload


class StudySubmissionPayload(BaseModel):
    understood: bool = False


class QuizSubmissionPayload(BaseModel):
    translation: str = ""
    article: str = ""
    word_type: str = ""
    sentence: str = ""
    learned: bool = False
    skipped: bool = False


class SettingsPayload(BaseModel):
    level: str
    srs_intensity: Literal["easy", "medium", "hard"]
    mode: Literal["mixed", "study-only", "quiz-only"]
    view: Literal["basic", "detail"]
    pace: Literal["timed", "continuous"]
    daily_goal_words: int = Field(ge=0, le=500)
