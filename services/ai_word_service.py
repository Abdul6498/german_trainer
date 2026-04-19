"""AI-backed German word generation for CEFR/sub-level training."""

from __future__ import annotations

import json
import os

from services.prompt_store import PromptStore


class AIWordService:
    """Generate German vocabulary with OpenAI and keep a local buffer."""

    def __init__(
        self,
        model: str = "gpt-4.1-mini",
        enabled: bool = True,
        level: str = "A1.1",
    ) -> None:
        self.model = model
        self.enabled = enabled
        self.level = level
        self._client = None
        self._buffer: list[str] = []
        self._init_error = ""
        self._prompts = PromptStore()
        self._init_client()

    @property
    def available(self) -> bool:
        return self.enabled and self._client is not None

    @property
    def init_error(self) -> str:
        return self._init_error

    def next_word(self) -> str | None:
        if not self.available:
            return None
        if not self._buffer:
            self._buffer = self._request_words(count=30)
        while self._buffer:
            candidate = self._normalize(self._buffer.pop(0))
            if candidate:
                return candidate
        return None

    def _request_words(self, count: int) -> list[str]:
        prompt = self._prompts.render(
            "ai_word_request_words",
            count=count,
            target_level=self.level,
        )
        system_prompt = self._prompts.get("ai_word_request_words").get("system", "")

        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {"role": "user", "content": prompt},
                ],
                max_output_tokens=500,
            )
            text = getattr(response, "output_text", "") or ""
            data = json.loads(text)
            words = data.get("words", [])
            if not isinstance(words, list):
                return []
            return [str(w) for w in words]
        except Exception:
            return []

    @staticmethod
    def _normalize(value: str) -> str:
        token = value.strip()
        if not token.isalpha():
            return ""
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
