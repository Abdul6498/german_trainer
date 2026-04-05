# German Trainer

A full-stack German learning app with a Python backend and a browser frontend. The backend keeps the AI study/quiz engine, spacing logic, and progress tracking. The frontend gives you a cleaner interface than the old tkinter popups.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export OPENAI_API_KEY="your_key_here"
python -u main.py --interval-minutes 5 --level A2.1 --srs-intensity hard --mode mixed --view basic --sentence-source ai --word-source ai --translation-source ai --openai-model gpt-4.1-mini --daily-goal-words 60 --ai-notes short
```

Then open `http://127.0.0.1:8000`.

## Run options

- `--mode mixed|study-only|quiz-only`
- `--view basic|detail`
- `--word-source ai|local`
- `--translation-source ai|deep-translator`
- `--sentence-source ai`
- `--daily-goal-words 60`
- `--ai-notes off|short|full`
- `--host 127.0.0.1`
- `--port 8000`

You can now also change `level`, `intensity`, and `daily goal` directly inside the app UI without restarting the server.

## Architecture

- Backend: FastAPI served from [main.py](/home/user/Workspace/german_trainer/main.py) and [app.py](/home/user/Workspace/german_trainer/webapp/app.py)
- Frontend source: TypeScript in [app.ts](/home/user/Workspace/german_trainer/webapp/src/app.ts)
- Browser-ready frontend assets: `webapp/static/`
- Trainer engine, AI services, and progress logic remain in the Python modules under `engine/` and `services/`

## Notes

- In AI mode, study cards and quiz feedback come from OpenAI-backed services.
- Sentence feedback is shown in results, but sentence quality does not affect quiz scoring.
- Runtime/local data stays in `storage/` and generated caches stay under `data/`.
