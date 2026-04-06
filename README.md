# German Trainer

A full-stack German learning app with a Python backend and a browser frontend. The backend keeps the AI study/quiz engine, spacing logic, and progress tracking. The frontend gives you a cleaner interface than the old tkinter popups.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export OPENAI_API_KEY="your_key_here"
python -u main.py --interval-minutes 5 --level A2.1 --srs-intensity hard --mode mixed --practice-mode learn-new --view basic --sentence-source ai --word-source ai --translation-source ai --openai-model gpt-4.1-mini --daily-goal-words 60 --ai-notes short
```

Then open `http://127.0.0.1:8000`.

## Run options

- `--mode mixed|study-only|quiz-only`
- `--practice-mode learn-new|repeat-practice`
- `--view basic|detail`
- `--word-source ai|local`
- `--translation-source ai|deep-translator`
- `--sentence-source ai`
- `--daily-goal-words 60`
- `--ai-notes off|short|full`
- `--host 127.0.0.1`
- `--port 8000`

You can now also change `level`, `intensity`, `mode`, `word plan`, `pace`, `view`, and `daily goal` directly inside the app UI without restarting the server.

## Word Plan

- `learn-new`
  - Study mode introduces new words from AI.
  - Quiz mode uses words you already studied and marked as understood.
- `repeat-practice`
  - Focuses on review/repetition from words already in your studied/quiz pool.
  - If no review words exist yet, the app falls back to study cards unless you are in `quiz-only`.

In `quiz-only`, the app now avoids inventing brand-new words. If you have no quiz-ready words yet, it stays idle and tells you to study a few first.

## Architecture

- Backend: FastAPI served from [main.py](/home/user/Workspace/german_trainer/main.py) and [app.py](/home/user/Workspace/german_trainer/webapp/app.py)
- Frontend source: TypeScript in [app.ts](/home/user/Workspace/german_trainer/webapp/src/app.ts)
- Browser-ready frontend assets: `webapp/static/`
- Trainer engine, AI services, and progress logic remain in the Python modules under `engine/` and `services/`

## Notes

- In AI mode, study cards and quiz feedback come from OpenAI-backed services.
- Sentence feedback is shown in results, but sentence quality does not affect quiz scoring.
- Runtime/local data stays in `storage/` and generated caches stay under `data/`.

## Fly.io Deploy

This project is ready to deploy on Fly.io with the included [Dockerfile](/home/user/Workspace/german_trainer/Dockerfile) and [fly.toml](/home/user/Workspace/german_trainer/fly.toml).

### 1. Install Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
```

### 2. Authenticate

```bash
fly auth login
```

### 3. Review the app name

The default app name in [fly.toml](/home/user/Workspace/german_trainer/fly.toml) is `abdul-german-trainer`. If Fly says it is already taken, change the `app = "..."` value to something unique.

### 4. Create the app and set secrets

```bash
fly launch --no-deploy
fly secrets set OPENAI_API_KEY=your_key_here
```

Optional secrets if you want different defaults:

```bash
fly secrets set INTERVAL_MINUTES=5 DAILY_GOAL_WORDS=60
```

### 5. Deploy

```bash
fly deploy
```

### 6. Open the app

```bash
fly open
```

### Notes for Fly

- The service listens on `0.0.0.0:8080` inside the container.
- Health checks use `/healthz`.
- By default the app will sleep when idle on Fly free/low-cost settings and start again on demand.
- Files under `storage/` and generated caches under `data/` are ephemeral inside the container. If you want persistent progress/history on Fly, we should add a Fly volume or move state to a database/object store.
