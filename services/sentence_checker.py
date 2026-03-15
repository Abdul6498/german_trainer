"""German sentence checking with language_tool_python."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SentenceCheckResult:
    available: bool
    is_correct: bool
    corrected: str
    issues: list[str]


class SentenceChecker:
    """Wrap language_tool_python with graceful fallbacks."""

    def __init__(self, language: str = "de-DE") -> None:
        self.language = language
        self._tool = None
        self._init_error = ""
        self._init_tool()

    def check(self, sentence: str) -> SentenceCheckResult:
        text = sentence.strip()
        if not text:
            return SentenceCheckResult(available=self._tool is not None, is_correct=False, corrected="", issues=["No sentence provided."])

        if self._tool is None:
            return SentenceCheckResult(
                available=False,
                is_correct=True,
                corrected=text,
                issues=[f"LanguageTool unavailable: {self._init_error or 'not initialized'}"],
            )

        try:
            matches = self._tool.check(text)
            corrected = self._tool.correct(text)
            issues: list[str] = []
            for match in matches[:5]:
                message = getattr(match, "message", "Grammar issue")
                replacements = getattr(match, "replacements", []) or []
                replacement_hint = f" -> {', '.join(replacements[:3])}" if replacements else ""
                issues.append(f"{message}{replacement_hint}")
            return SentenceCheckResult(
                available=True,
                is_correct=len(matches) == 0,
                corrected=corrected,
                issues=issues,
            )
        except Exception as exc:
            return SentenceCheckResult(
                available=False,
                is_correct=True,
                corrected=text,
                issues=[f"LanguageTool check failed: {exc}"],
            )

    def _init_tool(self) -> None:
        try:
            import language_tool_python

            try:
                self._tool = language_tool_python.LanguageTool(self.language)
                return
            except Exception as local_exc:
                self._init_error = str(local_exc)

            self._tool = language_tool_python.LanguageToolPublicAPI(self.language)
        except Exception as exc:
            self._tool = None
            self._init_error = str(exc)
