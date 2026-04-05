"""Quiz orchestration across services and exercise modes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from random import choice

from engine.grammar_checker import GrammarChecker, NounInfo
from engine.sentence_generator import SentenceGenerator
from engine.spaced_repetition import SpacedRepetitionEngine
from services.ai_sentence_service import AISentenceService, AIWordProfile
from services.progress_tracker import ProgressTracker
from services.sentence_checker import SentenceChecker
from services.translator import TranslatorService
from services.word_source import WordSource


@dataclass
class QuizItem:
    english_word: str
    german_word: str
    word_type: str
    cefr_level: str
    noun_info: NounInfo
    noun_details: dict[str, object]
    compound_parts: list[str]
    analysis_details: dict[str, object]
    conjugations: dict[str, str]
    examples: list[str]
    ai_word_notes: list[str]
    focus_mode: str


@dataclass
class QuizResult:
    is_correct: bool
    translation_correct: bool
    article_correct: bool
    type_correct: bool
    sentence_has_required_word: bool
    sentence_correct: bool
    sentence_corrected: str
    sentence_issues: list[str]
    sentence_translation_en: str
    sentence_structure: str
    sentence_structure_points: list[str]
    expected_translation: str
    expected_article: str
    expected_plural: str
    expected_type: str
    examples: list[str]
    conjugations: dict[str, str]


class QuizEngine:
    """Prepare and evaluate quiz rounds, then persist progress and stats."""

    def __init__(
        self,
        translator: TranslatorService,
        grammar_checker: GrammarChecker,
        sentence_generator: SentenceGenerator,
        ai_sentence_service: AISentenceService,
        sentence_checker: SentenceChecker | None,
        word_source: WordSource,
        progress_tracker: ProgressTracker,
        spaced_repetition: SpacedRepetitionEngine,
        sentence_source: str = "ai",
        daily_goal_words: int = 60,
    ) -> None:
        self.translator = translator
        self.grammar_checker = grammar_checker
        self.sentence_generator = sentence_generator
        self.ai_sentence_service = ai_sentence_service
        self.sentence_checker = sentence_checker
        self.word_source = word_source
        self.progress_tracker = progress_tracker
        self.spaced_repetition = spaced_repetition
        self.sentence_source = sentence_source
        self.daily_goal_words = max(0, int(daily_goal_words))

    def create_quiz(self, english_word: str | None = None, *, mark_presented: bool = True) -> QuizItem:
        if english_word is None:
            english_word = self._select_word_for_daily_goal()
        if mark_presented:
            self.progress_tracker.mark_word_presented(english_word)

        if self.word_source.source == "ai":
            raw_token = english_word or self.word_source.next_word()
            raw_token = raw_token.strip()

            # Canonicalize AI-generated token through DE<->EN translation to avoid
            # accidental English outputs such as "Mouth" in the German slot.
            english_guess = self.translator.to_english(raw_token).strip()
            german_roundtrip = self.translator.to_german(english_guess).strip()

            if german_roundtrip and self._normalize(german_roundtrip) != self._normalize(raw_token):
                german_word = german_roundtrip
                english_word = self.translator.to_english(german_word).strip() or english_guess
            else:
                german_word = raw_token
                english_word = english_guess or raw_token
        else:
            english_word = english_word or self.word_source.next_word()
            german_word = self.translator.to_german(english_word)

        cached_quiz = self._quiz_from_cached_meta(english_word or "")
        if cached_quiz is not None:
            return cached_quiz

        ai_profile = self._build_ai_profile(
            seed_german=german_word,
            seed_english=english_word or "",
        )
        if ai_profile:
            return self._quiz_from_ai_profile(ai_profile)

        analysis = self.grammar_checker.analyze_word(german_word)
        if analysis.word_type == "noun" and german_word and german_word[0].islower():
            german_word = german_word[0].upper() + german_word[1:]
            analysis = self.grammar_checker.analyze_word(german_word)

        # Resolve common ambiguity where translated infinitives are capitalized
        # (e.g. "Lernen") and thus interpreted as nouns. If the lowercase form
        # maps to the same English cue and is detected as a verb, prefer it.
        if (
            analysis.word_type == "noun"
            and german_word
            and german_word[0].isupper()
            and german_word.lower().endswith("en")
            and english_word
        ):
            lower_word = german_word[0].lower() + german_word[1:]
            lower_analysis = self.grammar_checker.analyze_word(lower_word)
            lower_en = self.translator.to_english(lower_word).strip()
            lower_from_en = self.translator.to_german(english_word).strip()
            if (
                lower_analysis.word_type == "verb"
                and (
                    self._normalize(lower_en) == self._normalize(english_word)
                    or self._normalize(lower_from_en) == self._normalize(lower_word)
                )
            ):
                german_word = lower_word
                analysis = lower_analysis
            elif self._normalize(lower_from_en) == self._normalize(lower_word):
                # Verb service can intermittently fail; if EN->DE roundtrip points to
                # lowercase infinitive, treat it as verb to avoid false noun labeling.
                german_word = lower_word
                analysis = self.grammar_checker.analyze_word(german_word)
                if analysis.word_type == "noun":
                    analysis.word_type = "verb"
                    analysis.details = analysis.details or {}

        if analysis.word_type == "verb" and german_word and german_word[0].isupper():
            german_word = german_word[0].lower() + german_word[1:]
            analysis = self.grammar_checker.analyze_word(german_word)

        noun_info = (
            self.grammar_checker.noun_info(german_word)
            if analysis.word_type == "noun"
            else NounInfo(is_noun=False, article="", plural="", gender="")
        )
        noun_details = self.grammar_checker.noun_details(german_word) or {} if analysis.word_type == "noun" else {}
        compound_parts = self.grammar_checker.parse_compound(german_word)
        word_type = analysis.word_type
        conjugations = analysis.conjugations or (self.grammar_checker.conjugations(german_word) if word_type == "verb" else {})
        examples = self.sentence_generator.build_examples(
            german_word,
            word_type,
            article=noun_info.article,
            plural=noun_info.plural,
            conjugations=conjugations,
        )
        if self.sentence_source == "ai":
            ai_examples = self.ai_sentence_service.build_examples(
                german_word=german_word,
                english_word=english_word,
                word_type=word_type,
                article=noun_info.article,
                plural=noun_info.plural,
                count=3,
            )
            examples = ai_examples or [f"AI sentence unavailable for '{german_word}'."]
        ai_word_notes: list[str] = []

        focus_mode = choice(["translation", "sentence", "fill_blank", "article", "conjugation", "grammar"])
        if word_type != "noun" and focus_mode == "article":
            focus_mode = "conjugation"
        if word_type != "verb" and focus_mode == "conjugation":
            focus_mode = "article"

        # Persist full word metadata locally to improve continuity and
        # avoid recomputing details during later study/review sessions.
        self.progress_tracker.update_word_meta(
            english_word,
            {
                "german_word": german_word,
                "word_type": word_type,
                "cefr_level": analysis.level,
                "noun_info": {
                    "article": noun_info.article,
                    "plural": noun_info.plural,
                    "gender": noun_info.gender,
                },
                "noun_details": noun_details,
                "compound_parts": compound_parts,
                "analysis_details": analysis.details or {},
                "conjugations": conjugations,
                "examples": examples,
                "ai_word_notes": ai_word_notes,
                "source": {
                    "word_source": self.word_source.source,
                    "sentence_source": self.sentence_source,
                },
                "generated_at": datetime.now().isoformat(),
            },
        )

        return QuizItem(
            english_word=english_word,
            german_word=german_word,
            word_type=word_type,
            cefr_level=analysis.level,
            noun_info=noun_info,
            noun_details=noun_details,
            compound_parts=compound_parts,
            analysis_details=analysis.details or {},
            conjugations=conjugations,
            examples=examples,
            ai_word_notes=ai_word_notes,
            focus_mode=focus_mode,
        )

    def _select_word_for_daily_goal(self) -> str:
        candidate = self.word_source.next_word()
        if self.daily_goal_words <= 0:
            return candidate

        new_today = self.progress_tracker.new_words_today()
        goal_reached = new_today >= self.daily_goal_words

        for _ in range(30):
            is_new = self.progress_tracker.is_new_word(candidate)
            if not goal_reached and is_new:
                return candidate
            if goal_reached and not is_new:
                return candidate
            candidate = self.word_source.next_word()
        return candidate

    def _build_ai_profile(self, *, seed_german: str, seed_english: str) -> AIWordProfile | None:
        if not self.ai_sentence_service.available:
            return None
        return self.ai_sentence_service.build_word_profile(
            seed_german=seed_german,
            seed_english=seed_english,
            level=self.ai_sentence_service.style_level,
        )

    def _quiz_from_cached_meta(self, english_word: str) -> QuizItem | None:
        if not english_word:
            return None
        meta = self.progress_tracker.get_word_meta(english_word)
        if not meta:
            return None
        source = meta.get("source", {})
        if not isinstance(source, dict) or str(source.get("word_source", "")).strip().lower() != "ai":
            return None

        german_word = str(meta.get("german_word", "")).strip()
        if not german_word:
            return None
        word_type = str(meta.get("word_type", "other")).strip().lower() or "other"
        cefr_level = str(meta.get("cefr_level", "")).strip()

        noun_meta = meta.get("noun_info", {})
        noun_info = NounInfo(
            is_noun=word_type == "noun",
            article=str(noun_meta.get("article", "")).strip() if isinstance(noun_meta, dict) else "",
            plural=str(noun_meta.get("plural", "")).strip() if isinstance(noun_meta, dict) else "",
            gender=str(noun_meta.get("gender", "")).strip() if isinstance(noun_meta, dict) else "",
        )
        noun_details = meta.get("noun_details", {}) if isinstance(meta.get("noun_details", {}), dict) else {}
        compound_parts_raw = meta.get("compound_parts", [])
        compound_parts = [str(x).strip() for x in compound_parts_raw] if isinstance(compound_parts_raw, list) else []
        analysis_details = meta.get("analysis_details", {}) if isinstance(meta.get("analysis_details", {}), dict) else {}
        conjugations_raw = meta.get("conjugations", {})
        conjugations = (
            {str(k): str(v).strip() for k, v in conjugations_raw.items() if str(v).strip()}
            if isinstance(conjugations_raw, dict)
            else {}
        )
        examples_raw = meta.get("examples", [])
        examples = [str(x).strip() for x in examples_raw] if isinstance(examples_raw, list) else []
        examples = [x for x in examples if x]
        notes_raw = meta.get("ai_word_notes", [])
        ai_word_notes = [str(x).strip() for x in notes_raw] if isinstance(notes_raw, list) else []
        ai_word_notes = [x for x in ai_word_notes if x]

        if not examples:
            examples = self.sentence_generator.build_examples(
                german_word,
                word_type,
                article=noun_info.article,
                plural=noun_info.plural,
                conjugations=conjugations,
            )

        focus_mode = choice(["translation", "sentence", "fill_blank", "article", "conjugation", "grammar"])
        if word_type != "noun" and focus_mode == "article":
            focus_mode = "conjugation"
        if word_type != "verb" and focus_mode == "conjugation":
            focus_mode = "article"

        return QuizItem(
            english_word=english_word,
            german_word=german_word,
            word_type=word_type,
            cefr_level=cefr_level,
            noun_info=noun_info,
            noun_details=noun_details,
            compound_parts=compound_parts,
            analysis_details=analysis_details,
            conjugations=conjugations,
            examples=examples,
            ai_word_notes=ai_word_notes,
            focus_mode=focus_mode,
        )

    def _quiz_from_ai_profile(self, profile: AIWordProfile) -> QuizItem:
        word_type = profile.word_type
        german_word = profile.german_word
        english_word = profile.english_word

        is_noun = word_type == "noun"
        article = profile.article if is_noun else ""
        plural = profile.plural if is_noun else ""
        gender = profile.gender if is_noun else ""
        noun_info = NounInfo(is_noun=is_noun, article=article, plural=plural, gender=gender)

        noun_details: dict[str, object] = {}
        if is_noun:
            genus = {"masculine": "m", "feminine": "f", "neutral": "n"}.get(gender.casefold(), "-")
            noun_details = {
                "lemma": german_word,
                "genus": genus,
                "pos": ["Substantiv"],
                "flexion": profile.noun_flexion,
            }

        conjugations = profile.conjugations if word_type == "verb" else {}
        examples = profile.examples or self.sentence_generator.build_examples(
            german_word,
            word_type,
            article=noun_info.article,
            plural=noun_info.plural,
            conjugations=conjugations,
        )
        ai_word_notes = profile.notes

        focus_mode = choice(["translation", "sentence", "fill_blank", "article", "conjugation", "grammar"])
        if word_type != "noun" and focus_mode == "article":
            focus_mode = "conjugation"
        if word_type != "verb" and focus_mode == "conjugation":
            focus_mode = "article"

        self.progress_tracker.update_word_meta(
            english_word,
            {
                "german_word": german_word,
                "word_type": word_type,
                "cefr_level": profile.cefr_level,
                "noun_info": {
                    "article": noun_info.article,
                    "plural": noun_info.plural,
                    "gender": noun_info.gender,
                },
                "noun_details": noun_details,
                "compound_parts": [],
                "analysis_details": {"provider": "ai", **(profile.analysis_details or {})},
                "conjugations": conjugations,
                "examples": examples,
                "ai_word_notes": ai_word_notes,
                "source": {
                    "word_source": self.word_source.source,
                    "sentence_source": self.sentence_source,
                },
                "generated_at": datetime.now().isoformat(),
            },
        )

        return QuizItem(
            english_word=english_word,
            german_word=german_word,
            word_type=word_type,
            cefr_level=profile.cefr_level,
            noun_info=noun_info,
            noun_details=noun_details,
            compound_parts=[],
            analysis_details={"provider": "ai", **(profile.analysis_details or {})},
            conjugations=conjugations,
            examples=examples,
            ai_word_notes=ai_word_notes,
            focus_mode=focus_mode,
        )

    def evaluate(
        self,
        quiz: QuizItem,
        user_translation: str,
        user_article: str,
        user_word_type: str,
        user_sentence: str,
        skipped: bool = False,
    ) -> QuizResult:
        expected_translation = quiz.german_word
        translation_correct = self._translation_matches(
            user_translation=user_translation,
            expected_translation=expected_translation,
            expected_english=quiz.english_word,
        )

        expected_article = quiz.noun_info.article if quiz.word_type == "noun" else "-"
        article_correct = quiz.word_type != "noun" or user_article == expected_article
        type_correct = user_word_type == quiz.word_type
        sentence_has_required_word = self.sentence_generator.validate_sentence(user_sentence, [quiz.german_word])
        corrected_sentence = user_sentence.strip()
        sentence_issues: list[str] = []
        sentence_translation_en = ""
        sentence_structure = ""
        sentence_structure_points: list[str] = []
        sentence_check_available = False
        sentence_check_is_correct = True

        if self.sentence_source == "ai":
            ai_full = self.ai_sentence_service.check_sentence_full(
                user_sentence=user_sentence,
                german_word=quiz.german_word,
                level=self.ai_sentence_service.style_level,
            )
            if ai_full:
                if ai_full.corrected_sentence:
                    corrected_sentence = ai_full.corrected_sentence
                sentence_issues = ai_full.issues or []
                sentence_translation_en = ai_full.translation_en
                sentence_structure = ai_full.structure
                sentence_structure_points = ai_full.structure_points or []
                # In AI mode, exact token matching (e.g., "lesen" vs "lese")
                # can incorrectly flag valid sentences. Trust AI judgment here.
                sentence_has_required_word = bool(user_sentence.strip())
        elif self.sentence_checker is not None:
            sentence_check = self.sentence_checker.check(user_sentence)
            sentence_check_available = sentence_check.available
            sentence_check_is_correct = sentence_check.is_correct
            corrected_sentence = sentence_check.corrected
            sentence_issues = list(sentence_check.issues)
            if not sentence_check_available:
                sentence_issues = []

        if self.sentence_source == "ai":
            # In AI mode, trust AI feedback first for sentence correctness.
            sentence_correct = sentence_has_required_word and len(sentence_issues) == 0
        else:
            sentence_correct = sentence_has_required_word and sentence_check_is_correct

        # Quiz scoring excludes sentence quality. Sentences are feedback-only.
        # Required scoring: translation + type, and article for nouns.
        base_correct = translation_correct and type_correct
        if quiz.word_type == "noun":
            base_correct = base_correct and article_correct
        is_correct = base_correct and not skipped

        existing_record = self.progress_tracker.get_word_progress(quiz.english_word)
        updated_record = self.spaced_repetition.update(existing_record, is_correct)
        merged_record = {**existing_record, **updated_record}
        self.progress_tracker.update_word_progress(quiz.english_word, merged_record)
        self.progress_tracker.record_attempt(is_correct)

        return QuizResult(
            is_correct=is_correct,
            translation_correct=translation_correct,
            article_correct=article_correct,
            type_correct=type_correct,
            sentence_has_required_word=sentence_has_required_word,
            sentence_correct=sentence_correct,
            sentence_corrected=corrected_sentence,
            sentence_issues=sentence_issues,
            sentence_translation_en=sentence_translation_en,
            sentence_structure=sentence_structure,
            sentence_structure_points=sentence_structure_points,
            expected_translation=expected_translation,
            expected_article=expected_article,
            expected_plural=quiz.noun_info.plural if quiz.word_type == "noun" else "-",
            expected_type=quiz.word_type,
            examples=quiz.examples,
            conjugations=quiz.conjugations,
        )

    def mark_learned(self, english_word: str) -> None:
        """Mark a word as learned so it is deprioritized in future selection."""
        record = self.progress_tracker.get_word_progress(english_word)
        now = datetime.now()
        record["learned"] = True
        record["learning_stage"] = "quiz"
        record["correct_count"] = max(int(record.get("correct_count", 0)), 20)
        record["last_seen"] = now.isoformat()
        record["next_review"] = (now + timedelta(days=365)).isoformat()
        self.progress_tracker.update_word_progress(english_word, record)

    def mark_understood(self, english_word: str) -> None:
        """Move a word from study stage to quiz stage."""
        record = self.progress_tracker.get_word_progress(english_word)
        record["learning_stage"] = "quiz"
        self.progress_tracker.update_word_progress(english_word, record)

    @staticmethod
    def _normalize(value: str) -> str:
        return value.strip().casefold()

    def _translation_matches(self, user_translation: str, expected_translation: str, expected_english: str) -> bool:
        """Accept exact match and EN-roundtrip match to reduce false negatives."""
        user_norm = self._normalize(user_translation)
        expected_norm = self._normalize(expected_translation)
        if not user_norm:
            return False
        if user_norm == expected_norm:
            return True

        # Allow synonym/variant if user German maps back to expected English.
        try:
            back_to_english = self.translator.to_english(user_translation)
        except Exception:
            back_to_english = ""
        return self._normalize(back_to_english) == self._normalize(expected_english)
