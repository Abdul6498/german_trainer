"""Optional AI-backed sentence generation and correction via OpenAI API."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass


@dataclass
class AISentenceResult:
    examples: list[str]
    corrected_sentence: str
    issues: list[str]
    translation_en: str = ""
    structure: str = ""
    structure_points: list[str] | None = None


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

        prompt = (
            "Create natural German example sentences for learners. "
            "Return STRICT JSON only: {\"examples\":[...]} with exactly "
            f"{count} sentences.\n"
            f"word: {german_word}\n"
            f"english: {english_word}\n"
            f"word_type: {word_type}\n"
            f"article: {article or '-'}\n"
            f"plural: {plural or '-'}\n"
            f"target_level: {self.style_level}\n"
            "Rules:\n"
            f"{self._style_rules(self.style_level)}\n"
            "- Include the target word exactly as given in each sentence.\n"
            "- Grammatically correct modern standard German."
        )

        data = self._json_request(prompt)
        examples: list[str] = []
        if data:
            raw_examples = data.get("examples", [])
            if isinstance(raw_examples, list):
                examples = [str(x).strip() for x in raw_examples if str(x).strip()]

        if not examples:
            text = self._text_request(
                "Create exactly 3 short German example sentences for this word.\n"
                f"word: {german_word}\n"
                f"target_level: {self.style_level}\n"
                "Return ONLY 3 lines, one sentence per line, no numbering."
            )
            if text:
                examples = [line.strip(" -\t") for line in text.splitlines() if line.strip()]

        cleaned = [str(x).strip() for x in examples if str(x).strip()]
        return cleaned[:count] if cleaned else None

    def correct_sentence(self, *, user_sentence: str, german_word: str) -> AISentenceResult | None:
        if self._client is None or not user_sentence.strip():
            return None

        prompt = (
            "You are a German teacher. Check the learner sentence and return STRICT JSON only: "
            "{\"corrected\":\"...\",\"issues\":[\"...\"]}.\n"
            f"target_word: {german_word}\n"
            f"learner_sentence: {user_sentence}\n"
            f"target_level: {self.style_level}\n"
            "Rules:\n"
            f"{self._style_rules(self.style_level)}\n"
            "- Corrected sentence must be grammatical German and learner-friendly.\n"
            "- Keep original meaning where possible.\n"
            "- Keep the target word in corrected sentence.\n"
            "- Issues should be short, practical feedback."
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

        prompt = (
            "You are my expert German teacher. "
            "Create detailed notes for ONE word and return STRICT JSON only: {\"notes\":[...]}.\n"
            f"target_level: {self.style_level}\n"
            f"word_de: {german_word}\n"
            f"word_en: {english_word}\n"
            f"word_type: {word_type}\n"
            f"article: {article or '-'}\n"
            f"plural: {plural or '-'}\n"
            "Rules:\n"
            "- 8 to 12 note lines.\n"
            "- Start in English and slowly mix simple German.\n"
            "- Explain practical usage and mistakes.\n"
            "- Mention cases/perfekt/modal usage when relevant.\n"
            "- Include one mini real-life context.\n"
            "- Use only this generated word as the center of explanation."
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
        prompt = (
            "Analyze one German sentence for a learner and return STRICT JSON only: "
            "{\"translation_en\":\"...\",\"structure\":\"...\",\"points\":[\"...\"]}.\n"
            f"target_level: {target_level}\n"
            f"sentence_de: {german_sentence}\n"
            "Rules:\n"
            f"{self._style_rules(target_level)}\n"
            "- translation_en: natural English meaning.\n"
            "- structure: short pattern like 'Subject + Verb + Object'.\n"
            "- points: 3-6 practical bullets explaining case, verb position, tense, and key grammar in easy language.\n"
            "- Keep explanation in English with small German terms where useful."
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
        prompt = (
            "Check one German learner sentence and return STRICT JSON only: "
            "{\"corrected\":\"...\",\"issues\":[\"...\"],\"translation_en\":\"...\",\"structure\":\"...\",\"points\":[\"...\"]}.\n"
            f"target_level: {target_level}\n"
            f"target_word: {german_word}\n"
            f"learner_sentence: {user_sentence}\n"
            "Rules:\n"
            f"{self._style_rules(target_level)}\n"
            "- corrected: grammatical German sentence; keep learner meaning where possible.\n"
            "- Keep target_word in corrected when possible.\n"
            "- issues: short actionable items; empty list if acceptable.\n"
            "- translation_en: natural English translation.\n"
            "- structure: short sentence pattern.\n"
            "- points: 2-4 quick grammar notes."
        )
        data = self._json_request(prompt)
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
        prompt = (
            "Build ONE German learning word profile and return STRICT JSON only.\n"
            "JSON schema keys: "
            "{\"german_word\":\"...\",\"english_word\":\"...\",\"word_type\":\"noun|verb|adjective|adverb|preposition|pronoun|other\","
            "\"cefr_level\":\"...\",\"article\":\"der|die|das|-\",\"plural\":\"... or -\","
            "\"gender\":\"masculine|feminine|neutral|-\",\"noun_flexion\":{},\"conjugations\":{},"
            "\"examples\":[\"...\",\"...\"],\"notes\":[],\"analysis_details\":{}}.\n"
            f"target_level: {target_level}\n"
            f"seed_german: {seed_german}\n"
            f"seed_english: {seed_english}\n"
            "Rules:\n"
            f"{self._style_rules(target_level)}\n"
            "- If seed_german is an infinitive concept (e.g. Lernen/Kommen), prefer verb lowercase infinitive.\n"
            "- german_word must be a single common lemma.\n"
            "- english_word must be a clean single-word or short-phrase meaning.\n"
            "- For nouns: fill article/gender/plural and noun_flexion if possible.\n"
            "- For verbs: fill conjugations for ich/du/er/sie/es/wir/ihr/sie.\n"
            "- Provide exactly 2 natural example sentences using german_word.\n"
            "- Keep noun_flexion compact; include only nominativ singular/plural if possible.\n"
            f"{note_rule}"
        )
        data = self._json_request(prompt)
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

    def _json_request(self, prompt: str) -> dict[str, object] | None:
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            f"You are a precise German {self.style_level} teaching assistant. "
                            "Always follow constraints and output strict JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=280 if self.compact_mode else 500,
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
        lvl = level.upper()
        if lvl == "A1.1":
            return (
                "- Strict A1.1 style.\\n"
                "- Present tense only.\\n"
                "- One short clause.\\n"
                "- 3 to 6 words.\\n"
                "- Very high-frequency daily vocabulary."
            )
        if lvl == "A1.2":
            return (
                "- A1.2 style.\\n"
                "- Present tense only.\\n"
                "- One short clause, occasional fixed phrase.\\n"
                "- 4 to 8 words.\\n"
                "- Simple prepositions and daily contexts."
            )
        if lvl == "A2.1":
            return (
                "- A2.1 style.\\n"
                "- Mostly present tense; Perfekt allowed.\\n"
                "- One clause, occasionally two short clauses.\\n"
                "- 5 to 9 words."
            )
        if lvl == "A2.2":
            return (
                "- A2.2 style.\\n"
                "- Present + Perfekt where natural.\\n"
                "- One to two short clauses.\\n"
                "- 6 to 11 words."
            )
        if lvl == "B1.1":
            return (
                "- B1.1 style.\\n"
                "- Natural practical German.\\n"
                "- One to two clauses with clear connectors.\\n"
                "- 7 to 12 words."
            )
        if lvl in {"B1.2", "B1", "BB1"}:
            return (
                "- B1.2 style.\\n"
                "- Natural modern German with mild complexity.\\n"
                "- One to two clauses.\\n"
                "- 8 to 14 words."
            )
        return (
            f"- {lvl} learner style.\\n"
            "- Keep language clear, natural, and practical."
        )

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
