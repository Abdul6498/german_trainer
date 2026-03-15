"""Grammar helpers powered by german-nouns and verbformen-cli APIs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass

from german_nouns.lookup import Nouns
from verbformen_cli import Client
from verbformen_cli.models import NotFound, PartOfSpeech


@dataclass
class NounInfo:
    is_noun: bool
    article: str = ""
    plural: str = ""
    gender: str = ""


@dataclass
class WordAnalysis:
    word_type: str
    level: str = ""
    conjugations: dict[str, str] | None = None
    details: dict[str, object] | None = None


class GrammarChecker:
    """Resolve grammar metadata with package APIs and defensive fallbacks."""

    _PREPOSITIONS = {
        "mit",
        "bei",
        "von",
        "zu",
        "aus",
        "nach",
        "seit",
        "gegen",
        "ohne",
        "durch",
        "fuer",
        "vor",
        "hinter",
        "ueber",
        "unter",
        "zwischen",
    }

    def __init__(self) -> None:
        self._nouns = Nouns()
        self._verbformen = Client.default_client()
        self._cache: dict[tuple[str, str], object] = {}

    def noun_info(self, german_word: str) -> NounInfo:
        """Look up noun metadata from german-nouns; fallback to simple heuristics."""
        token = german_word.strip()
        if not token:
            return NounInfo(is_noun=False)

        candidate = token[:1].upper() + token[1:]
        try:
            entries = self._nouns[candidate]
        except Exception:
            entries = []

        if entries:
            entry = entries[0]
            genus = str(entry.get("genus", "")).strip().lower()
            article = {"m": "der", "f": "die", "n": "das"}.get(genus, "")
            flexion = entry.get("flexion", {})
            plural = str(
                flexion.get("nominativ plural")
                or flexion.get("akkusativ plural")
                or flexion.get("genitiv plural")
                or ""
            ).strip()
            gender = {"der": "masculine", "die": "feminine", "das": "neutral"}.get(article, "")
            if article:
                return NounInfo(is_noun=True, article=article, plural=plural, gender=gender)

        if candidate[:1].isupper():
            guessed_article = "der"
            if candidate.endswith(("ung", "heit", "keit", "schaft", "ion", "ik")):
                guessed_article = "die"
            elif candidate.endswith(("chen", "lein", "ment", "um")):
                guessed_article = "das"
            return NounInfo(
                is_noun=True,
                article=guessed_article,
                plural=f"{candidate}e",
                gender={"der": "masculine", "die": "feminine", "das": "neutral"}[guessed_article],
            )

        return NounInfo(is_noun=False)

    def analyze_word(self, german_word: str) -> WordAnalysis:
        """Return part of speech + CEFR level when available."""
        token = german_word.strip()
        if not token:
            return WordAnalysis(word_type="unknown")

        lowered = token.casefold().replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
        if lowered in self._PREPOSITIONS:
            return WordAnalysis(word_type="preposition", details={"preposition_case_hint": "check context (dat/akk/gen)"})

        variants = [token]
        lower_variant = token[:1].lower() + token[1:] if token[:1].isupper() else token
        if lower_variant != token:
            variants.append(lower_variant)

        found: dict[str, WordAnalysis] = {}
        for probe in variants:
            for pos, label in (
                (PartOfSpeech.VERB, "verb"),
                (PartOfSpeech.ADJECTIVE, "adjective"),
                (PartOfSpeech.ADVERB, "adverb"),
            ):
                result = self._safe_search(probe, pos)
                if result and not isinstance(result, NotFound):
                    level = ""
                    raw_level = getattr(result, "level", None)
                    if raw_level is not None:
                        level = str(getattr(raw_level, "value", raw_level))
                    conjugations = self._verb_conjugations(result) if label == "verb" else None
                    found[label] = WordAnalysis(
                        word_type=label,
                        level=level,
                        conjugations=conjugations,
                        details=self._extract_result_details(result),
                    )

        noun = self.noun_info(token)
        noun_details = self.noun_details(token)
        has_verb = "verb" in found

        # Important ambiguity rule:
        # Capitalized infinitives like "Sprechen" can be misread as nouns.
        # When a valid verb exists and token looks infinitive-like, prefer verb.
        if has_verb and token.lower().endswith("en"):
            return found["verb"]

        if noun.is_noun:
            return WordAnalysis(word_type="noun", details=noun_details or {})

        if has_verb:
            return found["verb"]
        if "adjective" in found:
            return found["adjective"]
        if "adverb" in found:
            return found["adverb"]

        return WordAnalysis(word_type="verb", details={})

    def conjugations(self, german_verb: str) -> dict[str, str]:
        analysis = self.analyze_word(german_verb)
        if analysis.conjugations:
            return analysis.conjugations
        return self._fallback_conjugation(german_verb)

    def _safe_search(self, token: str, pos: PartOfSpeech) -> object | None:
        cache_key = (token.casefold(), pos.value)
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._verbformen.search, token, pos)
                result = future.result(timeout=2.5)
                self._cache[cache_key] = result
                return result
        except (FuturesTimeoutError, Exception):
            return None

    def _verb_conjugations(self, verb_result: object) -> dict[str, str] | None:
        conjugations = getattr(verb_result, "conjugations", None)
        if conjugations:
            for table in conjugations:
                if getattr(table, "title", "").lower().startswith("present"):
                    return {
                        "ich": getattr(table, "ich", ""),
                        "du": getattr(table, "du", ""),
                        "er/sie/es": getattr(table, "er", ""),
                        "wir": getattr(table, "wir", ""),
                        "ihr": getattr(table, "ihr", ""),
                        "sie": getattr(table, "sie", ""),
                    }

        present = getattr(verb_result, "present", None)
        if present:
            stem = str(present).strip()
            return {
                "ich": stem,
                "du": stem,
                "er/sie/es": stem,
                "wir": stem,
                "ihr": stem,
                "sie": stem,
            }
        return None

    def _fallback_conjugation(self, verb: str) -> dict[str, str]:
        stem = verb[:-2] if verb.endswith("en") and len(verb) > 3 else verb
        return {
            "ich": f"{stem}e",
            "du": f"{stem}st",
            "er/sie/es": f"{stem}t",
            "wir": verb,
            "ihr": f"{stem}t",
            "sie": verb,
        }

    def noun_details(self, german_word: str) -> dict[str, object] | None:
        token = german_word.strip()
        if not token:
            return None
        candidate = token[:1].upper() + token[1:]
        try:
            entries = self._nouns[candidate]
        except Exception:
            return None
        if not entries:
            return None
        return dict(entries[0])

    def parse_compound(self, german_word: str) -> list[str]:
        token = german_word.strip()
        if not token:
            return []
        try:
            return list(self._nouns.parse_compound(token))
        except Exception:
            return []

    @staticmethod
    def _extract_result_details(result: object) -> dict[str, object]:
        keys = [
            "search",
            "definitions",
            "part_of_speech",
            "text",
            "behavior",
            "present",
            "imperfect",
            "perfect",
            "auxiliary_verb",
            "flection",
            "use",
            "level",
            "comparative",
            "superlative",
        ]
        details: dict[str, object] = {}
        for key in keys:
            value = getattr(result, key, None)
            if value is None:
                continue
            details[key] = getattr(value, "value", value)
        return details
