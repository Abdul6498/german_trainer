"""Entry point for the German Trainer web application."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn
from rich.console import Console

from webapp.app import create_app


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="German Trainer Web App")
    parser.add_argument("--interval-minutes", type=int, default=_env_int("INTERVAL_MINUTES", 5), help="Minutes between trainer prompts.")
    parser.add_argument(
        "--level",
        default="A1.1",
        help="CEFR level/sub-level (A1.1, A1.2, A2.1, A2.2, B1.1, B1.2).",
    )
    parser.add_argument(
        "--srs-intensity",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="How aggressively spaced repetition repeats mistakes.",
    )
    parser.add_argument(
        "--mode",
        choices=["mixed", "study-only", "quiz-only"],
        default="mixed",
        help="Learning flow mode.",
    )
    parser.add_argument(
        "--practice-mode",
        choices=["learn-new", "repeat-practice"],
        default="learn-new",
        help="Choose whether to introduce new words or practice already-understood words.",
    )
    parser.add_argument(
        "--view",
        choices=["basic", "detail"],
        default="basic",
        help="Initial frontend density preference.",
    )
    parser.add_argument(
        "--pace",
        choices=["timed", "continuous"],
        default="timed",
        help="Timed mode waits between cards; continuous mode moves to the next card immediately.",
    )
    parser.add_argument(
        "--sentence-source",
        choices=["ai"],
        default="ai",
        help="Sentence generation/correction backend.",
    )
    parser.add_argument("--openai-model", default="gpt-4.1-mini", help="OpenAI model for AI features.")
    parser.add_argument(
        "--word-source",
        choices=["ai", "local"],
        default="ai",
        help="Vocabulary source backend.",
    )
    parser.add_argument(
        "--translation-source",
        choices=["ai", "deep-translator"],
        default="ai",
        help="Translation backend.",
    )
    parser.add_argument(
        "--daily-goal-words",
        type=int,
        default=_env_int("DAILY_GOAL_WORDS", 60),
        help="Daily target for new words before repetitions are preferred.",
    )
    parser.add_argument(
        "--ai-notes",
        choices=["off", "short", "full"],
        default="short",
        help="AI word explanation note density.",
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"), help="Bind host for the web server.")
    parser.add_argument("--port", type=int, default=_env_int("PORT", 8000), help="Bind port for the web server.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = Path(__file__).resolve().parent
    console = Console()
    app = create_app(root_dir, args)

    console.print(
        f"Starting German Trainer Web App on http://{args.host}:{args.port} "
        f"(level={args.level}, mode={args.mode}, practice_mode={args.practice_mode}, "
        f"pace={args.pace}, interval={args.interval_minutes}m, ai_notes={args.ai_notes})"
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
