# German Trainer

A local Python desktop trainer that pops up periodic German exercises for vocabulary, articles, sentence practice, verb work, and core grammar concepts. The vocabulary pool combines CEFR curriculum words (`A1`..`C2`) with `wonderwords`, cached in `data/generated_words_<level>.txt`.

Learning flow:
- First encounter of a word: **Study mode** shows German word, English meaning, and grammar details.
- If you check **\"Yes, I understand\"**, that word moves to **Quiz mode**.
- Next encounters: English prompt + answer form quiz.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
export OPENAI_API_KEY="your_key_here"
python -u main.py --interval-minutes 1 --level A1.1 --srs-intensity hard --mode mixed --view basic --sentence-source ai --word-source ai --translation-source ai --openai-model gpt-4.1-mini --ai-notes off
```

Optional:

```bash
python -u main.py --interval-minutes 1 --level A2.1 --srs-intensity hard --mode mixed --view basic --sentence-source ai --word-source ai --translation-source ai --openai-model gpt-4.1-mini --daily-goal-words 60 --ai-notes short
```

Mode options:
- `--mode mixed`: stage-based (study first, quiz later)
- `--mode study-only`: always show study cards
- `--mode quiz-only`: always show quiz form

View options:
- `--view basic`: core learning tables (article/plural/gender, examples, conjugation)
- `--view detail`: full dictionary tables (`german-nouns` flexion + `verbformen` metadata)

Sentence source:
- `--sentence-source ai`: OpenAI sentences/corrections only (requires `OPENAI_API_KEY`)
- `--openai-model`: defaults to `gpt-4.1-mini`

AI-first pipeline:
- In AI mode, the app uses: `AI German word -> AI English translation -> grammar enrichment -> AI sentence generation`.
- Study cards include AI level-aware word explanation notes for the current CEFR level.
- Result view includes AI translation of your entered German sentence plus sentence-structure explanation.

Word and translation source:
- `--word-source ai|local` (default `ai`)
- `--translation-source ai|deep-translator` (default `ai`)
- `--daily-goal-words`: default `60`; before this target app prefers new words, then repeats seen words
- `--ai-notes off|short|full`: controls AI note verbosity and token usage

Sub-levels:
- `--level A1.1`, `A1.2`, `A2.1`, `A2.2`, `B1.1`, `B1.2`
- Backward aliases also work: `A1`, `A2`, `B1`, `BB1`

Audio note (WSL/Linux):
- Pronunciation tries `playsound`, then `ffplay`, `mpg123`, `paplay`, `aplay`.
- If none are installed, install one backend (for example `ffmpeg` or `mpg123`) and retry.

Sentence correction:
- The app uses `language_tool_python` (`de-DE`) to detect grammar/style issues in your sentence.
- Result view shows detected issues and a corrected sentence suggestion.
- OpenAI also proposes improved sentence corrections.
- OpenAI also returns English translation + structure notes for your sentence (helpful for grammar learning).
