# Architecture

## Overview

The app now runs as a web application:

- Python backend: FastAPI
- Frontend: TypeScript source with browser-ready static assets
- Core trainer logic: still lives in `engine/` and `services/`

## Main parts

- [main.py](/home/user/Workspace/german_trainer/main.py): CLI entrypoint and web server startup
- [app.py](/home/user/Workspace/german_trainer/webapp/app.py): FastAPI app factory and routes
- [service.py](/home/user/Workspace/german_trainer/webapp/service.py): session orchestration between API and quiz engine
- [app.ts](/home/user/Workspace/german_trainer/webapp/src/app.ts): frontend state/render/event logic
- `webapp/static/`: served HTML/CSS/JS assets

## Data flow

1. Browser loads the static frontend from FastAPI.
2. Frontend polls `/api/session` for countdown, active card, and stats.
3. Backend creates study/quiz cards through `QuizEngine`.
4. Frontend submits study and quiz actions back to the API.
5. Backend updates spaced repetition, progress, metadata cache, and result feedback.

## Notes

- Study/quiz timing is now session-driven in the backend instead of tkinter popup scheduling.
- AI-backed word profiles and sentence feedback are reused through the existing Python services.
- `storage/word_meta.json` remains the main local cache for reusable AI word data.

