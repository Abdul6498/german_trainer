"""Optional AI-backed sentence generation and correction via OpenAI API."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from services.prompt_store import PromptStore


@dataclass
class AISentenceResult:
    examples: list[str]
    corrected_sentence: str
    issues: list[str]
    translation_en: str = ""
    structure: str = ""
    structure_points: list[str] | None = None
    is_correct: bool = False
    checks: list[dict[str, object]] | None = None
    estimated_level: str = ""
    score_out_of_10: str = ""


@dataclass
class AIWordProfile:
    german_word: str
    english_word: str
    word_type: str
    cefr_level: str
    article: str
    plural: str
    gender: str
    noun_flexion: dict[str, str]
    conjugations: dict[str, str]
    examples: list[str]
    notes: list[str]
    analysis_details: dict[str, object]


class AISentenceService:
    """Use OpenAI model for sentence generation/correction and study notes."""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        enabled: bool = True,
        style_level: str = "A1.1",
        compact_mode: bool = True,
        notes_mode: str = "off",
    ) -> None:
        self.model = model
        self.enabled = enabled
        self.style_level = style_level.upper().strip() or "A1.1"
        self.compact_mode = compact_mode
        mode = notes_mode.strip().lower()
        self.notes_mode = mode if mode in {"off", "short", "full"} else "off"
        self._client = None
        self._init_error = ""
        self._prompts = PromptStore()
        self._init_client()

    def set_style_level(self, style_level: str) -> None:
        self.style_level = style_level.upper().strip() or "A1.1"

    @property
    def available(self) -> bool:
        return self.enabled and self._client is not None

    @property
    def init_error(self) -> str:
        return self._init_error

    def build_examples(
        self,
        *,
        german_word: str,
        english_word: str,
        word_type: str,
        article: str,
        plural: str,
        count: int = 3,
    ) -> list[str] | None:
        if self._client is None:
            return None

        prompt = self._prompts.render(
            "ai_sentence_build_examples",
            count=count,
            german_word=german_word,
            english_word=english_word,
            word_type=word_type,
            article=article or "-",
            plural=plural or "-",
            target_level=self.style_level,
            style_rules=self._style_rules(self.style_level),
        )

        data = self._json_request(prompt)
        examples: list[str] = []
        if data:
            raw_examples = data.get("examples", [])
            if isinstance(raw_examples, list):
                examples = [str(x).strip() for x in raw_examples if str(x).strip()]

        if not examples:
            text = self._text_request(
                self._prompts.render(
                    "ai_sentence_build_examples",
                    key="fallback_user",
                    german_word=german_word,
                    target_level=self.style_level,
                )
            )
            if text:
                examples = [line.strip(" -\t") for line in text.splitlines() if line.strip()]

        cleaned = [str(x).strip() for x in examples if str(x).strip()]
        return cleaned[:count] if cleaned else None

    def correct_sentence(self, *, user_sentence: str, german_word: str) -> AISentenceResult | None:
        if self._client is None or not user_sentence.strip():
            return None

        prompt = self._prompts.render(
            "ai_sentence_correct_sentence",
            german_word=german_word,
            user_sentence=user_sentence,
            target_level=self.style_level,
            style_rules=self._style_rules(self.style_level),
        )
        data = self._json_request(prompt)
        if not data:
            return None

        corrected = str(data.get("corrected", "")).strip()
        issues_raw = data.get("issues", [])
        issues = [str(x).strip() for x in issues_raw] if isinstance(issues_raw, list) else []
        return AISentenceResult(examples=[], corrected_sentence=corrected, issues=[x for x in issues if x])

    def build_study_notes(
        self,
        *,
        german_word: str,
        english_word: str,
        word_type: str,
        article: str,
        plural: str,
    ) -> list[str]:
        if self._client is None:
            return []

        prompt = self._prompts.render(
            "ai_sentence_build_study_notes",
            target_level=self.style_level,
            german_word=german_word,
            english_word=english_word,
            word_type=word_type,
            article=article or "-",
            plural=plural or "-",
        )
        data = self._json_request(prompt)
        if not data:
            return []
        notes = data.get("notes", [])
        if not isinstance(notes, list):
            return []
        return [str(x).strip() for x in notes if str(x).strip()]

    def analyze_sentence(
        self,
        *,
        german_sentence: str,
        level: str | None = None,
    ) -> AISentenceResult | None:
        """Translate a learner sentence and explain its structure in simple terms."""
        if self._client is None or not german_sentence.strip():
            return None

        target_level = (level or self.style_level).upper().strip() or self.style_level
        prompt = self._prompts.render(
            "ai_sentence_analyze_sentence",
            target_level=target_level,
            german_sentence=german_sentence,
            style_rules=self._style_rules(target_level),
        )
        data = self._json_request(prompt)
        if not data:
            return None

        translation_en = str(data.get("translation_en", "")).strip()
        structure = str(data.get("structure", "")).strip()
        points_raw = data.get("points", [])
        points = [str(x).strip() for x in points_raw] if isinstance(points_raw, list) else []
        return AISentenceResult(
            examples=[],
            corrected_sentence="",
            issues=[],
            translation_en=translation_en,
            structure=structure,
            structure_points=[p for p in points if p],
        )

    def check_sentence_full(
        self,
        *,
        user_sentence: str,
        german_word: str,
        level: str | None = None,
    ) -> AISentenceResult | None:
        """Single-call sentence correction + translation + structure analysis."""
        if self._client is None or not user_sentence.strip():
            return None

        target_level = (level or self.style_level).upper().strip() or self.style_level
        prompt = self._prompts.render(
            "ai_sentence_check_sentence_full",
            target_level=target_level,
            german_word=german_word,
            user_sentence=user_sentence,
            style_rules=self._style_rules(target_level),
        )
        data = self._json_request(prompt, max_output_tokens=650)
        if not data:
            return None

        corrected = str(data.get("corrected", "")).strip()
        issues_raw = data.get("issues", [])
        issues = [str(x).strip() for x in issues_raw] if isinstance(issues_raw, list) else []
        translation_en = str(data.get("translation_en", "")).strip()
        structure = str(data.get("structure", "")).strip()
        points_raw = data.get("points", [])
        points = [str(x).strip() for x in points_raw] if isinstance(points_raw, list) else []
        return AISentenceResult(
            examples=[],
            corrected_sentence=corrected,
            issues=[x for x in issues if x],
            translation_en=translation_en,
            structure=structure,
            structure_points=[x for x in points if x],
        )

    def build_word_profile(
        self,
        *,
        seed_german: str,
        seed_english: str,
        level: str | None = None,
    ) -> AIWordProfile | None:
        """Generate a full, level-aware word profile using AI only."""
        if self._client is None:
            return None

        target_level = (level or self.style_level).upper().strip() or self.style_level
        note_rule = {
            "off": "- notes: keep empty array.",
            "short": "- notes: provide 2 short learning tips.",
            "full": "- notes: provide 6 concise learning tips.",
        }.get(self.notes_mode, "- notes: keep empty array.")
        prompt = self._prompts.render(
            "ai_sentence_build_word_profile",
            target_level=target_level,
            seed_german=seed_german,
            seed_english=seed_english,
            style_rules=self._style_rules(target_level),
            note_rule=note_rule,
        )
        data = self._json_request(prompt, max_output_tokens=500)
        if not data:
            return None

        german_word = str(data.get("german_word", "")).strip()
        english_word = str(data.get("english_word", "")).strip()
        if not german_word or not english_word:
            return None

        word_type = str(data.get("word_type", "other")).strip().lower()
        if word_type not in {"noun", "verb", "adjective", "adverb", "preposition", "pronoun", "other"}:
            word_type = "other"

        article = str(data.get("article", "-")).strip().lower() or "-"
        plural = str(data.get("plural", "-")).strip() or "-"
        gender = str(data.get("gender", "-")).strip().lower() or "-"
        cefr_level = str(data.get("cefr_level", target_level)).strip() or target_level

        noun_flexion_raw = data.get("noun_flexion", {})
        noun_flexion = (
            {str(k): str(v).strip() for k, v in noun_flexion_raw.items()}
            if isinstance(noun_flexion_raw, dict)
            else {}
        )

        conjugations_raw = data.get("conjugations", {})
        conjugations = (
            {str(k): str(v).strip() for k, v in conjugations_raw.items() if str(v).strip()}
            if isinstance(conjugations_raw, dict)
            else {}
        )

        examples_raw = data.get("examples", [])
        examples = [str(x).strip() for x in examples_raw] if isinstance(examples_raw, list) else []
        examples = [x for x in examples if x][:2]

        notes_raw = data.get("notes", [])
        notes = [str(x).strip() for x in notes_raw] if isinstance(notes_raw, list) else []
        notes = [x for x in notes if x]
        if self.notes_mode == "off":
            notes = []
        elif self.notes_mode == "short":
            notes = notes[:2]
        else:
            notes = notes[:6]

        analysis_raw = data.get("analysis_details", {})
        analysis_details = (
            {str(k): v for k, v in analysis_raw.items()} if isinstance(analysis_raw, dict) else {}
        )

        return AIWordProfile(
            german_word=german_word,
            english_word=english_word,
            word_type=word_type,
            cefr_level=cefr_level,
            article=article,
            plural=plural,
            gender=gender,
            noun_flexion=noun_flexion,
            conjugations=conjugations,
            examples=examples,
            notes=notes,
            analysis_details=analysis_details,
        )

    def build_story_practice(
        self,
        *,
        german_word: str,
        english_word: str,
        word_type: str,
        level: str | None = None,
        article: str = "",
        plural: str = "",
    ) -> dict[str, object] | None:
        if self._client is None:
            return None

        target_level = (level or self.style_level).upper().strip() or self.style_level
        prompt = self._prompts.render(
            "ai_story_build_story",
            target_level=target_level,
            german_word=german_word,
            english_word=english_word,
            word_type=word_type,
            article=article or "-",
            plural=plural or "-",
            style_rules=self._style_rules(target_level),
        )
        data = self._json_request(prompt)
        if not data:
            return None

        title = str(data.get("title", "")).strip()
        topic = str(data.get("topic", "")).strip()
        text = str(data.get("text", "")).strip()
        vocabulary_raw = data.get("vocabulary", [])
        hints_raw = data.get("hints", [])
        question = str(data.get("question", "")).strip()
        if not text:
            return None
        vocabulary = [str(x).strip() for x in vocabulary_raw] if isinstance(vocabulary_raw, list) else []
        hints = [str(x).strip() for x in hints_raw] if isinstance(hints_raw, list) else []
        return {
            "topic": topic or title or f"Thema mit {german_word}",
            "title": title or f"Story with {german_word}",
            "text": text,
            "vocabulary": [x for x in vocabulary if x][:8],
            "hints": [x for x in hints if x][:5],
            "question": question or f"Schreibe die Geschichte in deinen eigenen Worten nach. | Rewrite the story in your own words.",
        }

    def check_story_recall(
        self,
        *,
        original_story: str,
        user_story: str,
        level: str | None = None,
        hints: list[str] | None = None,
        vocabulary: list[str] | None = None,
    ) -> AISentenceResult | None:
        if self._client is None or not user_story.strip():
            return None

        target_level = (level or self.style_level).upper().strip() or self.style_level
        prompt = self._prompts.render(
            "ai_story_check_story",
            target_level=target_level,
            original_story=original_story,
            user_story=user_story,
            hints=", ".join(hints or []) or "-",
            vocabulary=", ".join(vocabulary or []) or "-",
            style_rules=self._style_rules(target_level),
        )
        data = self._json_request(prompt)
        if not data:
            return None

        corrected = str(data.get("corrected", "")).strip()
        issues_raw = data.get("issues", [])
        points_raw = data.get("points", [])
        checks_raw = data.get("checks", [])
        issues = [str(x).strip() for x in issues_raw] if isinstance(issues_raw, list) else []
        points = [str(x).strip() for x in points_raw] if isinstance(points_raw, list) else []
        checks = [dict(x) for x in checks_raw] if isinstance(checks_raw, list) else []
        return AISentenceResult(
            examples=[],
            corrected_sentence=corrected,
            issues=[x for x in issues if x],
            translation_en=str(data.get("summary_en", "")).strip(),
            structure=str(data.get("structure", "Story Recall")).strip(),
            structure_points=[x for x in points if x],
            is_correct=bool(data.get("is_correct", False)),
            checks=checks,
            estimated_level=str(data.get("estimated_level", "")).strip(),
            score_out_of_10=str(data.get("score_out_of_10", "")).strip(),
        )

    def _json_request(self, prompt: str, max_output_tokens: int | None = None) -> dict[str, object] | None:
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": self._prompts.render(
                            "ai_common_json_system",
                            key="system",
                            style_level=self.style_level,
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=max_output_tokens or (280 if self.compact_mode else 500),
            )
            text = getattr(response, "output_text", "") or ""
            return self._parse_json_loose(text)
        except Exception:
            return None

    def _text_request(self, prompt: str) -> str | None:
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": prompt}],
                max_output_tokens=250,
            )
            text = (getattr(response, "output_text", "") or "").strip()
            return text or None
        except Exception:
            return None

    def _init_client(self) -> None:
        if not self.enabled:
            self._init_error = "disabled by configuration"
            return
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            self._init_error = "OPENAI_API_KEY not set"
            return
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
        except Exception as exc:
            self._init_error = str(exc)
            self._client = None

    @staticmethod
    def _style_rules(level: str) -> str:
        return PromptStore().style_rules(level)

    @staticmethod
    def _parse_json_loose(text: str) -> dict[str, object] | None:
        raw = text.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            pass

        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            try:
                return json.loads(fence.group(1))
            except Exception:
                pass

        brace_start = raw.find("{")
        brace_end = raw.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            snippet = raw[brace_start : brace_end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                return None
        return None
