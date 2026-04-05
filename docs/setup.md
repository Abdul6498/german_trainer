# Setup

## Install

```bash
cd /home/user/Workspace/german_trainer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
export OPENAI_API_KEY="your_key_here"
python main.py --interval-minutes 5 --level A2.1 --mode mixed --view basic --word-source ai --translation-source ai --sentence-source ai --ai-notes short
```

Open `http://127.0.0.1:8000`.

## Useful options

- `--host`: default `127.0.0.1`
- `--port`: default `8000`
- `--mode`: `mixed`, `study-only`, `quiz-only`
- `--view`: `basic`, `detail`
- `--daily-goal-words`: default `60`
- `--ai-notes`: `off`, `short`, `full`

## Storage

- `storage/progress.json`
- `storage/history.json`
- `storage/word_meta.json`

