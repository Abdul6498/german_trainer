"""Translation service adapter."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from deep_translator import GoogleTranslator


class TranslatorService:
    """Translate English words to German."""

    def __init__(self) -> None:
        self._translator = GoogleTranslator(source="en", target="de")
        self._reverse_translator = GoogleTranslator(source="de", target="en")
        self._timeout_seconds = 3.0
        self._fallback = {
            "house": "Haus",
            "book": "Buch",
            "eat": "essen",
            "run": "laufen",
            "car": "Auto",
            "drink": "trinken",
            "write": "schreiben",
            "walk": "gehen",
            "sleep": "schlafen",
            "friend": "Freund",
        }

    def to_german(self, english_word: str) -> str:
        """Translate one token and clean whitespace."""
        token = english_word.strip()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._translator.translate, token)
                translated = future.result(timeout=self._timeout_seconds)
            return str(translated).strip()
        except (FuturesTimeoutError, Exception):
            return self._fallback.get(token.casefold(), token)

    def to_english(self, german_word: str) -> str:
        token = german_word.strip()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._reverse_translator.translate, token)
                translated = future.result(timeout=self._timeout_seconds)
            return str(translated).strip()
        except (FuturesTimeoutError, Exception):
            return token
