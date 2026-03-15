"""AI-backed EN->DE translator using OpenAI."""

from __future__ import annotations

import os


class AITranslatorService:
    """Translate between English and German with OpenAI."""

    def __init__(self, model: str = "gpt-4.1-mini", enabled: bool = True) -> None:
        self.model = model
        self.enabled = enabled
        self._client = None
        self._init_error = ""
        self._init_client()

    @property
    def available(self) -> bool:
        return self.enabled and self._client is not None

    @property
    def init_error(self) -> str:
        return self._init_error

    def to_german(self, english_word: str) -> str:
        token = english_word.strip()
        if not token:
            return token
        if not self.available:
            return token

        prompt = (
            "Translate this English word to standard German. "
            "Return ONLY the German word (no punctuation, no explanation).\n"
            f"word: {token}"
        )
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are a precise EN->DE dictionary assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=40,
            )
            output = (getattr(response, "output_text", "") or "").strip()
            cleaned = output.splitlines()[0].strip().strip('"').strip("'")
            return cleaned or token
        except Exception:
            return token

    def to_english(self, german_word: str) -> str:
        token = german_word.strip()
        if not token:
            return token
        if not self.available:
            return token

        prompt = (
            "Translate this German word to English. "
            "Return ONLY the English word (no punctuation, no explanation).\n"
            f"word: {token}"
        )
        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": "You are a precise DE->EN dictionary assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=40,
            )
            output = (getattr(response, "output_text", "") or "").strip()
            cleaned = output.splitlines()[0].strip().strip('"').strip("'")
            return cleaned or token
        except Exception:
            return token

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
            self._client = None
            self._init_error = str(exc)
