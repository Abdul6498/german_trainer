"""FastAPI application factory for the German Trainer web UI."""

from __future__ import annotations

from argparse import Namespace
from io import BytesIO
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from services.pronunciation import PronunciationService
from webapp.schemas import QuizSubmissionPayload, SettingsPayload, StudySubmissionPayload
from webapp.service import TrainerWebService


def _payload_to_dict(payload: object) -> dict[str, object]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()  # type: ignore[no-any-return]
    if hasattr(payload, "dict"):
        return payload.dict()  # type: ignore[no-any-return]
    return dict(payload)  # type: ignore[arg-type]


def create_app(root_dir: Path, args: Namespace) -> FastAPI:
    service = TrainerWebService(root_dir, args)
    pronunciation = PronunciationService()
    app = FastAPI(title="German Trainer", version="2.0.0")
    static_dir = root_dir / "webapp" / "static"

    @app.get("/api/session")
    def get_session():
        return service.get_session()

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.post("/api/study")
    def submit_study(payload: StudySubmissionPayload):
        return service.submit_study(payload.understood)

    @app.post("/api/quiz")
    def submit_quiz(payload: QuizSubmissionPayload):
        return service.submit_quiz(_payload_to_dict(payload))

    @app.post("/api/next")
    def next_after_result():
        return service.next_after_result()

    @app.post("/api/trigger")
    def trigger_now():
        return service.trigger_now()

    @app.post("/api/settings")
    def update_settings(payload: SettingsPayload):
        return service.update_settings(
            level=payload.level,
            srs_intensity=payload.srs_intensity,
            mode=payload.mode,
            view=payload.view,
            daily_goal_words=payload.daily_goal_words,
        )

    @app.get("/api/pronunciation")
    def pronunciation_audio(text: str):
        audio_bytes = pronunciation.synthesize_bytes(text)
        return StreamingResponse(
            BytesIO(audio_bytes),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/")
    def index():
        return FileResponse(static_dir / "index.html")

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app
