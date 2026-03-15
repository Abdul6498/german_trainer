"""Sentence generation and validation utilities."""

from __future__ import annotations

from random import sample


class SentenceGenerator:
    """Generate grammar-aware German practice sentences."""

    def build_examples(
        self,
        german_word: str,
        word_type: str,
        count: int = 3,
        *,
        article: str = "",
        plural: str = "",
        conjugations: dict[str, str] | None = None,
    ) -> list[str]:
        if word_type == "noun":
            return self._noun_examples(german_word, article=article, plural=plural, count=count)
        if word_type == "verb":
            return self._verb_examples(german_word, conjugations=conjugations or {}, count=count)
        if word_type == "adjective":
            templates = [
                f"Das Wetter ist {german_word}.",
                f"Die Aufgabe ist {german_word}.",
                f"Das ist sehr {german_word}.",
            ]
            return sample(templates, k=min(count, len(templates)))

        templates = [
            f"Ich lerne heute das Wort {german_word}.",
            f"Wir sprechen ueber {german_word}.",
            f"Das Thema ist {german_word}.",
        ]
        return sample(templates, k=min(count, len(templates)))

    def _noun_examples(self, word: str, article: str, plural: str, count: int) -> list[str]:
        nom_article = article if article in {"der", "die", "das"} else "das"
        akk_article = {"der": "den", "die": "die", "das": "das"}.get(nom_article, "das")
        poss = "Meine" if nom_article == "die" else "Mein"
        plural_form = plural or f"{word}e"
        templates = [
            f"{nom_article.capitalize()} {word} ist wichtig.",
            f"Ich sehe {akk_article} {word}.",
            f"{poss} {word} ist neu.",
            f"Wir lernen heute das Wort {word}.",
            f"Die Mehrzahl ist: {plural_form}.",
        ]
        return sample(templates, k=min(count, len(templates)))

    def _verb_examples(self, word: str, conjugations: dict[str, str], count: int) -> list[str]:
        ich = conjugations.get("ich", word)
        wir = conjugations.get("wir", word)
        er = conjugations.get("er/sie/es", word)
        templates = [
            f"Ich {ich} heute.",
            f"Wir {wir} zusammen.",
            f"Er {er} jeden Tag.",
            f"Kannst du {word}?",
        ]
        return sample(templates, k=min(count, len(templates)))

    def validate_sentence(self, user_sentence: str, required_words: list[str]) -> bool:
        lowered = user_sentence.casefold()
        return all(word.casefold() in lowered for word in required_words)
