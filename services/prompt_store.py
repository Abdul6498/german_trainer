"""Load and render JSON-backed prompt templates."""

from __future__ import annotations

import json
from pathlib import Path


class PromptStore:
    """Read prompt templates from the repository prompt folder."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = prompts_dir or (Path(__file__).resolve().parent.parent / "prompts")

    def get(self, name: str) -> dict[str, str]:
        path = self.prompts_dir / f"{name}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items()}

    def render(self, name: str, key: str = "user", **values: object) -> str:
        template = self.get(name).get(key, "")
        normalized = {k: str(v) for k, v in values.items()}
        rendered = template
        for placeholder, value in normalized.items():
            rendered = rendered.replace(f"{{{placeholder}}}", value)
        return rendered

    def style_rules(self, level: str) -> str:
        token = level.upper().strip()
        slug = token.lower().replace(".", "_")
        grammar_dir = self.prompts_dir / "grammar"
        path = grammar_dir / f"{slug}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return str(data.get("rules", "")).strip()

        default_path = grammar_dir / "default.json"
        if default_path.exists():
            data = json.loads(default_path.read_text(encoding="utf-8"))
            template = str(data.get("rules", "")).strip()
            return template.replace("{level}", token or "Unknown")

        return "- Keep language clear, natural, practical, and teacher-friendly."
