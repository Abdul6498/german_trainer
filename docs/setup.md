# Setup

## Prerequisites

- Python 3.11+
- `tkinter` available in your Python install
- WSL users: WSLg enabled for popup windows and audio (or run from Windows Python)

## Install

```bash
cd /home/user/Workspace/german_trainer
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Useful options

- `--interval-minutes`: popup interval (default `5`)
- `--level`: `A1.1`, `A1.2`, `A2.1`, `A2.2`, `B1.1`, `B1.2` (aliases: `A1`, `A2`, `B1`, `BB1`)
- `--srs-intensity`: `easy`, `medium`, `hard`
- `--mode`: `mixed`, `study-only`, `quiz-only`
- `--view`: `basic`, `detail`
- `--sentence-source`: `ai` (AI-only)
- `--word-source`: `ai`, `local`
- `--translation-source`: `ai`, `deep-translator`
- `--openai-model`: OpenAI model name for AI sentence mode (default `gpt-4.1-mini`)

Example:

```bash
python main.py --interval-minutes 2 --level A1.1 --srs-intensity hard --mode mixed --view basic --sentence-source ai --word-source ai --translation-source ai --openai-model gpt-4.1-mini
```

## Storage files

- `storage/progress.json`: per-word spaced repetition state
- `storage/history.json`: aggregate statistics
- `storage/word_meta.json`: cached word metadata (translation, grammar details, conjugations, examples, sources)
- `data/generated_words_<level>.txt`: CEFR-focused English vocabulary cache generated from curriculum + `wonderwords`
